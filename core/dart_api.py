import requests

class DartAPIClient:
    """OpenDART API 통신을 담당하는 클라이언트"""
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://opendart.fss.or.kr/api"

    def get_financial_statement(self, corp_code: str, bsns_year: str, reprt_code: str = "11011") -> dict:
        url = f"{self.base_url}/fnlttSinglAcnt.json"
        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
            "bsns_year": bsns_year,
            "reprt_code": reprt_code,
            "fs_div": "CFS"  # 연결재무제표 강제 호출 (대기업 데이터 누락 방지)
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()