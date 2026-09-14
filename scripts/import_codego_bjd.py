#!/usr/bin/env python3
"""Normalize 행정표준코드관리시스템 '법정동코드 전체자료' into Korea Region DB CSV.

Expected common columns:
- 법정동코드
- 법정동명
- 폐지여부

The official file is tab-separated and CP949/EUC-KR encoded. This importer
tries common encodings automatically and never drops abolished rows.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import date
from pathlib import Path

ENCODINGS = ("utf-8-sig", "cp949", "euc-kr", "utf-8")


def read_text(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    for enc in ENCODINGS:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"지원 인코딩으로 읽을 수 없습니다: {path}")


def detect_delimiter(first_line: str) -> str:
    if "\t" in first_line:
        return "\t"
    if "," in first_line:
        return ","
    raise ValueError("구분자를 찾지 못했습니다. TSV 또는 CSV 원본을 사용하세요.")


def normalize_headers(headers: list[str]) -> dict[str, str]:
    out = {}
    for h in headers:
        k = re.sub(r"\s+", "", (h or "").strip())
        out[k] = h
    return out


def pick(header_map: dict[str, str], *candidates: str) -> str:
    for c in candidates:
        key = re.sub(r"\s+", "", c)
        if key in header_map:
            return header_map[key]
    raise KeyError(f"필수 컬럼을 찾지 못했습니다: {candidates}")


def level_and_type(code: str, short_name: str, full_name: str) -> tuple[int, str]:
    if not re.fullmatch(r"\d{10}", code):
        raise ValueError(f"법정동코드는 10자리 숫자여야 합니다: {code}")
    # 세종특별자치시(3611000000)처럼 최상위 지역인데 코드가 xx00000000
    # 패턴을 따르지 않는 예외가 있으므로 공식 명칭의 계층도 함께 본다.
    if len(full_name.split()) == 1:
        return 1, "SIDO"
    if code[2:] == "00000000":
        return 1, "SIDO"
    if code[5:] == "00000":
        return 2, "SIGUNGU"
    if code[8:] == "00":
        if short_name.endswith("읍"):
            return 3, "LEGAL_EUP"
        if short_name.endswith("면"):
            return 3, "LEGAL_MYEON"
        return 3, "LEGAL_DONG"
    return 4, "LEGAL_RI"


def parent_code(code: str, level: int) -> str | None:
    if level == 1:
        return None
    if level == 2:
        return code[:2] + "00000000"
    if level == 3:
        return code[:5] + "00000"
    if level == 4:
        return code[:8] + "00"
    raise ValueError(level)


def normalize_status(value: str) -> str:
    v = (value or "").strip().lower()
    current_tokens = {"존재", "현존", "0", "n", "no", "false", "사용"}
    abolished_tokens = {"폐지", "말소", "1", "y", "yes", "true", "미사용"}
    if v in current_tokens:
        return "CURRENT"
    if v in abolished_tokens:
        return "ABOLISHED"
    if "폐지" in v or "말소" in v:
        return "ABOLISHED"
    if "존재" in v or "현존" in v:
        return "CURRENT"
    return "UNKNOWN"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path, help="법정동코드 전체자료 TXT/TSV/CSV")
    ap.add_argument("--out-dir", type=Path, default=Path("data/normalized"))
    ap.add_argument("--snapshot-date", default=date.today().isoformat())
    args = ap.parse_args()

    text, encoding = read_text(args.input)
    lines = text.splitlines()
    if not lines:
        raise SystemExit("빈 파일입니다.")

    delimiter = detect_delimiter(lines[0])
    reader = csv.DictReader(lines, delimiter=delimiter)
    if not reader.fieldnames:
        raise SystemExit("헤더가 없습니다.")

    hm = normalize_headers(reader.fieldnames)
    code_col = pick(hm, "법정동코드", "지역코드")
    name_col = pick(hm, "법정동명", "지역주소명")
    status_col = pick(hm, "폐지여부", "폐지구분")

    rows: list[dict[str, str]] = []
    aliases: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []

    for line_no, row in enumerate(reader, start=2):
        code = re.sub(r"\D", "", (row.get(code_col) or "").strip())
        full_name = re.sub(r"\s+", " ", (row.get(name_col) or "").strip())
        if not code and not full_name:
            continue
        try:
            short_name = full_name.split()[-1]
            level, place_type = level_and_type(code, short_name, full_name)
            pcode = parent_code(code, level)
            place_id = f"bjd:{code}"
            rows.append({
                "place_id": place_id,
                "place_type": place_type,
                "hierarchy_level": str(level),
                "name_ko": short_name,
                "full_name_ko": full_name,
                "official_code": code,
                "parent_place_id": f"bjd:{pcode}" if pcode else "",
                "legal_status": normalize_status(row.get(status_col) or ""),
                "source_id": "codego_bjd",
                "source_snapshot_date": args.snapshot_date,
            })
            if short_name != full_name:
                aliases.append({"place_id": place_id, "alias": short_name, "alias_type": "SHORT_NAME", "source_id": "codego_bjd"})
        except Exception as exc:
            errors.append({"line": str(line_no), "code": code, "name": full_name, "error": str(exc)})

    args.out_dir.mkdir(parents=True, exist_ok=True)
    place_path = args.out_dir / "places_legal.csv"
    alias_path = args.out_dir / "place_aliases_legal.csv"
    error_path = args.out_dir / "import_errors_codego_bjd.json"
    meta_path = args.out_dir / "codego_bjd_import_meta.json"

    place_fields = ["place_id", "place_type", "hierarchy_level", "name_ko", "full_name_ko", "official_code", "parent_place_id", "legal_status", "source_id", "source_snapshot_date"]
    with place_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=place_fields); w.writeheader(); w.writerows(rows)

    alias_fields = ["place_id", "alias", "alias_type", "source_id"]
    with alias_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=alias_fields); w.writeheader(); w.writerows(aliases)

    error_path.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
    raw_sha256 = hashlib.sha256(args.input.read_bytes()).hexdigest()
    meta = {
        "input": str(args.input), "input_sha256": raw_sha256, "detected_encoding": encoding,
        "delimiter": "TAB" if delimiter == "\t" else delimiter, "snapshot_date": args.snapshot_date,
        "rows": len(rows), "current": sum(r["legal_status"] == "CURRENT" for r in rows),
        "abolished": sum(r["legal_status"] == "ABOLISHED" for r in rows),
        "unknown_status": sum(r["legal_status"] == "UNKNOWN" for r in rows), "errors": len(errors),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
