import pandas as pd
import os
import tkinter as tk
from tkinter import messagebox

# --- 기본 설정 ---
# 출고 파일에서 읽어올 열 목록 (기존 그대로 유지)
column_group_out = [
    '출고일', '구분', '출고방법', '판매처', '상품명', '가용출고수량', 
    '비고', '상품코드', '수령자', '주문서코드', '판매처상품명', 
    '판매처옵션명', '주문수량', '주문번호', '품목별주문번호'
]

# 입고 파일에서 읽어올 열 목록
column_group_in = [
    "입고일", "구분", "옵션명", "공급처", "상품명", "가용입고수량", 
    "비고", "상품코드", "옵션코드", "공급처코드", "입고단가", 
    "박스수량", "보관장소", "바코드번호", "제조일"
]

# 업로드 폴더에서 엑셀 파일 찾기 (.xls, .xlsx)
upload_folder = '업로드'
uploaded_files = [f for f in os.listdir(upload_folder) if f.endswith('.xls') or f.endswith('.xlsx')]

if len(uploaded_files) == 0:
    print("업로드 폴더에 파일이 없습니다. 프로그램을 종료합니다.")
    exit(1)
# 여러 파일이 있어도 처리하도록 함

# --- 사용자 확인 ---
root = tk.Tk()
root.withdraw()
response = messagebox.askyesno("확인", "마켓 출고건들은 상품명을 정리 해 주셨나요? \n아직 안됐으면 아니요 버튼을 누르고 다시 실행 해 주세요")
if not response:
    print("사용자가 마켓 출고 정리를 하지 않았습니다. 프로그램을 종료합니다.")
    exit(1)

# --- 마켓 상품명 파일 읽기 ---
market_sales_file_path = '마켓 상품명.xlsx'
market_sales_df = pd.read_excel(market_sales_file_path)
# 마켓 상품명 리스트: 첫 번째 열의 결측치 제거 후 문자열로 변환
market_sales_list = market_sales_df.iloc[:, 0].dropna().astype(str).str.strip().tolist()

# --- classify 함수 (출고 및 입고 모두 적용) ---
def classify(row):
    구분 = str(row.get('구분', '')).strip()
    비고 = str(row.get('비고', ''))
    
    # 우선: "비고"에 "밀크런"이 포함되어 있으면 "로켓" 반환 (다른 조건보다 우선)
    if "밀크런" in 비고:
        return "로켓"
    if "올리브영" in 비고:
        return "올리브영"
    
    # 조정 관련 처리
    # 세트 입출고를 그냥 지워버리면 총 숫자 맞출 때 안 맞으니, 그냥 내용 기입하고, 취합 단계에서 빼버리자
    if 구분 == "(-)조정":
        if "세트" in 비고:
            return "세트용 출고"  
        else:
            return "출고조정"
    if 구분 == "(+)조정":
        if "세트" in 비고:
            return "세트용 입고"
        elif "가구매" in 비고: 
            return "가구매 입고"
        else:
            return "입고조정"
    
    # 입고 파일의 처리: 정상입고와 반품입고 구분
    if 구분 == "정상입고":
        # 신규 조건: 비고에 "세트"가 포함되어 있으면 "세트용 입고" 반환
        if "세트" in 비고:
            return "세트용 입고"
        else:
            return "정상입고"
    if 구분 == "반품입고":
        return "반품입고"
    
    # 출고 파일의 정상출고 건: 기존 분류 로직 적용
    if 구분 == "정상출고":
        # 신규 조건: "출고방식"이 비어있고, "비고"에 "세트"가 포함되어 있으면 "세트용 출고" 반환
        출고방식 = str(row.get('출고방식', '')).strip()
        if 출고방식 == "" and "세트" in 비고:
            return "세트용 출고"
        
        판매처상품명 = str(row.get('판매처상품명', '')).strip()
        판매처옵션명 = str(row.get('판매처옵션명', ''))
        판매처 = str(row.get('판매처', '')).strip()
        
        if 판매처 == "*쿠팡(쉽먼트)_미오":
            return "로켓"
        elif 판매처상품명 in market_sales_list:
            return "마켓"
        elif '온누리인터' in 판매처옵션명:
            return "인터"
        elif '큐텐' in 판매처옵션명:
            return "큐텐"
        elif '고알레' in 판매처상품명:
            return "고알레"
        elif any(x in 판매처옵션명 for x in ['마케팅', '시딩', '개인구매']):
            return "마케팅"
        elif '제품 불량 재발송' in 판매처옵션명:
            return "불량"
        elif '수기발주' in 판매처:
            return "수기"
        elif (판매처 == '아임웹_미오' and '전화구매' not in 판매처옵션명) or (판매처 == ''):
            return "미분류"
        else:
            return "일반"
    
    # 그 외의 경우, 원래 구분 값 그대로 반환
    return 구분

