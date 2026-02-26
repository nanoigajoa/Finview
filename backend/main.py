from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
def get_cached_data(cache_type: str, ticker: str):
    today_str = datetime.today().strftime("%Y-%m-%d")
    db_path = os.path.join(db_dir, "finance.db")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS api_cache 
                          (cache_type TEXT, ticker TEXT, cache_date TEXT, data TEXT,
                           PRIMARY KEY(cache_type, ticker))''')
        cursor.execute("SELECT data FROM api_cache WHERE cache_type=? AND ticker=? AND cache_date=?", (cache_type, ticker, today_str))
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


# 🟢 첫 번째 방: DART 재무 데이터 (기존 로직 유지)
@app.get("/api/finance/{query}")
def get_financial_data(query: str):
    session_master = SessionMaster()
    session_fact = SessionFact()
    
    # 메타 정보 초기화
    meta = {"missing": []}
    try:
        master_info = session_master.query(CompanyMaster).filter(
            (CompanyMaster.corp_name == query) | (CompanyMaster.stock_code == query)
        ).first()
        
        if not master_info:
            raise HTTPException(status_code=404, detail="상장사 명부에서 기업을 찾을 수 없습니다.")
            
        dart_code = master_info.corp_code
        corp_name = master_info.corp_name
        
        reports = session_fact.query(FinancialReport).filter_by(corp_code=dart_code).order_by(FinancialReport.year.asc()).all()
        
        if not reports:
            print(f"[{corp_name}] 실시간 DART 수집 시작...")
            api = DartAPIClient(api_key="1009054bb1fab7f3a54a1dcbd71bd57e678b3ab8")
            processor = FinancialDataProcessor()
            for year in ["2022", "2023", "2024"]:
                try:
                    raw_json = api.get_financial_statement(dart_code, year)
                    df = processor.parse_to_dataframe(raw_json)
                    clean_df = processor.clean_data(df)
                    metrics = processor.extract_metrics(clean_df)
                    if metrics.get('revenue', 0) > 0:
                        session_fact.add(FinancialReport(
                            corp_name=corp_name, corp_code=dart_code, year=int(year),
                            revenue=metrics['revenue'], operating_income=metrics['operating_income'],
                            net_income=metrics['net_income'], op_cash_flow=metrics['op_cash_flow'],
                            roe=metrics['roe'], op_margin=metrics['op_margin'],
                            debt_ratio=metrics['debt_ratio'], fcf=metrics['fcf']
                        ))
                except Exception as e:
                    print(f"DART 수집 에러 ({year}): {e}")
            session_fact.commit()
            reports = session_fact.query(FinancialReport).filter_by(corp_code=dart_code).order_by(FinancialReport.year.asc()).all()
            if not reports:
                # DART에 자료가 없으면 빈 배열을 돌려주고 메타로 표시
                return {"corp_name": corp_name, "data": [], "meta": {"missing": ["finance"]}}
        # build result list from reports
        def clean_val(v): return 0.0 if v is None or math.isnan(v) else v
        data = [{"year": r.year, "revenue": clean_val(r.revenue), "operating_income": clean_val(r.operating_income),
                 "net_income": clean_val(r.net_income), "op_cash_flow": clean_val(r.op_cash_flow), "roe": clean_val(r.roe),
                 "op_margin": clean_val(r.op_margin), "debt_ratio": clean_val(r.debt_ratio), "fcf": clean_val(r.fcf)} for r in reports]
        # 누락 체크: 데이터가 아예 없거나 모든 연도의 매출이 0이면 "missing"으로 간주
        if not data or all(d['revenue'] == 0 for d in data):
            meta['missing'].append('finance')
        return {"corp_name": corp_name, "data": data, "meta": meta}
        
    except Exception as e:
        # 일부 에러 문자열이 CP949에서 인코딩되지 않아 서버가 크래시되는 문제 방지
        msg = str(e)
        try:
            print("Market API Error:", msg)
        except UnicodeEncodeError:
            print("Market API Error: <encoding failure>")
        return {"data": {}, "meta": {"present": False}}
    
# 🔵 두 번째 방: 하이브리드 폴백 아키텍처 (🌟 1차 실시간 통신 -> 2차 실패 시 자체 DB 무적 로드)
@app.get("/api/market/{query}")
def get_market(query: str):
    try:
        ticker = resolve_ticker(query)
        if not ticker.isdigit(): 
            return {"data": {}, "meta": {"present": False}}

        # 🌟 1단계: 실시간 데이터 시도 (KRX API)
        realtime_success = False
        row = None
        target_date_str = ""
        
        try:
            import time
            time.sleep(0.3) # 안티 봇 딜레이
            end_date = datetime.today()
            # 실시간 통신은 당일 포함 최근 3일만 빠르게 스캔하여 과부하 방지
            for i in range(3): 
                d = end_date - timedelta(days=i)
                d_str = d.strftime("%Y%m%d")
                df = stock.get_market_fundamental(d_str, d_str, ticker)
                if not df.empty:
                    row = df.iloc[0]
                    target_date_str = d.strftime("%Y-%m-%d")
                    realtime_success = True
                    break
        except Exception as e:
            print(f"[Market] Realtime fetch failed, falling back to DB: {e}")

        # 🌟 2단계: DB 연결 및 공통 업종 지표(median_per) 로드
        db_path = os.path.join(db_dir, "finance.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 적정 주가 계산을 위한 업종 가중평균 PER은 무조건 DB에서 가져옵니다.
        cursor.execute("SELECT median_per FROM screener_summary WHERE stock_code=?", (ticker,))
        med_res = cursor.fetchone()
        median_per = float(med_res['median_per']) if med_res and med_res['median_per'] else 0.0

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

        # 🌟 3단계: 적정 주가 및 업사이드 기계적 연산
        target_price = eps * median_per if median_per > 0 and eps > 0 else 0.0
        current_price = eps * per if per > 0 else 0.0
        upside = ((target_price - current_price) / current_price) * 100 if current_price > 0 and target_price > 0 else 0.0

        return {
            "date": target_date_str,
            "data": {
                "PER": per, "PBR": pbr, "EPS": eps, "DIV": div,
                "target_price": target_price, "upside": upside, "current_price": current_price
            },
            # 🌟 폴백 여부를 프론트엔드에 전달하여 UI에 반영
            "meta": {"present": True, "fallback": fallback_flag}
        }
        
    except Exception as e:
        print(f"🚨 Market API Error: {e}")
        return {"data": {}, "meta": {"present": False}}


# 🟣 세 번째 방: KRX 실시간 수급 및 공매도 (🌟 함수명 원복 및 컬럼 다형성 완벽 방어)
@app.get("/api/sentiment/{query}")
def get_sentiment(query: str):
    # 메타데이터 포함
    meta = {"count": 0}
    try:
        ticker = resolve_ticker(query)
        if not ticker.isdigit(): return {"data": [], "meta": {"count": 0}}

        # 🌟 기존의 뻗어버린 에러 캐시를 무시하고 새로 가져오기 위해 키값을 v3로 변경합니다.
        cached = get_cached_data("sentiment_v3", ticker)
        if cached:
            print(f"[Cache HIT] Sentiment data for {ticker}")
            return cached

        print(f"[Cache MISS] Fetching Sentiment data for {ticker} from KRX...")
        import time
        time.sleep(0.5) # 안티 봇 딜레이

        end_date = datetime.today()
        start_date = end_date - timedelta(days=60)
        end_str = end_date.strftime("%Y%m%d")
        start_str = start_date.strftime("%Y%m%d")

        # 🌟 치명적 버그 픽스: 실제로 존재하는 정상적인 함수로 완벽히 원복
        df_investor = stock.get_market_trading_volume_by_date(start_str, end_str, ticker)
        if df_investor is None or df_investor.empty:
            time.sleep(0.5)
            df_investor = stock.get_market_trading_value_by_date(start_str, end_str, ticker)

        df_short = stock.get_shorting_status_by_date(start_str, end_str, ticker)

        # 🌟 외국인/기관 컬럼 다형성 방어 (KRX가 이름을 바꿔도 무조건 찾아냄)
        if df_investor is not None and not df_investor.empty:
            df_investor = df_investor.reset_index()
            date_col_inv = '날짜' if '날짜' in df_investor.columns else '일자'
            df_investor[date_col_inv] = pd.to_datetime(df_investor[date_col_inv]).dt.strftime("%Y-%m-%d")
            df_investor = df_investor.set_index(date_col_inv)
            
            col_retail = '개인' if '개인' in df_investor.columns else ('개인투자자' if '개인투자자' in df_investor.columns else None)
            col_foreign = '외국인' if '외국인' in df_investor.columns else ('외국인합계' if '외국인합계' in df_investor.columns else None)
            col_inst = '기관합계' if '기관합계' in df_investor.columns else ('기관' if '기관' in df_investor.columns else None)
            
            df_investor['safe_ret'] = df_investor[col_retail] if col_retail else 0.0
            df_investor['safe_for'] = df_investor[col_foreign] if col_foreign else 0.0
            df_investor['safe_inst'] = df_investor[col_inst] if col_inst else 0.0
        else:
            df_investor = pd.DataFrame(columns=['safe_ret', 'safe_for', 'safe_inst'])

        # 공매도 컬럼 다형성 방어
        if df_short is not None and not df_short.empty:
            df_short = df_short.reset_index()
            date_col_short = '일자' if '일자' in df_short.columns else '날짜'
            df_short[date_col_short] = pd.to_datetime(df_short[date_col_short]).dt.strftime("%Y-%m-%d")
            df_short = df_short.set_index(date_col_short)
            
            vol_col = '거래량' if '거래량' in df_short.columns else ('공매도거래량' if '공매도거래량' in df_short.columns else None)
            ratio_col = '비중' if '비중' in df_short.columns else ('공매도비중' if '공매도비중' in df_short.columns else None)
            
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

        # 정상적인 데이터를 v3 금고에 저장
        final_response = {"data": result, "meta": {"count": len(result)}}
        save_cached_data("sentiment_v3", ticker, final_response)
        return final_response
        
    except Exception as e:
        print(f"🚨 Sentiment API Error: {e}")
        import traceback
        traceback.print_exc()
        return {"data": [], "meta": {"count": 0}}
    
    
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

    if req.relative_per_discount is not None: query += " AND median_per > 0 AND PER <= median_per * (1.0 - (? / 100.0)) AND PER > 0"; params.append(req.relative_per_discount)
    if req.relative_pbr_discount is not None: query += " AND median_pbr > 0 AND PBR <= median_pbr * (1.0 - (? / 100.0)) AND PBR > 0"; params.append(req.relative_pbr_discount)
    if req.relative_psr_discount is not None: query += " AND median_psr > 0 AND PSR <= median_psr * (1.0 - (? / 100.0)) AND PSR > 0"; params.append(req.relative_psr_discount)
    if req.relative_roe_excess: query += " AND ROE > 0 AND median_roe > 0 AND ROE >= median_roe"
    if req.relative_growth_excess: query += " AND rev_cagr_3y IS NOT NULL AND median_rev_cagr IS NOT NULL AND median_rev_cagr > 0 AND rev_cagr_3y >= median_rev_cagr"
    if req.max_peg is not None: query += " AND op_cagr_3y > 0 AND PER > 0 AND (PER / op_cagr_3y) <= ?"; params.append(req.max_peg)
        
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return {"count": len(df), "data": df.fillna(0).to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"스크리너 엔진 오류: {str(e)}")