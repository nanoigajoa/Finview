import pandas as pd
from pykrx import stock
import FinanceDataReader as fdr  # 🌟 신규 장착된 메타데이터 전용 API
from datetime import datetime, timedelta
import sqlite3
import os
import time

def get_safe_business_day():
    today = datetime.today()
    if today.hour < 18:
        today -= timedelta(days=1)
        
    print("✅ 자체 검증 달력 엔진 가동: KRX 실제 영업일 탐색 중...")
    
    # 1. 최근 진짜 영업일 탐색
    while True:
        if today.weekday() <= 4:
            target_date = today.strftime("%Y%m%d")
            if not stock.get_market_cap(target_date, market="KOSPI").empty:
                break
        today -= timedelta(days=1)
        
    # 2. 1개월 전 진짜 영업일 탐색
    month_ago = today - timedelta(days=30)
    while True:
        if month_ago.weekday() <= 4:
            month_date = month_ago.strftime("%Y%m%d")
            if not stock.get_market_cap(month_date, market="KOSPI").empty:
                break
        month_ago -= timedelta(days=1)
        
    return target_date, month_date

def run_daily_batch():
    print("🚀 T-0 멀티팩터 스크리너 배치 파이프라인 (100% API Edition) 가동...")
    start_time = time.time()

    target_date, one_month_ago = get_safe_business_day()
    print(f"✅ 기준일: {target_date} / 수급 집계: {one_month_ago} ~ {target_date}")

    # 🌟 [리팩토링 완료] 지저분한 웹 크롤링을 버리고, FDR API 한 줄로 우아하게 해결
    print("✅ 데이터 수집 중: FinanceDataReader API를 통한 표준 업종 추출...")
# 🌟 [리팩토링 완료] 지저분한 웹 크롤링을 버리고, FDR API 한 줄로 우아하게 해결
    print("✅ 데이터 수집 중: FinanceDataReader API를 통한 표준 업종 추출...")
    try:
        # 'KRX-DESC'를 호출해야 'Sector'(업종) 데이터가 포함된 명부를 줍니다.
        df_master_fdr = fdr.StockListing('KRX-DESC')
        
        # 라이브러리 버전에 따라 종목코드 컬럼명이 'Code' 또는 'Symbol'일 수 있으므로 방어 로직 추가
        code_col = 'Code' if 'Code' in df_master_fdr.columns else 'Symbol'
        
        # Sector(업종) 데이터가 비어있는 종목(ETF, 스팩 등)은 제외하여 데이터 오염 방지
        df_master_fdr = df_master_fdr.dropna(subset=['Sector'])
        
        # 종목코드와 산업군(Sector)을 딕셔너리로 완벽 매핑
        sector_map = dict(zip(df_master_fdr[code_col], df_master_fdr['Sector']))
        print(f"   -> 총 {len(sector_map)}개 상장사의 표준 업종 API 매핑 성공!")
    except Exception as e:
        print(f"   -> 업종 API 호출 실패: {e}")
        sector_map = {}
        
    print("✅ 시가총액 데이터 수집 중...")
    df_cap = pd.concat([stock.get_market_cap(target_date, market="KOSPI"), stock.get_market_cap(target_date, market="KOSDAQ")])
    df_cap.index = df_cap.index.astype(str) 

    print("✅ 펀더멘털 데이터 수집 중...")
    df_fund = pd.concat([stock.get_market_fundamental(target_date, market="KOSPI"), stock.get_market_fundamental(target_date, market="KOSDAQ")])
    df_fund.index = df_fund.index.astype(str)

    print("✅ 기관 수급 데이터 수집 중...")
    df_inst = pd.concat([
        stock.get_market_net_purchases_of_equities_by_ticker(one_month_ago, target_date, market="KOSPI", investor="기관합계"),
        stock.get_market_net_purchases_of_equities_by_ticker(one_month_ago, target_date, market="KOSDAQ", investor="기관합계")
    ])
    df_inst.index = df_inst.index.astype(str)

    print("✅ 데이터 병합(Join) 및 진짜 산업별 통계 연산 중...")
    df_master = df_cap[['시가총액']].join(df_fund[['PER', 'PBR', 'EPS', 'DIV']], how='left')
    df_master = df_master.join(df_inst[['순매수거래대금']], how='left').fillna(0)
    
    df_master['ROE'] = df_master.apply(lambda x: (x['PBR'] / x['PER'] * 100) if x['PER'] > 0 else 0.0, axis=1)
    df_master = df_master.reset_index().rename(columns={'티커': 'stock_code', 'index': 'stock_code'})

    # 🌟 완벽한 산업 섹터 주입
    df_master['sector_name'] = df_master['stock_code'].map(sector_map).fillna('분류안됨')
    df_master['corp_name'] = df_master['stock_code'].apply(lambda x: stock.get_market_ticker_name(x))

    # 🌟 산업별 진짜 중간값(Median) 정밀 타격
    valid_fund = df_master[df_master['PER'] > 0]
    median_df = valid_fund.groupby('sector_name')[['PER', 'PBR', 'ROE']].median().reset_index()
    median_df.rename(columns={'PER':'median_per', 'PBR':'median_pbr', 'ROE':'median_roe'}, inplace=True)
    
    df_master = pd.merge(df_master, median_df, on='sector_name', how='left').fillna(0)

    final_cols = ['stock_code', 'corp_name', 'sector_name', 'PER', 'PBR', 'ROE', 'EPS', 'DIV', '시가총액', '순매수거래대금', 'median_per', 'median_pbr', 'median_roe']
    df_final = df_master[final_cols].copy()

    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "finance.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    df_final.to_sql('screener_summary', conn, if_exists='replace', index=False)
    conn.close()

    elapsed = round(time.time() - start_time, 2)
    print(f"🎉 배치 완료! 크롤링 없는 100% 순수 API 파이프라인 구축 성공 (소요시간: {elapsed}초)")

if __name__ == "__main__":
    run_daily_batch()