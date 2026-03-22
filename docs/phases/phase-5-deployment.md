# Phase 5 — Deployment & Observability

- **Goal:** 운영 안정화, 배치 자동화 검증, 모니터링 체계 구축
- **Status:** ⬜ 미완료

## Tasks

### 배치 자동화 검증

- [ ] GitHub Actions 7일 연속 정상 실행 확인 (Agent: Engineer)
- [ ] 배치 실패 시 GitHub Issue 자동 생성 또는 이메일 알림 설정 (Agent: Engineer)
- [ ] `daily_screener_batch.py` 실행 시간 측정 및 10분 초과 시 최적화 (Agent: Engineer)

### API 성능 최적화

- [ ] `/api/finance` 응답시간 측정 (목표: 캐시 히트 < 500ms, DART 실시간 < 5s) (Agent: Engineer)
- [ ] `/api/screener` 응답시간 측정 (목표: 필터 조합 < 1s) (Agent: Engineer)
- [ ] `api_cache` 히트율 로깅 추가 (캐시 적중/미적중 카운터) (Agent: Engineer)

### 데이터 관리

- [ ] `finance.db` 증분 백업 전략 수립 (GitHub Actions 자동 커밋 또는 외부 스토리지) (Skill: -, Agent: Architect)
- [ ] `screener_summary` 행 수 모니터링 (500개 미만 시 배치 실패로 간주) (Agent: Engineer)
- [ ] DART API 월별 할당량 잔여량 로깅 추가 (Agent: Engineer)

### 보안

- [ ] `.env` 파일 `.gitignore` 등록 확인 (DART_API_KEY 노출 방지) (Agent: Reviewer)
- [ ] GitHub Actions secrets으로 DART_API_KEY 이전 검토 (Agent: Architect)

## Required Skills

- smart-caching
- data-fallback-cascade

## Deliverables

- GitHub Actions 7일 실행 이력 스크린샷
- API 응답시간 벤치마크 결과
- 캐시 히트율 초기 측정값
- 백업 전략 문서 (ADR 또는 README 갱신)

## Definition of Done

- [ ] GitHub Actions 7일 연속 성공 확인
- [ ] `/api/finance` 캐시 히트 응답시간 < 500ms
- [ ] `/api/screener` 응답시간 < 1s (전체 필터 없는 기본 조회)
- [ ] 캐시 히트율 > 80% (일 기준)
- [ ] DART API 키 GitHub Secret으로 이전 완료
- [ ] `finance.db` 백업 방안 확정
- [ ] PR 요약 작성: What(운영 안정화) / Why(배치 신뢰성) / Risk(DB 잠금 충돌) / Next(기능 확장)
