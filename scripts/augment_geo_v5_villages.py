#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def read(path: Path):
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write(path: Path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v4-dir", type=Path, required=True)
    ap.add_argument("--village-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    places = read(args.v4_dir / "places_geo_master.csv")
    relations = read(args.v4_dir / "relations_geo_master.csv")
    aliases = read(args.v4_dir / "aliases_geo_master.csv")
    village_places = read(args.village_dir / "places_village.csv")
    village_relations = read(args.village_dir / "village_relations.csv")
    village_aliases = read(args.village_dir / "village_aliases.csv")

    existing = {r["place_id"] for r in places}
    duplicate_place_ids = []
    added_places = 0
    for r in village_places:
        pid = r.get("place_id", "")
        if not pid:
            continue
        if pid in existing:
            duplicate_place_ids.append(pid)
            continue
        places.append(r)
        existing.add(pid)
        added_places += 1

    seen_rel = {
        (r.get("from_place_id"), r.get("to_place_id"), r.get("relation_type"), r.get("valid_from", ""), r.get("valid_to", ""))
        for r in relations
    }
    unresolved = []
    added_relations = 0
    for r in village_relations:
        key = (r.get("from_place_id"), r.get("to_place_id"), r.get("relation_type"), r.get("valid_from", ""), r.get("valid_to", ""))
        if key in seen_rel:
            continue
        if r.get("from_place_id") not in existing or r.get("to_place_id") not in existing:
            unresolved.append(r)
            continue
        relations.append(r)
        seen_rel.add(key)
        added_relations += 1

    seen_alias = {(r.get("place_id"), r.get("alias"), r.get("alias_type")) for r in aliases}
    added_aliases = 0
    for r in village_aliases:
        key = (r.get("place_id"), r.get("alias"), r.get("alias_type"))
        if r.get("place_id") in existing and r.get("alias") and key not in seen_alias:
            aliases.append(r)
            seen_alias.add(key)
            added_aliases += 1

    pf = ["place_id", "place_type", "hierarchy_level", "name_ko", "full_name_ko", "official_code", "parent_place_id", "legal_status", "valid_from", "valid_to", "source_id", "validity_source_id", "source_snapshot_date", "latitude", "longitude"]
    rf = ["from_place_id", "to_place_id", "relation_type", "confidence", "legal_status", "valid_from", "valid_to", "source_id", "source_snapshot_date"]
    af = ["place_id", "alias", "alias_type", "source_id"]

    write(args.out_dir / "places_geo_master.csv", places, pf)
    write(args.out_dir / "relations_geo_master.csv", relations, rf)
    write(args.out_dir / "aliases_geo_master.csv", aliases, af)
    write(args.out_dir / "unresolved_geo_relations.csv", unresolved, rf)
    write(args.out_dir / "duplicate_village_place_ids.csv", [{"place_id": x} for x in duplicate_place_ids], ["place_id"])

    report = {
        "base_v4_places": len(read(args.v4_dir / "places_geo_master.csv")),
        "places": len(places),
        "added_village_places": added_places,
        "relations": len(relations),
        "added_village_relations": added_relations,
        "aliases": len(aliases),
        "added_village_aliases": added_aliases,
        "unresolved_geo_relations": len(unresolved),
        "duplicate_village_place_ids": len(duplicate_place_ids),
        "rural_village_count": sum(r.get("place_type") == "RURAL_VILLAGE" for r in places),
        "rural_center_count": sum(r.get("place_type") == "RURAL_CENTER" for r in places),
        "newtown_count": sum(r.get("place_type") == "NEWTOWN" for r in places),
        "station_count": sum(r.get("place_type") == "STATION" for r in places),
    }
    (args.out_dir / "geo_master_v5_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
