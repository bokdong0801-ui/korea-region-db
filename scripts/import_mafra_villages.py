#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

SOURCE_ID = "mafra_rural_village_basic"


def read_csv(path: Path, encoding: str = "utf-8-sig"):
    with path.open(encoding=encoding, newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def digits(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def norm_date(value: str) -> str:
    d = digits(value)
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) >= 8 else d


def classify(label: str, source_type: str, target_type: str) -> str:
    text = f"{label} {source_type}".replace(" ", "")
    center_terms = ("기초생활거점", "중심지", "면소재지", "읍소재지", "소재지형")
    if any(term in text for term in center_terms):
        return "RURAL_CENTER"
    if target_type == "LEGAL_RI" or len(digits(label)) >= 0:
        return "RURAL_VILLAGE"
    return "RURAL_PLACE"


def row_sort_key(row):
    year = int(digits(row.get("기준년도", ""))[:4] or 0)
    updated = int(digits(row.get("최종 갱신일", ""))[:8] or 0)
    rownum = int(digits(row.get("ROW_NUM", "")) or 0)
    return (year, updated, rownum)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("raw_csv", type=Path)
    ap.add_argument("--v4-places", type=Path, required=True)
    ap.add_argument("--snapshot-date", default="2026-09-15")
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    raw = read_csv(args.raw_csv, "cp949")
    v4_places = read_csv(args.v4_places)
    legal_by_code = {
        r["official_code"]: r
        for r in v4_places
        if r.get("place_id", "").startswith("bjd:") and r.get("official_code")
    }

    grouped = defaultdict(list)
    bad_ids = []
    for i, row in enumerate(raw, 1):
        vid = digits(row.get("마을ID", ""))
        if len(vid) < 10:
            bad_ids.append({"row_number": str(i), "village_id": vid, "source_label": row.get("마을명", ""), "reason": "VILLAGE_ID_SHORTER_THAN_10_DIGITS"})
            continue
        row = dict(row)
        row["_vill_id"] = vid
        grouped[vid].append(row)

    places = []
    relations = []
    aliases = []
    details = []
    snapshots = []
    unresolved = []
    target_types = Counter()
    place_types = Counter()
    id_lengths = Counter()

    for vid, rows in sorted(grouped.items()):
        rows_sorted = sorted(rows, key=row_sort_key)
        latest = rows_sorted[-1]
        label = (latest.get("마을명") or "").strip()
        source_type = (latest.get("마을유형") or "").strip()
        candidate = vid[:10]
        target = legal_by_code.get(candidate)
        id_lengths[str(len(vid))] += 1

        if target:
            target_type = target.get("place_type", "")
            target_types[target_type] += 1
            ptype = classify(label, source_type, target_type)
            relation_type = "VILLAGE_IN" if ptype == "RURAL_VILLAGE" else "RURAL_CENTER_IN"
            target_id = target["place_id"]
            relations.append({
                "from_place_id": f"village:mafra:{vid}",
                "to_place_id": target_id,
                "relation_type": relation_type,
                "confidence": "1.0",
                "legal_status": "RECORDED",
                "valid_from": "",
                "valid_to": "",
                "source_id": SOURCE_ID,
                "source_snapshot_date": args.snapshot_date,
            })
        else:
            target_type = ""
            target_id = ""
            ptype = "RURAL_VILLAGE"
            unresolved.append({
                "place_id": f"village:mafra:{vid}",
                "village_id": vid,
                "source_label": label,
                "candidate_legal_code": candidate,
                "reason": "LEGAL_CODE_NOT_FOUND_IN_V4",
            })

        place_types[ptype] += 1
        full_name = f"{target.get('full_name_ko', '')} · {label}" if target else label
        places.append({
            "place_id": f"village:mafra:{vid}",
            "place_type": ptype,
            "hierarchy_level": "VILLAGE",
            "name_ko": label,
            "full_name_ko": full_name,
            "official_code": vid,
            "parent_place_id": target_id,
            "legal_status": "RECORDED",
            "valid_from": "",
            "valid_to": "",
            "source_id": SOURCE_ID,
            "validity_source_id": SOURCE_ID,
            "source_snapshot_date": args.snapshot_date,
            "latitude": "",
            "longitude": "",
        })

        labels_seen = set()
        for r in rows_sorted:
            old_label = (r.get("마을명") or "").strip()
            if old_label and old_label not in labels_seen:
                aliases.append({
                    "place_id": f"village:mafra:{vid}",
                    "alias": old_label,
                    "alias_type": "SOURCE_LABEL" if old_label == label else "HISTORICAL_SOURCE_LABEL",
                    "source_id": SOURCE_ID,
                })
                labels_seen.add(old_label)
            snapshots.append({
                "place_id": f"village:mafra:{vid}",
                "village_id": vid,
                "source_label": old_label,
                "base_year": digits(r.get("기준년도", ""))[:4],
                "village_type": (r.get("마을유형") or "").strip(),
                "update_date": norm_date(r.get("최종 갱신일", "")),
                "candidate_legal_code": candidate,
                "target_place_id": target_id,
                "is_selected_latest": "Y" if r is latest else "N",
            })

        details.append({
            "place_id": f"village:mafra:{vid}",
            "village_id": vid,
            "source_label": label,
            "village_type": source_type,
            "base_year": digits(latest.get("기준년도", ""))[:4],
            "update_date": norm_date(latest.get("최종 갱신일", "")),
            "candidate_legal_code": candidate,
            "target_place_id": target_id,
            "target_place_type": target_type,
            "target_full_name_ko": target.get("full_name_ko", "") if target else "",
            "link_granularity": target_type,
            "source_record_count": str(len(rows)),
            "source_id": SOURCE_ID,
            "source_snapshot_date": args.snapshot_date,
        })

    pf = ["place_id", "place_type", "hierarchy_level", "name_ko", "full_name_ko", "official_code", "parent_place_id", "legal_status", "valid_from", "valid_to", "source_id", "validity_source_id", "source_snapshot_date", "latitude", "longitude"]
    rf = ["from_place_id", "to_place_id", "relation_type", "confidence", "legal_status", "valid_from", "valid_to", "source_id", "source_snapshot_date"]
    af = ["place_id", "alias", "alias_type", "source_id"]
    df = ["place_id", "village_id", "source_label", "village_type", "base_year", "update_date", "candidate_legal_code", "target_place_id", "target_place_type", "target_full_name_ko", "link_granularity", "source_record_count", "source_id", "source_snapshot_date"]
    sf = ["place_id", "village_id", "source_label", "base_year", "village_type", "update_date", "candidate_legal_code", "target_place_id", "is_selected_latest"]
    uf = ["place_id", "village_id", "source_label", "candidate_legal_code", "reason"]
    bif = ["row_number", "village_id", "source_label", "reason"]

    write_csv(args.out_dir / "places_village.csv", places, pf)
    write_csv(args.out_dir / "village_relations.csv", relations, rf)
    write_csv(args.out_dir / "village_aliases.csv", aliases, af)
    write_csv(args.out_dir / "village_details.csv", details, df)
    write_csv(args.out_dir / "village_snapshots.csv", snapshots, sf)
    write_csv(args.out_dir / "village_unresolved_regions.csv", unresolved, uf)
    write_csv(args.out_dir / "village_bad_ids.csv", bad_ids, bif)

    years = [int(digits(r.get("기준년도", ""))[:4]) for r in raw if digits(r.get("기준년도", ""))[:4]]
    dates = [digits(r.get("최종 갱신일", ""))[:8] for r in raw if len(digits(r.get("최종 갱신일", ""))) >= 8]
    report = {
        "source_rows": len(raw),
        "unique_village_ids": len(grouped),
        "duplicate_snapshot_rows": len(raw) - len(grouped),
        "places": len(places),
        "relations": len(relations),
        "aliases": len(aliases),
        "unresolved_regions": len(unresolved),
        "bad_ids": len(bad_ids),
        "id_length_counts": dict(sorted(id_lengths.items())),
        "place_type_counts": dict(sorted(place_types.items())),
        "target_type_counts": dict(sorted(target_types.items())),
        "min_base_year": min(years) if years else None,
        "max_base_year": max(years) if years else None,
        "max_update_date": max(dates) if dates else None,
        "privacy_fields_excluded": ["대표자명", "대표자직책"],
        "source_snapshot_date": args.snapshot_date,
    }
    (args.out_dir / "village_import_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
