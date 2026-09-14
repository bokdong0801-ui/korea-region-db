#!/usr/bin/env python3
"""Import extracted MOIS jscode files (KiKcd_H / KiKcd_B / KiKmix).

The Ministry of the Interior and Safety publishes a ZIP containing text/Excel
files. Text headers are included in recent releases. This importer intentionally
uses header-name matching instead of fixed column positions so it survives minor
layout changes.

Usage:
  python scripts/import_mois_jscode.py data/raw/jscode20260720_extracted \
      --snapshot-date 2026-07-20 --out-dir data/normalized
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

ENCODINGS = ("utf-8-sig", "cp949", "euc-kr", "utf-8")


def decode(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    raise UnicodeError(f"cannot decode: {path}")


def find_one(root: Path, prefix: str) -> Path:
    found = [p for p in root.rglob("*") if p.is_file() and p.name.lower().startswith(prefix.lower())]
    # Prefer text-like files over spreadsheets because stdlib parser handles them reliably.
    found.sort(key=lambda p: (p.suffix.lower() not in {"", ".txt", ".csv", ".tsv"}, len(p.name)))
    if not found:
        raise FileNotFoundError(f"{prefix} 파일을 찾지 못했습니다: {root}")
    return found[0]


def parse_table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    text = decode(path)
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"empty file: {path}")
    first = lines[0]
    delimiter = "\t" if "\t" in first else "," if "," in first else None
    if delimiter is None:
        # Some releases use | delimiters.
        delimiter = "|" if "|" in first else None
    if delimiter is None:
        raise ValueError(f"delimiter not detected: {path}")
    r = csv.DictReader(lines, delimiter=delimiter)
    if not r.fieldnames:
        raise ValueError(f"header missing: {path}")
    return list(r.fieldnames), list(r)


def norm(s: str) -> str:
    return re.sub(r"[\s_()·./-]+", "", (s or "").strip()).lower()


def choose(headers: list[str], candidates: tuple[str, ...], required: bool = True) -> str | None:
    nh = {norm(h): h for h in headers}
    for c in candidates:
        c0 = norm(c)
        if c0 in nh:
            return nh[c0]
    # fallback: substring match, longest candidate first
    for c in sorted(candidates, key=len, reverse=True):
        c0 = norm(c)
        for k, original in nh.items():
            if c0 and c0 in k:
                return original
    if required:
        raise KeyError(f"column not found. candidates={candidates}, headers={headers}")
    return None


def status(value: str) -> str:
    v = norm(value)
    if not v:
        return "CURRENT"
    if any(x in v for x in ("폐지", "말소", "삭제")) or v in {"1", "y", "yes", "true"}:
        return "ABOLISHED"
    return "CURRENT"


def infer_admin_type(name: str) -> str:
    short = name.split()[-1] if name.split() else name
    # ADMIN_DONG is an umbrella type in v1. Detailed 읍/면/동/출장소 subtype
    # will be stored later in attributes when the official layout is finalized.
    return "ADMIN_DONG"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("extracted_dir", type=Path)
    ap.add_argument("--snapshot-date", required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("data/normalized"))
    args = ap.parse_args()

    hfile = find_one(args.extracted_dir, "KiKcd_H")
    bfile = find_one(args.extracted_dir, "KiKcd_B")
    mfile = find_one(args.extracted_dir, "KiKmix")

    h_headers, h_rows = parse_table(hfile)
    b_headers, b_rows = parse_table(bfile)
    m_headers, m_rows = parse_table(mfile)

    h_code = choose(h_headers, ("행정기관코드", "행정동코드", "기관코드"))
    h_name = choose(h_headers, ("행정기관명", "행정동명", "기관명", "행정구역명"))
    h_status = choose(h_headers, ("폐지여부", "말소여부", "폐지구분"), required=False)

    b_code = choose(b_headers, ("법정동코드", "법정주소코드", "법정코드"))
    b_name = choose(b_headers, ("법정동명", "법정주소명", "주소명"))
    b_status = choose(b_headers, ("폐지여부", "말소여부", "폐지구분"), required=False)

    m_admin = choose(m_headers, ("행정기관코드", "행정동코드", "기관코드"))
    m_legal = choose(m_headers, ("법정동코드", "법정주소코드", "법정코드"))
    m_status = choose(m_headers, ("폐지여부", "말소여부", "폐지구분"), required=False)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    admin_out = []
    for r in h_rows:
        code = re.sub(r"\D", "", r.get(h_code, ""))
        name = re.sub(r"\s+", " ", r.get(h_name, "").strip())
        if not code or not name:
            continue
        admin_out.append({
            "place_id": f"adm:{code}",
            "place_type": infer_admin_type(name),
            "name_ko": name.split()[-1],
            "full_name_ko": name,
            "official_code": code,
            "legal_status": status(r.get(h_status, "") if h_status else ""),
            "source_id": "mois_jscode",
            "source_snapshot_date": args.snapshot_date,
        })

    legal_out = []
    for r in b_rows:
        code = re.sub(r"\D", "", r.get(b_code, ""))
        name = re.sub(r"\s+", " ", r.get(b_name, "").strip())
        if not code or not name:
            continue
        legal_out.append({
            "place_id": f"bjd:{code}",
            "name_ko": name.split()[-1],
            "full_name_ko": name,
            "official_code": code,
            "legal_status": status(r.get(b_status, "") if b_status else ""),
            "source_id": "mois_jscode",
            "source_snapshot_date": args.snapshot_date,
        })

    relation_out = []
    for r in m_rows:
        acode = re.sub(r"\D", "", r.get(m_admin, ""))
        lcode = re.sub(r"\D", "", r.get(m_legal, ""))
        if not acode or not lcode:
            continue
        rel_status = status(r.get(m_status, "") if m_status else "")
        relation_out.append({
            "from_place_id": f"adm:{acode}",
            "to_place_id": f"bjd:{lcode}",
            "relation_type": "ADMINISTERS",
            "legal_status": rel_status,
            "source_id": "mois_jscode",
            "source_snapshot_date": args.snapshot_date,
        })

    def write_csv(name: str, rows: list[dict[str, str]]) -> None:
        path = args.out_dir / name
        if not rows:
            path.write_text("", encoding="utf-8-sig")
            return
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)

    write_csv("places_admin.csv", admin_out)
    write_csv("places_legal_mois.csv", legal_out)
    write_csv("relations_admin_legal.csv", relation_out)

    meta = {
        "snapshot_date": args.snapshot_date,
        "files": {"admin": hfile.name, "legal": bfile.name, "mapping": mfile.name},
        "rows": {"admin": len(admin_out), "legal": len(legal_out), "mapping": len(relation_out)},
        "headers": {"admin": h_headers, "legal": b_headers, "mapping": m_headers},
    }
    (args.out_dir / "mois_jscode_import_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
