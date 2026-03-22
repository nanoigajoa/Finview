"""
quarterly_processor.py
======================
DART 3종 보고서(연간/상반기/3분기누적)로부터 분기별 독립 수치를 계산한다.

계산 공식:
  상반기(H1)      = 11012 보고서 그대로
  Q3 standalone  = 11013(YTD) − 11012(H1)
  Q4 standalone  = 11011(Annual) − 11013(YTD)
  연간합계        = 11011 보고서 그대로

반환 구조:
  {
    "h1":      {"revenue": ..., "op_income": ..., "net_income": ..., "ocf": ...},
    "q3":      {...},
    "q4":      {...},
    "annual":  {...},
  }
"""

_ACCOUNT_MAP = {
    "revenue":    ["매출액", "수익(매출액)", "영업수익"],
    "op_income":  ["영업이익", "영업이익(손실)"],
    "net_income": ["당기순이익", "당기순이익(손실)"],
    "ocf":        ["영업활동현금흐름", "영업활동으로 인한 현금흐름"],
}


def _extract(items: list, prefer_cfs: bool = True) -> dict:
    """DART list 항목에서 계정별 금액을 추출한다 (억 원 단위)."""
    result = {k: None for k in _ACCOUNT_MAP}

    for item in items:
        acct = item.get("account_nm", "")
        is_cfs = item.get("fs_div") == "CFS"
        raw = str(item.get("thstrm_amount", "0")).strip().replace(",", "")
        try:
            amt = 0.0 if raw in ["-", "", "NaN"] else float(raw)
        except ValueError:
            amt = 0.0

        # 억 원 변환
        amt_hundredm = amt / 1e8

        for key, keywords in _ACCOUNT_MAP.items():
            if acct in keywords:
                if result[key] is None or (prefer_cfs and is_cfs):
                    result[key] = amt_hundredm
                break

    # None → 0.0
    return {k: (v if v is not None else 0.0) for k, v in result.items()}


def compute_quarterly(annual_items: list, h1_items: list, q3_ytd_items: list) -> dict:
    """3종 보고서 list로부터 분기별 독립 수치를 계산한다."""
    annual = _extract(annual_items)
    h1     = _extract(h1_items)
    q3_ytd = _extract(q3_ytd_items)

    def sub(a, b):
        return round(a - b, 2)

    q3 = {k: sub(q3_ytd[k], h1[k]) for k in _ACCOUNT_MAP}
    q4 = {k: sub(annual[k], q3_ytd[k]) for k in _ACCOUNT_MAP}

    return {
        "h1":     {k: round(h1[k], 2)     for k in _ACCOUNT_MAP},
        "q3":     q3,
        "q4":     q4,
        "annual": {k: round(annual[k], 2) for k in _ACCOUNT_MAP},
    }
