# Template: Fullstack (BFF Pattern)

> Finview 프로젝트에서 추출한 아키텍처 템플릿.
> Backend-for-Frontend 패턴: 정적 프론트엔드 + 전용 API 서버.

---

## Directory Structure

```
project-root/
├── backend/
│   └── main.py               # FastAPI 앱 + 라우터 + 캐싱
├── core/
│   ├── __init__.py
│   ├── models.py             # SQLAlchemy ORM (팩트 데이터)
│   ├── master_models.py      # SQLAlchemy ORM (마스터 데이터)
│   ├── [domain]_api.py       # 외부 API 클라이언트
│   └── processor.py          # 도메인 데이터 가공 로직
├── etl/
│   ├── __init__.py
│   ├── init_master.py        # 마스터 DB 1회 초기화
│   ├── batch_job.py          # 대상 데이터 배치 수집
│   └── daily_[domain]_batch.py  # 전체 데이터 일배치
├── frontend/
│   ├── index.html            # 진입 페이지
│   ├── [feature].html        # 기능별 페이지
│   ├── script.js             # API 통신 + 렌더링 로직
│   └── style.css             # 다크 테마 컴포넌트
├── data/
│   ├── [fact].db             # 팩트 SQLite DB
│   └── [master].db           # 마스터 SQLite DB
├── config/
│   └── .env                  # API 키 등 민감 설정
├── docs/                     # 이 템플릿의 산출물 위치
│   ├── design_doc.md
│   ├── skills/
│   ├── templates/
│   ├── adr/
│   └── phases/
├── .github/
│   └── workflows/
│       └── etl.yml           # GitHub Actions 일배치
└── requirements.txt
```

---

## Layer Responsibilities

| 레이어 | 파일 위치 | 책임 |
|--------|----------|------|
| **ETL** | `etl/` | 외부 데이터 수집 → DB 적재 (스케줄 배치) |
| **Core Domain** | `core/` | 외부 API 클라이언트, ORM 모델, 데이터 가공 |
| **Backend API** | `backend/` | REST 엔드포인트, 캐싱, 비즈니스 로직 |
| **Frontend** | `frontend/` | UI 렌더링, API 통신, 차트 시각화 |
| **Data** | `data/` | SQLite 이중 DB (팩트/마스터 분리) |
| **Automation** | `.github/workflows/` | 배치 자동화 (GitHub Actions) |

---

## Coding Conventions

- **Python:**
  - SQLAlchemy 선언적 모델 (`DeclarativeBase`)
  - 환경변수는 `python-dotenv` + `config/.env` 전용
  - ETL 함수는 멱등성(idempotent) 보장 — 중복 실행 시 무해
  - 외부 API 호출은 `core/[domain]_api.py` 에 격리
  - 데이터 가공 로직은 `core/processor.py` 에 집중
  - 폴백 로직은 항상 3단계 (실시간 → 캐시 → 추정)

- **JavaScript (Frontend):**
  - 프레임워크 없음 — Vanilla JS
  - API 호출은 `fetch()` + `Promise.all()` (병렬 처리)
  - 차트는 Plotly.js (금융 데이터 최적화)
  - 컬럼 다형성 방어: `col = data[key1] ?? data[key2] ?? null`
  - 타임아웃 처리: `Promise.race([fetch(), timeout(5000)])`

- **Database:**
  - 마스터 DB와 팩트 DB 물리적 분리
  - 캐시 테이블은 팩트 DB에 통합 (`api_cache`)
  - 날짜 기반 캐시 유효성 검증

---

## Branch Strategy

```
feature/* → dev → main
```

- `feature/` : 단일 기능 또는 단일 Phase 작업
- `dev` : 통합 테스트 환경
- `main` : 배포 기준 브랜치 (GitHub Actions 트리거)
- PR 요약 포함 필수: What changed / Why / Risk / Next phase dependency

---

## Required Skills

- `dart-api-client` — 외부 금융 API 클라이언트 패턴
- `smart-caching` — 날짜 기반 DB 캐싱 전략
- `data-fallback-cascade` — 3단계 데이터 가용성 보장
- `financial-metrics-calc` — 재무 KPI 산출 로직
- `sector-weighted-average` — 시가총액 가중 섹터 평균
- `multi-factor-screener` — 복합 필터 SQL 빌더

---

## Agent Map

| 레이어 | 담당 Agent |
|--------|-----------|
| 시스템 설계, DB 스키마, ADR | Architect |
| ETL + Core Domain + Backend API 구현 | Engineer |
| 코드 품질, 패턴 준수, DoD 검증 | Reviewer |
| 필터 조합 테스트, 엣지케이스 정의 | QA |
