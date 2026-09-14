# Geo Master V5 — Toponym / Village Layer Status

Status: **PIPELINE READY / PRODUCTION SOURCE BLOCKED**

Date: 2026-09-15 (Asia/Seoul)

## Intended official source

- Provider: 국토교통부 국토지리정보원 (NGII)
- Distribution: VWorld
- Dataset ID: `30231`
- Dataset: 연속수치지형도 지명
- Layer/file: `N3P_H0040000`
- License: CC BY
- Required fields used by V5: `UFID`, `NAME`, `DIVI`, `TYPE`, `BJCD`, `SCLS`, `FMTA`
- Village code: `TYPE=PNT007` (부락)
- Natural toponym code: `DIVI=PNN001`

## Relation policy

V5 creates a relation to an existing V4 legal place **only when the source `BJCD` exactly matches an existing legal-place `official_code`**.

- `PNT007` -> `VILLAGE` + `VILLAGE_IN`
- other natural names -> `NATURAL_TOPONYM` + `TOPONYM_IN`
- administrative/legal names are retained as separate toponym entity types
- no fuzzy name inference
- no proximity inference
- unmatched `BJCD` values are preserved for audit

## Implemented pipeline

- `scripts/download_vworld_names.py`
- `scripts/inspect_vworld_names.py`
- `scripts/import_ngii_place_names.py`
- `scripts/augment_geo_v5_toponyms.py`
- `scripts/make_v5_test_fixture.py`
- `.github/workflows/discover-vworld-names-v5.yml`
- `.github/workflows/validate-toponym-v5-pipeline.yml`
- `.github/workflows/build-toponym-v5.yml`

## Validation

Dedicated deterministic pipeline validation against the audited V4 master: **PASS**

Workflow run: `34864872361`

Validated behavior:

- NGII-compatible SHP ingestion
- `PNT007` -> `VILLAGE_IN`
- natural toponym -> `TOPONYM_IN`
- exact `BJCD` matching to V4 legal region IDs
- V4 -> V5 overlay
- unresolved relation gate

## Production blocker

The official VWorld bulk endpoint for dataset `30231` is currently returning HTTP `502 Bad Gateway` from both external verification and GitHub Actions. The production workflow therefore intentionally stops before normalization rather than using an unofficial mirror or fabricated API credential.

Failed production run caused by upstream download failure: `34864641939`.

No production V5 release/artifact is declared until the official national source is successfully acquired and the strict V5 quality gate passes.

## Next acceptable source paths

1. Retry the official VWorld bulk distribution when service recovers.
2. Use a user-owned VWorld / public-data API credential for the official national-place-name API, after validating that the response exposes the required official identifiers/classification needed for the same relation policy.
3. Use another official NGII bulk distribution containing the same `N3P_H0040000` attributes.

Unofficial scraped place-name lists are not accepted as a substitute for V5 production.
