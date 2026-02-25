import pandas as pd
from pykrx import stock
from datetime import datetime, timedelta
import sqlite3
import os
import time

def run_daily_batch():
    print("🚀 T-0 멀티팩터 스크리너 배치 파이프라인 가동을 시작합니다...")
    start_time = time.time()

    # 1. 날짜 설정 (가장 최근 영업일 탐색)
    today = datetime.today()
    # 주말 보정 (토요일->금요일, 일요일->금요일)
    if today.weekday() == 5: today -= timedelta(days=1)
    elif today.weekday() == 6: today -= timedelta(days=2)
    target_date = today.strftime("%Y%m%d")
    
    # 수급 누적용 1달 전 날짜
    one_month_ago = (today - timedelta(days=30)).strftime("%Y%m%d")
    print(f"✅ 기준일: {target_date} / 수급 집계: {one_month_ago} ~ {target_date}")

    # 2. 시장별 펀더멘털 및 시가총액 일괄 조회 (KOSPI, KOSDAQ)
    print("✅ 데이터 수집 중: 전 종목 펀더멘털 및 시가총액 (API 타격 최소화)...")
    
    df_fund_kospi = stock.get_market_fundamental(target_date, market="KOSPI")
    df_fund_kospi['market_type'] = 'KOSPI'
    df_fund_kosdaq = stock.get_market_fundamental(target_date, market="KOSDAQ")
    df_fund_kosdaq['market_type'] = 'KOSDAQ'
    df_fund = pd.concat([df_fund_kospi, df_fund_kosdaq])

    df_cap_kospi = stock.get_market_cap(target_date, market="KOSPI")
    df_cap_kosdaq = stock.get_market_cap(target_date, market="KOSDAQ")
    df_cap = pd.concat([df_cap_kospi, df_cap_kosdaq])

    # 3. 1개월 기관 누적 순매수 일괄 조회 (단일 호출로 시장 전체 조회)
    print("✅ 데이터 수집 중: 최근 1개월 기관 합계 누적 수급...")
    df_inst_kospi = stock.get_market_net_purchases_of_equities_by_ticker(one_month_ago, target_date, market="KOSPI", investor="기관합계")
    df_inst_kosdaq = stock.get_market_net_purchases_of_equities_by_ticker(one_month_ago, target_date, market="KOSDAQ", investor="기관합계")
    df_inst = pd.concat([df_inst_kospi, df_inst_kosdaq])

    # 4. 데이터프레임 병합 (Join)
    print("✅ 데이터 병합 및 Z-Score 1단계(Median) 계산 중...")
    df_master = df_fund.join(df_cap[['시가총액']], how='left')
    df_master = df_master.join(df_inst[['순매수거래대금']], how='left').fillna(0)
    
    # ROE 파생 변수 생성 (PBR / PER)
    df_master['ROE'] = df_master.apply(lambda x: (x['PBR'] / x['PER'] * 100) if x['PER'] > 0 else 0.0, axis=1)

    # 5. 시장(섹터 대용)별 Median 계산 및 병합
    median_df = df_master.groupby('market_type')[['PER', 'PBR', 'ROE']].median().reset_index()
    median_df.rename(columns={'PER':'median_per', 'PBR':'median_pbr', 'ROE':'median_roe'}, inplace=True)
    
    df_master = df_master.reset_index() # 인덱스에 있던 티커를 컬럼으로 올림
    df_master.rename(columns={'티커': 'stock_code', 'index': 'stock_code'}, inplace=True)
    df_master = pd.merge(df_master, median_df, on='market_type', how='left')

    # 종목명 매핑
    df_master['corp_name'] = df_master['stock_code'].apply(lambda x: stock.get_market_ticker_name(x))

    # 최종 테이블 컬럼 정리
    final_cols = [
        'stock_code', 'corp_name', 'market_type', 
        'PER', 'PBR', 'ROE', 'EPS', 'DIV', 
        '시가총액', '순매수거래대금', 
        'median_per', 'median_pbr', 'median_roe'
    ]
    df_final = df_master[final_cols].copy()

    # 6. 데이터베이스 저장 (Materialized View 역할)
    print("✅ 데이터베이스(SQLite)에 요약 마트 테이블 적재 중...")
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "finance.db")
    
    # 경로가 없으면 생성
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    # 기존 테이블을 완전히 덮어쓰기 (매일매일 가장 최신 스냅샷만 유지)
    df_final.to_sql('screener_summary', conn, if_exists='replace', index=False)
    conn.close()

    elapsed = round(time.time() - start_time, 2)
    print(f"🎉 배치 완료! 총 2,500여 개 종목 데이터가 성공적으로 적재되었습니다. (소요시간: {elapsed}초)")

if __name__ == "__main__":
    run_daily_batch()