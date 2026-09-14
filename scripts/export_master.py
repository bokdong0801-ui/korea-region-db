#!/usr/bin/env python3
"""Export Korea Region DB master CSVs to JSON and MySQL INSERT SQL."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def sql_value(value: str | None) -> str:
    if value is None or value == "":
        return "NULL"
    value = value.replace("\\", "\\\\").replace("'", "''")
    return f"'{value}'"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--master-dir", type=Path, default=Path("data/master"))
    ap.add_argument("--out-dir", type=Path, default=Path("data/exports"))
    args = ap.parse_args()

    places = read_csv(args.master_dir / "places_master.csv")
    relations = read_csv(args.master_dir / "relations_master.csv")
    aliases = read_csv(args.master_dir / "aliases_master.csv") if (args.master_dir / "aliases_master.csv").exists() else []

    args.out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "places": places,
        "relations": relations,
        "aliases": aliases,
    }
    (args.out_dir / "korea_regions.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    sql = [
        "SET NAMES utf8mb4;",
        "SET FOREIGN_KEY_CHECKS=0;",
        "",
    ]
    place_cols = ["place_id", "place_type", "name_ko", "full_name_ko", "official_code", "parent_place_id", "legal_status", "source_id", "source_snapshot_date"]
    for r in places:
        values = ", ".join(sql_value(r.get(c)) for c in place_cols)
        sql.append(f"INSERT INTO places ({', '.join(place_cols)}) VALUES ({values}) ON DUPLICATE KEY UPDATE name_ko=VALUES(name_ko), full_name_ko=VALUES(full_name_ko), legal_status=VALUES(legal_status), source_id=VALUES(source_id), source_snapshot_date=VALUES(source_snapshot_date);")

    for r in aliases:
        values = ", ".join(sql_value(r.get(c)) for c in ["place_id", "alias", "alias_type", "source_id"])
        sql.append("INSERT IGNORE INTO place_aliases (place_id, alias, alias_type, source_id) VALUES (" + values + ");")

    for r in relations:
        values = ", ".join(sql_value(r.get(c)) for c in ["from_place_id", "to_place_id", "relation_type", "source_id"])
        sql.append("INSERT IGNORE INTO place_relations (from_place_id, to_place_id, relation_type, source_id) VALUES (" + values + ");")

    sql.extend(["", "SET FOREIGN_KEY_CHECKS=1;"])
    (args.out_dir / "korea_regions_mysql.sql").write_text("\n".join(sql) + "\n", encoding="utf-8")

    print(json.dumps({
        "places": len(places), "relations": len(relations), "aliases": len(aliases),
        "json": str(args.out_dir / "korea_regions.json"),
        "sql": str(args.out_dir / "korea_regions_mysql.sql")
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
