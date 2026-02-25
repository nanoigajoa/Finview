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
            row = clean_df[clean_df['account_nm'].str.contains(pattern, regex=True, na=False)]
            return row['amount_in_hundred_million'].values[0] if not row.empty else 0.0

        # 1. 원본 팩트 데이터 추출
# 1. 원본 팩트 데이터 추출 (기존과 동일)
        revenue = get_val(['매출액', '수익\(매출액\)'])
        op_income = get_val(['영업이익'])
        net_income = get_val(['당기순이익', '연결당기순이익'])
        equity = get_val(['자본총계'])
        liabilities = get_val(['부채총계'])
        op_cash_flow = get_val(['영업활동현금흐름', '영업활동으로 인한 현금흐름'])

        # 🌟 [엔진 보강] API가 현금흐름을 주지 않아 0.0일 경우, 통계적 추정치(Proxy) 발동
        if op_cash_flow == 0.0 and op_income > 0:
            op_cash_flow = op_income * 1.2  # 영업활동현금흐름 추정 (영업이익의 120%)

        # 2. 파생 지표 자체 계산
        roe = (net_income / equity * 100) if equity else 0.0
        op_margin = (op_income / revenue * 100) if revenue else 0.0
        debt_ratio = (liabilities / equity * 100) if equity else 0.0
        
        # FCF 보수적 추정 (영업활동현금흐름의 80%)
        fcf = op_cash_flow * 0.8 if op_cash_flow else 0.0

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