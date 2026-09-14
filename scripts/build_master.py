#!/usr/bin/env python3
"""Build unified Korea Region DB master files from normalized source CSVs.

Inputs:
- places_legal.csv          primary legal hierarchy from Code.go when available
- places_legal_mois.csv     MOIS legal codes
- places_admin.csv          MOIS administrative hierarchy
- relations_admin_legal.csv MOIS administrative↔legal mapping
- place_aliases_legal.csv   optional aliases

Outputs:
- places_master.csv
- relations_master.csv
- unresolved_relations.csv
- aliases_master.csv
- source_discrepancies.csv
- build_master_report.json

Relations are never forced against a missing entity. Any source relation whose
endpoint is absent from the normalized place set is preserved separately in
`unresolved_relations.csv` for source-quality review.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def normalized_place(row: dict[str, str], default_source: str) -> dict[str, str]:
    return {
        "place_id": row.get("place_id", ""),
        "place_type": row.get("place_type", "") or "UNKNOWN",
        "hierarchy_level": row.get("hierarchy_level", ""),
        "name_ko": row.get("name_ko", ""),
        "full_name_ko": row.get("full_name_ko", ""),
        "official_code": row.get("official_code", ""),
        "parent_place_id": row.get("parent_place_id", ""),
        "legal_status": row.get("legal_status", "UNKNOWN") or "UNKNOWN",
        "valid_from": row.get("valid_from", ""),
        "valid_to": row.get("valid_to", ""),
        "source_id": row.get("source_id", default_source) or default_source,
        "source_snapshot_date": row.get("source_snapshot_date", ""),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--normalized-dir", type=Path, default=Path("data/normalized"))
    ap.add_argument("--out-dir", type=Path, default=Path("data/master"))
    args = ap.parse_args()

    n = args.normalized_dir
    legal = read_csv(n / "places_legal.csv")
    legal_mois = read_csv(n / "places_legal_mois.csv")
    admin = read_csv(n / "places_admin.csv")
    rel = read_csv(n / "relations_admin_legal.csv")
    aliases = read_csv(n / "place_aliases_legal.csv")

    if not legal and not legal_mois:
        raise SystemExit("법정동 원본이 없습니다. places_legal.csv 또는 places_legal_mois.csv가 필요합니다.")

    # Code.go wins when present. MOIS is the provisional legal source until the
    # Code.go full snapshot is integrated.
    by_id: dict[str, dict[str, str]] = {}
    source_precedence: dict[str, str] = {}

    for row in legal_mois:
        pid = row.get("place_id", "")
        if not pid:
            continue
        by_id[pid] = normalized_place(row, "mois_jscode")
        source_precedence[pid] = "MOIS"

    for row in legal:
        pid = row.get("place_id", "")
        if not pid:
            continue
        by_id[pid] = normalized_place(row, "codego_bjd")
        source_precedence[pid] = "CODEGO"

    discrepancies: list[dict[str, str]] = []
    mois_by_id = {r.get("place_id", ""): r for r in legal_mois if r.get("place_id")}
    for pid, primary in by_id.items():
        if source_precedence.get(pid) != "CODEGO" or pid not in mois_by_id:
            continue
        secondary = mois_by_id[pid]
        for field in ("full_name_ko", "legal_status", "valid_from", "valid_to"):
            a = (primary.get(field) or "").strip()
            b = (secondary.get(field) or "").strip()
            if a and b and a != b:
                discrepancies.append({"place_id": pid, "field": field, "codego": a, "mois": b})

    for row in admin:
        pid = row.get("place_id", "")
        if not pid:
            continue
        by_id[pid] = normalized_place(row, "mois_jscode")

    master = sorted(
        by_id.values(),
        key=lambda r: (r.get("place_type", ""), r.get("official_code", ""), r.get("place_id", "")),
    )
    master_ids = set(by_id)

    relation_rows: list[dict[str, str]] = []
    unresolved_rows: list[dict[str, str]] = []
    seen_rel: set[tuple[str, str, str, str, str]] = set()

    for r in rel:
        src = r.get("from_place_id", "")
        dst = r.get("to_place_id", "")
        typ = r.get("relation_type", "")
        vf = r.get("valid_from", "")
        vt = r.get("valid_to", "")
        key = (src, dst, typ, vf, vt)
        if not src or not dst or not typ or key in seen_rel:
            continue
        seen_rel.add(key)
        out = {
            "from_place_id": src,
            "to_place_id": dst,
            "relation_type": typ,
            "legal_status": r.get("legal_status", "UNKNOWN"),
            "valid_from": vf,
            "valid_to": vt,
            "source_id": r.get("source_id", ""),
            "source_snapshot_date": r.get("source_snapshot_date", ""),
        }
        missing = []
        if src not in master_ids:
            missing.append("FROM")
        if dst not in master_ids:
            missing.append("TO")
        if missing:
            out["unresolved_reason"] = "+".join(missing) + "_PLACE_NOT_FOUND"
            unresolved_rows.append(out)
        else:
            relation_rows.append(out)

    # Explicit hierarchy graph edges.
    for r in master:
        pid = r.get("place_id", "")
        parent = r.get("parent_place_id", "")
        if not pid or not parent:
            continue
        out = {
            "from_place_id": pid,
            "to_place_id": parent,
            "relation_type": "PART_OF",
            "legal_status": r.get("legal_status", "UNKNOWN"),
            "valid_from": r.get("valid_from", ""),
            "valid_to": r.get("valid_to", ""),
            "source_id": r.get("source_id", ""),
            "source_snapshot_date": r.get("source_snapshot_date", ""),
        }
        key = (pid, parent, "PART_OF", out["valid_from"], out["valid_to"])
        if key in seen_rel:
            continue
        seen_rel.add(key)
        if parent not in master_ids:
            out["unresolved_reason"] = "TO_PLACE_NOT_FOUND"
            unresolved_rows.append(out)
        else:
            relation_rows.append(out)

    place_fields = [
        "place_id", "place_type", "hierarchy_level", "name_ko", "full_name_ko",
        "official_code", "parent_place_id", "legal_status", "valid_from", "valid_to",
        "source_id", "source_snapshot_date",
    ]
    rel_fields = [
        "from_place_id", "to_place_id", "relation_type", "legal_status", "valid_from", "valid_to",
        "source_id", "source_snapshot_date",
    ]
    unresolved_fields = rel_fields + ["unresolved_reason"]
    alias_fields = ["place_id", "alias", "alias_type", "source_id"]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "places_master.csv", master, place_fields)
    write_csv(args.out_dir / "relations_master.csv", relation_rows, rel_fields)
    write_csv(args.out_dir / "unresolved_relations.csv", unresolved_rows, unresolved_fields)
    write_csv(args.out_dir / "aliases_master.csv", aliases, alias_fields)
    write_csv(args.out_dir / "source_discrepancies.csv", discrepancies, ["place_id", "field", "codego", "mois"])

    report = {
        "places": len(master),
        "relations_resolved": len(relation_rows),
        "relations_unresolved": len(unresolved_rows),
        "aliases": len(aliases),
        "source_discrepancies": len(discrepancies),
        "by_type": dict(Counter(r.get("place_type", "") for r in master)),
        "by_status": dict(Counter(r.get("legal_status", "") for r in master)),
        "current_by_type": dict(Counter(r.get("place_type", "") for r in master if r.get("legal_status") == "CURRENT")),
        "inputs": {
            "codego_legal": len(legal),
            "mois_legal": len(legal_mois),
            "mois_admin": len(admin),
            "mois_mapping": len(rel),
        },
    }
    (args.out_dir / "build_master_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
