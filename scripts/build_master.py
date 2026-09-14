#!/usr/bin/env python3
"""Build unified Korea Region DB master files from normalized source CSVs.

Source roles in V1:
- Code.go full legal-dong snapshot: primary legal identity/name/status source.
- MOIS jscode: historical validity dates, administrative entities, and ADMINISTERS mappings.

Missing relation endpoints are never invented. Explicitly audited source anomalies may
be moved to relation_exceptions.csv via data/rules/relation_exceptions.csv; anything
else remains in unresolved_relations.csv and fails the V1 quality gate.
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
        w.writeheader(); w.writerows(rows)


def normalized_place(row: dict[str, str], default_source: str) -> dict[str, str]:
    source_id = row.get("source_id", default_source) or default_source
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
        "source_id": source_id,
        "validity_source_id": row.get("validity_source_id", "") or (source_id if row.get("valid_from") or row.get("valid_to") else ""),
        "source_snapshot_date": row.get("source_snapshot_date", ""),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--normalized-dir", type=Path, default=Path("data/normalized"))
    ap.add_argument("--rules-dir", type=Path, default=Path("data/rules"))
    ap.add_argument("--out-dir", type=Path, default=Path("data/master"))
    args = ap.parse_args()

    n = args.normalized_dir
    legal = read_csv(n / "places_legal.csv")
    legal_mois = read_csv(n / "places_legal_mois.csv")
    admin = read_csv(n / "places_admin.csv")
    rel = read_csv(n / "relations_admin_legal.csv")
    aliases = read_csv(n / "place_aliases_legal.csv")
    exception_rules = read_csv(args.rules_dir / "relation_exceptions.csv")

    if not legal and not legal_mois:
        raise SystemExit("법정동 원본이 없습니다. places_legal.csv 또는 places_legal_mois.csv가 필요합니다.")

    by_id: dict[str, dict[str, str]] = {}
    source_precedence: dict[str, str] = {}

    # MOIS contributes the broader historical universe and validity dates.
    for row in legal_mois:
        pid = row.get("place_id", "")
        if not pid:
            continue
        item = normalized_place(row, "mois_jscode")
        item["validity_source_id"] = "mois_jscode" if item["valid_from"] or item["valid_to"] else ""
        by_id[pid] = item
        source_precedence[pid] = "MOIS"

    # Code.go wins for legal identity/name/status, while MOIS dates are retained
    # when the downloadable Code.go full file does not carry date columns.
    for row in legal:
        pid = row.get("place_id", "")
        if not pid:
            continue
        codego = normalized_place(row, "codego_bjd")
        previous = by_id.get(pid)
        if previous:
            if not codego["valid_from"]:
                codego["valid_from"] = previous.get("valid_from", "")
            if not codego["valid_to"]:
                codego["valid_to"] = previous.get("valid_to", "")
            if codego["valid_from"] or codego["valid_to"]:
                codego["validity_source_id"] = previous.get("validity_source_id", "") or "mois_jscode"
        by_id[pid] = codego
        source_precedence[pid] = "CODEGO"

    discrepancies: list[dict[str, str]] = []
    mois_by_id = {r.get("place_id", ""): r for r in legal_mois if r.get("place_id")}
    for pid, primary in by_id.items():
        if source_precedence.get(pid) != "CODEGO" or pid not in mois_by_id:
            continue
        secondary = mois_by_id[pid]
        for field in ("full_name_ko", "legal_status"):
            a = (primary.get(field) or "").strip()
            b = (secondary.get(field) or "").strip()
            if a and b and a != b:
                discrepancies.append({"place_id": pid, "field": field, "codego": a, "mois": b})

    for row in admin:
        pid = row.get("place_id", "")
        if not pid:
            continue
        item = normalized_place(row, "mois_jscode")
        item["validity_source_id"] = "mois_jscode" if item["valid_from"] or item["valid_to"] else ""
        by_id[pid] = item

    master = sorted(by_id.values(), key=lambda r: (r.get("place_type", ""), r.get("official_code", ""), r.get("place_id", "")))
    master_ids = set(by_id)

    rule_map = {
        (r.get("from_place_id", ""), r.get("to_place_id", ""), r.get("relation_type", "")): r
        for r in exception_rules
        if r.get("from_place_id") and r.get("to_place_id") and r.get("relation_type")
    }
    used_rule_keys: set[tuple[str, str, str]] = set()

    relation_rows: list[dict[str, str]] = []
    unresolved_rows: list[dict[str, str]] = []
    exception_rows: list[dict[str, str]] = []
    seen_rel: set[tuple[str, str, str, str, str]] = set()

    rel_fields = ["from_place_id", "to_place_id", "relation_type", "legal_status", "valid_from", "valid_to", "source_id", "source_snapshot_date"]

    def route_relation(out: dict[str, str]) -> None:
        src, dst, typ = out["from_place_id"], out["to_place_id"], out["relation_type"]
        missing = []
        if src not in master_ids:
            missing.append("FROM")
        if dst not in master_ids:
            missing.append("TO")
        if not missing:
            relation_rows.append(out)
            return
        rule_key = (src, dst, typ)
        rule = rule_map.get(rule_key)
        if rule:
            used_rule_keys.add(rule_key)
            exception_rows.append({
                **out,
                "unresolved_reason": "+".join(missing) + "_PLACE_NOT_FOUND",
                "resolution_code": rule.get("resolution_code", "AUDITED_EXCEPTION"),
                "resolution_note": rule.get("note", ""),
                "resolution_source_id": rule.get("source_id", ""),
            })
        else:
            unresolved_rows.append({**out, "unresolved_reason": "+".join(missing) + "_PLACE_NOT_FOUND"})

    for r in rel:
        src, dst, typ = r.get("from_place_id", ""), r.get("to_place_id", ""), r.get("relation_type", "")
        vf, vt = r.get("valid_from", ""), r.get("valid_to", "")
        key = (src, dst, typ, vf, vt)
        if not src or not dst or not typ or key in seen_rel:
            continue
        seen_rel.add(key)
        route_relation({
            "from_place_id": src,
            "to_place_id": dst,
            "relation_type": typ,
            "legal_status": r.get("legal_status", "UNKNOWN"),
            "valid_from": vf,
            "valid_to": vt,
            "source_id": r.get("source_id", ""),
            "source_snapshot_date": r.get("source_snapshot_date", ""),
        })

    # Explicit hierarchy graph edges.
    for r in master:
        pid, parent = r.get("place_id", ""), r.get("parent_place_id", "")
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
        route_relation(out)

    unused_rules = [r for k, r in rule_map.items() if k not in used_rule_keys]

    place_fields = [
        "place_id", "place_type", "hierarchy_level", "name_ko", "full_name_ko", "official_code",
        "parent_place_id", "legal_status", "valid_from", "valid_to", "source_id", "validity_source_id",
        "source_snapshot_date",
    ]
    unresolved_fields = rel_fields + ["unresolved_reason"]
    exception_fields = unresolved_fields + ["resolution_code", "resolution_note", "resolution_source_id"]
    alias_fields = ["place_id", "alias", "alias_type", "source_id"]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "places_master.csv", master, place_fields)
    write_csv(args.out_dir / "relations_master.csv", relation_rows, rel_fields)
    write_csv(args.out_dir / "unresolved_relations.csv", unresolved_rows, unresolved_fields)
    write_csv(args.out_dir / "relation_exceptions.csv", exception_rows, exception_fields)
    write_csv(args.out_dir / "unused_relation_exception_rules.csv", unused_rules, list(exception_rules[0].keys()) if exception_rules else ["from_place_id", "to_place_id", "relation_type", "resolution_code", "note", "source_id"])
    write_csv(args.out_dir / "aliases_master.csv", aliases, alias_fields)
    write_csv(args.out_dir / "source_discrepancies.csv", discrepancies, ["place_id", "field", "codego", "mois"])

    report = {
        "places": len(master),
        "relations_resolved": len(relation_rows),
        "relations_exceptions": len(exception_rows),
        "relations_unresolved": len(unresolved_rows),
        "unused_exception_rules": len(unused_rules),
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
            "relation_exception_rules": len(exception_rules),
        },
    }
    (args.out_dir / "build_master_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
