from sqlalchemy import Column, String
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine

MasterBase = declarative_base()

class CompanyMaster(MasterBase):
    """기업 고유번호 마스터 테이블 (고유번호.db 전용)"""
    __tablename__ = 'company_master'
    
    corp_code = Column(String(8), primary_key=True)   # DART 고유번호 (8자리)
    corp_name = Column(String(100), nullable=False)   # 기업명
    stock_code = Column(String(6), nullable=True)     # 주식 종목코드 (6자리)

def init_master_db(db_url="sqlite:///data/고유번호.db"):
    # 🌟 파일명을 명시적으로 '고유번호.db'로 지정하여 독립된 파일을 생성합니다.
    engine = create_engine(db_url)
    MasterBase.metadata.create_all(engine)
    return engine