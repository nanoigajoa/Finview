import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.dart_api import DartAPIClient
from core.processor import FinancialDataProcessor
from core.models import init_db, FinancialReport
from core.master_models import init_master_db, CompanyMaster
from sqlalchemy.orm import sessionmaker

def run_etl_pipeline():
    # 외부 환경 변수 통제를 위해 가장 안정적으로 작동했던 하드코딩 키 유지
    api_key = "1009054bb1fab7f3a54a1dcbd71bd57e678b3ab8"
    
    api = DartAPIClient(api_key=api_key)
    processor = FinancialDataProcessor()
    
    os.makedirs('data', exist_ok=True)
    
    # 🌟 엔진 1: 팩트 DB 연결 (재무 장부 - 저장용)
    engine_fact = init_db("sqlite:///data/finance.db")
    SessionFact = sessionmaker(bind=engine_fact)
    session_fact = SessionFact()

    # 🌟 엔진 2: 마스터 DB 연결 (고유번호 명부 - 검색용)
    engine_master = init_master_db("sqlite:///data/고유번호.db")
    SessionMaster = sessionmaker(bind=engine_master)
    session_master = SessionMaster()

    target_years = ["2022", "2023", "2024"]
    
    # 분석 대상 기업 (이제 DART 고유번호를 외울 필요 없이 이름만 적습니다)
    target_companies = ["삼성SDI", "NAVER", "카카오", "SOOP"]

    for company_name in target_companies:
        # [핵심 로직] 마스터 DB에서 기업 이름으로 8자리 고유번호를 자동 검색
        master_info = session_master.query(CompanyMaster).filter_by(corp_name=company_name).first()
        
        if not master_info:
            print(f"⚠️ 마스터 DB에 '{company_name}' 정보가 없습니다. 상장사 이름을 확인해주세요.")
            continue
            
        dart_code = master_info.corp_code
        print(f"🔍 '{company_name}'의 고유번호({dart_code})를 명부에서 찾았습니다!")

        for year in target_years:
            # 팩트 DB에서 중복 데이터 검사
            exists = session_fact.query(FinancialReport).filter_by(corp_code=dart_code, year=int(year)).first()
            if exists:
                print(f"  ⏩ {year}년 데이터는 이미 존재하여 건너뜁니다.")
                continue

            print(f"  🚀 {year}년 재무 데이터 수집 및 엔진 가동...")
            
            try:
                raw_json = api.get_financial_statement(dart_code, year)
                df = processor.parse_to_dataframe(raw_json)
                clean_df = processor.clean_data(df)
                metrics = processor.extract_metrics(clean_df)
                
                if metrics.get('revenue', 0) > 0:
                    new_report = FinancialReport(
                        corp_name=company_name,
                        corp_code=dart_code,
                        year=int(year),
                        revenue=metrics['revenue'],
                        operating_income=metrics['operating_income'],
                        net_income=metrics['net_income'],
                        op_cash_flow=metrics['op_cash_flow'],
                        roe=metrics['roe'],
                        op_margin=metrics['op_margin'],
                        debt_ratio=metrics['debt_ratio'],
                        fcf=metrics['fcf']
                    )
                    session_fact.add(new_report)
                    session_fact.commit()
                    print(f"  ✅ [{year}] 팩트 데이터베이스 적재 완료!")
                else:
                    print(f"  ⚠️ [{year}] 재무 데이터가 부족합니다.")
                    
            except Exception as e:
                print(f"  ❌ [{year}] 에러 발생: {e}")
                session_fact.rollback()

    session_fact.close()
    session_master.close()
    print("🏁 완벽한 팩트 기반 데이터 레이크 구축 및 연결 완료")

if __name__ == "__main__":
    run_etl_pipeline()