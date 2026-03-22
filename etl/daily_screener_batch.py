import pandas as pd
from pykrx import stock
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import sqlite3
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", ".env"))

def get_safe_business_day():
    today = datetime.today()
    if today.hour < 18:
        today -= timedelta(days=1)
    while True:
        if today.weekday() <= 4:
            target_date = today.strftime("%Y%m%d")
            try:
                if len(stock.get_market_ticker_list(target_date, market="KOSPI")) > 0:
                    break
            except Exception:
                pass
        today -= timedelta(days=1)
    month_ago = today - timedelta(days=30)
    while True:
        if month_ago.weekday() <= 4:
            month_date = month_ago.strftime("%Y%m%d")
            try:
                if len(stock.get_market_ticker_list(month_date, market="KOSPI")) > 0:
                    break
            except Exception:
                pass
        month_ago -= timedelta(days=1)
    return target_date, month_date

def run_daily_batch():
    print("🚀 T-0 가치투자 스크리너 배치 (CAGR & Quality Filter Edition) 가동...")
    start_time = time.time()
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "finance.db")
    master_db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "고유번호.db")

    target_date, one_month_ago = get_safe_business_day()
    
    print("✅ 데이터 수집 중: FinanceDataReader 표준 업종 추출...")
    try:
        df_master_fdr = fdr.StockListing('KRX-DESC')
        code_col = 'Code' if 'Code' in df_master_fdr.columns else 'Symbol'
        df_master_fdr = df_master_fdr.dropna(subset=['Sector'])
        sector_map = dict(zip(df_master_fdr[code_col], df_master_fdr['Sector']))
    except Exception as e:
        print(f"   -> 업종 API 호출 실패: {e}")
        sector_map = {}

    print("✅ KRX 시가총액, 펀더멘털, 수급 데이터 수집 중...")
    df_cap = pd.concat([stock.get_market_cap(target_date, market="KOSPI"), stock.get_market_cap(target_date, market="KOSDAQ")])
    df_fund = pd.concat([stock.get_market_fundamental(target_date, market="KOSPI"), stock.get_market_fundamental(target_date, market="KOSDAQ")])
    df_inst = pd.concat([
        stock.get_market_net_purchases_of_equities_by_ticker(one_month_ago, target_date, market="KOSPI", investor="기관합계"),
        stock.get_market_net_purchases_of_equities_by_ticker(one_month_ago, target_date, market="KOSDAQ", investor="기관합계")
    ])
    df_cap.index = df_cap.index.astype(str)
    df_fund.index = df_fund.index.astype(str)
    df_inst.index = df_inst.index.astype(str)

    print("✅ DART API: 2,500개 종목 4년 치 재무 데이터 Bulk 수집 및 퀄리티 연산 중...")
    try:
        conn_master = sqlite3.connect(master_db_path)
        df_master_code = pd.read_sql("SELECT stock_code, corp_code FROM company_master", conn_master)
        conn_master.close()
        
        api_key = os.getenv("DART_API_KEY", "")
        corp_codes = df_master_code['corp_code'].dropna().tolist()
        
        years = ['2021', '2022', '2023', '2024']
        fin_data = {code: {y: {} for y in years} for code in corp_codes}
        
        for year in years:
            for i in range(0, len(corp_codes), 100):
                chunk = ",".join(corp_codes[i:i+100])
                url = f"https://opendart.fss.or.kr/api/fnlttMultiAcnt.json?crtfc_key={api_key}&corp_code={chunk}&bsns_year={year}&reprt_code=11011"
                res = requests.get(url).json()
                
                if res.get("status") == "000":
                    for item in res.get("list", []):
                        code = item.get("corp_code")
                        acct = item.get("account_nm")
                        
                        # 🌟 무결점 파서(Parser) 방어 로직: 회계상 '-' 기호나 빈 값을 안전하게 0.0으로 치환
                        raw_amt = str(item.get("thstrm_amount", "0")).strip().replace(',', '')
                        try:
                            amt = 0.0 if raw_amt in ['-', '', 'NaN'] else float(raw_amt)
                        except ValueError:
                            amt = 0.0
                        
                        if acct in ["매출액", "수익(매출액)", "영업수익"]:
                            if 'rev' not in fin_data[code][year] or item.get("fs_div") == "CFS": fin_data[code][year]['rev'] = amt
                        elif acct in ["영업이익", "영업이익(손실)"]:
                            if 'op' not in fin_data[code][year] or item.get("fs_div") == "CFS": fin_data[code][year]['op'] = amt
                        elif acct in ["당기순이익", "당기순이익(손실)"]:
                            if 'ni' not in fin_data[code][year] or item.get("fs_div") == "CFS": fin_data[code][year]['ni'] = amt
                        elif acct == "부채총계":
                            if 'liab' not in fin_data[code][year] or item.get("fs_div") == "CFS": fin_data[code][year]['liab'] = amt
                        elif acct == "자본총계":
                            if 'eq' not in fin_data[code][year] or item.get("fs_div") == "CFS": fin_data[code][year]['eq'] = amt
                        elif acct in ["영업활동현금흐름", "영업활동으로 인한 현금흐름"]:
                            if 'ocf' not in fin_data[code][year] or item.get("fs_div") == "CFS": fin_data[code][year]['ocf'] = amt
                        elif acct in ["유형자산의 취득", "유형자산취득"]:
                            # CAPEX는 현금유출(음수)이므로 abs()로 양수화
                            if 'capex' not in fin_data[code][year] or item.get("fs_div") == "CFS": fin_data[code][year]['capex'] = abs(amt)

        quality_list = []
        for idx, row in df_master_code.iterrows():
            code = row['corp_code']
            stock_code = row['stock_code']
            fd = fin_data.get(code, {})

            r21, r24 = fd.get('2021', {}).get('rev', 0), fd.get('2024', {}).get('rev', 0)
            o21, o24 = fd.get('2021', {}).get('op', 0), fd.get('2024', {}).get('op', 0)
            ni21, ni24 = fd.get('2021', {}).get('ni', 0), fd.get('2024', {}).get('ni', 0)

            rev_cagr = (((r24 / r21) ** (1/3)) - 1) * 100 if r21 > 0 and r24 > 0 else 0.0
            op_cagr = (((o24 / o21) ** (1/3)) - 1) * 100 if o21 > 0 and o24 > 0 else 0.0
            # P2: EPS CAGR = 순이익 CAGR (주식 수 안정 가정) — PEG 표준 분모
            eps_cagr = (((ni24 / ni21) ** (1/3)) - 1) * 100 if ni21 > 0 and ni24 > 0 else 0.0

            # P0: ocf_pass = 실제 영업활동현금흐름 3개년 연속 플러스 (순이익 기준 아님)
            ocf22 = fd.get('2022', {}).get('ocf', 0)
            ocf23 = fd.get('2023', {}).get('ocf', 0)
            ocf24 = fd.get('2024', {}).get('ocf', 0)
            ocf_pass = 1 if (ocf22 > 0 and ocf23 > 0 and ocf24 > 0) else 0

            l24, e24 = fd.get('2024', {}).get('liab', 0), fd.get('2024', {}).get('eq', 0)
            debt_ratio = (l24 / e24) * 100 if e24 > 0 else 0.0
            dart_roe = (ni24 / e24) * 100 if e24 > 0 else 0.0

            # P2: FCF = OCF - CAPEX (직접 계산), CAPEX 없으면 OCF의 80% 보수적 추정
            capex24 = fd.get('2024', {}).get('capex', 0)
            if ocf24 > 0:
                fcf24 = round((ocf24 - capex24) / 100000000 if capex24 > 0 else ocf24 * 0.8 / 100000000, 2)
            else:
                fcf24 = 0.0

            quality_list.append({
                'stock_code': stock_code, 'revenue': r24,
                'rev_cagr_3y': round(rev_cagr, 2), 'op_cagr_3y': round(op_cagr, 2),
                'eps_cagr_3y': round(eps_cagr, 2),
                'ocf_pass': ocf_pass, 'debt_ratio': round(debt_ratio, 2),
                'dart_roe': round(dart_roe, 2), 'fcf': fcf24
            })
            
        df_quality = pd.DataFrame(quality_list)
        df_quality.set_index('stock_code', inplace=True)
        print("   -> 퀄리티 지표(CAGR, 부채비율, 흑자검증) 연산 및 매핑 완료!")
    except Exception as e:
        print(f"   -> DART Bulk 퀄리티 수집 실패: {e}")
        df_quality = pd.DataFrame()

    print("✅ 마스터 데이터 병합 중...")
    df_master = df_cap[['시가총액']].join(df_fund[['PER', 'PBR', 'EPS', 'DIV']], how='left')
    df_master = df_master.join(df_inst[['순매수거래대금']], how='left')
    
    if not df_quality.empty:
        df_master = df_master.join(df_quality, how='left')
    else:
        for col in ['revenue', 'rev_cagr_3y', 'op_cagr_3y', 'eps_cagr_3y', 'ocf_pass', 'debt_ratio', 'dart_roe', 'fcf']:
            df_master[col] = 0.0
            
    df_master = df_master.fillna(0).reset_index().rename(columns={'티커': 'stock_code', 'index': 'stock_code'})

    df_master['sector_name'] = df_master['stock_code'].map(sector_map).fillna('분류안됨')
    df_master['corp_name'] = df_master['stock_code'].apply(lambda x: stock.get_market_ticker_name(x))
    
    # P1: ROE 출처 분리 — market_roe(시장 역산)와 dart_roe(DART 실적) 명시적 분리
    # ROE(스크리너 기준) = dart_roe 우선(실제 장부), 없으면 market_roe(시장 추정) 폴백
    df_master['market_roe'] = df_master.apply(lambda x: round((x['PBR'] / x['PER'] * 100), 2) if x['PER'] > 0 else 0.0, axis=1)
    df_master['ROE'] = df_master.apply(lambda x: x['dart_roe'] if x.get('dart_roe', 0) != 0 else x['market_roe'], axis=1)
    df_master['PSR'] = df_master.apply(lambda x: (x['시가총액'] / x['revenue']) if x['revenue'] > 0 else 0.0, axis=1)
    # 🌟 추가: 각 기업 데이터의 완전성 플래그 (PER, PBR, 매출 모두 >0일 때 완전)
    df_master['is_complete'] = ((df_master['PER'] > 0) & (df_master['PBR'] > 0) & (df_master['revenue'] > 0)).astype(int)

