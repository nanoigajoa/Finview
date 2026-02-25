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

# 🟢 첫 번째 방: DART 재무 데이터 조회 (기존 완벽 작동 로직 보존)
@app.get("/api/finance/{query}")
def get_financial_data(query: str):
    session_master = SessionMaster()
    session_fact = SessionFact()
    
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
            print(f"[{corp_name}] DB에 데이터가 없습니다. 실시간 DART API 수집을 시작합니다...")
            api = DartAPIClient(api_key="1009054bb1fab7f3a54a1dcbd71bd57e678b3ab8")
            processor = FinancialDataProcessor()
            target_years = ["2022", "2023", "2024"]
            
            for year in target_years:
                try:
                    raw_json = api.get_financial_statement(dart_code, year)
                    df = processor.parse_to_dataframe(raw_json)
                    clean_df = processor.clean_data(df)
                    metrics = processor.extract_metrics(clean_df)
                    
                    if metrics.get('revenue', 0) > 0:
                        new_report = FinancialReport(
                            corp_name=corp_name, corp_code=dart_code, year=int(year),
                            revenue=metrics['revenue'], operating_income=metrics['operating_income'],
                            net_income=metrics['net_income'], op_cash_flow=metrics['op_cash_flow'],
                            roe=metrics['roe'], op_margin=metrics['op_margin'],
                            debt_ratio=metrics['debt_ratio'], fcf=metrics['fcf']
                        )
                        session_fact.add(new_report)
                except Exception as e:
                    print(f"실시간 수집 에러 ({year}): {e}")
            
            session_fact.commit()
            reports = session_fact.query(FinancialReport).filter_by(corp_code=dart_code).order_by(FinancialReport.year.asc()).all()
            
            if not reports:
                raise HTTPException(status_code=404, detail="DART 서버에도 해당 기업의 재무 데이터가 부족합니다.")

        def clean_val(v):
            if v is None or math.isnan(v): return 0.0
            return v

        data = []
        for r in reports:
            data.append({
                "year": r.year, "revenue": clean_val(r.revenue), "operating_income": clean_val(r.operating_income),
                "net_income": clean_val(r.net_income), "op_cash_flow": clean_val(r.op_cash_flow), "roe": clean_val(r.roe),
                "op_margin": clean_val(r.op_margin), "debt_ratio": clean_val(r.debt_ratio), "fcf": clean_val(r.fcf)
            })
            
        return {"corp_name": corp_name, "data": data}
        
    finally:
        session_master.close()
        session_fact.close()

