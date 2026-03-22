# Phase 4 — Testing & Validation

- **Goal:** 데이터 품질 검증, 엣지케이스 처리, 폴백 시나리오 완결성 확보
- **Status:** ⬜ 미완료

## Tasks

### 데이터 품질 검증

- [ ] 섹터 가중평균 PER vs 단순 평균 PER 오차율 분석 (5개 섹터 샘플) (Skill: sector-weighted-average, Agent: QA)
- [ ] FCF 추정값 (`영업이익×1.2`) vs 실제 DART 현금흐름 오차율 검증 (10개 종목) (Skill: financial-metrics-calc, Agent: QA)
- [ ] ROE/op_margin 극단값 종목 샘플링 (상위 5개, 하위 5개) 이상치 확인 (Agent: QA)

### 폴백 시나리오 테스트

- [ ] KRX API 비정상 응답 시뮬레이션 → Stage 2 (캐시) 자동 전환 확인 (Skill: data-fallback-cascade, Agent: QA)
- [ ] `api_cache` 테이블 비어있을 때 Stage 3 (추정) 진입 확인 (Agent: QA)
- [ ] `fallback: true` 시 프론트엔드 경고 배너 노출 확인 (Agent: QA)

### 컬럼 다형성 테스트

- [ ] KRX API 컬럼명 변형 시나리오 3종 테스트 (한글/영문 컬럼 혼용) (Agent: QA)
- [ ] `script.js` 컬럼 폴리모피즘 방어 로직 동작 확인 (Agent: QA)

### 스크리너 필터 조합 테스트

- [ ] 단일 필터 14개 각각 독립 동작 확인 (Agent: QA)
- [ ] `min_roe + max_per + relative_per_discount` 3중 조합 테스트 (Agent: QA)
- [ ] `max_peg` 필터 시 `rev_cagr_3y ≤ 0` 종목 제외 확인 (Agent: QA)
- [ ] 빈 결과 반환 시 프론트엔드 "결과 없음" 메시지 확인 (Agent: QA)
- [ ] 모든 필터 동시 적용 시 쿼리 오류 없음 확인 (Agent: QA)

## Required Skills

- financial-metrics-calc
- data-fallback-cascade
- sector-weighted-average
- multi-factor-screener

## Deliverables

- 테스트 결과 요약 (통과/실패 항목)
- 발견된 버그 목록 + 수정 완료 확인
- 데이터 품질 리포트 (FCF 추정 오차율, 섹터 평균 정확도)

## Definition of Done

- [ ] 스크리너 단일 필터 14개 전부 정상 동작 확인
- [ ] 폴백 3단계 시나리오 전부 통과
- [ ] 컬럼 다형성 3종 시나리오 통과
- [ ] FCF 추정 오차율 < 30% (10개 종목 평균 기준)
- [ ] 섹터 가중평균 PER이 KRX/나이스 공개 데이터 대비 ±10% 이내
- [ ] PR 요약 작성
