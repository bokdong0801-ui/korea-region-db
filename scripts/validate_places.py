#!/usr/bin/env python3
"""Structural validation for normalized Korea Region DB place CSV files."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

VALID_TYPES = {
    "SIDO", "SIGUNGU", "LEGAL_EUP", "LEGAL_MYEON", "LEGAL_DONG", "LEGAL_RI",
    "ADMIN_DONG", "STATION", "NEWTOWN", "DEVELOPMENT_DISTRICT", "VILLAGE", "LIVING_AREA"
}
VALID_STATUS = {"CURRENT", "ABOLISHED", "PLANNED", "UNKNOWN"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_file", type=Path)
    args = ap.parse_args()

    with args.csv_file.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    issues: list[dict[str, str]] = []
    ids = [r.get("place_id", "") for r in rows]
    id_counts = Counter(ids)
    all_ids = set(ids)

    for i, r in enumerate(rows, start=2):
        pid = r.get("place_id", "")
        ptype = r.get("place_type", "")
        status = r.get("legal_status", "")
        code = r.get("official_code", "")
        parent = r.get("parent_place_id", "")
        full = r.get("full_name_ko", "")

        if not pid:
            issues.append({"line": str(i), "type": "MISSING_ID", "detail": full})
        if id_counts[pid] > 1:
            issues.append({"line": str(i), "type": "DUPLICATE_ID", "detail": pid})
        if ptype not in VALID_TYPES:
            issues.append({"line": str(i), "type": "INVALID_TYPE", "detail": ptype})
        if status not in VALID_STATUS:
            issues.append({"line": str(i), "type": "INVALID_STATUS", "detail": status})
        if pid.startswith("bjd:") and not re.fullmatch(r"\d{10}", code):
            issues.append({"line": str(i), "type": "INVALID_BJD_CODE", "detail": code})
        if parent and parent not in all_ids:
            issues.append({"line": str(i), "type": "MISSING_PARENT", "detail": f"{pid} -> {parent}"})
        if not full:
            issues.append({"line": str(i), "type": "MISSING_FULL_NAME", "detail": pid})

    summary = {
        "rows": len(rows),
        "unique_ids": len(set(ids)),
        "issues": len(issues),
        "by_type": dict(Counter(r.get("place_type", "") for r in rows)),
        "by_status": dict(Counter(r.get("legal_status", "") for r in rows)),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if issues:
        print(json.dumps(issues[:100], ensure_ascii=False, indent=2))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
