# Skill: smart-caching

- **Purpose:** 날짜 기반 DB 캐싱으로 외부 API 호출을 최소화하면서 데이터 신선도를 보장한다.
- **Inputs:** `cache_type` (캐시 종류), `ticker` (종목코드), `ttl_days` (유효기간)
- **Outputs:** 캐시 HIT 시 저장 데이터, MISS 시 None

## Best Practices

- 캐시 키: `(cache_type, ticker, cache_date)` 복합키 — 날짜별 버전 관리
- 캐시 테이블은 팩트 DB에 통합 (`api_cache`) — 별도 Redis 불필요 (SQLite 수준)
- 캐시 유효성 검증: `cache_date == today` 또는 `cache_date >= today - ttl_days`
- JSON 직렬화 저장 (`json.dumps`) — 어떤 구조도 저장 가능
- 캐시 MISS 후 원본 데이터를 즉시 캐시에 저장 (write-through)
- 장중(09:00~15:30 KST) 외에는 당일 캐시를 재사용 — 불필요한 재요청 방지

## Anti-patterns

- ❌ 캐시 없이 매 요청마다 외부 API 호출 — 할당량 초과 + 레이턴시 증가
- ❌ In-memory 캐시만 사용 — 서버 재시작 시 소실
- ❌ 캐시 TTL 미설정 — 오래된 데이터 서빙
- ❌ 캐시 키에 날짜 미포함 — 갱신 불가

## Example

```python
# backend/main.py 내 캐싱 패턴
import json
from datetime import date
from sqlalchemy.orm import Session

def get_cached(session: Session, cache_type: str, ticker: str):
    today = str(date.today())
    row = session.execute(
        "SELECT data FROM api_cache WHERE cache_type=:t AND ticker=:k AND cache_date=:d",
        {"t": cache_type, "k": ticker, "d": today}
    ).fetchone()
    return json.loads(row[0]) if row else None

def set_cache(session: Session, cache_type: str, ticker: str, data: dict):
    today = str(date.today())
    session.execute(
        """INSERT OR REPLACE INTO api_cache (cache_type, ticker, cache_date, data)
           VALUES (:t, :k, :d, :v)""",
        {"t": cache_type, "k": ticker, "d": today, "v": json.dumps(data)}
    )
    session.commit()
```
