# Skill: dart-api-client

- **Purpose:** OpenDART 공시 API에서 연결재무제표를 안정적으로 수집한다.
- **Inputs:** `corp_code` (DART 8자리), `bsns_year` (사업연도), `reprt_code` (보고서 유형)
- **Outputs:** JSON 재무제표 원본 (계정과목 리스트)

## Best Practices

- `reprt_code="11011"` (사업보고서) 항상 강제 — 분기 보고서 사용 시 연결 데이터 누락 발생
- `fs_div="CFS"` 연결재무제표 강제 — 별도재무제표(`OFS`) 사용 시 대형사 왜곡
- 종목코드 → DART corp_code 매핑은 별도 마스터 DB 경유 (`company_master` 테이블)
- 마스터 DB는 `init_master.py`로 1회 초기화 후 분기마다 갱신
- API 키는 반드시 `.env` 파일 + `python-dotenv` 로드

## Anti-patterns

- ❌ 분기 보고서(`reprt_code="11013"`)로 연간 지표 계산 — 연환산 오차 발생
- ❌ 별도재무제표(`OFS`) 사용 — 지주사/대형사 매출 과소 계상
- ❌ corp_code를 하드코딩 — 마스터 DB 갱신 시 오류
- ❌ API 키를 소스코드에 직접 삽입

## Example

```python
# core/dart_api.py
import requests, os
from dotenv import load_dotenv
load_dotenv("config/.env")

class DartAPIClient:
    BASE_URL = "https://opendart.fss.or.kr/api"

    def get_financial_statement(self, corp_code: str, bsns_year: str, reprt_code: str = "11011"):
        params = {
            "crtfc_key": os.getenv("DART_API_KEY"),
            "corp_code": corp_code,
            "bsns_year": bsns_year,
            "reprt_code": reprt_code,
            "fs_div": "CFS",  # 연결재무제표 강제
        }
        resp = requests.get(f"{self.BASE_URL}/fnlttSinglAcnt.json", params=params)
        resp.raise_for_status()
        return resp.json()
```
