#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://data.mafra.go.kr"
DETAIL = BASE + "/opendata/data/indexOpenDataDetail.do?data_id=20170216000000000771"
COUNT = BASE + "/opendata/data/getDataCount.do"
EXPORT = BASE + "/opendata/data/getDataFile.do"
ENTITY = "TI_EPIS_FMLG_VILAGE_BASS_INFO"
DATA_ID = "20170216000000000771"
API_ID = "20160127000000000340"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def open_retry(opener, request, *, timeout: int, attempts: int = 4):
    last = None
    for attempt in range(1, attempts + 1):
        try:
            return opener.open(request, timeout=timeout), attempt
        except Exception as exc:
            last = repr(exc)
            if attempt < attempts:
                time.sleep(min(20, 2 ** attempt))
    raise RuntimeError(f"request failed after {attempts} attempts: {last}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot-date", default="2026-09-15")
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/152 Safari/537.36",
        "Referer": DETAIL,
    }

    detail_req = urllib.request.Request(DETAIL, headers={"User-Agent": headers["User-Agent"]})
    resp, detail_attempts = open_retry(opener, detail_req, timeout=60, attempts=3)
    with resp:
        detail_html = resp.read()
    if ENTITY.encode() not in detail_html:
        raise SystemExit("MAFRA detail page did not expose expected village entity")

    # Download the official CSV first. The portal's count AJAX endpoint is
    # observably less reliable than the file endpoint and is only an audit aid.
    form = urllib.parse.urlencode({
        "s_entity_id": ENTITY,
        "fileGubun": "CSV",
        "s_search_form_name": "",
        "s_search_form_value": "",
    }).encode("utf-8")
    export_req = urllib.request.Request(
        EXPORT,
        data=form,
        headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    resp, export_attempts = open_retry(opener, export_req, timeout=120, attempts=3)
    with resp:
        raw = resp.read()
        content_type = resp.headers.get("Content-Type", "")
        content_disposition = resp.headers.get("Content-Disposition", "")

    if len(raw) < 100_000:
        raise SystemExit(f"MAFRA village CSV unexpectedly small: {len(raw)} bytes")
    try:
        decoded = raw.decode("cp949")
    except UnicodeDecodeError as e:
        raise SystemExit(f"MAFRA village CSV is not valid cp949: {e}")

    lines = [x for x in decoded.splitlines() if x.strip()]
    actual_count = max(0, len(lines) - 1)
    if not (3000 <= actual_count <= 5000):
        raise SystemExit(f"Unexpected MAFRA village CSV row count: {actual_count}")
    expected_header = "마을ID,마을명,기준년도,마을유형"
    if not decoded.startswith(expected_header):
        raise SystemExit("Unexpected MAFRA village CSV header")

    # Optional independent count audit. A timeout is recorded but does not
    # invalidate a structurally valid official CSV export.
    expected_count = None
    count_attempts = 0
    count_error = ""
    count_qs = urllib.parse.urlencode({
        "s_entity_id": ENTITY,
        "s_search_form_name": "",
        "s_search_form_value": "",
    })
    count_req = urllib.request.Request(COUNT + "?" + count_qs, data=b"", headers=headers, method="POST")
    try:
        resp, count_attempts = open_retry(opener, count_req, timeout=15, attempts=1)
        with resp:
            count_raw = resp.read()
        count_payload = json.loads(count_raw.decode("utf-8"))
        expected_count = int(count_payload[0]["tot_cnt"])
        if not (3000 <= expected_count <= 5000):
            raise RuntimeError(f"unexpected count endpoint value: {expected_count}")
        if expected_count != actual_count:
            raise RuntimeError(f"row-count mismatch: endpoint={expected_count}, csv={actual_count}")
    except Exception as exc:
        count_error = repr(exc)
        expected_count = None

    out = args.out_dir / f"mafra_rural_villages_{args.snapshot_date}.csv"
    out.write_bytes(raw)
    meta = {
        "source_id": "mafra_rural_village_basic",
        "source_agency": "농림축산식품부 공공데이터포털",
        "data_id": DATA_ID,
        "api_id": API_ID,
        "entity_id": ENTITY,
        "detail_url": DETAIL,
        "count_endpoint": COUNT,
        "export_endpoint": EXPORT,
        "snapshot_date": args.snapshot_date,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "row_count": actual_count,
        "count_endpoint_row_count": expected_count,
        "count_endpoint_verified": expected_count is not None,
        "count_endpoint_error": count_error,
        "detail_attempts_used": detail_attempts,
        "count_attempts_used": count_attempts,
        "export_attempts_used": export_attempts,
        "encoding": "cp949",
        "bytes": len(raw),
        "sha256": sha256(raw),
        "content_type": content_type,
        "content_disposition": content_disposition,
        "raw_filename": out.name,
        "privacy_note": "Raw source includes representative name/job columns. V5 normalized/public artifact must omit those personal fields.",
    }
    (args.out_dir / "mafra_village_download_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
