# from pykrx.stock.market import core as _c
# import inspect
# # 내부 fetcher 클래스 확인
# print([x for x in dir(_c) if not x.startswith('_')])

import pandas as pd
from pykrx import stock

# DataFrame.__getitem__ 임시 패치 — pykrx가 죽기 직전 df 캡처
_orig = pd.DataFrame.__getitem__
_caught = {}

def _debug(self, key):
    try:
        return _orig(self, key)
    except KeyError:
        if isinstance(key, (list, pd.Index)):
            _caught['df'] = self
        raise

pd.DataFrame.__getitem__ = _debug
try:
    stock.get_market_cap("20260320", market="KOSPI")
except:
    if 'df' in _caught:
        print("실제 컬럼:", list(_caught['df'].columns))
        print(_caught['df'].head(2))
finally:
    pd.DataFrame.__getitem__ = _orig