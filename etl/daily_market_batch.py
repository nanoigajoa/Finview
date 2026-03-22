"""
daily_market_batch.py
=====================
매일 실행 (평일 18:00 KST)
역할: KRX 시장 데이터만 갱신 → screener_summary 재생성

빠름 (~2~3분): DART 호출 없음. KRX + screener_quality 읽기 + 섹터 계산만.
"""

import pandas as pd
from pykrx import stock
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import sqlite3
import os
import time
import json
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", ".env"))


def _has_market_data(date_str):
    """삼성전자 OHLCV로 해당 날짜에 실제 거래 데이터가 있는지 확인"""
    try:
        df = stock.get_market_ohlcv_by_date(date_str, date_str, "005930")
        return not df.empty
    except Exception:
        return False


def get_safe_business_day():
    today = datetime.today()
    if today.hour < 18:
        today -= timedelta(days=1)
    # 최근 실거래일 탐색 — OHLCV 데이터 존재 여부로 검증 (최대 14일)
    for _ in range(14):
        if today.weekday() <= 4:
            target_date = today.strftime("%Y%m%d")
            if _has_market_data(target_date):
                break
        today -= timedelta(days=1)
    else:
        today = datetime.today()
        while today.weekday() > 4:
            today -= timedelta(days=1)
        target_date = today.strftime("%Y%m%d")

    month_ago = today - timedelta(days=30)
    for _ in range(14):
        if month_ago.weekday() <= 4:
            month_date = month_ago.strftime("%Y%m%d")
            if _has_market_data(month_date):
                break
        month_ago -= timedelta(days=1)
    else:
        month_ago = today - timedelta(days=30)
        while month_ago.weekday() > 4:
            month_ago -= timedelta(days=1)
        month_date = month_ago.strftime("%Y%m%d")

    return target_date, month_date