# 🔵 두 번째 방: KRX 실시간 시장 펀더멘털 조회 (기존 완벽 작동 로직 보존)
@app.get("/api/market/{query}")
def get_market_data(query: str, target_date: str = None):
    session_master = SessionMaster()
    
    try:
        master_info = session_master.query(CompanyMaster).filter(
            (CompanyMaster.corp_name == query) | (CompanyMaster.stock_code == query)
        ).first()
        
        if not master_info or not master_info.stock_code:
            raise HTTPException(status_code=404, detail="상장사 명부에서 종목코드를 찾을 수 없습니다.")
            
        stock_code = master_info.stock_code
        
        if not target_date:
            today = datetime.today()
            start_date = (today - timedelta(days=7)).strftime("%Y%m%d")
            end_date = today.strftime("%Y%m%d")
        else:
            start_date = target_date
            end_date = target_date

        df = stock.get_market_fundamental(start_date, end_date, stock_code)
        
        if df.empty:
            raise HTTPException(status_code=404, detail="해당 날짜의 시장 데이터가 없습니다.")
            
        latest_data = df.iloc[-1]
        
        def clean_val(v):
            if pd.isna(v): return 0.0
            return float(v)

        return {
            "corp_name": master_info.corp_name,
            "date": df.index[-1].strftime("%Y-%m-%d"),
            "data": {
                "BPS": clean_val(latest_data.get('BPS')),
                "PER": clean_val(latest_data.get('PER')),
                "PBR": clean_val(latest_data.get('PBR')),
                "EPS": clean_val(latest_data.get('EPS')),
                "DIV": clean_val(latest_data.get('DIV')),
                "DPS": clean_val(latest_data.get('DPS'))
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"시장 데이터 조회 에러: {str(e)}")
    finally:
        session_master.close()

# 🟣 세 번째 방: KRX 실시간 수급 및 공매도 트래커 (🌟 외국인 수급 버그 픽스 완료)
@app.get("/api/sentiment/{query}")
def get_sentiment_data(query: str):
    session_master = SessionMaster()
    try:
        master_info = session_master.query(CompanyMaster).filter(
            (CompanyMaster.corp_name == query) | (CompanyMaster.stock_code == query)
        ).first()
        
        if not master_info or not master_info.stock_code:
            raise HTTPException(status_code=404, detail="종목코드를 찾을 수 없습니다.")

        stock_code = master_info.stock_code
        end_date = datetime.today()
        start_date = end_date - timedelta(days=100) 
        
        sd_str = start_date.strftime("%Y%m%d")
        ed_str = end_date.strftime("%Y%m%d")

        # 🌟 핵심 수정: on='순매수' 파라미터를 추가하여 기관과 외국인 데이터를 동시에 가져옵니다.
        df_short = stock.get_shorting_volume_by_date(sd_str, ed_str, stock_code)
        df_investor = stock.get_market_trading_volume_by_date(sd_str, ed_str, stock_code, on='순매수')

        if df_short.empty or df_investor.empty:
            raise HTTPException(status_code=404, detail="수급 데이터가 없습니다.")

        # 두 데이터를 날짜 기준으로 병합
        df = pd.concat([df_short, df_investor], axis=1).dropna()

        def safe_get(df, cols, default=0.0):
            for c in cols:
                if c in df.columns: return df[c]
            return pd.Series([default]*len(df), index=df.index)

        short_vol = safe_get(df, ['공매도거래량', '공매도량'])
        total_vol = safe_get(df, ['거래량', '총거래량'], default=1.0)
        short_ratio = (short_vol / total_vol.replace(0, 1)) * 100

        # 이제 외국인 컬럼도 완벽하게 추출됩니다.
        inst_buy = safe_get(df, ['기관합계', '기관'])
        foreigner_buy = safe_get(df, ['외국인'])
        retail_buy = safe_get(df, ['개인']) # 🌟 신규 추가: 개인 수급 추출

        data = []
        for date, row in df.iterrows():
            data.append({
                "date": date.strftime("%Y-%m-%d"),
                "short_vol": float(short_vol.loc[date]),
                "short_ratio": float(short_ratio.loc[date]),
                "inst_buy": float(inst_buy.loc[date]),
                "foreigner_buy": float(foreigner_buy.loc[date]),
                "retail_buy": float(retail_buy.loc[date]) # 🌟 신규 추가: JSON으로 전송
            })

        data = sorted(data, key=lambda x: x["date"])
        return {"corp_name": master_info.corp_name, "data": data}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session_master.close()
        
# --- [신규 기능] 멀티팩터 스크리너 엔진 (기존 완벽 작동 로직 보존) ---

class ScreenerRequest(BaseModel):
    min_roe: Optional[float] = None
    max_per: Optional[float] = None
    max_pbr: Optional[float] = None
    min_market_cap: Optional[float] = None 
    inst_buy_flag: Optional[bool] = False

@app.post("/api/screener")
def run_screener(req: ScreenerRequest):
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "finance.db")
    
    query = "SELECT * FROM screener_summary WHERE 1=1"
    params = []
    
    if req.min_roe is not None:
        query += " AND ROE >= ?"
        params.append(req.min_roe)
        
    if req.max_per is not None:
        query += " AND PER <= ? AND PER > 0"
        params.append(req.max_per)
        
    if req.max_pbr is not None:
        query += " AND PBR <= ? AND PBR > 0"
        params.append(req.max_pbr)
        
    if req.min_market_cap is not None:
        query += " AND 시가총액 >= ?"
        params.append(req.min_market_cap)
        
    if req.inst_buy_flag:
        query += " AND 순매수거래대금 > 0"
        
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        df = df.fillna(0)
        results = df.to_dict(orient="records")
        
        return {
            "count": len(results), 
            "data": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"스크리너 엔진 오류: {str(e)}")