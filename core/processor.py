import pandas as pd

class FinancialDataProcessor:
    """수집된 재무 데이터를 정제하고 파생 지표를 계산하는 클래스"""
    
    def parse_to_dataframe(self, json_data: dict) -> pd.DataFrame:
        if json_data and json_data.get("status") == "000":
            return pd.DataFrame(json_data["list"])
        return pd.DataFrame()

    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
            
        df['thstrm_amount'] = df['thstrm_amount'].astype(str).str.replace(',', '', regex=False)
        df['thstrm_amount'] = pd.to_numeric(df['thstrm_amount'], errors='coerce')
        df['amount_in_hundred_million'] = df['thstrm_amount'] / 100000000
        return df

    def extract_metrics(self, clean_df: pd.DataFrame) -> dict:
        if clean_df.empty:
            return {}

        def get_val(keywords):
            pattern = '|'.join(keywords)
            rows = clean_df[clean_df['account_nm'].str.contains(pattern, regex=True, na=False)]
            if rows.empty:
                return 0.0
            cfs_rows = rows[rows['fs_div'] == 'CFS'] if 'fs_div' in rows.columns else pd.DataFrame()
            target = cfs_rows if not cfs_rows.empty else rows
            return target['amount_in_hundred_million'].values[0]

        # 1. 원본 팩트 데이터 추출
# 1. 원본 팩트 데이터 추출 (기존과 동일)
        revenue = get_val(['매출액', '수익\(매출액\)'])
        op_income = get_val(['영업이익'])
        net_income = get_val(['당기순이익', '연결당기순이익'])
        equity = get_val(['자본총계'])
        liabilities = get_val(['부채총계'])
        op_cash_flow = get_val(['영업활동현금흐름', '영업활동으로 인한 현금흐름'])
        # CAPEX: 현금유출이므로 DART에서 음수로 기록 → abs()로 양수화
        capex = abs(get_val(['유형자산의 취득', '유형자산취득']))

        if op_cash_flow == 0.0 and op_income > 0:
            op_cash_flow = op_income * 1.2  # OCF 누락 시 영업이익 기반 추정

        # 2. 파생 지표 자체 계산
        roe = (net_income / equity * 100) if equity else 0.0
        op_margin = (op_income / revenue * 100) if revenue else 0.0
        debt_ratio = (liabilities / equity * 100) if equity else 0.0

        # FCF = OCF - CAPEX (CAPEX 데이터 있으면 직접 계산, 없으면 OCF의 80% 보수적 추정)
        if capex > 0:
            fcf = op_cash_flow - capex
        else:
            fcf = op_cash_flow * 0.8

        return {
            'revenue': revenue,
            'operating_income': op_income,
            'net_income': net_income,
            'op_cash_flow': op_cash_flow,
            'roe': roe,
            'op_margin': op_margin,
            'debt_ratio': debt_ratio,
            'fcf': fcf
        }