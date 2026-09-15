# Geo Master V5 — MAFRA Village + NGII Natural Toponym Status

Status: **MAFRA V5 COMPLETE / REGION SEARCH V5 COMPLETE / NGII NATURAL TOPONYM SOURCE BLOCKED**

Date: 2026-09-15 (Asia/Seoul)

## Completed base: MAFRA rural villages

Official MAFRA rural-village source is fully integrated into the audited V5 master.

- standard village IDs: `3,306 / 3,306`
- official 8-digit scope IDs: `15 / 15`
- total MAFRA entities: `3,321 / 3,321`
- unresolved regions: `0`
- bad IDs: `0`
- V5 places: `68,790`
- V5 relations: `127,664`
- rural villages: `3,051`
- rural centers: `270`
- duplicate village place IDs: `0`
- unresolved geo relations: `0`

Audited artifact: `10381378865` (`korea-mafra-village-v5-audit-20260915`)
Successful workflow run: `34931940805`

## Completed consumer: Region Search V1 rebuilt from V5

The search site now builds from audited MAFRA V5 rather than V4.

- source release: `V5-MAFRA-20260915`
- indexed places: `68,790`
- relations: `127,664`
- village category: `3,321`
- NEWTOWN: `22`
- STATION: `1,052`
- detail buckets: `128`

Artifact: `10380899955` (`korea-region-search-v1-v5-20260915`)
Successful workflow run: `34932034832`

## Intended NGII official natural-name source

Primary bulk source:

- Provider: 국토교통부 국토지리정보원 (NGII)
- Distribution: VWorld
- Dataset ID: `30231`
- Dataset: 연속수치지형도 지명
- Layer/file: `N3P_H0040000`
- License: CC BY
- Required bulk fields: `UFID`, `NAME`, `DIVI`, `TYPE`, `BJCD`, `SCLS`, `FMTA`
- Natural toponym selection: `DIVI=PNN001`
- Village code inside NGII layer: `TYPE=PNT007` (부락)

Authenticated fallback source prepared:

- VWorld 2D Data API layer: `LT_P_NSNMSSITENM` (국가지명)
- GitHub secret name: `VWORLD_API_KEY`
- probe script: `scripts/probe_vworld_national_names_api.py`
- manual workflow: `.github/workflows/probe-vworld-national-names-api.yml`
- policy: inspect real API response schema first; never guess mappings from API fields to bulk SHP fields

## Natural-name integration policy

The production importer now supports `--natural-only` and retains only official NGII records where `DIVI=PNN001`.

Relations are created only when the source `BJCD` exactly matches an existing legal-place `official_code`.

- `TYPE=PNT007` -> `VILLAGE` + `VILLAGE_IN`
- other `DIVI=PNN001` -> `NATURAL_TOPONYM` + `TOPONYM_IN`
- no fuzzy name inference
- no proximity inference
- unmatched official codes are preserved for audit rather than guessed
- raw official source is preserved unchanged

## Pipeline validation

Natural-only importer change: **PASS**

Workflow: `Validate Toponym V5 Pipeline`
Run: `34932331329`

Validated behavior:

- NGII-compatible SHP ingestion
- natural-only selection support
- exact BJCD matching
- village/natural-toponym relation creation
- overlay integrity
- unresolved-relation gate

## Current production blocker

The official VWorld bulk endpoint for dataset `30231` still fails upstream.

Latest discovery retry:

- workflow: `Discover NGII VWorld Place Names V5`
- run: `34932273578`
- result: **FAIL at official bulk download**

Latest MAFRA-V5-based production attempt:

- workflow: `Build Korea Natural Toponym Geo Master V5`
- run: `34932546821`
- MAFRA V5 input gate: **PASS**
- official NGII/VWorld SHP acquisition: **FAIL**
- normalization/integration intentionally skipped

No NGII production natural-toponym count is declared while the official source is unavailable.

## Next acceptable execution path

1. Keep official VWorld bulk source as primary and retry when upstream service recovers.
2. Add a user-owned `VWORLD_API_KEY` GitHub repository secret and manually run `Probe VWorld National Names API`.
3. Inspect the returned official `LT_P_NSNMSSITENM` property schema. Only if it exposes sufficient official classification/parent identifiers should the API be promoted to a nationwide ingestion fallback.
4. If the VWorld API schema is insufficient, use an approved key for the official `국토교통부_국가지명` OpenAPI / WFS and preserve the same exact-code/no-inference policy.

Unofficial scraped place-name lists, leaked/public example API keys, and inferred administrative links are not accepted as production substitutes.
