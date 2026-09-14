# Korea Region DB Data Model v1

## 1. Entity layers

### Official administrative/legal layer
- `SIDO`: 시·도
- `SIGUNGU`: 시·군·구
- `LEGAL_EUP`: 법정 읍
- `LEGAL_MYEON`: 법정 면
- `LEGAL_DONG`: 법정 동(가 포함)
- `LEGAL_RI`: 법정 리
- `ADMIN_DONG`: 주민등록 행정기관/행정동

### Named-place layer (Phase 3+)
- `NEWTOWN`: 신도시
- `DEVELOPMENT_DISTRICT`: 택지개발·도시개발·공공주택 등 개발지구
- `VILLAGE`: 자연마을/마을
- `LIVING_AREA`: 생활권·통칭지역

### Transport layer (Phase 4+)
- `STATION`: 철도/도시철도 역

## 2. Identity rules

공식 법정동은 `bjd:{10자리 법정동코드}`를 기본 ID로 사용합니다.

예:
- `bjd:1100000000` 서울특별시
- `bjd:1111000000` 서울특별시 종로구
- `bjd:1111010100` 서울특별시 종로구 청운동

행정동은 법정동과 코드체계가 다르므로 별도 namespace를 사용합니다.

- `adm:{행정기관코드}`

역·신도시·지구·마을은 공식 소스의 안정적인 ID가 있으면 해당 ID를 우선 사용하고, 없으면 내부 UUID/slug와 source key를 병행합니다.

## 3. Legal district hierarchy

10자리 법정동 코드의 계층을 다음처럼 읽습니다.

- 시도: 앞 2자리 + `00000000`
- 시군구: 앞 5자리 + `00000`
- 읍면동: 앞 8자리 + `00`
- 리: 10자리 전체

부모 코드:
- 시군구 → 시도
- 읍면동 → 시군구
- 리 → 읍면동

## 4. Never delete abolished places

폐지 지역은 삭제하지 않습니다.

`legal_status`:
- `CURRENT`
- `ABOLISHED`
- `PLANNED`
- `UNKNOWN`

변경 이력은 `place_history`에 기록합니다.

`event_type`:
- `CREATED`
- `RENAMED`
- `ABOLISHED`
- `MERGED`
- `SPLIT`
- `BOUNDARY_CHANGE`
- `TYPE_CHANGE`

중요: 단순히 이름이 비슷하다는 이유로 과거→현재 successor를 자동 추정하지 않습니다. 공식 변경 공지 또는 행정안전부 변경내역으로 검증한 관계만 기록합니다.

## 5. Administrative dong mapping

행정동과 법정동은 1:1이라고 가정하지 않습니다.

행정안전부 `KiKmix`를 기준으로 관계 테이블에 기록합니다.

예상 관계:
- `ADMINISTERS`: 행정동 → 관할 법정동
- `ADMINISTERED_BY`: 법정동 → 행정동(역관계는 export 시 계산 가능)

하나의 법정동이 여러 행정동에 나뉘거나, 하나의 행정동이 여러 법정동을 관할할 수 있으므로 N:M 구조를 허용합니다.

## 6. Place relations

지역 전체는 단순 트리가 아니라 그래프입니다.

향후 relation 예:
- `PART_OF`
- `CONTAINS`
- `OVERLAPS`
- `NEAR`
- `ADMINISTERS`
- `STATION_IN`
- `SERVES`
- `NEWTOWN_IN`
- `DISTRICT_IN`

## 7. Source policy

A급 공식 출처를 우선합니다.

- 행정표준코드관리시스템
- 행정안전부
- 국토교통부
- 국토지리정보원
- 국가철도공단/한국철도공사 및 도시철도 운영기관
- LH 및 지방자치단체/공기업

모든 원본은 다운로드 시점, URL, SHA-256을 남깁니다.

## 8. SEO/page generation policy

DB에 존재한다고 해서 서비스 SEO 페이지를 자동 index하지 않습니다.

1. 전국 지역 정보 DB: 가능한 한 전체 구축
2. 지역 정보 페이지: 데이터 품질을 통과한 엔티티만 생성
3. ENGLISH PT 서비스 페이지: 검색의도와 고유 콘텐츠 기준을 통과한 지역만 별도 생성

지역명만 바꾼 서비스 페이지의 대량 생성을 금지합니다.
