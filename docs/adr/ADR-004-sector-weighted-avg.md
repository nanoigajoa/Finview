# ADR-004: 섹터 시가총액 가중평균 방법론 채택

- **날짜:** 2026-03-20
- **상태:** 승인됨

## 결정

섹터 대표 PER/PBR/ROE 계산 시 단순 평균 대신 **시가총액 가중평균 + 역산 방법론**을 사용한다.

## 배경

- 단순 산술 평균 PER은 소형 이상치 종목에 크게 왜곡됨 (예: PER 1000배 적자기업 포함 시)
- 네이버증권·토스증권 등 주요 플랫폼이 가중평균 PER을 업종 대표값으로 사용
- 적정가 산출(`target_price = EPS × 섹터PER`)의 신뢰성이 벤치마크 품질에 직결

## 선택된 방안

**역산(Reverse-Engineering) 가중평균:**
```
net_income_implied = 시가총액 / PER
sector_weighted_per = Σ(시가총액) / Σ(net_income_implied)
```

이 방식은 시총이 큰 기업의 수익성이 섹터 PER에 더 많이 반영됨.
PER 음수(적자) 종목은 역산 과정에서 제외.
Median PER도 병행 제공 — 이상치에 강인한 보조 지표.

## 대안과 기각 이유

| 대안 | 기각 이유 |
|------|----------|
| 단순 산술 평균 | 이상치 왜곡, 경제적 의미 부족 |
| 중앙값만 사용 | 대형주 효과 무시 |
| FnGuide/Wisefn 데이터 | 유료 서비스, 접근 불가 |

## 결과

- `daily_screener_batch.py`에서 섹터별 가중평균 산출 후 `screener_summary`에 저장
- 스크리너에서 `relative_per_discount` 필터가 이 값을 기준으로 작동
- 적정가 계산: `target_price = EPS × sector_weighted_per`
- `test_code.py`로 섹터 평균 대비 개별 종목 위치 검증 가능
