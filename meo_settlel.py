# app.py

import io
import pandas as pd
import streamlit as st

st.set_page_config(page_title="엑셀 입출고 분류기", layout="centered")
st.title("📦 정산용 입출고 내역 자동 분류기")

# --- 1. 업로드 UI 정의 ---
st.write("### 1) 마켓 상품명 파일 업로드")
market_file = st.file_uploader(
    "마켓 상품명.xlsx 파일을 선택하세요",
    type=["xlsx"]
)

st.write("### 2) 입출고 엑셀 파일들 업로드 (다중 선택 가능)")
uploaded_files = st.file_uploader(
    "출고·입고 엑셀(.xls/.xlsx) 파일을 모두 선택하세요",
    type=["xls", "xlsx"],
    accept_multiple_files=True
)

# --- 2. '정리 여부' 확인 (기존 tkinter 메시지박스 대체) ---
if market_file and uploaded_files:
    response = st.radio(
        "마켓 출고건들은 상품명을 정리하셨나요?",
        ["정리함", "아직 안함"]
    )
    if response == "아직 안함":
        st.warning("❗ 마켓 출고건을 정리한 뒤 다시 실행해주세요.")
        st.stop()
else:
    st.info("▶ 위 두 단계를 모두 완료한 뒤, 분류 버튼을 눌러주세요.")
    st.stop()

# --- 3. 마켓 상품명 리스트 생성 ---
try:
    market_sales_df = pd.read_excel(market_file)
    market_sales_list = (
        market_sales_df.iloc[:, 0]
        .dropna()
        .astype(str)
        .str.strip()
        .tolist()
    )
except Exception as e:
    st.error(f"마켓 상품명 파일을 읽는 중 오류가 발생했습니다:\n{e}")
    st.stop()

# --- 4. 컬럼 그룹 정의 ---
column_group_out = [
    '출고일', '구분', '출고방법', '판매처', '상품명', '가용출고수량',
    '비고', '상품코드', '수령자', '주문서코드', '판매처상품명',
    '판매처옵션명', '주문수량', '주문번호', '품목별주문번호'
]
column_group_in = [
    "입고일", "구분", "옵션명", "공급처", "상품명", "가용입고수량",
    "비고", "상품코드", "옵션코드", "공급처코드", "입고단가",
    "박스수량", "보관장소", "바코드번호", "제조일"
]

# --- 5. 분류 함수 정의 ---
def classify(row, market_list):
    구분 = str(row.get('구분', '')).strip()
    비고 = str(row.get('비고', ''))

    if "밀크런" in 비고:
        return "로켓"
    if "올리브영" in 비고:
        return "올리브영"
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
    if 구분 == "정상입고":
        if "세트" in 비고:
            return "세트용 입고"
        else:
            return "정상입고"
    if 구분 == "반품입고":
        return "반품입고"
    if 구분 == "정상출고":
        출고방식 = str(row.get('출고방식', '')).strip()
        if 출고방식 == "" and "세트" in 비고:
            return "세트용 출고"
        판매처상품명 = str(row.get('판매처상품명', '')).strip()
        판매처옵션명 = str(row.get('판매처옵션명', ''))
        판매처 = str(row.get('판매처', '')).strip()
        if 판매처 == "*쿠팡(쉽먼트)_미오":
            return "로켓"
        elif 판매처상품명 in market_list:
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
    return 구분

# --- 6. 업로드된 파일들 처리 ---
df_out_list = []
df_in_list = []
errors = []

# … (Streamlit 상단, 업로드 등 생략) …

