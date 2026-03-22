# Phase 2 — Core Domain Implementation

- **Goal:** DART 재무데이터 수집 → KPI 산출 → DB 적재 파이프라인 구축
- **Status:** ✅ 완료

## Tasks

- [x] `core/dart_api.py` — OpenDART 클라이언트 (CFS 강제, ADR-005) (Skill: dart-api-client, Agent: Engineer)
- [x] `core/processor.py` — DART JSON → DataFrame → KPI 산출 (Skill: financial-metrics-calc, Agent: Engineer)
- [x] `core/metrics.py` — 핵심 지표 계산 보조 모듈 (Skill: financial-metrics-calc, Agent: Engineer)
- [x] `etl/batch_job.py` — 대상 종목 3개년 재무데이터 배치 ETL (Skill: dart-api-client, financial-metrics-calc, Agent: Engineer)
- [x] `etl/daily_screener_batch.py` — 전 종목 스크리너 데이터 일배치 (Skill: sector-weighted-average, data-fallback-cascade, Agent: Engineer)

## Required Skills

- dart-api-client
- financial-metrics-calc
- sector-weighted-average
- data-fallback-cascade

## Deliverables

- `financial_reports` 테이블: 주요 종목 2022~2024 3개년 재무 KPI 적재
- `screener_summary` 테이블: 전 종목 20+ 컬럼 (PER, PBR, CAGR, 섹터 중앙값 등) 적재
- `test_code.py`: 섹터 평균 검증 CLI 도구

## Definition of Done

- [x] `financial_reports` 테이블에 최소 10개 종목 × 3개년 데이터 확인
- [x] `screener_summary` 테이블에 500개 이상 종목 데이터 확인
- [x] `roe`, `op_margin`, `debt_ratio` 값이 0이 아닌 정상 범위인지 샘플 5개 검증
- [x] 섹터 가중평균 PER이 단순 평균 대비 합리적 값인지 `test_code.py`로 확인
- [x] FCF 폴백 로직 (op_cash_flow=0 시 영업이익×1.2) 동작 확인
- [x] PR 요약 작성
