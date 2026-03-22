"""
quarterly_dart_batch.py
=======================
분기 1회 실행 (2월 / 5월 / 8월 / 11월 15일 18:00 KST)
역할: DART 전 종목 재무제표 수집 → screener_quality 저장

느림 (~10~20분): 2,500개 기업 × 4년치 DART API 벌크 호출.
일배치(daily_market_batch.py)가 이 테이블을 읽어서 screener_summary를 만든다.
"""

import pandas as pd
from pykrx import stock
import requests
import sqlite3
import os
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", ".env"))


def run_quarterly_batch(progress_cb=None):
    def log(msg):
        print(msg)
        if progress_cb:
            progress_cb(msg)

    log("📊 분기배치 시작 — DART 전 종목 재무 품질 데이터 수집...")
    start_time = time.time()

    db_path        = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "finance.db")
    master_db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "고유번호.db")
    api_key        = os.getenv("DART_API_KEY", "")

    if not api_key:
        log("❌ DART_API_KEY 없음. config/.env 또는 GitHub Secrets를 확인하세요.")
        return

    # ── 1. 마스터 DB에서 전 종목 corp_code 로드 ────────────────────
    log("✅ 종목 마스터 로드 중...")
    conn_master = sqlite3.connect(master_db_path)
    df_master_code = pd.read_sql("SELECT stock_code, corp_code, corp_name FROM company_master", conn_master)
    conn_master.close()
    corp_codes = df_master_code['corp_code'].dropna().tolist()
    log(f"  → {len(corp_codes)}개 종목 대상")

    # ── 2. DART 벌크 API — 4년치 재무데이터 수집 ──────────────────
    log("✅ DART 벌크 API 수집 중 (2021~2024, CFS 우선)...")
    years = ['2021', '2022', '2023', '2024']
    fin_data = {code: {y: {} for y in years} for code in corp_codes}

    for year in years:
        log(f"  [{year}] 수집 중...")
        for i in range(0, len(corp_codes), 100):
            chunk = ",".join(corp_codes[i:i + 100])
            url = (
                f"https://opendart.fss.or.kr/api/fnlttMultiAcnt.json"
                f"?crtfc_key={api_key}&corp_code={chunk}&bsns_year={year}&reprt_code=11011"
            )
            try:
                res = requests.get(url, timeout=30).json()
            except Exception as e:
                log(f"    청크 {i}~{i+100} 오류: {e}")
                continue

            if res.get("status") != "000":
                continue

            for item in res.get("list", []):
                code = item.get("corp_code")
                acct = item.get("account_nm")
                raw  = str(item.get("thstrm_amount", "0")).strip().replace(',', '')
                try:
                    amt = 0.0 if raw in ['-', '', 'NaN'] else float(raw)
                except ValueError:
                    amt = 0.0

                fd  = fin_data.get(code, {}).get(year, {})
                cfs = item.get("fs_div") == "CFS"

                def set_if_cfs(key, val):
                    if key not in fd or cfs:
                        fin_data[code][year][key] = val

                if   acct in ["매출액", "수익(매출액)", "영업수익"]:            set_if_cfs('rev',   amt)
                elif acct in ["영업이익", "영업이익(손실)"]:                    set_if_cfs('op',    amt)
                elif acct in ["당기순이익", "당기순이익(손실)"]:                set_if_cfs('ni',    amt)
                elif acct == "부채총계":                                        set_if_cfs('liab',  amt)
                elif acct == "자본총계":                                        set_if_cfs('eq',    amt)
                elif acct in ["영업활동현금흐름", "영업활동으로 인한 현금흐름"]: set_if_cfs('ocf',   amt)
                elif acct in ["유형자산의 취득", "유형자산취득"]:               set_if_cfs('capex', abs(amt))
                # DART 기반 EPS/BPS — pykrx 의존 제거용
                elif acct in ["주당순이익", "기본주당순이익(손실)", "기본주당순이익"]:
                    set_if_cfs('dart_eps', amt)
                elif acct in ["주당순자산", "주당순자산가치"]:
                    set_if_cfs('dart_bps', amt)

        time.sleep(0.5)  # DART API 부하 방지

    # ── 2b. TTM용 중간보고서 수집 (상반기 11012 / 3분기누적 11013) ──
    # prev_year(2024)와 current_year(2025/2026) 대상 — 정확한 TTM 역산을 위해 필요
    current_year = str(datetime.now().year)
    prev_year    = str(datetime.now().year - 1)
    interim_keys = [
        (prev_year,    '11012', 'ni_h1'),
        (prev_year,    '11013', 'ni_q3ytd'),
        (current_year, '11011', 'ni_annual_cy'),
        (current_year, '11012', 'ni_h1_cy'),
        (current_year, '11013', 'ni_q3ytd_cy'),
    ]
    for yr, reprt_code, field_key in interim_keys:
        log(f"  [TTM] {yr} reprt={reprt_code} ({field_key}) 수집 중...")
        collected = 0
        for i in range(0, len(corp_codes), 100):
            chunk = ",".join(corp_codes[i:i + 100])
            url = (
                f"https://opendart.fss.or.kr/api/fnlttMultiAcnt.json"
                f"?crtfc_key={api_key}&corp_code={chunk}&bsns_year={yr}&reprt_code={reprt_code}"
            )
            try:
                res = requests.get(url, timeout=30).json()
            except Exception as e:
                continue
            if res.get("status") != "000":
                continue
            for item in res.get("list", []):
                code = item.get("corp_code")
                acct = item.get("account_nm")
                if acct not in ["당기순이익", "당기순이익(손실)"]:
                    continue
                raw = str(item.get("thstrm_amount", "0")).strip().replace(',', '')
                try:
                    amt = 0.0 if raw in ['-', '', 'NaN'] else float(raw)
                except ValueError:
                    amt = 0.0
                cfs = item.get("fs_div") == "CFS"
                if code in fin_data:
                    if yr not in fin_data[code]:
                        fin_data[code][yr] = {}
                    existing = fin_data[code][yr].get(field_key)
                    if existing is None or cfs:
                        fin_data[code][yr][field_key] = amt
                        collected += 1
            time.sleep(0.3)
        log(f"    → {collected}건 수집")

    # ── 3. 품질 지표 계산 ──────────────────────────────────────────
    log("✅ 재무 품질 지표 계산 중 (CAGR / OCF / FCF / 부채비율)...")
    quality_list = []
    for _, row in df_master_code.iterrows():
        code       = row['corp_code']
        stock_code = row['stock_code']
        corp_name  = row['corp_name']
        fd         = fin_data.get(code, {})

        r21, r24 = fd.get('2021', {}).get('rev', 0), fd.get('2024', {}).get('rev', 0)
        o21, o24 = fd.get('2021', {}).get('op',  0), fd.get('2024', {}).get('op',  0)
        ni21, ni24 = fd.get('2021', {}).get('ni', 0), fd.get('2024', {}).get('ni', 0)

        rev_cagr = (((r24 / r21) ** (1/3)) - 1) * 100 if r21 > 0 and r24 > 0 else 0.0
        op_cagr  = (((o24 / o21) ** (1/3)) - 1) * 100 if o21 > 0 and o24 > 0 else 0.0
        eps_cagr = (((ni24 / ni21) ** (1/3)) - 1) * 100 if ni21 > 0 and ni24 > 0 else 0.0

        ocf22 = fd.get('2022', {}).get('ocf', 0)
        ocf23 = fd.get('2023', {}).get('ocf', 0)
        ocf24 = fd.get('2024', {}).get('ocf', 0)
        ocf_pass = 1 if (ocf22 > 0 and ocf23 > 0 and ocf24 > 0) else 0

        l24, e24 = fd.get('2024', {}).get('liab', 0), fd.get('2024', {}).get('eq', 0)
        debt_ratio = (l24 / e24) * 100 if e24 > 0 else 0.0
        dart_roe   = (ni24 / e24) * 100 if e24 > 0 else 0.0

        capex24 = fd.get('2024', {}).get('capex', 0)
        if ocf24 > 0:
            # capex가 0이면 해당 계정 없음(금융사 등) — OCF 그대로 FCF로 사용
            fcf = round((ocf24 - capex24) / 1e8, 2)
        else:
            fcf = 0.0

        dart_eps24 = fd.get('2024', {}).get('dart_eps', 0)
        dart_bps24 = fd.get('2024', {}).get('dart_bps', 0)
        # 주식수 역산: annual_ni(원) / dart_eps(원/주) — 발행주식수 추정
        dart_shares = round(ni24 / dart_eps24) if dart_eps24 != 0 else 0

        # ── TTM 순이익 계산 ──────────────────────────────────────────
        # ni_annual_prev = ni24 (fin_data['2024']['ni'])
        ni_annual_prev  = ni24
        ni_h1_prev      = fd.get(prev_year, {}).get('ni_h1',      0)
        ni_q3ytd_prev   = fd.get(prev_year, {}).get('ni_q3ytd',   0)
        ni_annual_cy    = fd.get(current_year, {}).get('ni_annual_cy', 0)
        ni_h1_cy        = fd.get(current_year, {}).get('ni_h1_cy',    0)
        ni_q3ytd_cy     = fd.get(current_year, {}).get('ni_q3ytd_cy', 0)

        if ni_annual_cy > 0:
            ttm_ni, ttm_source = ni_annual_cy, 'annual_cy'
        elif ni_q3ytd_cy > 0 and ni_annual_prev > 0 and ni_q3ytd_prev > 0:
            q4_prev = ni_annual_prev - ni_q3ytd_prev
            ttm_ni, ttm_source = ni_q3ytd_cy + q4_prev, 'q3ytd'
        elif ni_h1_cy > 0 and ni_annual_prev > 0 and ni_h1_prev > 0:
            h2_prev = ni_annual_prev - ni_h1_prev
            ttm_ni, ttm_source = ni_h1_cy + h2_prev, 'h1'
        else:
            ttm_ni, ttm_source = ni_annual_prev, 'annual_prev'

        quality_list.append({
            'stock_code':   stock_code,
            'corp_name':    corp_name,
            'revenue':      r24,
            'rev_cagr_3y':  round(rev_cagr, 2),
            'op_cagr_3y':   round(op_cagr,  2),
            'eps_cagr_3y':  round(eps_cagr, 2),
            'ocf_pass':     ocf_pass,
            'debt_ratio':   round(debt_ratio, 2),
            'dart_roe':     round(dart_roe, 2),
            'fcf':          fcf,
            'annual_ni':    ni24,          # 원 단위 (DART raw)
            'ttm_ni':       ttm_ni,        # 원 단위 (DART raw)
            'ttm_source':   ttm_source,    # 신선도 레이블
            'dart_eps':     dart_eps24,    # 주당순이익 (원/주) — pykrx EPS 대체
            'dart_bps':     dart_bps24,    # 주당순자산 (원/주) — pykrx BPS 대체
            'dart_shares':  dart_shares,   # 추정 발행주식수 (주)
        })

    df_quality = pd.DataFrame(quality_list)

    # ── 4. screener_quality 저장 ────────────────────────────────────
    conn = sqlite3.connect(db_path)
    df_quality.to_sql('screener_quality', conn, if_exists='replace', index=False)
    conn.close()

    # ── 5. data_registry 업데이트 ────────────────────────────────────
    log("✅ data_registry 업데이트 중...")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS data_registry (
        stock_code TEXT, data_type TEXT, last_success TEXT, status TEXT, note TEXT,
        PRIMARY KEY (stock_code, data_type))''')
    registry_rows = []
    for item in quality_list:
        sc = item['stock_code']
        has_data = item.get('revenue', 0) > 0
        if has_data:
            registry_rows.append((sc, 'finance', now_str, 'ok', ''))
        else:
            registry_rows.append((sc, 'finance', None, 'missing', 'DART 재무 데이터 없음'))
    cursor.executemany('''INSERT OR REPLACE INTO data_registry
        (stock_code, data_type, last_success, status, note) VALUES (?, ?, ?, ?, ?)''', registry_rows)
    conn.commit()
    conn.close()
    log(f"  → data_registry finance {len(registry_rows)}개 종목 기록")

    elapsed = round(time.time() - start_time, 2)
    log(f"🎉 분기배치 완료! screener_quality {len(df_quality)}개 종목 저장 (소요: {elapsed}초)")
    log("   → 이제 daily_market_batch.py 를 실행하면 screener_summary가 갱신됩니다.")


if __name__ == "__main__":
    run_quarterly_batch()