for uploaded_file in uploaded_files:
    try:
        df = pd.read_excel(uploaded_file)
    except Exception as e:
        errors.append(f"파일 읽기 실패: {uploaded_file.name} ({e})")
        continue

    df.columns = df.columns.str.strip()  # 헤더 공백 제거

    # 출고 파일 판별
    is_out_file = '출고일' in df.columns
    # 입고 파일 판별
    is_in_file = '입고일' in df.columns

    if is_out_file:
        # --- 출고 처리 ---
        df_filtered = df[df['구분'].isin(["정상출고", "(-)조정"])].copy()
        df_filtered = df_filtered[column_group_out]  # column_group_out 중 실제 존재하는 것만 우선 가져옴
        df_filtered['출고일'] = pd.to_datetime(
            df_filtered['출고일'], errors='coerce'
        ).dt.strftime('%Y-%m-%d')

        # '분류제안', '분류확정' 열 추가
        df_filtered.insert(0, '분류제안', '')
        df_filtered.insert(1, '분류확정', '')

        # 부족한 column_group_out 열을 빈 문자열로 채우기
        for col in column_group_out:
            if col not in df_filtered.columns:
                df_filtered[col] = ""

        # 분류 함수 적용
        df_filtered['분류제안'] = df_filtered.apply(
            lambda row: classify(row, market_sales_list), axis=1
        )
        df_filtered = df_filtered[df_filtered['분류제안'].notna()]

        # 최종 컬럼 순서 맞추기
        df_filtered = df_filtered[['분류제안', '분류확정'] + column_group_out]
        df_out_list.append(df_filtered)

    elif is_in_file:
        # --- 입고 처리 ---
        df_filtered = df[df['구분'].isin(["반품입고", "정상입고", "(+)조정"])].copy()
        df_filtered = df_filtered[column_group_in]  # column_group_in 중 실제 존재하는 것만 우선 가져옴
        df_filtered['입고일'] = pd.to_datetime(
            df_filtered['입고일'], errors='coerce'
        ).dt.strftime('%Y-%m-%d')

        # '분류제안', '분류확정' 열 추가
        df_filtered.insert(0, '분류제안', '')
        df_filtered.insert(1, '분류확정', '')

        # 부족한 column_group_in 열을 빈 문자열로 채우기
        for col in column_group_in:
            if col not in df_filtered.columns:
                df_filtered[col] = ""

        # 컬럼명 재매핑 (입고 → 출고 형식으로 통일)
        rename_dict = {
            "입고일": "출고일",
            "공급처": "판매처",
            "가용입고수량": "가용출고수량",
            "옵션명": "판매처옵션명"
        }
        df_filtered.rename(columns=rename_dict, inplace=True)

        # 이제 column_group_out 기준으로 “부족한 열”을 빈 문자열로 채우기
        for col in column_group_out:
            if col not in df_filtered.columns:
                df_filtered[col] = ""

        # 분류 함수 적용
        df_filtered['분류제안'] = df_filtered.apply(
            lambda row: classify(row, market_sales_list), axis=1
        )
        df_filtered = df_filtered[df_filtered['분류제안'].notna()]

        # 최종 컬럼 순서 맞추기: '분류제안', '분류확정' + column_group_out
        df_filtered = df_filtered[['분류제안', '분류확정'] + column_group_out]
        df_in_list.append(df_filtered)

    else:
        errors.append(f"처리 대상 아님: {uploaded_file.name} (입출고용 키 컬럼 없음)")
        continue

# … (후단부: final_df 결합, 엑셀 저장 등) …



# 오류가 있었으면 화면에 출력
if errors:
    st.warning("일부 파일 처리 시 오류 발생:")
    for err in errors:
        st.write(f"- {err}")

# 결과 데이터프레임 생성
if df_out_list:
    out_df = pd.concat(df_out_list, ignore_index=True, sort=False)
else:
    out_df = pd.DataFrame(columns=['분류제안'])
if df_in_list:
    in_df = pd.concat(df_in_list, ignore_index=True, sort=False)
else:
    in_df = pd.DataFrame(columns=['분류제안'])

final_df = pd.concat([out_df, in_df], ignore_index=True, sort=False)

if final_df.empty:
    st.error("▶ 업로드된 파일 중 유효한 출고/입고 데이터가 없습니다.")
    st.stop()

# --- 7. 결과 다운로드 제공 ---
buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
    final_df.to_excel(writer, index=False, sheet_name='최종분류')
    # writer.save()
buffer.seek(0)

st.success("✅ 분류가 완료되었습니다!")
st.download_button(
    label="📥 최종분류결과.xlsx 다운로드",
    data=buffer.getvalue(),
    file_name="최종분류결과.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# --- 8. 추가 요약 정보 (선택 사항) ---
with st.expander("▶ 출고/입고 요약 보기"):
    st.write("#### [출고 파일 요약]")
    if not out_df.empty:
        st.write(f"- 총 건수: {len(out_df)}")
        st.write("- 분류별 건수:")
        st.write(out_df['분류제안'].value_counts().to_frame("건수"))
    else:
        st.write("- 출고 데이터가 없습니다.")

    st.write("\n#### [입고 파일 요약]")
    if not in_df.empty:
        st.write(f"- 총 건수: {len(in_df)}")
        st.write("- 분류별 건수:")
        st.write(in_df['분류제안'].value_counts().to_frame("건수"))
    else:
        st.write("- 입고 데이터가 없습니다.")
