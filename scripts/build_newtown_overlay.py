#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--development-dir", type=Path, required=True)
    ap.add_argument("--rules", type=Path, required=True)
    ap.add_argument("--snapshot-date", default="2026-09-14")
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    dev_places = read_csv(args.development_dir / "places_development.csv")
    by_code = {r.get("official_code", ""): r for r in dev_places if r.get("official_code")}
    rules = read_csv(args.rules)

    ids = [r.get("newtown_id", "") for r in rules]
    if len(rules) != 22:
        raise SystemExit(f"Expected 22 official newtown rows, got {len(rules)}")
    if len(set(ids)) != len(ids):
        raise SystemExit("Duplicate newtown_id in rules")

    gen_counts = Counter(r.get("generation", "") for r in rules)
    if gen_counts != Counter({"1": 5, "2": 12, "3": 5}):
        raise SystemExit(f"Unexpected generation counts: {dict(gen_counts)}")

    places = []
    relations = []
    aliases = []
    details = []
    unmatched = []

    for rule in rules:
        place_id = rule["newtown_id"].strip()
        name = rule["name_ko"].strip()
        generation = rule["generation"].strip()
        source_id = rule["source_id"].strip()
        source_url = rule["official_source_url"].strip()
        codes = [x.strip() for x in rule.get("district_codes", "").split("|") if x.strip()]

        project_place_ids = []
        project_names = []
        for code in codes:
            target = by_code.get(code)
            if not target:
                unmatched.append({
                    "newtown_id": place_id,
                    "name_ko": name,
                    "generation": generation,
                    "district_code": code,
                    "reason": "TPSIS_DISTRICT_CODE_NOT_FOUND",
                })
                continue
            project_place_ids.append(target["place_id"])
            project_names.append(target["name_ko"])
            relations.append({
                "from_place_id": place_id,
                "to_place_id": target["place_id"],
                "relation_type": "NEWTOWN_PROJECT_OF",
                "confidence": "1.0",
                "legal_status": "CURRENT",
                "valid_from": "",
                "valid_to": "",
                "source_id": "molit_newtown_catalog+tpsis_district_info",
                "source_snapshot_date": args.snapshot_date,
            })

        places.append({
            "place_id": place_id,
            "place_type": "NEWTOWN",
            "hierarchy_level": "NEWTOWN",
            "name_ko": name,
            "full_name_ko": name,
            "official_code": "",
            "parent_place_id": "",
            "legal_status": "CURRENT",
            "valid_from": "",
            "valid_to": "",
            "source_id": source_id,
            "validity_source_id": source_id,
            "source_snapshot_date": args.snapshot_date,
            "latitude": "",
            "longitude": "",
        })

        for alias in [x.strip() for x in rule.get("aliases", "").split("|") if x.strip()]:
            aliases.append({
                "place_id": place_id,
                "alias": alias,
                "alias_type": "SEARCH_ALIAS",
                "source_id": source_id,
            })

        details.append({
            "place_id": place_id,
            "generation": generation,
            "name_ko": name,
            "district_official_codes": "|".join(codes),
            "district_place_ids": "|".join(project_place_ids),
            "district_names": "|".join(project_names),
            "project_count": str(len(project_place_ids)),
            "official_source_url": source_url,
            "source_id": source_id,
            "source_snapshot_date": args.snapshot_date,
            "verification_status": "VERIFIED_OFFICIAL_LIST_AND_TPSIS_MAPPING" if len(project_place_ids) == len(codes) else "UNRESOLVED",
        })

    pf = ["place_id", "place_type", "hierarchy_level", "name_ko", "full_name_ko", "official_code", "parent_place_id", "legal_status", "valid_from", "valid_to", "source_id", "validity_source_id", "source_snapshot_date", "latitude", "longitude"]
    rf = ["from_place_id", "to_place_id", "relation_type", "confidence", "legal_status", "valid_from", "valid_to", "source_id", "source_snapshot_date"]
    af = ["place_id", "alias", "alias_type", "source_id"]
    df = ["place_id", "generation", "name_ko", "district_official_codes", "district_place_ids", "district_names", "project_count", "official_source_url", "source_id", "source_snapshot_date", "verification_status"]
    uf = ["newtown_id", "name_ko", "generation", "district_code", "reason"]

    write_csv(args.out_dir / "places_named.csv", places, pf)
    write_csv(args.out_dir / "named_relations.csv", relations, rf)
    write_csv(args.out_dir / "named_aliases.csv", aliases, af)
    write_csv(args.out_dir / "newtown_details.csv", details, df)
    write_csv(args.out_dir / "newtown_unmatched_projects.csv", unmatched, uf)

    report = {
        "newtowns": len(places),
        "project_relations": len(relations),
        "aliases": len(aliases),
        "unmatched_projects": len(unmatched),
        "generation_counts": dict(sorted(gen_counts.items())),
        "multi_project_newtowns": sum(1 for r in details if int(r["project_count"]) > 1),
        "verified_newtowns": sum(1 for r in details if r["verification_status"].startswith("VERIFIED")),
        "snapshot_date": args.snapshot_date,
    }
    (args.out_dir / "newtown_overlay_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if unmatched:
        raise SystemExit(f"Newtown overlay has {len(unmatched)} unresolved TPSIS project mappings")


if __name__ == "__main__":
    main()
