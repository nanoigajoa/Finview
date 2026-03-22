# Skill: multi-factor-screener

- **Purpose:** 절대값 + 상대값 복합 필터를 조합하여 동적 SQL 쿼리를 생성하고 종목을 스크리닝한다.
- **Inputs:** 필터 파라미터 딕셔너리 (14종), `screener_summary` 테이블
- **Outputs:** 조건을 충족하는 종목 리스트 + 결과 수

## Best Practices

- **조건부 WHERE 빌딩:** 파라미터가 `None`이면 해당 조건을 쿼리에서 제외 — 모든 조합 지원
- **절대값 필터:** `min_roe`, `max_per`, `max_pbr`, `max_debt_ratio`, `max_peg` 등
- **상대값 필터:** `relative_per_discount` = 종목 PER이 섹터 중앙값 대비 X% 이상 저평가
  - `company_per < median_per × (1 - discount/100)`
- **플래그 필터:** `inst_buy_flag=True` (기관 순매수 양수), `ocf_pass=True` (3개년 연속 흑자)
- **PEG 필터:** `PEG = PER / rev_cagr_3y` — PEG < max_peg 조건 (rev_cagr > 0 필수)
- 결과는 시가총액 기준 내림차순 정렬 (기본값)
- 페이지네이션: 50건 단위

## Anti-patterns

- ❌ 모든 조건을 AND로 하드코딩 — 선택적 필터 불가
- ❌ PEG 계산 시 CAGR=0 또는 음수 허용 — 0 나누기 오류
- ❌ 결과 수 미반환 — 사용자가 필터 강도를 알 수 없음

## Example

```python
# backend/main.py — 동적 SQL 빌더
from fastapi import HTTPException
from sqlalchemy import text

def build_screener_query(params: dict) -> tuple[str, dict]:
    conditions = []
    bind = {}

    if params.get("min_roe") is not None:
        conditions.append("ROE >= :min_roe")
        bind["min_roe"] = params["min_roe"]

    if params.get("max_per") is not None:
        conditions.append("PER BETWEEN 0.1 AND :max_per")
        bind["max_per"] = params["max_per"]

    if params.get("relative_per_discount") is not None:
        discount = params["relative_per_discount"] / 100
        conditions.append("PER < median_per * :per_factor")
        bind["per_factor"] = 1 - discount

    if params.get("ocf_pass_flag"):
        conditions.append("ocf_pass = 1")

    if params.get("max_peg") is not None:
        conditions.append("rev_cagr_3y > 0")
        conditions.append("(PER / rev_cagr_3y) <= :max_peg")
        bind["max_peg"] = params["max_peg"]

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    sql = f"""
        SELECT * FROM screener_summary
        {where}
        ORDER BY 시가총액 DESC
    """
    return sql, bind
```

## Reusable across

- 채권 스크리닝 시스템
- 부동산 투자 필터링
- 일반 다요소 데이터 검색 인터페이스
