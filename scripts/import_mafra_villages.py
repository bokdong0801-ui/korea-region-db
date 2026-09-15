#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

SOURCE_ID = "mafra_rural_village_basic"
LEGAL_TYPES = {"LEGAL_RI", "LEGAL_DONG", "LEGAL_EUP", "LEGAL_MYEON"}
ADMIN_TYPES = {"ADMIN_DONG", "ADMIN_EUP", "ADMIN_MYEON"}


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
    center_terms = ("기초생활거점", "중심지", "면소재지", "읍소재지", "소재지형", "권역")
    if any(term in text for term in center_terms):
        return "RURAL_CENTER"
    return "RURAL_VILLAGE"


def row_sort_key(row):
    year = int(digits(row.get("기준년도", ""))[:4] or 0)
    updated = int(digits(row.get("최종 갱신일", ""))[:8] or 0)
    rownum = int(digits(row.get("ROW_NUM", "")) or 0)
    return (year, updated, rownum)


def candidate_code(village_id: str) -> tuple[str, str]:
    """Return an exact V4 code candidate without fuzzy inference.

    MAFRA uses 12-digit village identifiers whose first 10 digits are usually a
    legal/admin region code. A small number of source rows contain an 8-digit
    읍·면·동 scope identifier; in the official code system the corresponding
    scope record is the same 8 digits plus `00`. We only accept that expansion
    when the resulting 10-digit code exists exactly in V4.
    """
    if len(village_id) >= 10:
        return village_id[:10], "FIRST_10_DIGITS"
    if len(village_id) == 8:
        return village_id + "00", "EIGHT_DIGIT_SCOPE_PLUS_00"
    return "", "UNSUPPORTED_ID_LENGTH"


def choose_exact_target(rows: list[dict]) -> dict | None:
    if not rows:
        return None
    def rank(r):
        t = r.get("place_type", "")
        if t == "LEGAL_RI": p = 0
        elif t == "LEGAL_DONG": p = 1
        elif t in {"LEGAL_EUP", "LEGAL_MYEON"}: p = 2
        elif t in ADMIN_TYPES: p = 3
        else: p = 9
        current = 0 if r.get("legal_status") == "CURRENT" else 1
        return (p, current, r.get("place_id", ""))
    return sorted(rows, key=rank)[0]


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
    targets_by_code = defaultdict(list)
    for r in v4_places:
        code = r.get("official_code", "")
        if code and r.get("place_type") in (LEGAL_TYPES | ADMIN_TYPES):
            targets_by_code[code].append(r)

    grouped = defaultdict(list)
    bad_ids = []
    for i, row in enumerate(raw, 1):
        vid = digits(row.get("마을ID", ""))
        candidate, resolution = candidate_code(vid)
        if not candidate:
            bad_ids.append({"row_number": str(i), "village_id": vid, "source_label": row.get("마을명", ""), "reason": resolution})
            continue
        row = dict(row)
        row["_vill_id"] = vid
        row["_candidate_code"] = candidate
        row["_id_resolution"] = resolution
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
    resolution_counts = Counter()

    for vid, rows in sorted(grouped.items()):
        rows_sorted = sorted(rows, key=row_sort_key)
        latest = rows_sorted[-1]
        label = (latest.get("마을명") or "").strip()
        source_type = (latest.get("마을유형") or "").strip()
        candidate = latest["_candidate_code"]
        id_resolution = latest["_id_resolution"]
        resolution_counts[id_resolution] += 1
        target = choose_exact_target(targets_by_code.get(candidate, []))
        id_lengths[str(len(vid))] += 1

        if target:
            target_type = target.get("place_type", "")
            target_types[target_type] += 1
            ptype = classify(label, source_type, target_type)
            if target_type in ADMIN_TYPES:
                relation_type = "VILLAGE_IN_ADMIN" if ptype == "RURAL_VILLAGE" else "RURAL_CENTER_IN_ADMIN"
            else:
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
            ptype = classify(label, source_type, "")
            unresolved.append({
                "place_id": f"village:mafra:{vid}",
                "village_id": vid,
                "source_label": label,
                "candidate_region_code": candidate,
                "id_resolution": id_resolution,
                "reason": "EXACT_REGION_CODE_NOT_FOUND_IN_V4",
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
                "candidate_region_code": r.get("_candidate_code", candidate),
                "id_resolution": r.get("_id_resolution", id_resolution),
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
            "candidate_region_code": candidate,
            "id_resolution": id_resolution,
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
    df = ["place_id", "village_id", "source_label", "village_type", "base_year", "update_date", "candidate_region_code", "id_resolution", "target_place_id", "target_place_type", "target_full_name_ko", "link_granularity", "source_record_count", "source_id", "source_snapshot_date"]
    sf = ["place_id", "village_id", "source_label", "base_year", "village_type", "update_date", "candidate_region_code", "id_resolution", "target_place_id", "is_selected_latest"]
    uf = ["place_id", "village_id", "source_label", "candidate_region_code", "id_resolution", "reason"]
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
        "duplicate_snapshot_rows": len(raw) - len(grouped) - len(bad_ids),
        "places": len(places),
        "relations": len(relations),
        "aliases": len(aliases),
        "unresolved_regions": len(unresolved),
        "bad_ids": len(bad_ids),
        "id_length_counts": dict(sorted(id_lengths.items())),
        "id_resolution_counts": dict(sorted(resolution_counts.items())),
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
