from sqlalchemy import Column, Integer, String, Float, UniqueConstraint
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine

Base = declarative_base()

class FinancialReport(Base):
    """재무 리포트 팩트 테이블 (순이익, 현금흐름 방 추가 완료)"""
    __tablename__ = 'financial_reports'
    
    __table_args__ = (UniqueConstraint('corp_code', 'year', name='uq_corp_year'),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    corp_name = Column(String(50), nullable=False)
    corp_code = Column(String(8), nullable=False)
    year = Column(Integer, nullable=False)
    
    # 원본 팩트 데이터 컬럼
    revenue = Column(Float)
    operating_income = Column(Float)
    net_income = Column(Float)      # 추가됨
    op_cash_flow = Column(Float)    # 추가됨
    
    # 자체 계산 파생 지표 컬럼
    roe = Column(Float)
    op_margin = Column(Float)
    debt_ratio = Column(Float)
    fcf = Column(Float)

def init_db(db_url="sqlite:///data/finance.db"):
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return engine