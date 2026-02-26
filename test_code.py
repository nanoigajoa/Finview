import sqlite3
import pandas as pd
import os

def test_sector_metrics(corp_name):
    print("\n🚀 평균(Mean) vs 중간값(Median) 데이터 검증 엔진 가동...\n")
    
    # DB 경로 설정 (프로젝트 루트 경로 기준)
    # 만약 현재 폴더 위치가 다르면 경로를 "data/finance.db" 등으로 수정하세요.
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "finance.db")
    
    if not os.path.exists(db_path):
        # 만약 data 폴더 안에 없다면 현재 폴더 하위 탐색
        db_path = "data/finance.db"
        if not os.path.exists(db_path):
            print(f"❌ DB 파일을 찾을 수 없습니다. 경로를 확인해주세요: {db_path}")
            return
            
    # DB 연결 및 데이터 로드
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM screener_summary", conn)
    conn.close()
    
    # 기업 정보 찾기
    target_stock = df[df['corp_name'] == corp_name]
    
    if target_stock.empty:
        print(f"❌ '{corp_name}' 종목을 DB에서 찾을 수 없습니다. 띄어쓰기를 확인해주세요.")
        return
        
    target_data = target_stock.iloc[0]
    sector = target_data['sector_name']
    
    print(f"🔍 [{corp_name}] 분석 시작 (섹터: {sector})")
    
    # 해당 섹터 데이터 필터링 (이상치 제거 로직: PER > 0 및 PER < 100)
    sector_df = df[df['sector_name'] == sector]
    valid_sector_df = sector_df[(sector_df['PER'] > 0) & (sector_df['PER'] < 100)]
    
    print(f"✅ '{sector}' 섹터 내 유효 비교 기업 수: {len(valid_sector_df)}개")
    
    # 평균값(Mean)과 중간값(Median) 연산
    metrics = ['PER', 'PBR', 'PSR', 'ROE', 'rev_cagr_3y']
    
    sector_mean = valid_sector_df[metrics].mean()
    sector_median = valid_sector_df[metrics].median()
    
    # 결과 시각화 출력
    print("\n" + "=" * 70)
    print(f"{'지표(Metrics)':<15} | {'기업 수치':<12} | {'섹터 평균(Mean)':<15} | {'섹터 중간값(Median)':<15}")
    print("-" * 70)
    
    for m in metrics:
        val = target_data[m]
        mean_val = sector_mean[m]
        median_val = sector_median[m]
        
        # 기업 수치가 평균보다 싼지/좋은지 시각적 마킹 (*)
        is_better_mean = (val < mean_val) if m in ['PER', 'PBR', 'PSR'] else (val > mean_val)
        marker = "⭐" if is_better_mean else "  "
        
        print(f"{m:<15} | {val:>10.2f} {marker} | {mean_val:>15.2f} | {median_val:>15.2f}")
        
    print("=" * 70)
    print("💡 [참고] ⭐ 표시는 해당 기업 지표가 '섹터 평균(Mean)' 대비 우위(저평가 또는 고성장)에 있음을 의미합니다.")
    print("💡 평균(Mean)은 특정 기업의 극단적 실적에 크게 흔들리지만, 중간값(Median)은 흔들리지 않고 섹터의 정중앙을 보여줍니다.\n")

if __name__ == "__main__":
    while True:
        target = input("분석할 종목명을 입력하세요 (종료하려면 'q' 입력): ").strip()
        if target.lower() == 'q':
            print("분석을 종료합니다.")
            break
        if target:
            test_sector_metrics(target)