import os
import sys
import io
import zipfile
import requests
import xml.etree.ElementTree as ET

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 🌟 기존 models.py가 아닌, 새로 만든 master_models.py에서 뼈대를 가져옵니다.
from core.master_models import init_master_db, CompanyMaster
from sqlalchemy.orm import sessionmaker

def build_company_master():
    api_key = "1009054bb1fab7f3a54a1dcbd71bd57e678b3ab8"
    url = "https://opendart.fss.or.kr/api/corpCode.xml"
    
    print("📡 DART 서버에서 기업 고유번호 명부(ZIP)를 다운로드 중입니다...")
    response = requests.get(url, params={"crtfc_key": api_key})
    
    if response.status_code == 200:
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            xml_data = z.read('CORPCODE.xml')
            
        print("🔍 XML 파싱 및 상장사 필터링 중...")
        root = ET.fromstring(xml_data)
        
        os.makedirs('data', exist_ok=True)
        # 🌟 고유번호.db를 생성하고 연결합니다.
        engine = init_master_db("sqlite:///data/고유번호.db")
        Session = sessionmaker(bind=engine)
        session = Session()
        
        inserted_count = 0
        
        for list_node in root.findall('list'):
            corp_code = list_node.find('corp_code').text
            corp_name = list_node.find('corp_name').text
            stock_code = list_node.find('stock_code').text
            
            if stock_code and stock_code.strip():
                master_record = CompanyMaster(
                    corp_code=corp_code.strip(),
                    corp_name=corp_name.strip(),
                    stock_code=stock_code.strip()
                )
                session.merge(master_record)
                inserted_count += 1
                
        session.commit()
        session.close()
        print(f"✅ 완벽합니다! 총 {inserted_count}개 상장사가 '고유번호.db'에 독립적으로 구축되었습니다.")
    else:
        print(f"❌ 다운로드 실패: HTTP {response.status_code}")

if __name__ == "__main__":
    build_company_master()