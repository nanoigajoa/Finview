import requests
import time

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

    def get_bulk_financial_statements(self, corp_codes: list, bsns_year: str,
                                      reprt_code: str = "11011", chunk_size: int = 100) -> list:
        """최대 100개 종목을 한 번에 조회하는 벌크 API (fnlttMultiAcnt).
        corp_codes 전체를 chunk_size 단위로 나눠 호출하고, list 항목 전체를 합쳐 반환."""
        all_items = []
        url = f"{self.base_url}/fnlttMultiAcnt.json"
        for i in range(0, len(corp_codes), chunk_size):
            chunk = ",".join(corp_codes[i:i + chunk_size])
            params = {
                "crtfc_key": self.api_key,
                "corp_code": chunk,
                "bsns_year": bsns_year,
                "reprt_code": reprt_code,
            }
            try:
                res = requests.get(url, params=params, timeout=30).json()
                if res.get("status") == "000":
                    all_items.extend(res.get("list", []))
            except Exception:
                pass
            time.sleep(0.3)
        return all_items

    def get_quarterly_statements(self, corp_code: str, bsns_year: str) -> dict:
        """단일 종목의 연간(11011) + 상반기(11012) + 3분기누적(11013) 를 한 번에 조회.
        반환: {"annual": [...], "h1": [...], "q3_ytd": [...]}
        각 값이 비어 있으면 빈 list."""
        result = {}
        for key, reprt_code in [("annual", "11011"), ("h1", "11012"), ("q3_ytd", "11013")]:
            url = f"{self.base_url}/fnlttSinglAcnt.json"
            params = {
                "crtfc_key": self.api_key,
                "corp_code": corp_code,
                "bsns_year": bsns_year,
                "reprt_code": reprt_code,
                "fs_div": "CFS",
            }
            try:
                res = requests.get(url, params=params, timeout=30).json()
                result[key] = res.get("list", []) if res.get("status") == "000" else []
            except Exception:
                result[key] = []
            time.sleep(0.2)
        return result