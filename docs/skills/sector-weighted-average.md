# Skill: sector-weighted-average

- **Purpose:** 시가총액 가중 방식으로 섹터 대표 지표(PER, PBR, PSR, ROE)를 산출한다. 단순 평균 대비 대형주 편향을 반영한 경제적으로 의미있는 벤치마크를 생성한다.
- **Inputs:** 섹터별 `(PER, PBR, EPS, 시가총액)` 종목 리스트
- **Outputs:** 섹터별 `{weighted_per, weighted_pbr, weighted_psr, weighted_roe, median_per, ...}`

## Best Practices

- **역산(Reverse-Engineering) 방법론:** PER/PBR/EPS/시총에서 순이익·자기자본 역산 후 합산
  - `net_income_implied = 시가총액 / PER`
  - `equity_implied = 시가총액 / PBR`
  - `revenue_implied = 시총 / PSR` (PSR 있을 경우)
  - `sector_per = sum(시가총액) / sum(net_income_implied)` — 시총 가중 PER
- **중앙값(Median)도 함께 제공** — 이상치 종목에 강인한 벤치마크
- 시총 0 또는 PER 음수 종목은 역산에서 제외 (분모 0 방지)
- FinanceDataReader로 섹터 분류 매핑 (`fdr.StockListing("KRX-DESC")`)

## Anti-patterns

- ❌ 단순 산술 평균 PER — 소형주·이상치 종목에 왜곡됨
- ❌ PER 음수 종목 포함 — 역산 시 분모 부호 반전으로 오류
- ❌ 섹터 내 종목 수 < 3인 섹터에 가중평균 적용 — 대표성 없음

## Example

```python
# etl/daily_screener_batch.py 내 섹터 가중평균 로직
import pandas as pd

def calc_sector_weighted_avg(sector_df: pd.DataFrame) -> dict:
    df = sector_df.copy()
    df = df[(df["PER"] > 0) & (df["시가총액"] > 0)].copy()

    # 역산
    df["net_income_implied"] = df["시가총액"] / df["PER"]
    df["equity_implied"] = df["시가총액"] / df["PBR"].replace(0, float("nan"))

    total_mktcap = df["시가총액"].sum()
    total_net_income = df["net_income_implied"].sum()
    total_equity = df["equity_implied"].sum()

    weighted_per = total_mktcap / total_net_income if total_net_income else None
    weighted_pbr = total_mktcap / total_equity if total_equity else None
    weighted_roe = (total_net_income / total_equity * 100) if total_equity else None

    return {
        "weighted_per": round(weighted_per, 2) if weighted_per else None,
        "weighted_pbr": round(weighted_pbr, 2) if weighted_pbr else None,
        "weighted_roe": round(weighted_roe, 2) if weighted_roe else None,
        "median_per": df["PER"].median(),
        "median_pbr": df["PBR"].median(),
        "median_roe": df["ROE"].median() if "ROE" in df.columns else None,
    }
```

## Reusable across

- 주식 스크리닝 시스템
- 포트폴리오 벤치마킹 도구
- 섹터 로테이션 분석 시스템
