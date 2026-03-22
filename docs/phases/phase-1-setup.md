# Phase 1 — Project Setup

- **Goal:** 개발 환경 구성 및 데이터 파이프라인 기반 확립
- **Status:** ✅ 완료

## Tasks

- [x] Python 의존성 설치 `requirements.txt` (Agent: Engineer)
- [x] `.env` 환경변수 설정 (`DART_API_KEY`) (Agent: Engineer)
- [x] `core/models.py` — FinancialReport ORM 선언 (Skill: -, Agent: Architect)
- [x] `core/master_models.py` — CompanyMaster ORM 선언 (Skill: -, Agent: Architect)
- [x] `etl/init_master.py` — DART 종목 마스터 초기화 (Skill: dart-api-client, Agent: Engineer)
- [x] `data/` 디렉토리 생성 및 두 SQLite DB 초기화 (Agent: Engineer)
- [x] `.github/workflows/etl.yml` — GitHub Actions 배치 스케줄 설정 (Agent: Engineer)

## Required Skills

- dart-api-client

## Deliverables

- `data/고유번호.db` — 상장 종목 마스터 데이터 로드 완료
- `data/finance.db` — 빈 스키마 생성 완료
- `.github/workflows/etl.yml` — 매일 18:00 KST 배치 스케줄 등록

## Definition of Done

- [x] `고유번호.db`에 KOSPI+KOSDAQ 상장 종목 corp_code ↔ stock_code 매핑 완료
- [x] `finance.db`에 `financial_reports`, `screener_summary`, `api_cache` 테이블 스키마 생성
- [x] GitHub Actions YAML syntax 유효성 확인 (`act` 또는 push 테스트)
- [x] DART API 키 정상 동작 확인 (1개 종목 테스트 조회)
- [x] PR 요약 작성: What(환경 구성) / Why(데이터 파이프라인 기반) / Risk(API 키 노출 방지) / Next(Phase 2 ETL)
