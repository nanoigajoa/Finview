# ADR-001: SQLite 이중 DB 구조 채택

- **날짜:** 2026-03-20
- **상태:** 승인됨

## 결정

팩트 데이터(`finance.db`)와 마스터 데이터(`고유번호.db`)를 물리적으로 분리된 SQLite 파일로 운영한다.

## 배경

- DART 종목 마스터(corp_code ↔ stock_code 매핑)는 갱신 주기가 분기 단위로 느리다.
- 재무 팩트 데이터와 스크리너 캐시는 일별로 갱신된다.
- 두 데이터를 같은 DB에 두면 배치 쓰기 중 마스터 조회 성능 저하 가능성이 있다.

## 선택된 방안

**이중 SQLite 분리:**
- `data/고유번호.db` → `company_master` 테이블 (읽기 전용, 초기화 후 분기 갱신)
- `data/finance.db` → `financial_reports`, `screener_summary`, `api_cache` (일배치 쓰기)

## 대안과 기각 이유

| 대안 | 기각 이유 |
|------|----------|
| 단일 SQLite | 배치 잠금 중 마스터 읽기 지연 |
| PostgreSQL | 운영 복잡성 증가, 이 규모에서 불필요 |
| Redis + SQLite | 캐시 레이어 이중화, 추가 의존성 |

## 결과

- 마스터 조회는 항상 `고유번호.db` 전용 세션 사용
- 배치 ETL은 `finance.db` 독립 세션 사용
- GitHub Actions 실행 중 API 서버가 `finance.db` 접근 시 일시적 잠금 발생 가능 → 18:00 KST 배치 실행 시간에 트래픽이 낮으므로 허용
