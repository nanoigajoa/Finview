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

engine_master = init_master_db("sqlite:///data/고유번호.db")
SessionMaster = sessionmaker(bind=engine_master)

engine_fact = init_db("sqlite:///data/finance.db")
SessionFact = sessionmaker(bind=engine_fact)

# 🟢 첫 번째 방: DART 재무 데이터 조회 (기존 완벽 작동 로직)
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
        
        # 실시간 DART 수집 로직 (Cache Miss 방어)
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

        # NaN 소독기
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

# 🔵 두 번째 방: KRX 실시간 시장 펀더멘털 조회 (신규 편입)
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

# 🟣 세 번째 방: KRX 실시간 수급 및 공매도 트래커 (최근 3개월치 일괄 전송)
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
        # 최근 3개월(약 100일 여유) 데이터 조회
        end_date = datetime.today()
        start_date = end_date - timedelta(days=100) 
        
        sd_str = start_date.strftime("%Y%m%d")
        ed_str = end_date.strftime("%Y%m%d")

        # pykrx 공매도 & 수급 데이터 호출
        df_short = stock.get_shorting_volume_by_date(sd_str, ed_str, stock_code)
        df_trade = stock.get_market_trading_volume_by_date(sd_str, ed_str, stock_code)

        if df_short.empty or df_trade.empty:
            raise HTTPException(status_code=404, detail="수급 데이터가 없습니다.")

        # 두 데이터를 날짜 기준으로 병합
        df = pd.concat([df_short, df_trade], axis=1).dropna()

        # 컬럼 추출 안정성 확보 (pykrx 버전에 따른 컬럼명 대응)
        def safe_get(df, cols, default=0.0):
            for c in cols:
                if c in df.columns: return df[c]
            return pd.Series([default]*len(df), index=df.index)

        short_vol = safe_get(df, ['공매도거래량', '공매도량'])
        total_vol = safe_get(df, ['거래량', '총거래량'], default=1.0)
        short_ratio = (short_vol / total_vol.replace(0, 1)) * 100

        inst_buy = safe_get(df, ['기관합계', '기관'])
        foreigner_buy = safe_get(df, ['외국인'])

        data = []
        for date, row in df.iterrows():
            data.append({
                "date": date.strftime("%Y-%m-%d"),
                "short_vol": float(short_vol.loc[date]),
                "short_ratio": float(short_ratio.loc[date]),
                "inst_buy": float(inst_buy.loc[date]),
                "foreigner_buy": float(foreigner_buy.loc[date])
            })

        # 과거에서 현재 순으로 정렬 보장
        data = sorted(data, key=lambda x: x["date"])
        return {"corp_name": master_info.corp_name, "data": data}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session_master.close()
        
        
    # --- [신규 기능] 멀티팩터 스크리너 엔진 ---

# 1. 프론트엔드에서 날아올 JSON 데이터의 뼈대(규격) 정의
class ScreenerRequest(BaseModel):
    min_roe: Optional[float] = None
    max_per: Optional[float] = None
    max_pbr: Optional[float] = None
    min_market_cap: Optional[float] = None # 시가총액 (원 단위)
    inst_buy_flag: Optional[bool] = False  # 기관 순매수 여부

# 2. 스크리너 전용 POST API (동적 쿼리 조립)
@app.post("/api/screener")
def run_screener(req: ScreenerRequest):
    # 배치 스크립트가 만들어둔 정답지(screener_summary) 경로
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "finance.db")
    
    # 기본 쿼리 베이스
    query = "SELECT * FROM screener_summary WHERE 1=1"
    params = []
    
    # 프론트엔드에서 값이 들어온 조건만 동적으로 WHERE 절에 이어 붙임
    if req.min_roe is not None:
        query += " AND ROE >= ?"
        params.append(req.min_roe)
        
    if req.max_per is not None:
        # 🌟 핵심: PER가 마이너스인 '적자 기업'을 화면에서 자동으로 걸러주는 안전장치
        query += " AND PER <= ? AND PER > 0"
        params.append(req.max_per)
        
    if req.max_pbr is not None:
        query += " AND PBR <= ? AND PBR > 0"
        params.append(req.max_pbr)
        
    if req.min_market_cap is not None:
        # DB에는 원 단위로 저장되어 있으므로 억원 단위 환산 고려 (예: 1000억 = 100000000000)
        query += " AND 시가총액 >= ?"
        params.append(req.min_market_cap)
        
    if req.inst_buy_flag:
        # 최근 1개월 기관 순매수 금액이 0보다 큰 종목만 추출
        query += " AND 순매수거래대금 > 0"
        
    try:
        conn = sqlite3.connect(db_path)
        # Pandas의 read_sql_query를 이용해 SQL 결과를 즉시 DataFrame으로 변환
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        # NaN 값 등을 0으로 소독한 뒤 프론트엔드가 읽기 편한 딕셔너리 배열로 변환
        df = df.fillna(0)
        results = df.to_dict(orient="records")
        
        return {
            "count": len(results), 
            "data": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"스크리너 엔진 오류: {str(e)}")