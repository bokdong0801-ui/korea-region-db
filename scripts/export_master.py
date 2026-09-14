#!/usr/bin/env python3
"""Export Korea Region DB master CSVs to JSON and MySQL INSERT SQL."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
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
    unresolved = read_csv(args.master_dir / "unresolved_relations.csv")
    relation_exceptions = read_csv(args.master_dir / "relation_exceptions.csv")
    aliases = read_csv(args.master_dir / "aliases_master.csv")
    history = read_csv(args.master_dir / "place_history.csv")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "places": places,
        "relations": relations,
        "aliases": aliases,
        "history": history,
        "quality": {
            "unresolved_relations": unresolved,
            "relation_exceptions": relation_exceptions,
        },
    }
    (args.out_dir / "korea_regions.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    sql = ["SET NAMES utf8mb4;", "SET FOREIGN_KEY_CHECKS=0;", ""]
    place_cols = [
        "place_id", "place_type", "name_ko", "full_name_ko", "official_code", "parent_place_id",
        "legal_status", "valid_from", "valid_to", "source_id", "validity_source_id", "source_snapshot_date",
    ]
    for r in places:
        values = ", ".join(sql_value(r.get(c)) for c in place_cols)
        sql.append(
            f"INSERT INTO places ({', '.join(place_cols)}) VALUES ({values}) ON DUPLICATE KEY UPDATE "
            "name_ko=VALUES(name_ko), full_name_ko=VALUES(full_name_ko), legal_status=VALUES(legal_status), "
            "valid_from=VALUES(valid_from), valid_to=VALUES(valid_to), source_id=VALUES(source_id), "
            "validity_source_id=VALUES(validity_source_id), source_snapshot_date=VALUES(source_snapshot_date);"
        )

    for r in aliases:
        cols = ["place_id", "alias", "alias_type", "source_id"]
        values = ", ".join(sql_value(r.get(c)) for c in cols)
        sql.append(f"INSERT IGNORE INTO place_aliases ({', '.join(cols)}) VALUES ({values});")

    for r in relations:
        cols = ["from_place_id", "to_place_id", "relation_type", "source_id", "valid_from", "valid_to"]
        values = ", ".join(sql_value(r.get(c)) for c in cols)
        sql.append(f"INSERT IGNORE INTO place_relations ({', '.join(cols)}) VALUES ({values});")

    for r in history:
        cols = ["history_id", "place_id", "related_place_id", "event_type", "effective_date", "note", "source_id"]
        values = ", ".join(sql_value(r.get(c)) for c in cols)
        sql.append(f"INSERT IGNORE INTO place_history ({', '.join(cols)}) VALUES ({values});")

    sql.extend(["", "SET FOREIGN_KEY_CHECKS=1;"])
    (args.out_dir / "korea_regions_mysql.sql").write_text("\n".join(sql) + "\n", encoding="utf-8")

    print(json.dumps({
        "places": len(places),
        "relations": len(relations),
        "relation_exceptions": len(relation_exceptions),
        "unresolved_relations": len(unresolved),
        "aliases": len(aliases),
        "history_events": len(history),
        "json": str(args.out_dir / "korea_regions.json"),
        "sql": str(args.out_dir / "korea_regions_mysql.sql"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
