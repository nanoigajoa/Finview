# Phase 3 — Integration & API Layer

- **Goal:** FastAPI 백엔드 4개 엔드포인트 구축 및 프론트엔드 연결 완료
- **Status:** ✅ 완료

## Tasks

- [x] `backend/main.py` — FastAPI 앱 + CORS 설정 (Agent: Engineer)
- [x] `GET /api/finance/{query}` — 재무제표 + KPI 반환 (Skill: smart-caching, data-fallback-cascade, Agent: Engineer)
- [x] `GET /api/market/{query}` — 시장 지표 + 적정가 계산 (Skill: smart-caching, data-fallback-cascade, sector-weighted-average, Agent: Engineer)
- [x] `GET /api/sentiment/{query}` — 수급 + 공매도 60일 데이터 (Skill: smart-caching, data-fallback-cascade, Agent: Engineer)
- [x] `POST /api/screener` — 다요소 스크리닝 엔드포인트 (Skill: multi-factor-screener, Agent: Engineer)
- [x] `frontend/index.html` — 랜딩 + 검색 진입 (Agent: Engineer)
- [x] `frontend/dashboard.html` — 4탭 단일 종목 대시보드 (Agent: Engineer)
- [x] `frontend/screener.html` — 14개 필터 스크리너 UI (Agent: Engineer)
- [x] `frontend/script.js` — API 병렬 호출 + Plotly 차트 + 수급 시각화 (Agent: Engineer)
- [x] `frontend/style.css` — 다크 테마 반응형 컴포넌트 (Agent: Engineer)

## Required Skills

- smart-caching
- data-fallback-cascade
- multi-factor-screener
- sector-weighted-average

## Deliverables

- FastAPI 서버 (port 8000) — 4개 엔드포인트 정상 응답
- 단일 종목 대시보드: 성장/수익성/안정성/현금흐름 4탭 + 수급 섹션
- 스크리너: 14개 필터 + 페이지네이션 + 섹터 대비 미니 바 차트

## Definition of Done

- [x] `GET /api/finance/삼성전자` 응답 200 + 데이터 구조 확인
- [x] `GET /api/market/005930` 응답 200 + target_price 계산값 확인
- [x] `GET /api/sentiment/005930` 응답 200 + 60일 수급 데이터 확인
- [x] `POST /api/screener {"min_roe": 10}` 응답 200 + count > 0 확인
- [x] Plotly 4탭 차트 정상 렌더링 (브라우저 직접 확인)
- [x] `fallback: true` 시 프론트엔드 경고 배너 표시 확인
- [x] PR 요약 작성
