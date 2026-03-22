# Skill: financial-metrics-calc

- **Purpose:** DART 재무제표 원본 JSON을 파싱하여 투자 판단용 KPI를 산출한다.
- **Inputs:** DART API JSON 응답 (계정과목 리스트)
- **Outputs:** `{revenue, operating_income, net_income, op_cash_flow, roe, op_margin, debt_ratio, fcf}`

## Best Practices

- 금액 단위: 모든 값을 **억원** 기준으로 통일 (`/ 100_000_000`)
- 문자열 → 숫자 변환 시 쉼표 제거 필수 (`str.replace(",", "")`)
- 계정과목명 완전 일치 대신 **포함 검색** (`"매출액" in account_nm`) — DART 계정명 변동 대응
- 파생 지표 계산:
  - `ROE = (net_income / equity) × 100`
  - `op_margin = (operating_income / revenue) × 100`
  - `debt_ratio = (total_liabilities / equity) × 100`
  - `fcf = op_cash_flow × 0.8` (보수적 추정, 유지보수 CAPEX 20% 가정)
- `op_cash_flow == 0` 시 폴백: `fcf = operating_income × 1.2` (영업이익 대비 현금흐름 추정)
- CAGR 계산: `((end / start) ** (1 / years) - 1) × 100`

## Anti-patterns

- ❌ 단순 평균 CAGR — 복합 연간 성장률 아님
- ❌ 별도재무제표로 ROE 계산 — 지주사 이중계산 오류
- ❌ 영업이익을 FCF로 직접 사용 — CAPEX 미반영
- ❌ Zero-division 미처리 — equity=0 시 ROE 계산 오류

## Example

```python
# core/processor.py
import pandas as pd

def extract_metrics(df: pd.DataFrame) -> dict:
    def get(keyword):
        row = df[df["account_nm"].str.contains(keyword, na=False)]
        return float(row["thstrm_amount"].iloc[0]) if not row.empty else 0.0

    revenue = get("매출액")
    op_income = get("영업이익")
    net_income = get("당기순이익")
    equity = get("자본총계")
    liabilities = get("부채총계")
    op_cash = get("영업활동")

    roe = (net_income / equity * 100) if equity else 0.0
    op_margin = (op_income / revenue * 100) if revenue else 0.0
    debt_ratio = (liabilities / equity * 100) if equity else 0.0
    fcf = op_cash * 0.8 if op_cash else op_income * 1.2

    return {
        "revenue": revenue / 1e8,
        "operating_income": op_income / 1e8,
        "net_income": net_income / 1e8,
        "op_cash_flow": op_cash / 1e8,
        "roe": round(roe, 2),
        "op_margin": round(op_margin, 2),
        "debt_ratio": round(debt_ratio, 2),
        "fcf": round(fcf / 1e8, 2),
    }
```
