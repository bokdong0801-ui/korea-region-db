# Korea Region DB

대한민국 전국 지역 엔티티를 하나의 정규화된 DB로 관리하기 위한 프로젝트입니다.

## 목표

행정구역과 생활권을 섞지 않고 별도 타입으로 관리한 뒤 관계 테이블로 연결합니다.

1. 공식 행정/법정 지역: 시도 → 시군구 → 읍면동 → 리
2. 행정동과 법정동 매핑
3. 폐지/신설/명칭변경/분할/통합 이력
4. 역, 신도시, 택지지구, 도시개발지구, 공공주택지구
5. 자연마을·생활권·통칭지역
6. 좌표와 상하위/인접/중첩 관계
7. CSV / JSON / MySQL / SQL INSERT / 페이지 생성용 데이터 export

## 현재 상태

**Korea Region Master DB V1.0.0 완료 (2026-09-14)**

- 고정 브랜치: `release/v1.0.0`
- 릴리스 기록: `releases/V1.0.0.md`
- Code.go 법정동 전체자료 실제 병합: 53,387건
- MOIS 행정지역: 9,609건
- MOIS 법정지역: 53,391건
- 행정↔법정 원천 관계: 58,942건
- Master places: 63,023건
- Master relations: 121,893건
- 감사 예외 관계: 12건
- unresolved relations: **0건**
- aliases: 53,361건
- place_history: 101,506건

Code.go와 MOIS가 충돌하는 값은 삭제하거나 임의 보정하지 않고 `source_discrepancies.csv`에 보존합니다. V1 기준 71건이 기록되어 있습니다.

## 원천 정책

- **Code.go**: 법정지역 identity / name / current-abolished status의 우선 원천
- **MOIS jscode**: 행정지역, 행정↔법정 매핑, 생성·말소일의 우선 원천
- 폐지지역은 삭제하지 않고 status/history로 영구 보존
- 이름 유사도만으로 과거 지역의 successor를 추정하지 않음

## 디렉터리

- `data/raw/` 원본 자료(가능하면 무수정 보존)
- `data/normalized/` 정규화 CSV
- `data/exports/` JSON/SQL 등 배포 산출물
- `data/rules/` 공식 원천 예외 및 감사 규칙
- `sources/` 공식 출처·스냅샷 메타데이터
- `sql/` DB 스키마
- `scripts/` 수집·정규화·검증 스크립트
- `docs/` 데이터 모델 및 운영 규칙
- `releases/` 고정 릴리스 기록

## 다음 단계

1. 전국 철도·도시철도 역 DB
2. 신도시·택지개발·도시개발·공공주택지구 DB
3. 자연마을·생활권·통칭지역 DB
4. 좌표 및 인접/중첩 관계
5. 지역 페이지 생성용 JSON / slug registry

## 핵심 원칙

- 법정동과 행정동을 같은 엔티티로 합치지 않습니다.
- 폐지지역도 영구 보존합니다.
- 지역명 문자열이 아니라 `place_id`를 내부 식별자로 사용합니다.
- 신도시/역/마을/지구는 공식 행정구역 트리에 억지로 넣지 않고 별도 엔티티로 관리합니다.
- 검색/SEO 페이지는 DB 완성 후 별도 생성합니다.
