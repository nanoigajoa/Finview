# Skill: data-fallback-cascade

- **Purpose:** 외부 API 불안정 상황에서 3단계 폴백으로 데이터 가용성을 항상 보장한다.
- **Inputs:** `ticker` (종목코드), `primary_fn` (실시간 API 호출), `cache_fn` (DB 캐시 조회)
- **Outputs:** 데이터 + `fallback: bool` 메타 플래그

## Best Practices

- **단계 1 (Primary):** 실시간 외부 API (KRX, DART)
- **단계 2 (Secondary):** DB 캐시 (날짜 무관 가장 최근 레코드)
- **단계 3 (Tertiary):** 근사 추정 (예: FCF = 영업이익 × 1.2)
- 응답에 항상 `fallback: true/false` 플래그 포함 → 프론트엔드 경고 배너 표시
- 타임아웃 설정 (5초) — 실시간 API 행이면 즉시 캐시로 전환
- 추정값 사용 시 로그에 명시적 기록

## Anti-patterns

- ❌ 실시간 API 실패 시 전체 요청 실패 처리 — 사용자 경험 저하
- ❌ 폴백 데이터를 실시간 데이터와 동일하게 표시 — 투자 판단 오류 유발
- ❌ 추정 로직 없이 None 반환 — 차트 렌더링 실패

## Example

```python
# backend/main.py — 3단계 폴백 패턴
async def get_market_data(ticker: str, session: Session):
    fallback = False

    # Stage 1: 실시간 KRX API
    try:
        data = await asyncio.wait_for(fetch_krx(ticker), timeout=5.0)
        set_cache(session, "market", ticker, data)
        return {"data": data, "meta": {"fallback": False}}
    except Exception:
        pass

    # Stage 2: DB 캐시
    cached = get_latest_cache(session, "market", ticker)
    if cached:
        return {"data": cached, "meta": {"fallback": True}}

    # Stage 3: 근사 추정
    estimated = estimate_from_financial_reports(ticker, session)
    return {"data": estimated, "meta": {"fallback": True, "estimated": True}}
```

## Frontend 연동

```javascript
// script.js — 폴백 경고 배너
if (marketData.meta?.fallback) {
    document.getElementById('data-warning').style.display = 'block';
    document.getElementById('data-warning').textContent =
        '⚠️ 실시간 데이터 미수신. 캐시 데이터를 표시합니다.';
}
```
