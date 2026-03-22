from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import sessionmaker
import sys
import os
import math
import pandas as pd
from pykrx import stock
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import Optional
import sqlite3
import asyncio
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", ".env"))

# 코어 모듈 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import init_db, FinancialReport
from core.master_models import init_master_db, CompanyMaster
from core.dart_api import DartAPIClient
from core.processor import FinancialDataProcessor

app = FastAPI(title="Investment Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
app.mount("/static", StaticFiles(directory=_frontend_dir), name="static")

@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")

db_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
engine_master = init_master_db(f"sqlite:///{db_dir}/고유번호.db")
SessionMaster = sessionmaker(bind=engine_master)

engine_fact = init_db(f"sqlite:///{db_dir}/finance.db")
SessionFact = sessionmaker(bind=engine_fact)

# 🌟 신규: 유연한 종목코드 탐색기 (삼성SDS -> 삼성에스디에스 연결 및 KOSDAQ 탐색)
def resolve_ticker(query: str) -> str:
    if query.isdigit():
        return query
        
    # 1. 자체 DB 기반 초고속/유연한 탐색 (LIKE 검색 활용)
    db_path = os.path.join(db_dir, "finance.db")
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT stock_code FROM screener_summary WHERE corp_name = ? LIMIT 1", (query,))
            res = cursor.fetchone()
            if res:
                conn.close()
                ticker = str(res[0])
                print(f"[resolve] DB exact match: {query} -> {ticker}")
                return ticker
                
            cursor.execute("SELECT stock_code FROM screener_summary WHERE corp_name LIKE ? LIMIT 1", (f"%{query}%",))
            res = cursor.fetchone()
            if res:
                ticker = str(res[0])
                conn.close()
                print(f"[resolve] DB fuzzy match: {query} -> {ticker}")
                return ticker
            conn.close()
        except Exception as e:
            print(f"[resolve] DB search error: {e}")
            
    # 2. KRX 기본 탐색 (코스피 & 코스닥 모두 융통성 있게 탐색)
    try:
        for mkt in ["KOSPI", "KOSDAQ"]:
            for t in stock.get_market_ticker_list(market=mkt):
                t_name = stock.get_market_ticker_name(t)
                if query.upper() in t_name.upper() or t_name.upper() in query.upper():
                    print(f"[resolve] KRX match ({mkt}): {query} -> {t} ({t_name})")
                    return t
    except Exception as e:
        print(f"[resolve] KRX search error: {e}")
                
    print(f"[resolve] FAILED for query={query}")
    return query

# (이 위쪽의 라이브러리 임포트와 DB 설정, resolve_ticker 함수는 그대로 둡니다.)

import json

# 🌟 0. 스마트 캐시 엔진 (로컬 DB 금고)
def get_cached_data(cache_type: str, ticker: str, ttl_days: int = 1):
    """ttl_days=1: 당일만, ttl_days=7: 7일 이내 캐시 허용 (pykrx 실패 시 폴백용)"""
    cutoff_str = (datetime.today() - timedelta(days=ttl_days - 1)).strftime("%Y-%m-%d")
    db_path = os.path.join(db_dir, "finance.db")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS api_cache
                          (cache_type TEXT, ticker TEXT, cache_date TEXT, data TEXT,
                           PRIMARY KEY(cache_type, ticker))''')
        cursor.execute(
            "SELECT data FROM api_cache WHERE cache_type=? AND ticker=? AND cache_date >= ?",
            (cache_type, ticker, cutoff_str)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
    except Exception as e:
        print(f"Cache Read Error: {e}")
    return None

def save_cached_data(cache_type: str, ticker: str, data: dict):
    today_str = datetime.today().strftime("%Y-%m-%d")
    db_path = os.path.join(db_dir, "finance.db")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''INSERT OR REPLACE INTO api_cache (cache_type, ticker, cache_date, data)
                          VALUES (?, ?, ?, ?)''', (cache_type, ticker, today_str, json.dumps(data)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Cache Write Error: {e}")


def upsert_data_registry(stock_code: str, data_type: str, status: str, note: str = ""):
    """종목별 데이터 수집 이력을 data_registry 테이블에 기록."""
    db_path = os.path.join(db_dir, "finance.db")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS data_registry (
            stock_code TEXT, data_type TEXT, last_success TEXT, status TEXT, note TEXT,
            PRIMARY KEY (stock_code, data_type))''')
        if status == 'ok':
            cursor.execute('''INSERT OR REPLACE INTO data_registry
                (stock_code, data_type, last_success, status, note) VALUES (?, ?, ?, ?, ?)''',
                (stock_code, data_type, now_str, status, note))
        else:
            # 실패 시 last_success는 기존 값 유지
            cursor.execute('''INSERT INTO data_registry (stock_code, data_type, last_success, status, note)
                VALUES (?, ?, NULL, ?, ?)
                ON CONFLICT(stock_code, data_type) DO UPDATE SET status=excluded.status, note=excluded.note''',
                (stock_code, data_type, status, note))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Registry] upsert error: {e}")


# 🟢 첫 번째 방: DART 재무 데이터 (screener_quality + DART API 실시간 통합)
@app.get("/api/finance/{query}")
def get_financial_data(query: str):
    def clean_val(v):
        return 0.0 if v is None or (isinstance(v, float) and math.isnan(v)) else v

    ticker = resolve_ticker(query)

    session_master = SessionMaster()
    master_info = session_master.query(CompanyMaster).filter(
        (CompanyMaster.corp_name == query) | (CompanyMaster.stock_code == query) |
        (CompanyMaster.stock_code == ticker)
    ).first()
    session_master.close()

    corp_name = master_info.corp_name if master_info else query
    corp_code = master_info.corp_code if master_info else None

    if not master_info:
        return {"corp_name": query, "data": [],
                "meta": {"sources": {"finance": {"status": "missing", "from": "none", "note": "기업 마스터 없음"}}}}

    # 1. 당일 캐시 확인
    cached = get_cached_data("finance_v2", ticker)
    if cached:
        print(f"[Finance Cache HIT] {ticker}")
        return cached

    # 2. DART API 실시간 호출 (2021~2024 연간 재무제표)
    dart_data = []
    api_key = os.getenv("DART_API_KEY", "")
    if api_key and corp_code:
        try:
            processor = FinancialDataProcessor()
            for year in ['2021', '2022', '2023', '2024']:
                raw = DartAPIClient(api_key=api_key).get_financial_statement(corp_code, year)
                df = processor.parse_to_dataframe(raw)
                if not df.empty:
                    metrics = processor.extract_metrics(processor.clean_data(df))
                    if metrics.get('revenue', 0) > 0:
                        dart_data.append({
                            "year": int(year),
                            "revenue": clean_val(metrics.get('revenue', 0)),
                            "operating_income": clean_val(metrics.get('operating_income', 0)),
                            "net_income": clean_val(metrics.get('net_income', 0)),
                            "op_cash_flow": clean_val(metrics.get('op_cash_flow', 0)),
                            "roe": clean_val(metrics.get('roe', 0)),
                            "op_margin": clean_val(metrics.get('op_margin', 0)),
                            "debt_ratio": clean_val(metrics.get('debt_ratio', 0)),
                            "fcf": clean_val(metrics.get('fcf', 0)),
                        })
        except Exception as e:
            print(f"[Finance] DART API error for {corp_code}: {e}")

    if dart_data:
        upsert_data_registry(ticker, 'finance', 'ok')
        response = {
            "corp_name": corp_name, "data": dart_data,
            "meta": {"sources": {"finance": {"status": "ok", "from": "dart_realtime"}}}
        }
        save_cached_data("finance_v2", ticker, response)
        return response

    # 3. screener_quality 폴백 (CAGR 역산으로 연도별 근사치 생성)
    db_path = os.path.join(db_dir, "finance.db")
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM screener_quality WHERE stock_code=?", (ticker,))
        sq = cursor.fetchone()
        conn.close()

        if sq and sq['revenue'] and float(sq['revenue']) > 0:
            r24 = float(sq['revenue'])
            rev_cagr = float(sq['rev_cagr_3y'] or 0) / 100.0
            synth = []
            for i, yr in enumerate([2021, 2022, 2023, 2024]):
                factor = (1 + rev_cagr) ** (i - 3) if rev_cagr != 0 else 1.0
                synth.append({
                    "year": yr,
                    "revenue": round(r24 * factor, 2),
                    "operating_income": 0, "net_income": 0, "op_cash_flow": 0,
                    "roe": clean_val(sq['dart_roe']) if yr == 2024 else 0,
                    "op_margin": 0,
                    "debt_ratio": clean_val(sq['debt_ratio']) if yr == 2024 else 0,
                    "fcf": clean_val(sq['fcf']) if yr == 2024 else 0,
                })
            upsert_data_registry(ticker, 'finance', 'partial', 'DART API 없음, screener_quality 집계 사용')
            return {
                "corp_name": corp_name, "data": synth,
                "meta": {"sources": {"finance": {"status": "partial", "from": "screener_quality", "note": "연간 집계만 가능 (연도별 상세 없음)"}}}
            }
    except Exception as e:
        print(f"[Finance] screener_quality fallback error: {e}")

    # 4. 데이터 없음
    upsert_data_registry(ticker, 'finance', 'missing', 'DART API 및 screener_quality 모두 없음')
    return {
        "corp_name": corp_name, "data": [],
        "meta": {"sources": {"finance": {"status": "missing", "from": "none", "note": "데이터 없음"}}}
    }
    
# 🔵 두 번째 방: 하이브리드 폴백 아키텍처 (🌟 1차 실시간 통신 -> 2차 실패 시 자체 DB 무적 로드)
@app.get("/api/market/{query}")
def get_market(query: str):
    try:
        ticker = resolve_ticker(query)
        if not ticker.isdigit(): 
            return {"data": {}, "meta": {"present": False}}

        # 🌟 1단계: 실시간 데이터 시도 (KRX API)
        realtime_success = False
        current_price_realtime = 0.0
        row = None
        target_date_str = ""

        try:
            import time
            time.sleep(0.3) # 안티 봇 딜레이
            end_date = datetime.today()
            for i in range(3):
                d = end_date - timedelta(days=i)
                d_str = d.strftime("%Y%m%d")
                df = stock.get_market_fundamental(d_str, d_str, ticker)
                if not df.empty:
                    row = df.iloc[0]
                    target_date_str = d.strftime("%Y-%m-%d")
                    # P0: 실제 종가 직접 취득 (EPS×PER 역산 오차 제거)
                    df_price = stock.get_market_ohlcv_by_date(d_str, d_str, ticker)
                    if not df_price.empty:
                        current_price_realtime = float(df_price['종가'].iloc[0])
                    realtime_success = True
                    break
        except Exception as e:
            print(f"[Market] Realtime fetch failed, falling back to DB: {e}")

        # 2단계: DB 연결 및 섹터 벤치마크 PER 로드
        db_path = os.path.join(db_dir, "finance.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 적정 주가 계산을 위한 섹터 시총 가중평균 PER + TTM 데이터
        cursor.execute(
            "SELECT sector_per, ttm_eps, ttm_per, ttm_source FROM screener_summary WHERE stock_code=?",
            (ticker,)
        )
        med_res = cursor.fetchone()
        sector_per  = float(med_res['sector_per'])  if med_res and med_res['sector_per']  else 0.0
        ttm_eps_db  = float(med_res['ttm_eps'])     if med_res and med_res['ttm_eps']     else 0.0
        ttm_per_db  = float(med_res['ttm_per'])     if med_res and med_res['ttm_per']     else 0.0
        ttm_source_db = str(med_res['ttm_source'])  if med_res and med_res['ttm_source']  else 'annual_prev'

        # 분기 처리: 실시간 성공 vs DB 폴백
        if realtime_success and row is not None:
            per = float(row.get('PER', 0))
            pbr = float(row.get('PBR', 0))
            eps = float(row.get('EPS', 0))
            div = float(row.get('배당수익률', 0) if '배당수익률' in row else row.get('DIV', 0))
            fallback_flag = False
        else:
            print(f"[Market] Using DB Fallback for {ticker}")
            cursor.execute("SELECT PER, PBR, EPS, DIV FROM screener_summary WHERE stock_code=?", (ticker,))
            db_row = cursor.fetchone()
            if not db_row:
                conn.close()
                return {"data": {}, "meta": {"present": False}}
            per = float(db_row['PER'])
            pbr = float(db_row['PBR'])
            eps = float(db_row['EPS'])
            div = float(db_row['DIV'])
            target_date_str = datetime.today().strftime("%Y-%m-%d")
            fallback_flag = True
            
        conn.close()

        # 3단계: 적정 주가 및 업사이드 계산
        # TTM EPS 우선, 없으면 annual EPS
        effective_eps = ttm_eps_db if ttm_eps_db > 0 else eps
        eps_negative  = eps <= 0
        target_price  = effective_eps * sector_per if sector_per > 0 and effective_eps > 0 else 0.0

        # Graham Number: √(22.5 × EPS × BPS),  BPS = EPS×PER/PBR
        bps    = (eps * per / pbr) if pbr > 0 and per > 0 and eps > 0 else 0.0
        graham = round(math.sqrt(22.5 * abs(effective_eps) * bps), 2) if bps > 0 and effective_eps > 0 else 0.0

        # P0: 실시간 종가 우선, 폴백 시 EPS×PER 역산 (근사)
        if realtime_success and current_price_realtime > 0:
            current_price = current_price_realtime
        else:
            current_price = eps * per if per > 0 else 0.0
        upside = ((target_price - current_price) / current_price) * 100 if current_price > 0 and target_price > 0 else 0.0

        market_status = "partial" if fallback_flag else "ok"
        market_from = "cache" if fallback_flag else "realtime"
        upsert_data_registry(ticker, 'market', market_status)
        return {
            "date": target_date_str,
            "data": {
                "PER": per, "PBR": pbr, "EPS": eps, "DIV": div,
                "ttm_per": ttm_per_db, "ttm_eps": ttm_eps_db, "ttm_source": ttm_source_db,
                "ttm_available": ttm_eps_db > 0,
                "EPS_negative": eps_negative,
                "graham": graham,
                "target_price": target_price, "upside": upside, "current_price": current_price
            },
            "meta": {
                "present": True, "fallback": fallback_flag,
                "sources": {"market": {"status": market_status, "from": market_from}}
            }
        }

    except Exception as e:
        print(f"[Market API Error] {e}")
        return {"data": {}, "meta": {"present": False, "sources": {"market": {"status": "missing", "from": "none"}}}}


# ── Naver Finance 수급 스크래핑 (pykrx 폴백) ─────────────────────────────────
def _fetch_naver_investor_flow(ticker: str, pages: int = 3):
    """Naver Finance frgn.naver 외국인 순매수 스크래핑 (pykrx 실패 시 폴백)"""
    import requests as _req
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Referer': 'https://finance.naver.com',
    }
    frames = []
    for page in range(1, pages + 1):
        url = f"https://finance.naver.com/item/frgn.naver?code={ticker}&page={page}"
        try:
            resp = _req.get(url, headers=headers, timeout=10)
            dfs = pd.read_html(resp.text, header=0)
            for df in dfs:
                if '날짜' in df.columns and len(df) > 3:
                    frames.append(df.dropna(subset=['날짜']))
                    break
        except Exception as e:
            print(f"[Naver] frgn page={page} failed: {e}")
            break

    if not frames:
        return None

    combined = pd.concat(frames, ignore_index=True).dropna(subset=['날짜'])
    try:
        combined['날짜'] = pd.to_datetime(combined['날짜']).dt.strftime('%Y-%m-%d')
    except Exception:
        return None
    combined = combined.set_index('날짜')

    # 외국인 순매수 컬럼 탐지
    fgn_col = next((c for c in combined.columns if '외국인' in str(c) and
                    any(k in str(c) for k in ['순매수', '매수'])), None)
    if fgn_col is None:
        fgn_col = next((c for c in combined.columns if '외국인' in str(c)), None)

    combined['safe_for'] = (
        pd.to_numeric(combined[fgn_col].astype(str).str.replace(',', '').str.replace('+', ''),
                      errors='coerce').fillna(0)
        if fgn_col else 0.0
    )
    combined['safe_ret']  = 0.0
    combined['safe_inst'] = 0.0
    print(f"[Naver] frgn scrape OK: {len(combined)}행, fgn_col={fgn_col}")
    return combined[['safe_for', 'safe_ret', 'safe_inst']]


# 🟣 세 번째 방: KRX 실시간 수급 및 공매도 (🌟 함수명 원복 및 컬럼 다형성 완벽 방어)
@app.get("/api/sentiment/{query}")
def get_sentiment(query: str):
    # 메타데이터 포함
    meta = {"count": 0}
    try:
        ticker = resolve_ticker(query)
        if not ticker.isdigit(): return {"data": [], "meta": {"count": 0}}

        # sentiment 캐시: pykrx 실패 빈번 → 7일 이내 캐시 허용 (주말/공휴일 연속 실패 커버)
        cached = get_cached_data("sentiment_v3", ticker, ttl_days=7)
        if cached:
            print(f"[Cache HIT] Sentiment data for {ticker}")
            return cached

        print(f"[Cache MISS] Fetching Sentiment data for {ticker} from KRX...")
        import time
        time.sleep(0.5) # 안티 봇 딜레이

        # 주말이면 직전 금요일(마지막 거래일) 기준으로 롤백
        end_date = datetime.today()
        while end_date.weekday() > 4:  # 5=토, 6=일
            end_date -= timedelta(days=1)
        start_date = end_date - timedelta(days=60)
        end_str = end_date.strftime("%Y%m%d")
        start_str = start_date.strftime("%Y%m%d")
        print(f"[Sentiment] 기준일: {end_str} (오늘 weekday={datetime.today().weekday()})")

        # ── 수급 (investor flow) — 독립 try/except ────────────────────
        df_investor = None
        investor_source = "none"
        try:
            df_investor = stock.get_market_trading_value_by_date(start_str, end_str, ticker)
            if df_investor is not None and not df_investor.empty:
                investor_source = "trading_value"
                print(f"[Sentiment] investor: trading_value OK ({len(df_investor)}행)")
            else:
                df_investor = None
        except Exception as e:
            print(f"[Sentiment] trading_value failed: {e}")

        if df_investor is None:
            try:
                df_investor = stock.get_market_trading_volume_by_date(start_str, end_str, ticker)
                if df_investor is not None and not df_investor.empty:
                    investor_source = "trading_volume"
                    print(f"[Sentiment] investor: trading_volume OK ({len(df_investor)}행)")
                else:
                    df_investor = None
            except Exception as e:
                print(f"[Sentiment] trading_volume failed: {e}")

        # ── Naver Finance 폴백 (pykrx 모두 실패 시) ──────────────────────
        if df_investor is None:
            try:
                df_naver = _fetch_naver_investor_flow(ticker, pages=3)
                if df_naver is not None and not df_naver.empty:
                    df_investor = df_naver
                    investor_source = "naver_frgn"
                    print(f"[Sentiment] investor: naver_frgn OK ({len(df_investor)}행)")
            except Exception as e:
                print(f"[Sentiment] naver_frgn failed: {e}")

        # ── 공매도 (short selling) — 함수명 우선순위 체인 ──────────────
        df_short = None
        short_source = "none"
        for _fn_name, _fn in [
            ("shorting_volume",  lambda: stock.get_shorting_volume_by_date(start_str, end_str, ticker)),
            ("shorting_balance", lambda: stock.get_shorting_balance_by_date(start_str, end_str, ticker)),
            ("shorting_status",  lambda: stock.get_shorting_status_by_date(start_str, end_str, ticker)),
        ]:
            try:
                _res = _fn()
                if _res is not None and not _res.empty:
                    df_short = _res
                    short_source = _fn_name
                    print(f"[Sentiment] short: {_fn_name} OK ({len(df_short)}행)")
                    break
            except Exception as e:
                print(f"[Sentiment] {_fn_name} failed: {e}")

        # ── 컬럼명 진단 로그 ──────────────────────────────────────────
        if df_investor is not None and not df_investor.empty:
            print(f"[Sentiment] df_investor columns: {list(df_investor.columns)}")
        if df_short is not None and not df_short.empty:
            print(f"[Sentiment] df_short columns: {list(df_short.columns)}")

        # ── 외국인/기관 컬럼 다형성 방어 ─────────────────────────────
        # Naver 폴백은 이미 safe_* 컬럼이 세팅돼 있으므로 파싱 건너뜀
        if df_investor is not None and not df_investor.empty and 'safe_for' not in df_investor.columns:
            df_investor = df_investor.reset_index()
            date_col_inv = '날짜' if '날짜' in df_investor.columns else '일자'
            df_investor[date_col_inv] = pd.to_datetime(df_investor[date_col_inv]).dt.strftime("%Y-%m-%d")
            df_investor = df_investor.set_index(date_col_inv)

            col_retail  = next((c for c in ['개인', '개인투자자'] if c in df_investor.columns), None)
            col_foreign = next((c for c in ['외국인', '외국인합계'] if c in df_investor.columns), None)
            col_inst    = next((c for c in ['기관합계', '기관'] if c in df_investor.columns), None)

            df_investor['safe_ret']  = df_investor[col_retail]  if col_retail  else 0.0
            df_investor['safe_for']  = df_investor[col_foreign] if col_foreign else 0.0
            df_investor['safe_inst'] = df_investor[col_inst]    if col_inst    else 0.0
        elif df_investor is None or df_investor.empty:
            df_investor = pd.DataFrame(columns=['safe_ret', 'safe_for', 'safe_inst'])

        # 공매도 컬럼 다형성 방어
        if df_short is not None and not df_short.empty:
            df_short = df_short.reset_index()
            date_col_short = '일자' if '일자' in df_short.columns else '날짜'
            df_short[date_col_short] = pd.to_datetime(df_short[date_col_short]).dt.strftime("%Y-%m-%d")
            df_short = df_short.set_index(date_col_short)
            
            vol_col   = next((c for c in ['공매도', '거래량', '공매도거래량', '공매도량']   if c in df_short.columns), None)
            ratio_col = next((c for c in ['비중(%)', '비중', '공매도비중', '공매도비율'] if c in df_short.columns), None)
            
            df_short['safe_vol'] = df_short[vol_col] if vol_col else 0.0
            df_short['safe_ratio'] = df_short[ratio_col] if ratio_col else 0.0
        else:
            df_short = pd.DataFrame(columns=['safe_vol', 'safe_ratio'])

        # Outer Join 병합
        df_merged = df_investor.join(df_short[['safe_vol', 'safe_ratio']], how='outer').fillna(0)
        df_merged = df_merged.sort_index()

        # 데이터 조립
        result = [{"date": date, 
                   "retail_buy": float(row.get('safe_ret', 0)), 
                   "foreigner_buy": float(row.get('safe_for', 0)),
                   "inst_buy": float(row.get('safe_inst', 0)), 
                   "short_vol": float(row.get('safe_vol', 0)),
                   "short_ratio": float(row.get('safe_ratio', 0))} for date, row in df_merged.iterrows()]

        # 공매도 데이터 가용성 판별
        has_short = any(r['short_vol'] > 0 for r in result)
        has_investor = any(r['foreigner_buy'] != 0 or r['inst_buy'] != 0 for r in result)
        if result and has_investor:
            sent_status = "ok" if has_short else "partial"
            sent_note = "" if has_short else "공매도 데이터 미제공 종목"
        else:
            sent_status = "missing"
            sent_note = "수급 데이터 없음"

        upsert_data_registry(ticker, 'sentiment', sent_status, sent_note)
        final_response = {
            "data": result,
            "meta": {
                "count": len(result),
                "sources": {"sentiment": {
                    "status": sent_status,
                    "from": investor_source,
                    "short_source": short_source,
                    "note": sent_note,
                }}
            }
        }
        save_cached_data("sentiment_v3", ticker, final_response)
        return final_response

    except Exception as e:
        print(f"[Sentiment API Error] {e}")
        import traceback
        traceback.print_exc()
        return {"data": [], "meta": {"count": 0, "sources": {"sentiment": {"status": "missing", "from": "none", "note": str(e)}}}}
    
    
# --- 스크리너 엔진 영역 (기존 로직 완벽 유지) ---
class ScreenerRequest(BaseModel):
    min_roe: Optional[float] = None
    max_per: Optional[float] = None
    max_pbr: Optional[float] = None
    min_market_cap: Optional[float] = None 
    inst_buy_flag: Optional[bool] = False
    min_rev_cagr: Optional[float] = None
    min_op_cagr: Optional[float] = None
    max_debt_ratio: Optional[float] = None
    ocf_pass_flag: Optional[bool] = False
    relative_per_discount: Optional[float] = None 
    relative_pbr_discount: Optional[float] = None 
    relative_psr_discount: Optional[float] = None 
    relative_roe_excess: Optional[bool] = False   
    relative_growth_excess: Optional[bool] = False 
    max_peg: Optional[float] = None 

@app.post("/api/screener")
def run_screener(req: ScreenerRequest):
    db_path = os.path.join(db_dir, "finance.db")
    query = "SELECT * FROM screener_summary WHERE 1=1"
    params = []
    
    if req.min_roe is not None: query += " AND ROE >= ?"; params.append(req.min_roe)
    if req.max_per is not None: query += " AND PER <= ? AND PER > 0"; params.append(req.max_per)
    if req.max_pbr is not None: query += " AND PBR <= ? AND PBR > 0"; params.append(req.max_pbr)
    if req.min_market_cap is not None: query += " AND 시가총액 >= ?"; params.append(req.min_market_cap)
    if req.inst_buy_flag: query += " AND 순매수거래대금 > 0"
    if req.min_rev_cagr is not None: query += " AND rev_cagr_3y >= ?"; params.append(req.min_rev_cagr)
    if req.min_op_cagr is not None: query += " AND op_cagr_3y >= ?"; params.append(req.min_op_cagr)
    if req.max_debt_ratio is not None: query += " AND debt_ratio <= ? AND debt_ratio > 0"; params.append(req.max_debt_ratio)
    if req.ocf_pass_flag: query += " AND ocf_pass = 1"

    # P1: median_* → sector_* (시총 가중평균 벤치마크 컬럼명 통일)
    if req.relative_per_discount is not None: query += " AND sector_per > 0 AND PER <= sector_per * (1.0 - (? / 100.0)) AND PER > 0"; params.append(req.relative_per_discount)
    if req.relative_pbr_discount is not None: query += " AND sector_pbr > 0 AND PBR <= sector_pbr * (1.0 - (? / 100.0)) AND PBR > 0"; params.append(req.relative_pbr_discount)
    if req.relative_psr_discount is not None: query += " AND sector_psr > 0 AND PSR <= sector_psr * (1.0 - (? / 100.0)) AND PSR > 0"; params.append(req.relative_psr_discount)
    if req.relative_roe_excess: query += " AND ROE > 0 AND sector_roe > 0 AND ROE >= sector_roe"
    if req.relative_growth_excess: query += " AND rev_cagr_3y IS NOT NULL AND sector_rev_cagr IS NOT NULL AND sector_rev_cagr > 0 AND rev_cagr_3y >= sector_rev_cagr"
    # P2: PEG = PER / 순이익CAGR (표준 PEG 분모, 영업이익CAGR 아님)
    if req.max_peg is not None: query += " AND eps_cagr_3y > 0 AND PER > 0 AND (PER / eps_cagr_3y) <= ?"; params.append(req.max_peg)
        
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return {"count": len(df), "data": df.fillna(0).to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"스크리너 엔진 오류: {str(e)}")


# ── B: SSE 분기배치 스트리밍 ──────────────────────────────────────────────────
@app.get("/api/batch/quarterly/run")
async def run_quarterly_batch_sse():
    """분기 DART 배치를 SSE로 스트리밍 실행.
    프론트엔드는 EventSource('/api/batch/quarterly/run')로 진행 상황을 실시간 수신."""
    import importlib.util, threading, queue

    q: queue.Queue = queue.Queue()

    def progress_cb(msg: str):
        q.put({"event": "progress", "data": msg})

    def run_batch():
        try:
            spec = importlib.util.spec_from_file_location(
                "quarterly_dart_batch",
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "etl", "quarterly_dart_batch.py")
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.run_quarterly_batch(progress_cb=progress_cb)
        except Exception as e:
            q.put({"event": "error", "data": str(e)})
        finally:
            q.put(None)  # sentinel

    thread = threading.Thread(target=run_batch, daemon=True)
    thread.start()

    async def event_generator():
        loop = asyncio.get_event_loop()
        while True:
            item = await loop.run_in_executor(None, q.get)
            if item is None:
                yield "event: done\ndata: 배치 완료\n\n"
                break
            yield f"event: {item['event']}\ndata: {item['data']}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── 분기 재무 데이터 ─────────────────────────────────────────────────────────
@app.get("/api/quarterly/{query}/{year}")
def get_quarterly_data(query: str, year: int):
    """단일 종목의 분기별 재무 데이터(상반기/Q3/Q4/연간합계) 반환.
    캐시: api_cache 테이블 (당일 유효)."""
    cache_key = f"quarterly_{year}"
    ticker = resolve_ticker(query)

    cached = get_cached_data(cache_key, ticker)
    if cached:
        return cached

    # corp_code 조회
    session_master = SessionMaster()
    master_info = session_master.query(CompanyMaster).filter(
        (CompanyMaster.corp_name == query) | (CompanyMaster.stock_code == query) |
        (CompanyMaster.stock_code == ticker)
    ).first()
    session_master.close()

    if not master_info:
        raise HTTPException(status_code=404, detail="기업을 찾을 수 없습니다.")

    from core.dart_api import DartAPIClient
    from core.quarterly_processor import compute_quarterly

    api = DartAPIClient(api_key=os.getenv("DART_API_KEY", ""))
    raw = api.get_quarterly_statements(master_info.corp_code, str(year))
    result = compute_quarterly(raw["annual"], raw["h1"], raw["q3_ytd"])

    response = {
        "corp_name": master_info.corp_name,
        "year": year,
        "quarters": result,   # {h1, q3, q4, annual}
    }
    save_cached_data(cache_key, ticker, response)
    return response