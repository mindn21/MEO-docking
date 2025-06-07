import streamlit as st
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials

# 1) 시크릿에서 서비스 계정 정보와 스프레드시트 URL/워크시트명 불러오기
secrets           = st.secrets["gcp_service_account"]
SPREADSHEET_URL   = st.secrets["spreadsheet_url"]
WORKSHEET_NAME    = st.secrets["worksheet_name"]

# 2) 구글 API 인증
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
creds = Credentials.from_service_account_info(secrets, scopes=SCOPES)
gc    = gspread.authorize(creds)

# 3) 데이터 로드 및 최근 7일 필터
@st.cache_data(ttl=3600)
def load_data():
    ws = gc.open_by_url(SPREADSHEET_URL).worksheet(WORKSHEET_NAME)
    df = pd.DataFrame(ws.get_all_records())
    df.columns = df.columns.str.strip()

    # 1) 날짜 필터
    if "Day" in df.columns:
        df["Day"] = pd.to_datetime(df["Day"])
        last_week = df["Day"].max() - pd.Timedelta(days=7)
        df = df[df["Day"] >= last_week]

    # 2) 숫자형으로 변환할 컬럼 리스트
    num_cols = [
        "Impressions",
        "Clicks (All)",
        "Amount Spent",
        "Purchases",
        "Purchases Conversion Value",
        "3-Second Video Views",
    ]

    for col in num_cols:
        if col in df.columns:
            # 콤마 제거하고, 숫자로 변환. 에러나면 NaN → 0으로 채움
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(",", "", regex=True)
                .str.replace("원", "", regex=True)    # 혹시 '원' 문구가 섞여 있다면
                .pipe(pd.to_numeric, errors="coerce")
                .fillna(0)
            )

    return df

df = load_data()

# 4) 원본 데이터 샘플
st.title("📊 지난 7일 광고 성과 요약")
st.subheader("원본 데이터 샘플")
st.dataframe(df.head(), use_container_width=True)

# 5) 광고별 집계
grp = df.groupby("Campaign Name")
summary = grp.agg(
    Impressions        = ("Impressions",           "sum"),
    Clicks             = ("Clicks (All)",          "sum"),
    Amount_Spent       = ("Amount Spent",          "sum"),
    Purchases          = ("Purchases",             "sum"),
    Conversion_Value   = ("Purchases Conversion Value", "sum"),
    Video_Views_3s     = ("3-Second Video Views",  "sum"),
).reset_index()

# 6) 추가 지표 계산
summary["CTR (%)"]             = np.where(
    summary["Impressions"] > 0,
    summary["Clicks"] / summary["Impressions"] * 100,
    0
)
summary["CPC (원)"]            = np.where(
    summary["Clicks"] > 0,
    summary["Amount_Spent"] / summary["Clicks"],
    0
)
summary["Conversion Rate (%)"] = np.where(
    summary["Clicks"] > 0,
    summary["Purchases"] / summary["Clicks"] * 100,
    0
)
summary["ROAS"]                = np.where(
    summary["Amount_Spent"] > 0,
    summary["Conversion_Value"] / summary["Amount_Spent"],
    0
)

# 7) 전체 합계 계산
tot = {
    "Impressions":      summary["Impressions"].sum(),
    "Clicks":           summary["Clicks"].sum(),
    "Amount_Spent":     summary["Amount_Spent"].sum(),
    "Purchases":        summary["Purchases"].sum(),
    "Conversion_Value": summary["Conversion_Value"].sum(),
    "Video_Views_3s":   summary["Video_Views_3s"].sum(),
}
tot["CTR (%)"]             = (tot["Clicks"]/tot["Impressions"]*100) if tot["Impressions"]>0 else 0
tot["CPC (원)"]            = (tot["Amount_Spent"]/tot["Clicks"])    if tot["Clicks"]>0 else 0
tot["Conversion Rate (%)"] = (tot["Purchases"]/tot["Clicks"]*100)   if tot["Clicks"]>0 else 0
tot["ROAS"]                = (tot["Conversion_Value"]/tot["Amount_Spent"]) if tot["Amount_Spent"]>0 else 0

# 8) Streamlit 화면에 출력

st.subheader("🔹 캠페인별 7일 합계")
st.dataframe(summary, use_container_width=True)

st.subheader("🔹 전체 합계")
cols1 = st.columns(5)
cols1[0].metric("총 노출",      f"{tot['Impressions']:,}")
cols1[1].metric("총 클릭",      f"{tot['Clicks']:,}")
cols1[2].metric("총 비용",      f"{tot['Amount_Spent']:,.0f}원")
cols1[3].metric("평균 CTR",     f"{tot['CTR (%)']:.2f}%")
cols1[4].metric("평균 CPC",     f"{tot['CPC (원)']:.2f}원")

cols2 = st.columns(4)
cols2[0].metric("총 구매 수",    f"{tot['Purchases']:,}")
cols2[1].metric("총 전환 가치",  f"{tot['Conversion_Value']:,.0f}")
cols2[2].metric("평균 전환율",   f"{tot['Conversion Rate (%)']:.2f}%")
cols2[3].metric("전체 ROAS",     f"{tot['ROAS']:.2f}")

# 9) (기존) 일별 지출 차트 & 상세 캠페인표
if "Day" in df.columns and "Amount Spent" in df.columns:
    st.subheader("일별 지출 추이")
    daily = df.groupby("Day")["Amount Spent"].sum().reset_index()
    st.line_chart(daily.set_index("Day"))

if "Campaign Name" in df.columns:
    st.subheader("캠페인별 상세 지표")
    detail = df.groupby("Campaign Name")[
        ["Impressions", "Clicks (All)", "Amount Spent"]
    ].sum().reset_index()
    st.dataframe(detail, use_container_width=True)
