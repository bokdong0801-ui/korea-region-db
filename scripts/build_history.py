#!/usr/bin/env python3
"""Build place_history events from validated place validity ranges.

V1 only generates facts directly supported by official dates:
- CREATED at valid_from
- ABOLISHED at valid_to

It intentionally does NOT infer RENAMED/MERGED/SPLIT successor links from name
similarity. Those richer transitions must be added from official change notices.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def event_id(place_id: str, event_type: str, effective_date: str) -> str:
    key = f"{place_id}|{event_type}|{effective_date}".encode("utf-8")
    return "hist:" + hashlib.sha1(key).hexdigest()[:20]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--master-dir", type=Path, default=Path("data/master"))
    args = ap.parse_args()

    places = read_csv(args.master_dir / "places_master.csv")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for p in places:
        pid = p.get("place_id", "")
        if not pid:
            continue
        validity_source = p.get("validity_source_id", "") or p.get("source_id", "")
        vf = p.get("valid_from", "")
        vt = p.get("valid_to", "")
        if vf:
            hid = event_id(pid, "CREATED", vf)
            if hid not in seen:
                seen.add(hid)
                rows.append({
                    "history_id": hid,
                    "place_id": pid,
                    "related_place_id": "",
                    "event_type": "CREATED",
                    "effective_date": vf,
                    "note": "official validity start date",
                    "source_id": validity_source,
                })
        if vt:
            hid = event_id(pid, "ABOLISHED", vt)
            if hid not in seen:
                seen.add(hid)
                rows.append({
                    "history_id": hid,
                    "place_id": pid,
                    "related_place_id": "",
                    "event_type": "ABOLISHED",
                    "effective_date": vt,
                    "note": "official validity end date; successor is not inferred",
                    "source_id": validity_source,
                })

    rows.sort(key=lambda r: (r["effective_date"], r["place_id"], r["event_type"]))
    fields = ["history_id", "place_id", "related_place_id", "event_type", "effective_date", "note", "source_id"]
    out = args.master_dir / "place_history.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows)

    report = {
        "history_events": len(rows),
        "by_event_type": dict(Counter(r["event_type"] for r in rows)),
        "places_with_history": len({r["place_id"] for r in rows}),
        "policy": "No successor/predecessor inference from name similarity in V1",
    }
    (args.master_dir / "place_history_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