def run_daily_market_batch():
    print("📈 일배치 시작 — KRX 시장 데이터 갱신...")
    start_time = time.time()

    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "finance.db")
    target_date, one_month_ago = get_safe_business_day()
    print(f"  기준일: {target_date} / 1개월 전: {one_month_ago}")

    # ── 1. 섹터 매핑 ────────────────────────────────────────────────
    print("✅ 섹터 매핑 로드 중...")
    try:
        df_fdr = fdr.StockListing('KRX-DESC')
        code_col = 'Code' if 'Code' in df_fdr.columns else 'Symbol'
        df_fdr = df_fdr.dropna(subset=['Sector'])
        sector_map = dict(zip(df_fdr[code_col], df_fdr['Sector']))
    except Exception as e:
        print(f"  섹터 API 실패: {e}")
        sector_map = {}

    # ── 2. KRX 시장 데이터 ─────────────────────────────────────────
    print("✅ KRX 시가총액 / 펀더멘털 / 기관수급 수집 중...")

    # 기존 screener_summary 로드 — pykrx API 실패 시 폴백용
    try:
        _conn_prev = sqlite3.connect(db_path)
        df_prev = pd.read_sql(
            "SELECT stock_code, 시가총액, PER, PBR, EPS, DIV FROM screener_summary", _conn_prev
        )
        _conn_prev.close()
        df_prev = df_prev.set_index('stock_code')
        print(f"  → 기존 screener_summary {len(df_prev)}개 종목 폴백 준비")
    except Exception:
        df_prev = pd.DataFrame()

    # 시가총액
    try:
        df_cap = pd.concat([stock.get_market_cap(target_date, market="KOSPI"),
                             stock.get_market_cap(target_date, market="KOSDAQ")])
        print(f"  → 시가총액 수집 성공: {len(df_cap)}개")
    except Exception as e:
        print(f"  [경고] get_market_cap 실패 ({type(e).__name__}). 기존 데이터 사용.")
        df_cap = df_prev[['시가총액']].copy() if not df_prev.empty else pd.DataFrame(columns=['시가총액'])

    # 펀더멘털 (PER/PBR/EPS/DIV)
    try:
        df_fund = pd.concat([stock.get_market_fundamental(target_date, market="KOSPI"),
                              stock.get_market_fundamental(target_date, market="KOSDAQ")])
        print(f"  → 펀더멘털 수집 성공: {len(df_fund)}개")
    except Exception as e:
        print(f"  [경고] get_market_fundamental 실패 ({type(e).__name__}). 기존 데이터 사용.")
        fund_cols = [c for c in ['PER', 'PBR', 'EPS', 'DIV'] if not df_prev.empty and c in df_prev.columns]
        df_fund = df_prev[fund_cols].copy() if fund_cols else pd.DataFrame(columns=['PER', 'PBR', 'EPS', 'DIV'])

    # 기관수급
    try:
        df_inst = pd.concat([
            stock.get_market_net_purchases_of_equities_by_ticker(one_month_ago, target_date, market="KOSPI",  investor="기관합계"),
            stock.get_market_net_purchases_of_equities_by_ticker(one_month_ago, target_date, market="KOSDAQ", investor="기관합계"),
        ])
        print(f"  → 기관수급 수집 성공: {len(df_inst)}개")
    except Exception as e:
        print(f"  [경고] 기관수급 실패 ({type(e).__name__}). 0으로 초기화.")
        df_inst = pd.DataFrame(columns=['순매수거래대금'])

    df_cap.index  = df_cap.index.astype(str)
    df_fund.index = df_fund.index.astype(str)
    df_inst.index = df_inst.index.astype(str)

    df_market = df_cap[['시가총액']].join(df_fund[['PER', 'PBR', 'EPS', 'DIV']], how='left')
    inst_col = next((c for c in ['순매수거래대금', '순매수금액', '매수금액'] if c in df_inst.columns), None)
    if inst_col:
        df_market = df_market.join(df_inst[[inst_col]].rename(columns={inst_col: '순매수거래대금'}), how='left')
    else:
        df_market['순매수거래대금'] = 0
    df_market = df_market.fillna(0).reset_index().rename(columns={'티커': 'stock_code', 'index': 'stock_code'})

    # ── 3. 분기 품질 데이터 읽기 (quarterly_dart_batch.py 산출물) ───
    print("✅ 분기 재무 품질 데이터(screener_quality) 로드 중...")
    try:
        conn = sqlite3.connect(db_path)
        df_quality = pd.read_sql("SELECT * FROM screener_quality", conn)
        conn.close()
        df_quality = df_quality.set_index('stock_code')
        print(f"  → {len(df_quality)}개 종목 품질 데이터 로드 완료")
    except Exception as e:
        print(f"  → screener_quality 없음 ({e}). 품질 컬럼 0으로 초기화.")
        df_quality = pd.DataFrame()

    # ── 4. 시장 + 품질 병합 ────────────────────────────────────────
    df_master = df_market.set_index('stock_code')
    if not df_quality.empty:
        df_master = df_master.join(df_quality, how='left')
    else:
        for col in ['corp_name', 'revenue', 'rev_cagr_3y', 'op_cagr_3y', 'eps_cagr_3y',
                    'ocf_pass', 'debt_ratio', 'dart_roe', 'fcf']:
            df_master[col] = 0.0

    df_master = df_master.fillna(0).reset_index().rename(columns={'index': 'stock_code'})

    # corp_name: 품질 데이터에 없으면 pykrx에서 보완
    if 'corp_name' not in df_master.columns or (df_master['corp_name'] == 0).all():
        df_master['corp_name'] = df_master['stock_code'].apply(
            lambda x: stock.get_market_ticker_name(x) if x else ''
        )

    df_master['sector_name'] = df_master['stock_code'].map(sector_map).fillna('분류안됨')

    # ── 5. DART 기반 지표 보정 — pykrx EPS/PBR/시가총액 stale 문제 해결 ──────
    # dart_eps, dart_bps, dart_shares가 screener_quality에서 JOIN됐으면 사용
    # pykrx PER/PBR이 stale이거나 0인 종목을 DART + OHLCV 현재가로 재계산
    print("✅ DART 기반 PER/PBR/시가총액 보정 중...")
    ohlcv_prices = {}
    tickers_need_price = df_master[
        (df_master.get('dart_eps', pd.Series(0, index=df_master.index)) != 0) &
        ((df_master['PER'] == 0) | (df_master['PER'] > 200))
    ]['stock_code'].tolist() if 'dart_eps' in df_master.columns else []

    if tickers_need_price:
        print(f"  → OHLCV 현재가 수집 대상: {len(tickers_need_price)}개 (PER 이상치/결측 종목)")
        try:
            df_ohlcv_all = stock.get_market_ohlcv_by_date(target_date, target_date, tickers_need_price[0])
        except Exception:
            df_ohlcv_all = pd.DataFrame()

    def recalc_market_metrics(row):
        dart_eps    = row.get('dart_eps', 0)
        dart_bps    = row.get('dart_bps', 0)
        dart_shares = row.get('dart_shares', 0)
        per_orig    = row.get('PER', 0)
        pbr_orig    = row.get('PBR', 0)
        cap_orig    = row.get('시가총액', 0)
        rev         = row.get('revenue', 0)

        # pykrx PER/PBR이 유효하면 그대로 사용
        per_valid = 0 < per_orig < 200
        pbr_valid = 0 < pbr_orig < 50

        # DART EPS 기반 현재가 역산: 현재가 ≈ EPS × PER (stale이지만 오더 수준은 맞음)
        # → 시가총액 = 현재가 × 발행주식수 (DART 기반)
        if dart_shares > 0 and cap_orig > 0:
            price_implied = cap_orig / dart_shares
        elif dart_eps != 0 and per_orig > 0:
            price_implied = dart_eps * per_orig
        else:
            price_implied = 0

        per_new = round(price_implied / dart_eps, 2)   if (dart_eps > 0 and price_implied > 0) else per_orig
        pbr_new = round(price_implied / dart_bps, 2)   if (dart_bps > 0 and price_implied > 0) else pbr_orig
        cap_new = round(price_implied * dart_shares)    if (dart_shares > 0 and price_implied > 0) else cap_orig
        psr_new = round(cap_new / rev, 4)               if (rev > 0 and cap_new > 0) else 0.0

        return pd.Series({
            'PER':   per_orig if per_valid else per_new,
            'PBR':   pbr_orig if pbr_valid else pbr_new,
            '시가총액': cap_orig if cap_orig > 0 else cap_new,
            'PSR':   psr_new,
        })

    if 'dart_eps' in df_master.columns:
        recalc = df_master.apply(recalc_market_metrics, axis=1)
        df_master['PER']    = recalc['PER']
        df_master['PBR']    = recalc['PBR']
        df_master['시가총액'] = recalc['시가총액']
        df_master['PSR']    = recalc['PSR']
        print(f"  → DART 기반 보정 완료")
    else:
        df_master['PSR'] = df_master.apply(
            lambda x: (x['시가총액'] / x['revenue']) if x.get('revenue', 0) > 0 else 0.0, axis=1
        )

    df_master['market_roe'] = df_master.apply(
        lambda x: round((x['PBR'] / x['PER'] * 100), 2) if x['PER'] > 0 else 0.0, axis=1
    )
    df_master['ROE'] = df_master.apply(
        lambda x: x['dart_roe'] if x.get('dart_roe', 0) != 0 else x['market_roe'], axis=1
    )
    df_master['is_complete'] = (
        (df_master['PER'] > 0) & (df_master['PBR'] > 0) &
        (df_master.get('revenue', pd.Series(0, index=df_master.index)) > 0)
    ).astype(int)

    # ── TTM EPS / TTM PER 계산 ──────────────────────────────────────
    # EPS 베이스: DART dart_eps 우선, 없으면 pykrx EPS
    # TTM EPS = EPS_base × (ttm_ni / annual_ni)
    # ttm_source = 'annual_prev'이면 실질적 TTM 없음 → ttm_per = 0 (N/A 표시)
    def calc_ttm(row):
        annual_ni   = row.get('annual_ni', 0)
        ttm_ni      = row.get('ttm_ni', 0)
        ttm_source  = row.get('ttm_source', 'annual_prev')
        eps_base    = row.get('dart_eps', 0) or row.get('EPS', 0)
        per_base    = row.get('PER', 0)

        # annual_prev이면 TTM 데이터 없음 — 0 반환해서 프론트에서 N/A 표시
        if ttm_source == 'annual_prev' or annual_ni <= 0 or ttm_ni <= 0 or eps_base <= 0:
            return pd.Series({'ttm_eps': 0.0, 'ttm_per': 0.0})

        factor = ttm_ni / annual_ni
        return pd.Series({
            'ttm_eps': round(eps_base * factor, 2),
            'ttm_per': round(per_base / factor, 2) if per_base > 0 else 0.0,
        })

    ttm_df = df_master.apply(calc_ttm, axis=1)
    df_master['ttm_eps'] = ttm_df['ttm_eps']
    df_master['ttm_per'] = ttm_df['ttm_per']
    if 'ttm_source' not in df_master.columns:
        df_master['ttm_source'] = 'annual_prev'

    # ── 6. 섹터 시총 가중평균 계산 ─────────────────────────────────
    print("✅ 섹터 벤치마크(시총 가중평균 PER/PBR/PSR/ROE) 계산 중...")
    valid = df_master[(df_master['PER'] > 0) & (df_master['PER'] < 200)].copy()
    valid['implied_ni'] = valid['시가총액'] / valid['PER']
    valid['implied_eq'] = valid['시가총액'] / valid['PBR'].replace(0, float('nan'))

    sector_sums = valid.groupby('sector_name')[['시가총액', 'implied_ni', 'implied_eq', 'revenue']].sum()
    sector_metrics = pd.DataFrame()
    sector_metrics['sector_per'] = sector_sums['시가총액'] / sector_sums['implied_ni']
    sector_metrics['sector_pbr'] = sector_sums['시가총액'] / sector_sums['implied_eq']
    sector_metrics['sector_psr'] = sector_sums.apply(
        lambda x: x['시가총액'] / x['revenue'] if x['revenue'] > 0 else 0, axis=1
    )
    sector_metrics['sector_roe'] = (sector_sums['implied_ni'] / sector_sums['implied_eq']) * 100
    sector_metrics['sector_rev_cagr'] = valid.groupby('sector_name')['rev_cagr_3y'].median() \
        if 'rev_cagr_3y' in valid.columns else 0.0
    sector_metrics = sector_metrics.reset_index()

    df_master = pd.merge(df_master, sector_metrics, on='sector_name', how='left').fillna(0)

    # ── 7. 최종 컬럼 정리 및 저장 ──────────────────────────────────
    final_cols = [
        'stock_code', 'corp_name', 'sector_name',
        'PER', 'PBR', 'PSR', 'ROE', 'EPS', 'DIV',
        '시가총액', '순매수거래대금',
        'market_roe', 'dart_roe',
        'sector_per', 'sector_pbr', 'sector_psr', 'sector_roe', 'sector_rev_cagr',
        'rev_cagr_3y', 'op_cagr_3y', 'eps_cagr_3y', 'ocf_pass', 'debt_ratio', 'fcf', 'is_complete',
        'ttm_eps', 'ttm_per', 'ttm_source',
    ]
    # 없는 컬럼은 0으로 채움
    for col in final_cols:
        if col not in df_master.columns:
            df_master[col] = 0

    df_final = df_master[final_cols].copy()

    conn = sqlite3.connect(db_path)
    df_final.to_sql('screener_summary', conn, if_exists='replace', index=False)
    conn.close()

    # ── 8. data_registry 업데이트 ──────────────────────────────────
    print("✅ data_registry market 항목 업데이트 중...")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS data_registry (
        stock_code TEXT, data_type TEXT, last_success TEXT, status TEXT, note TEXT,
        PRIMARY KEY (stock_code, data_type))''')
    registry_rows = []
    for _, row in df_final.iterrows():
        sc = row['stock_code']
        has_per = row['PER'] > 0
        if has_per:
            registry_rows.append((sc, 'market', now_str, 'ok', ''))
        else:
            registry_rows.append((sc, 'market', None, 'partial', 'PER 없음 (적자 또는 상장폐지)'))
    cursor.executemany('''INSERT OR REPLACE INTO data_registry
        (stock_code, data_type, last_success, status, note) VALUES (?, ?, ?, ?, ?)''', registry_rows)
    conn.commit()
    conn.close()
    print(f"  → data_registry market {len(registry_rows)}개 종목 기록")

    elapsed = round(time.time() - start_time, 2)
    print(f"🎉 일일배치 완료! screener_summary {len(df_final)}개 종목 갱신 (소요: {elapsed}초)")


if __name__ == "__main__":
    run_daily_market_batch()