# --- 처리 결과를 저장할 리스트 ---
df_out_list = []  # 출고 파일 처리 결과
df_in_list = []   # 입고 파일 처리 결과

# --- 각 파일에 대해 처리 ---
for file in uploaded_files:
    file_path = os.path.join(upload_folder, file)
    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        print(f"파일 읽기 실패: {file}")
        continue
    
    # **읽은 후 마지막 행 삭제**
    if len(df) > 0:
        df = df.iloc[:-1]
    
    # --- 출고 파일 처리 ---
    if '출고일' in df.columns:
        # "구분" 열이 "정상출고" 또는 "(-)조정"인 행만 선택
        df = df[df['구분'].isin(["정상출고", "(-)조정"])].copy()
        # 지정된 열만 선택
        df = df[column_group_out]
        # 날짜 형식 변경: "출고일" -> YYYY-MM-DD
        df['출고일'] = pd.to_datetime(df['출고일'], errors='coerce').dt.strftime('%Y-%m-%d')
        
        # 맨 앞에 "분류제안"과 "분류확정" 열 추가  
        df.insert(0, '분류제안', '')
        df.insert(1, '분류확정', "")
        
        # classify 함수 적용 (조정 건 중 '세트' 포함된 경우는 None 반환되어 추후 삭제됨)
        df['분류제안'] = df.apply(classify, axis=1)
        df = df[df['분류제안'].notna()]  # 분류제안이 None인 행 삭제
        
        df_out_list.append(df)
        
    # --- 입고 파일 처리 ---
    elif '입고일' in df.columns:
        # "구분" 열이 "반품입고", "정상입고" 또는 "(+)조정"인 행만 선택
        df = df[df['구분'].isin(["반품입고", "정상입고", "(+)조정"])].copy()
        # 지정된 입고 파일 열만 선택
        df = df[column_group_in]
        # 날짜 형식 변경: "입고일" -> YYYY-MM-DD
        df['입고일'] = pd.to_datetime(df['입고일'], errors='coerce').dt.strftime('%Y-%m-%d')
        
        # 맨 앞에 "분류제안"과 "분류확정" 열 추가  
        df.insert(0, '분류제안', '')
        df.insert(1, '분류확정', '')
        
        # 열 이름 재매핑 (입고 파일 → 출고 파일 형식으로)
        rename_dict = {
            "입고일": "출고일",           # 날짜 열 통일
            "공급처": "판매처",           # 공급처 → 판매처
            "가용입고수량": "가용출고수량", # 수량 열 이름 통일
            "옵션명": "판매처옵션명"       # 옵션명 → 판매처옵션명
        }
        df.rename(columns=rename_dict, inplace=True)
        
        # 출고 파일에만 있는 열은 추가 (빈 값으로)
        missing_cols = [col for col in column_group_out if col not in df.columns]
        for col in missing_cols:
            df[col] = ""
        
        # classify 함수 적용
        df['분류제안'] = df.apply(classify, axis=1)
        df = df[df['분류제안'].notna()]  # 분류제안이 None인 행 삭제
        
        # 열 순서를 출고 파일과 동일하게 재정렬: '분류제안', '분류확정' + column_group_out
        df = df[['분류제안', '분류확정'] + column_group_out]
        
        df_in_list.append(df)
    else:
        print(f"파일 {file}은 처리 대상이 아닙니다.")
        continue

# --- 최종 결과 결합 ---
if df_out_list:
    out_df = pd.concat(df_out_list, ignore_index=True, sort=False)
else:
    out_df = pd.DataFrame(columns=['분류제안'])
if df_in_list:
    in_df = pd.concat(df_in_list, ignore_index=True, sort=False)
else:
    in_df = pd.DataFrame(columns=['분류제안'])
final_df = pd.concat([out_df, in_df], ignore_index=True, sort=False)

# --- 결과 파일 출력 ---
output_file_path = '최종분류결과.xlsx'
with pd.ExcelWriter(output_file_path, engine='xlsxwriter') as writer:
    final_df.to_excel(writer, sheet_name='최종분류', index=False)

print(f"최종 결과가 저장되었습니다: {output_file_path}")

# --- 요약 정보 출력 ---
print("\n[출고 파일 요약]")
if not out_df.empty:
    print(f"총 건수: {len(out_df)}")
    print("분류별 건수:")
    print(out_df['분류제안'].value_counts())
else:
    print("출고 파일 데이터가 없습니다.")

print("\n[입고 파일 요약]")
if not in_df.empty:
    print(f"총 건수: {len(in_df)}")
    print("분류별 건수:")
    print(in_df['분류제안'].value_counts())
else:
    print("입고 파일 데이터가 없습니다.")