# 🌟 5. 네이버/토스증권 방식: 시가총액 가중평균 (합산 연산 엔진)
    print("✅ 섹터별 시가총액 가중평균(업종 지표) 연산 중...")
    
    # 적자 기업(PER < 0)은 업종 PER 계산을 왜곡하므로 통상적으로 제외합니다.
    valid_fund = df_master[df_master['PER'] > 0].copy()
    
    # 1단계: 주어진 PER, PBR을 역산하여 각 기업의 '순이익'과 '자본총계'의 추정치(Implied)를 복원합니다.
    valid_fund['implied_ni'] = valid_fund['시가총액'] / valid_fund['PER']
    valid_fund['implied_eq'] = valid_fund['시가총액'] / valid_fund['PBR']
    
    # 2단계: 섹터별로 시가총액, 순이익, 자본총계, 매출액을 모두 합산(Sum)하여 하나의 '거대 섹터 기업'으로 만듭니다.
    sector_sums = valid_fund.groupby('sector_name')[['시가총액', 'implied_ni', 'implied_eq', 'revenue']].sum()
    
    # 3단계: 합산된 덩어리 데이터로 '진짜 업종 지표'를 도출합니다.
    # P1: 컬럼명 sector_* 로 통일 — median_* 는 실제 중앙값이 아닌 시총 가중평균이라 오해 소지
    sector_metrics = pd.DataFrame()
    sector_metrics['sector_per'] = sector_sums['시가총액'] / sector_sums['implied_ni']
    sector_metrics['sector_pbr'] = sector_sums['시가총액'] / sector_sums['implied_eq']

    # PSR은 합산 매출액이 0보다 클 때만 계산 (ZeroDivision 방어)
    sector_metrics['sector_psr'] = sector_sums.apply(
        lambda x: x['시가총액'] / x['revenue'] if x['revenue'] > 0 else 0, axis=1
    )

    # 업종 ROE = (업종 총 순이익 / 업종 총 자본) * 100
    sector_metrics['sector_roe'] = (sector_sums['implied_ni'] / sector_sums['implied_eq']) * 100

    # 매출 CAGR은 규모 편차가 크므로 실제 섹터 중앙값(Median) 사용
    sector_metrics['sector_rev_cagr'] = valid_fund.groupby('sector_name')['rev_cagr_3y'].median()
    
    sector_metrics = sector_metrics.reset_index()
    
    # 4단계: 기존 마스터 데이터에 네이버증권 방식의 지표를 병합합니다.
    df_master = pd.merge(df_master, sector_metrics, on='sector_name', how='left').fillna(0)
    
    # 최종 저장 컬럼 (sector_* = 시총 가중평균 벤치마크, dart_roe = DART 실적 기준)
    final_cols = ['stock_code', 'corp_name', 'sector_name', 'PER', 'PBR', 'PSR', 'ROE', 'EPS', 'DIV',
                  '시가총액', '순매수거래대금',
                  'market_roe', 'dart_roe',
                  'sector_per', 'sector_pbr', 'sector_psr', 'sector_roe', 'sector_rev_cagr',
                  'rev_cagr_3y', 'op_cagr_3y', 'eps_cagr_3y', 'ocf_pass', 'debt_ratio', 'fcf', 'is_complete']
    df_final = df_master[final_cols].copy()

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    df_final.to_sql('screener_summary', conn, if_exists='replace', index=False)
    conn.close()

    elapsed = round(time.time() - start_time, 2)
    print(f"🎉 배치 완료! 1차 상대 가치 평가 파이프라인 구축 성공 (소요시간: {elapsed}초)")

if __name__ == "__main__":
    run_daily_batch()