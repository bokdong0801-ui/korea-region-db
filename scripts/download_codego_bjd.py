#!/usr/bin/env python3
"""Download the official code.go.kr full legal-dong code snapshot.

Official endpoint:
  POST https://www.code.go.kr/etc/codeFullDown.do
  codeseId=법정동코드

The response is a ZIP containing a CP949/EUC-KR tab-separated text file.
Raw bytes are preserved and a SHA-256 manifest is written for auditability.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import urllib.parse
import urllib.request
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

URL = "https://www.code.go.kr/etc/codeFullDown.do"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=Path("data/raw/codego"))
    ap.add_argument("--snapshot-date", default=date.today().isoformat())
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    payload = urllib.parse.urlencode({"codeseId": "법정동코드"}).encode("utf-8")
    req = urllib.request.Request(
        URL,
        data=payload,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; KoreaRegionDB/1.0; +https://github.com/bokdong0801-ui/korea-region-db)",
            "Accept": "application/zip,application/octet-stream,*/*",
            "Referer": "https://www.code.go.kr/stdcode/regCodeL.do",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as response:
        raw = response.read()
        content_type = response.headers.get("Content-Type", "")

    if len(raw) < 100 or not zipfile.is_zipfile(io.BytesIO(raw)):
        preview = raw[:200].decode("utf-8", errors="replace")
        raise SystemExit(f"code.go.kr response is not a valid ZIP: content_type={content_type!r}, preview={preview!r}")

    zip_path = args.out_dir / f"codego_bjd_full_{args.snapshot_date}.zip"
    zip_path.write_bytes(raw)

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        members = [x for x in zf.infolist() if not x.is_dir()]
        if not members:
            raise SystemExit("code.go.kr ZIP is empty")
        txt_members = [x for x in members if x.filename.lower().endswith((".txt", ".tsv", ".csv"))]
        member = txt_members[0] if txt_members else members[0]
        text_bytes = zf.read(member)

    text_path = args.out_dir / f"codego_bjd_full_{args.snapshot_date}.txt"
    text_path.write_bytes(text_bytes)

    meta = {
        "source_id": "codego_bjd",
        "source_url": "https://www.code.go.kr/stdcode/regCodeL.do",
        "download_endpoint": URL,
        "request": {"codeseId": "법정동코드"},
        "snapshot_date": args.snapshot_date,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "zip_filename": zip_path.name,
        "zip_sha256": hashlib.sha256(raw).hexdigest(),
        "zip_size": len(raw),
        "member_original_name": member.filename,
        "text_filename": text_path.name,
        "text_sha256": hashlib.sha256(text_bytes).hexdigest(),
        "text_size": len(text_bytes),
        "content_type": content_type,
    }
    (args.out_dir / "codego_bjd_download_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
