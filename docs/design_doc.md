# Design Document — Finview
> Single source of truth. No code in this document.
> Last updated: 2026-03-21

---

## Problem Statement

국내 개인 투자자들은 재무제표 원본 데이터에서 KPI까지의 계산 과정이 불투명한 증권 앱에 의존하고 있다.
Finview는 DART 공시 원본 → 지표 산출 → 시각화 전 과정의 **완전한 추적 가능성(traceability)** 을 보장하는 금융 분석 플랫폼이다.

**목표:**
- 왜곡 없는 재무 KPI 제공 (DART 연결재무제표 기준 강제)
- 동종업계 대비 상대 가치 평가 (섹터 가중평균 방법론)
- 다요소 종목 스크리닝 (절대값 + 상대값 복합 필터)
- 투자 심리 지표 (기관/외국인/개인 수급 + 공매도)

---

## System Architecture

### Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                        External Data Sources                  │
│  [OpenDART API]  [KRX (pykrx)]  [FinanceDataReader]         │
└───────┬──────────────┬─────────────────┬─────────────────────┘
        │              │                 │
        ▼              ▼                 ▼
┌──────────────────────────────────────────────────────────────┐
│                        ETL Layer (Python)                     │
│                                                              │
│  quarterly_dart_batch.py ──→ screener_quality  (분기 1회)   │
│  daily_market_batch.py   ──→ screener_summary  (매일)        │
│  (finance.db의 data_registry에 수집 이력 기록)              │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    Backend API (FastAPI)                      │
│                                                              │
│  GET  /api/finance/{query}          ← DART 실시간 → screener_quality 폴백  │
│  GET  /api/market/{query}           ← KRX 실시간 → screener_summary 폴백  │
│  GET  /api/sentiment/{query}        ← KRX 실시간 수급 + 공매도             │
│  GET  /api/quarterly/{query}/{year} ← DART 분기별 재무 (H1/Q3/Q4/Annual)  │
│  POST /api/screener                 ← 다요소 종목 스크리닝                 │
│  GET  /api/batch/quarterly/run      ← 분기배치 SSE 스트리밍 실행           │
│                                                              │
│  모든 엔드포인트: meta.sources 통일 응답 구조 반환           │
└───────────────────────────┬──────────────────────────────────┘
                            │  HTTP (CORS enabled)
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                     Frontend (Vanilla JS)                     │
│                                                              │
│  index.html ──→ dashboard.html  (단일 종목 분석)            │
│             └→ screener.html    (다요소 스크리닝)           │
│                                                              │
│  script.js  — Plotly.js 기반 차트 / 수급 시각화            │
│             — meta.sources 기반 섹션별 데이터 상태 배지     │
│  style.css  — 다크 테마 반응형 UI                           │
└──────────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────┐
│  GitHub Actions   │
│  분기: quarterly  │
│  매일: 18:00 KST  │
│  ETL Auto-run     │
└──────────────────┘
```

### Template Used

**Fullstack (BFF Pattern)** — `docs/templates/fullstack-bff.md` 참조

---

## Component Breakdown

| Component | Responsibility | Agent | Skills |
|-----------|---------------|-------|--------|
| `etl/quarterly_dart_batch.py` | DART 전 종목 재무데이터 분기 수집 → screener_quality 저장 + data_registry 기록 | Engineer | dart-api-client, financial-metrics-calc |
| `etl/daily_market_batch.py` | KRX 시장 데이터 일 수집 → screener_summary 재생성 + data_registry 기록 | Engineer | sector-weighted-average |
| `core/dart_api.py` | OpenDART API 클라이언트 (단일/벌크/분기) | Engineer | dart-api-client |
| `core/processor.py` | DART JSON → DataFrame → KPI 산출 | Engineer | financial-metrics-calc |
| `core/quarterly_processor.py` | 3종 보고서(연간/H1/3분기누적)로 분기별 독립 수치 계산 | Engineer | financial-metrics-calc |
| `core/models.py` | FinancialReport ORM (deprecated, 미사용) | Architect | — |
| `core/master_models.py` | CompanyMaster ORM 모델 | Architect | — |
| `backend/main.py` | FastAPI 라우터 + 스마트 캐싱 + 3단계 폴백 + data_registry upsert | Engineer | smart-caching, data-fallback-cascade, multi-factor-screener |
| `frontend/dashboard.html` | 단일 종목 대시보드 UI + 데이터 소스 상태 바 | Engineer | — |
| `frontend/screener.html` | 스크리너 필터 UI | Engineer | — |
| `frontend/script.js` | API 오케스트레이션 + Plotly 차트 + meta.sources 배지 렌더링 | Engineer | — |
| `frontend/style.css` | 다크 테마 컴포넌트 스타일링 | Engineer | — |

---

## Data Model

### Database 1: `data/finance.db`

#### Table: `screener_quality` ← 분기배치 산출물 (Primary)
| Column | Type | Description |
|--------|------|-------------|
| stock_code | VARCHAR(6) | 종목코드 |
| corp_name | VARCHAR(100) | 기업명 |
| revenue | FLOAT | 2024 매출액 (원) |
| rev_cagr_3y | FLOAT | 매출 3년 CAGR (%) 2021→2024 |
| op_cagr_3y | FLOAT | 영업이익 3년 CAGR (%) |
| eps_cagr_3y | FLOAT | 순이익 3년 CAGR (%) |
| ocf_pass | INTEGER | 3개년 연속 OCF 흑자 여부 (0/1) |
| debt_ratio | FLOAT | 2024 부채비율 (%) |
| dart_roe | FLOAT | 2024 ROE (%) |
| fcf | FLOAT | 2024 FCF (억원) |

#### Table: `screener_summary` ← 일배치 산출물 (Primary)
| Column | Type | Description |
|--------|------|-------------|
| stock_code | VARCHAR(6) | 종목코드 |
| corp_name | VARCHAR(100) | 기업명 |
| sector_name | VARCHAR(50) | 업종명 |
| PER | FLOAT | 주가수익비율 |
| PBR | FLOAT | 주가순자산비율 |
| PSR | FLOAT | 주가매출비율 |
| ROE | FLOAT | 자기자본이익률 (%) |
| EPS | FLOAT | 주당순이익 |
| DIV | FLOAT | 배당수익률 |
| 시가총액 | FLOAT | 시가총액 (원) |
| 순매수거래대금 | FLOAT | 1개월 기관 순매수 거래대금 |
| market_roe | FLOAT | 시장 PBR/PER 역산 ROE |
| dart_roe | FLOAT | DART 기반 ROE |
| sector_per | FLOAT | 섹터 시총 가중평균 PER |
| sector_pbr | FLOAT | 섹터 시총 가중평균 PBR |
| sector_psr | FLOAT | 섹터 시총 가중평균 PSR |
| sector_roe | FLOAT | 섹터 시총 가중평균 ROE |
| sector_rev_cagr | FLOAT | 섹터 중앙값 매출 CAGR |
| rev_cagr_3y | FLOAT | 3년 매출 CAGR (%) |
| op_cagr_3y | FLOAT | 3년 영업이익 CAGR (%) |
| eps_cagr_3y | FLOAT | 3년 순이익 CAGR (%) |
| ocf_pass | INTEGER | 3개년 연속 OCF 흑자 여부 |
| debt_ratio | FLOAT | 부채비율 (%) |
| fcf | FLOAT | FCF (억원) |
| is_complete | INTEGER | PER+PBR+revenue 모두 존재 여부 |

#### Table: `data_registry` ← API/배치 수집 이력 (신규)
| Column | Type | Description |
|--------|------|-------------|
| stock_code | TEXT PK | 종목코드 |
| data_type | TEXT PK | 'finance' / 'market' / 'sentiment' / 'quarterly' |
| last_success | TEXT | 마지막 성공 일시 (실패 시 보존) |
| status | TEXT | 'ok' / 'partial' / 'missing' |
| note | TEXT | 실패 사유 (예: "공매도 데이터 미제공 종목") |

#### Table: `api_cache`
| Column | Type | Description |
|--------|------|-------------|
| cache_type | TEXT | 캐시 유형 (finance_v2, sentiment_v3, quarterly_YYYY 등) |
| ticker | VARCHAR(6) | 종목코드 |
| cache_date | DATE | 캐시 날짜 (당일 유효) |
| data | TEXT | JSON 직렬화 데이터 |

#### Table: `financial_reports` ← **DEPRECATED** (미사용)
> `/api/finance`가 screener_quality + DART API 실시간으로 전환됨. 테이블은 남아있으나 어떤 배치/API도 읽지 않음.

---

### Database 2: `data/고유번호.db`

#### Table: `company_master`
| Column | Type | Description |
|--------|------|-------------|
| corp_code | VARCHAR(8) PK | DART 고유번호 |
| corp_name | VARCHAR(100) | 기업명 |
| stock_code | VARCHAR(6) | 종목코드 |

---

## API / Interface Design

### Backend (FastAPI, Port 8000)

#### `GET /api/finance/{query}`
- **Input:** 기업명 또는 종목코드 (fuzzy match 지원)
- **폴백 체인:** DART API 실시간(4년치) → screener_quality 역산 → missing
- **캐시:** `api_cache.finance_v2` (당일 유효)
- **Output:**
```json
{
  "corp_name": "삼성전자",
  "data": [
    { "year": 2021, "revenue": 279605, "operating_income": 51634,
      "net_income": 39907, "op_cash_flow": 65032,
      "roe": 9.98, "op_margin": 18.45, "debt_ratio": 39.2, "fcf": 52025 }
  ],
  "meta": {
    "sources": {
      "finance": { "status": "ok", "from": "dart_realtime" }
    }
  }
}
```
- `from` 가능값: `dart_realtime` / `screener_quality` / `none`
- `status` 가능값: `ok` / `partial` (screener_quality 역산, 상세 없음) / `missing`

#### `GET /api/market/{query}`
- **Input:** 종목명 또는 종목코드
- **폴백 체인:** KRX 실시간 → screener_summary DB
- **Output:**
```json
{
  "date": "2026-03-21",
  "data": {
    "PER": 12.5, "PBR": 1.2, "EPS": 3500, "DIV": 2.1,
    "target_price": 85000, "upside": 12.3, "current_price": 75700
  },
  "meta": {
    "present": true, "fallback": false,
    "sources": {
      "market": { "status": "ok", "from": "realtime" }
    }
  }
}
```
- `from` 가능값: `realtime` / `cache`

#### `GET /api/sentiment/{query}`
- **Input:** 종목명 또는 종목코드
- **날짜 처리:** 주말이면 직전 금요일(마지막 거래일) 자동 롤백
- **캐시:** `api_cache.sentiment_v3` (당일 유효)
- **Output:**
```json
{
  "data": [
    { "date": "2026-03-20", "retail_buy": -50000,
      "foreigner_buy": 120000, "inst_buy": 80000,
      "short_vol": 500000, "short_ratio": 3.2 }
  ],
  "meta": {
    "count": 60,
    "sources": {
      "sentiment": { "status": "ok", "from": "realtime", "note": "" }
    }
  }
}
```
- `status`: `ok` (수급+공매도) / `partial` (수급만, 공매도 없음) / `missing`

#### `GET /api/quarterly/{query}/{year}`
- **Input:** 종목명 또는 종목코드, 연도 (예: 2024)
- **처리:** DART 3종 보고서(11011/11012/11013) → H1/Q3/Q4/Annual 분기별 역산
- **캐시:** `api_cache.quarterly_{year}` (당일 유효)
- **Output:**
```json
{
  "corp_name": "삼성전자", "year": 2024,
  "quarters": {
    "h1":     { "revenue": 150000, "op_income": 14000, "net_income": 11000, "ocf": 22000 },
    "q3":     { "revenue":  80000, "op_income":  9000, "net_income":  7000, "ocf": 12000 },
    "q4":     { "revenue":  90000, "op_income": 10000, "net_income":  8000, "ocf": 14000 },
    "annual": { "revenue": 320000, "op_income": 33000, "net_income": 26000, "ocf": 48000 }
  }
}
```

#### `POST /api/screener`
- **Input (필터 파라미터 14종):**
```json
{
  "min_roe": 10, "max_per": 15, "max_pbr": 2,
  "min_market_cap": 100000000000,
  "inst_buy_flag": true,
  "min_rev_cagr": 10, "min_op_cagr": 5,
  "max_debt_ratio": 100, "ocf_pass_flag": true,
  "max_peg": 1,
  "relative_per_discount": 20, "relative_pbr_discount": null,
  "relative_roe_excess": true, "relative_growth_excess": false
}
```
- **Output:** `{ "count": N, "data": [...] }`
- **소스:** `screener_summary` 테이블 직접 SQL 쿼리

#### `GET /api/batch/quarterly/run` (SSE)
- 분기배치(`quarterly_dart_batch.py`)를 서버에서 실행하며 진행상황을 SSE로 스트리밍
- 프론트엔드: `EventSource('/api/batch/quarterly/run')`

### 통일 응답 구조: `meta.sources`

모든 API가 동일한 형식으로 데이터 가용성을 반환:
```json
{
  "meta": {
    "sources": {
      "<type>": { "status": "ok|partial|missing", "from": "<source>", "note": "..." }
    }
  }
}
```
프론트엔드는 `meta.sources`를 읽어 섹션별 상태 배지(`badge-finance`, `badge-market`, `badge-sentiment`)를 렌더링한다.

### Frontend

| 페이지 | 파일 | 역할 |
|--------|------|------|
| 랜딩 | `frontend/index.html` | 검색 진입 + 스크리너 진입 |
| 대시보드 | `frontend/dashboard.html` | 단일 종목 상세 분석 (4탭 + 분기 탭) + 데이터 소스 배지 |
| 스크리너 | `frontend/screener.html` | 다요소 필터 + 결과 테이블 (페이지네이션) |

---

## Tech Stack

| 영역 | 기술 | 버전/비고 |
|------|------|----------|
| Backend Framework | FastAPI | Async, SSE 스트리밍 지원 |
| ORM | SQLAlchemy | 마스터 DB 조회용 (CompanyMaster) |
| Database | SQLite | 파일 기반 (2개 DB: finance.db / 고유번호.db) |
| Data Processing | pandas, numpy | ETL 파이프라인 |
| Data Sources | pykrx, FinanceDataReader, OpenDART | 한국 주식시장 전용 |
| Frontend | HTML5 + CSS3 + Vanilla JS | 프레임워크 없음 |
| Charts | Plotly.js | 인터랙티브 금융 차트 |
| Automation | GitHub Actions | 분기 / 매일 18:00 KST |
| Environment | python-dotenv | API 키 관리 |

---

## Risk Analysis

| 위험 | 가능성 | 영향 | 완화 방안 |
|------|--------|------|----------|
| KRX API 응답 불안정 | 높음 | 중간 | smart-caching + screener_summary 폴백 (ADR-003) |
| DART API 할당량 초과 | 중간 | 높음 | 당일 캐시(finance_v2) + 분기배치 벌크 API |
| KRX 컬럼명 변경 | 중간 | 높음 | 컬럼 다형성 방어 로직 (main.py, script.js) |
| 연결재무제표 누락 | 낮음 | 높음 | CFS 강제 → OFS 폴백 (ADR-005) |
| SQLite 동시성 충돌 | 낮음 | 중간 | ETL/API 배타적 접근 (GitHub Actions 스케줄) |
| 섹터 데이터 편향 | 중간 | 중간 | 시가총액 가중평균 방법론 (ADR-004) |
| 주말 KRX 데이터 없음 | 높음 | 낮음 | sentiment endpoint 직전 금요일 자동 롤백 |

---

## ADR Log

| ADR | 결정 | 근거 |
|-----|------|------|
| ADR-001 | SQLite 이중 DB 구조 채택 | `docs/adr/ADR-001-sqlite-dual-db.md` |
| ADR-002 | Vanilla JS (프레임워크 미사용) | `docs/adr/ADR-002-vanilla-js.md` |
| ADR-003 | 3단계 데이터 폴백 캐스케이드 | `docs/adr/ADR-003-data-fallback.md` |
| ADR-004 | 섹터 시가총액 가중평균 방법론 | `docs/adr/ADR-004-sector-weighted-avg.md` |
| ADR-005 | DART 연결재무제표(CFS) 강제 | `docs/adr/ADR-005-cfs-enforcement.md` |
| ADR-006 | financial_reports 폐기 — screener_quality + DART 실시간 통합 | 192개 종목 한계 → 2500개 커버. 배치 의존 제거 |
| ADR-007 | meta.sources 통일 응답 구조 도입 | 데이터 가용성을 API 응답에 포함 → 프론트 배지 렌더링 가능 |

---

## Implementation Phases

### Phase 1 — Project Setup ✅
- **Goal:** 개발 환경 구성 및 데이터 파이프라인 기반 확립
- **DoD:**
  - [x] 두 DB 정상 생성 확인
  - [x] 마스터 DB에 상장 종목 로드 완료
  - [x] GitHub Actions YAML 유효성 검증

### Phase 2 — Core Domain Implementation ✅
- **Goal:** DART 재무데이터 수집 → KPI 산출 파이프라인 구축
- **주요 변경:** `batch_job.py` → 삭제됨. `quarterly_dart_batch.py`로 대체.
- **DoD:**
  - [x] screener_quality 테이블 2500개 종목 적재
  - [x] screener_summary 24개 컬럼 정상 산출
  - [x] 섹터 가중평균 계산 검증

### Phase 3 — Integration & API Layer ✅
- **Goal:** FastAPI 백엔드 구축 및 프론트엔드 연결
- **주요 변경:** `/api/finance` 소스 교체, `meta.sources` 통일, `data_registry` 도입, 분기 탭 추가
- **DoD:**
  - [x] 6개 API 엔드포인트 정상 응답
  - [x] Plotly 차트 5탭 렌더링 확인 (growth/profit/stability/cashflow/분기)
  - [x] 스크리너 14개 필터 동작 확인
  - [x] meta.sources 배지 렌더링 확인
  - [x] 주말 수급 데이터 직전 금요일 롤백 확인

### Phase 4 — Testing & Validation ← **현재 단계**
- **Goal:** 데이터 품질 검증 및 엣지케이스 처리
- **Tasks:**
  - [ ] 소형주 검색 → screener_quality 폴백 재무 차트 표시 확인
  - [ ] 공매도 미제공 종목 → `partial` 배지 표시 확인
  - [ ] data_registry 배치 실행 후 status 업데이트 확인
  - [ ] 스크리너 필터 조합 경계값 테스트 (상한/하한/복합)
  - [ ] KRX 컬럼 변경 시 graceful degradation 확인
  - [ ] DART API 키 없을 때 screener_quality 폴백 동작 확인
  - [ ] 분기 탭 데이터 정합성 검증 (H1+Q3+Q4 = Annual)
- **DoD:**
  - [ ] 주요 폴백 시나리오 3종 (DART 없음 / KRX 없음 / 둘 다 없음) 모두 graceful
  - [ ] data_registry에 status 기록 확인
  - [ ] 스크리너 주요 필터 20개 조합 정상 동작

### Phase 5 — Deployment & Observability
- **Goal:** 운영 안정화 및 모니터링 체계 구축
- **Tasks:**
  - [ ] GitHub Actions 배치 성공/실패 알림 설정
  - [ ] DB 증분 백업 전략 수립
  - [ ] API 응답시간 로깅 추가
  - [ ] DART API 할당량 추적 로직
  - [ ] data_registry 기반 대시보드 수집 현황 페이지
- **DoD:**
  - [ ] 7일 연속 배치 성공 확인
  - [ ] API 평균 응답시간 < 2s (캐시 히트 기준)
  - [ ] data_registry coverage > 90% (finance + market)
