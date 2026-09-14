#!/usr/bin/env python3
"""Import extracted MOIS jscode files (KiKcd_H / KiKcd_B / KiKmix).

MOIS publishes both fixed-width TEXT and Excel versions. For reliability this
importer prefers the official XLSX files and falls back to delimited text only.
The original fixed-width TEXT is still preserved by the sync workflow for audit.

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
from typing import Any

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
    # Prefer the official spreadsheet; it exposes explicit columns while the
    # companion TEXT file is fixed-width.
    found.sort(key=lambda p: (0 if p.suffix.lower() == ".xlsx" else 1, len(p.name)))
    if not found:
        raise FileNotFoundError(f"{prefix} 파일을 찾지 못했습니다: {root}")
    return found[0]


def cell_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def parse_xlsx(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError("XLSX import requires openpyxl: pip install openpyxl") from exc

    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]

    raw_rows = list(ws.iter_rows(values_only=True))
    if not raw_rows:
        raise ValueError(f"empty workbook: {path}")

    # Find the first plausible header row. Recent MOIS spreadsheets place the
    # field names near the top, but this also tolerates title/blank rows.
    header_idx = None
    headers: list[str] = []
    for idx, row in enumerate(raw_rows[:30]):
        vals = [cell_str(v) for v in row]
        nonempty = [v for v in vals if v]
        joined = " ".join(nonempty)
        if len(nonempty) >= 2 and any(token in joined for token in ("코드", "기관", "법정", "행정", "시도")):
            header_idx = idx
            headers = vals
            break
    if header_idx is None:
        raise ValueError(f"header row not found in workbook: {path}")

    # Excel occasionally has blank header cells. Give them stable placeholder
    # names so Dict rows remain structurally intact.
    clean_headers: list[str] = []
    used: dict[str, int] = {}
    for i, h in enumerate(headers):
        name = h or f"__col_{i+1}"
        used[name] = used.get(name, 0) + 1
        if used[name] > 1:
            name = f"{name}_{used[name]}"
        clean_headers.append(name)

    rows: list[dict[str, str]] = []
    for raw in raw_rows[header_idx + 1:]:
        vals = [cell_str(v) for v in raw]
        if not any(vals):
            continue
        vals += [""] * max(0, len(clean_headers) - len(vals))
        rows.append(dict(zip(clean_headers, vals[:len(clean_headers)])))
    return clean_headers, rows


def parse_text_table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    text = decode(path)
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"empty file: {path}")
    first = lines[0]
    delimiter = "\t" if "\t" in first else "," if "," in first else "|" if "|" in first else None
    if delimiter is None:
        raise ValueError(
            f"fixed-width text detected: {path}. Use the companion XLSX file or implement the official layout."
        )
    r = csv.DictReader(lines, delimiter=delimiter)
    if not r.fieldnames:
        raise ValueError(f"header missing: {path}")
    return list(r.fieldnames), [{k: (v or "").strip() for k, v in row.items()} for row in r]


def parse_table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if path.suffix.lower() == ".xlsx":
        return parse_xlsx(path)
    return parse_text_table(path)


def norm(s: str) -> str:
    return re.sub(r"[\s_()·./-]+", "", (s or "").strip()).lower()


def choose(headers: list[str], candidates: tuple[str, ...], required: bool = True) -> str | None:
    nh = {norm(h): h for h in headers}
    for c in candidates:
        c0 = norm(c)
        if c0 in nh:
            return nh[c0]
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
    if any(x in v for x in ("폐지", "말소", "삭제")) or v in {"1", "y", "yes", "true", "폐지1"}:
        return "ABOLISHED"
    return "CURRENT"


def digits(value: str) -> str:
    # Excel may render codes as `1100000000.0`; normalize safely.
    v = value.strip()
    if re.fullmatch(r"\d+\.0", v):
        v = v[:-2]
    return re.sub(r"\D", "", v)


def infer_admin_type(name: str) -> str:
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

    h_code = choose(h_headers, ("행정기관코드", "행정동코드", "기관코드", "행정기관"))
    h_name = choose(h_headers, ("행정기관명", "행정동명", "기관명", "행정구역명", "행정기관명칭"))
    h_status = choose(h_headers, ("폐지여부", "말소여부", "폐지구분", "폐지"), required=False)

    b_code = choose(b_headers, ("법정동코드", "법정주소코드", "법정코드", "법정동"))
    b_name = choose(b_headers, ("법정동명", "법정주소명", "주소명", "법정동명칭"))
    b_status = choose(b_headers, ("폐지여부", "말소여부", "폐지구분", "폐지"), required=False)

    m_admin = choose(m_headers, ("행정기관코드", "행정동코드", "기관코드", "행정기관"))
    m_legal = choose(m_headers, ("법정동코드", "법정주소코드", "법정코드", "법정동"))
    m_status = choose(m_headers, ("폐지여부", "말소여부", "폐지구분", "폐지"), required=False)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    admin_out = []
    for r in h_rows:
        code = digits(r.get(h_code, ""))
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
        code = digits(r.get(b_code, ""))
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
        acode = digits(r.get(m_admin, ""))
        lcode = digits(r.get(m_legal, ""))
        if not acode or not lcode:
            continue
        relation_out.append({
            "from_place_id": f"adm:{acode}",
            "to_place_id": f"bjd:{lcode}",
            "relation_type": "ADMINISTERS",
            "legal_status": status(r.get(m_status, "") if m_status else ""),
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
