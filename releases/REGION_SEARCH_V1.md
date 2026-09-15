# Korea Region Search V1

Date: 2026-09-15

## Status

- Build: PASS
- Workflow run: 34929721033
- Artifact: `korea-region-search-v1-20260915`
- Artifact id: `10380514705`
- Artifact digest: `sha256:e47a520e40686018d7204be41cef32580af9c77097e157c897c0df272d06f6f3`
- Deployment: NOT DEPLOYED

## Audited input

Geo Master V4:
- places: 65,469
- relations: 124,343
- newtowns: 22
- stations: 1,052
- unresolved relations: 0

## V1 UI

- unified place-name search
- type filters
- current / abolished place filtering
- hierarchical browsing from SIDO downward
- detail screen by `place_id`
- related place / station / newtown / district relations
- mobile responsive layout

## Browser data architecture

`search-index.json` contains lightweight search fields for every entity.
Detail relation payloads are sharded into 128 JSON buckets to avoid one giant relation file.

When V5 village/toponym data is available, the same builder can consume the newer Geo Master and automatically expose `VILLAGE` / `NATURAL_TOPONYM` categories without changing the UI architecture.

## Next

1. Complete V5 village/toponym production source acquisition.
2. Rebuild Region Search V1 from V5.
3. Add stable slugs and static SEO page generation after the geographic entity model is stable.
