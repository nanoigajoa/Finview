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
            
        # 쉼표(,) 제거 후 숫자형 변환
        df['thstrm_amount'] = df['thstrm_amount'].astype(str).str.replace(',', '', regex=False)
        df['thstrm_amount'] = pd.to_numeric(df['thstrm_amount'], errors='coerce')
        
        # 1억 단위 스케일링
        df['amount_in_hundred_million'] = df['thstrm_amount'] / 100000000
        return df

    def extract_metrics(self, clean_df: pd.DataFrame) -> dict:
        """스케일링된 데이터프레임에서 핵심 계정을 찾아 KPI를 계산합니다."""
        if clean_df.empty:
            return {}

        def get_val(keywords):
            pattern = '|'.join(keywords)
            row = clean_df[clean_df['account_nm'].str.contains(pattern, regex=True, na=False)]
            return row['amount_in_hundred_million'].values[0] if not row.empty else 0.0

        # 핵심 재료 추출 (단위: 억원)
        revenue = get_val(['매출액', '수익\(매출액\)'])
        op_income = get_val(['영업이익'])
        net_income = get_val(['당기순이익', '연결당기순이익'])
        equity = get_val(['자본총계'])

        # 파생 지표 자체 계산
        roe = (net_income / equity * 100) if equity else 0.0
        op_margin = (op_income / revenue * 100) if revenue else 0.0

        return {
            'revenue': revenue,
            'operating_income': op_income,
            'roe': roe,
            'op_margin': op_margin
        }