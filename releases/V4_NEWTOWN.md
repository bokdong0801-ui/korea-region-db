# Korea Geo Master V4 — Newtown Overlay

Release snapshot: 2026-09-14

## Status

- GitHub Actions run: 34860645738
- Artifact ID: 10355006058
- Artifact name: `korea-geo-master-v4-newtown-20260914`
- Artifact SHA-256: `6649a480bb5271304b35cc909c46fdf3c83cb066c19bc59677e5b74d87dfc10e`
- Quality gate: PASS

## Audited base

V4 overlays the newtown layer onto the already quality-gated V3 artifact (`10341947255`).

- V3 places: 65,447
- V3 relations: 124,317
- V3 unresolved geo relations: 0

## Newtown overlay

Canonical rules source: `data/rules/newtowns_official.csv`

- Generation 1: 5
- Generation 2: 12
- Core Generation 3: 5
- Total NEWTOWN entities: 22
- TPSIS project relations: 26
- Aliases: 60
- Unmatched TPSIS projects: 0
- Verified newtowns: 22
- Multi-project newtowns: 4

The four multi-project newtown entities are handled as N:M overlays rather than being collapsed into one TPSIS district.

## Final V4 graph

- Places: 65,469
- Relations: 124,343
- Aliases: 59,030
- NEWTOWN entities: 22
- Unresolved geo relations: 0

Relation type used for the overlay: `NEWTOWN_PROJECT_OF`.

## Official catalog sources

- 1st-generation newtowns: Ministry of Land, Infrastructure and Transport (MOLIT), 5 cities — Bundang, Ilsan, Pyeongchon, Sanbon, Jungdong.
- 2nd-generation newtowns: MOLIT, 12 cities/projects — Pangyo, Dongtan 1, Dongtan 2, Gimpo Hangang, Paju Unjeong, Gwanggyo, Yangju (Okjeong/Hoecheon), Wirye, Godeok Internationalization, Incheon Geomdan, Asan (Tangjeong/Baebang), Daejeon Doan.
- Core 3rd-generation newtowns: MOLIT, 5 districts — Namyangju Wangsuk, Hanam Gyosan, Incheon Gyeyang, Goyang Changneung, Bucheon Daejang.

TPSIS development district IDs remain the project-level source of truth; a NEWTOWN entity may point to multiple TPSIS projects.
