from datetime import datetime
import io
import json
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st

# API연동
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 무조건 최상단 위치
st.set_page_config(layout="wide")

scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds = None

# [이중 안전장치] 1단계: Secrets에 설정이 있는지 확인 (웹 배포용)
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds = None

# [🔐 완벽 매칭 호환 로직] 1단계: Secrets에 직통으로 type이 있는지 확인
try:
    if "type" in st.secrets:
        creds_dict = {
            "type": st.secrets["type"],
            "project_id": st.secrets["project_id"],
            "private_key_id": st.secrets["private_key_id"],
            "private_key": st.secrets["private_key"].replace("\\n", "\n"),
            "client_email": st.secrets["client_email"],
            "client_id": st.secrets["client_id"],
            "auth_uri": st.secrets["auth_uri"],
            "token_uri": st.secrets["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["client_x509_cert_url"],
            "universe_domain": st.secrets["universe_domain"]
        }
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        # 내 컴퓨터(로컬)에서는 파일로 인증
        creds = ServiceAccountCredentials.from_json_keyfile_name("Ch1.json", scope)
except Exception:
    # 만약 웹 배포 환경에서 미세한 오타 등으로 튕겼을 때를 대비한 최종 백업
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name("Ch1.json", scope)
    except Exception as e:
        st.error(f"🚨 인증 수단을 찾을 수 없습니다. (로컬 파일 누락 또는 Secrets 설정 오류): {e}")
        st.stop()

if creds is None:
    st.error("🚨 인증 정보가 올바르지 않습니다.")
    st.stop()

client = gspread.authorize(creds)

@st.cache_data(ttl=3600)
def load_all_sheets():
    try:
        # 고유 시트 ID 기반 접근 시도
        spreadsheet = client.open_by_key("14Rn-yawMAO_L5BNiEsg6EZwgQ3nggxS9raGqLDIU2o0")
    except Exception:
        # 실패 시 기존 로컬 방식인 이름("Ch1")으로 접근
        spreadsheet = client.open("Ch1")
        
    sheet_names = ["C1", "C2", "C3", "C4", "C5", "C6"]
    dfs = {}
    
    for name in sheet_names:
        try:
            worksheet = spreadsheet.worksheet(name)
            records = worksheet.get_all_records()
            # 레코드가 있으면 데이터프레임 변환, 없으면 빈 데이터프레임 생성
            dfs[name.lower()] = pd.DataFrame(records) if records else pd.DataFrame()
        except Exception as e:
            # 특정 시트 로드 실패 시 에러 메시지만 출력하고 전체 앱이 멈추는 것을 방지
            st.warning(f"⚠️ '{name}' 시트를 불러오지 못했습니다. (원인: {e})")
            dfs[name.lower()] = pd.DataFrame()
            
    return dfs

# --- 이하 대시보드 UI/차트 코드 (기존과 동일) ---
iso_year, iso_week, iso_weekday = datetime.now().isocalendar()

with st.sidebar:
    st.markdown("## ⚙️ 분석 필터 셋팅")
    st.caption("대시보드에 표시될 데이터의 조회 조건을 설정하세요.")
    st.markdown("---")
    with st.container(border=True):
        st.markdown("###  기간 설정")
        selected_week = st.selectbox(
            "조회 주차 선택",
            options=list(range(1, 53)),
            index=iso_week - 1,
            format_func=lambda x: f" 제 {x}주차 (W{x:02d})"
        )
        if selected_week == iso_week:
            st.info(f"✨ **금일 기준 주차(W{iso_week:02d})** 데이터 조회 모드입니다.")
        else:
            st.warning(f"🔍 **과거 주차(W{selected_week:02d})** 데이터 조회 모드입니다. (현재: W{iso_week:02d}주차)")
    st.markdown("---")
    st.caption(f"📌 **마지막 동기화:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.caption("🔒 본 자료는 사내 공유용 보안 문서입니다.")

st.title("📦 물류 핵심 지표(KPI) 통합 대시보드")
st.caption("🚀 4대 지표 종합 모니터링 시스템")
st.markdown("")

CHART_HEIGHT = 280  
st.markdown(f"### 📅 {selected_week}주차의 전국 실적")

all_data = load_all_sheets()
st.session_state["all_data"] = all_data 
all_weeks = pd.DataFrame({"주차": range(1, 53)})

row1_col1, row1_col2 = st.columns([50, 50])
row2_col1, row2_col2 = st.columns([50, 50])

# [칼럼1] 정시배송율 KPI
df_c1 = all_data["c1"]
with row1_col1:
    current_df = df_c1[df_c1["주차"] == selected_week]
    current_total = current_df["총배송"].sum()
    current_ontime = current_df["정시배송"].sum()
    current_avg = (current_ontime / current_total * 100) if current_total > 0 else None
    prev_df = df_c1[df_c1["주차"] == (selected_week - 1)]
    prev_total = prev_df["총배송"].sum()
    prev_ontime = prev_df["정시배송"].sum()
    prev_avg = (prev_ontime / prev_total * 100) if prev_total > 0 else None
    delta_value = (current_avg - prev_avg) if (current_avg is not None and prev_avg is not None) else None

    with st.container(border=True):
        st.metric(label="정시배송율", value=f"{current_avg:.2f}%" if current_avg is not None else "데이터 없음", delta=f"{delta_value:+.2f}%p (전주 대비)" if delta_value is not None else "데이터 없음")
        weekly_otd = (df_c1.groupby("주차").apply(lambda g: (g["정시배송"].sum() / g["총배송"].sum() * 100) if g["총배송"].sum() > 0 else 0)).reset_index(name="정시배송율_실적")
        weekly_otd_full = all_weeks.merge(weekly_otd, on="주차", how="left").fillna(0)
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=weekly_otd_full["주차"], y=weekly_otd_full["정시배송율_실적"], mode='lines', line=dict(color='#10B981', width=2.5, shape='spline'), fill='tozeroy', fillcolor='rgba(16, 185, 129, 0.1)'))
        fig1.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=CHART_HEIGHT)
        st.plotly_chart(fig1, use_container_width=True)

# [칼럼2] 미납율 KPI
df_c2 = all_data["c2"]
with row1_col2:
    current_df = df_c2[df_c2["주차"] == selected_week]
    current_total = current_df["발주금액"].sum()
    current_ontime = current_df["출하금액"].sum()
    current_avg = (current_ontime / current_total * 100) if current_total > 0 else None
    prev_df = df_c2[df_c2["주차"] == (selected_week - 1)]
    prev_total = prev_df["발주금액"].sum()
    prev_ontime = prev_df["출하금액"].sum()
    prev_avg = (prev_ontime / prev_total * 100) if prev_total > 0 else None
    delta_value = (current_avg - prev_avg) if (current_avg is not None and prev_avg is not None) else None

    with st.container(border=True):
        st.metric(label="미납율", value=f"{current_avg:.2f}%" if current_avg is not None else "데이터 없음", delta=f"{delta_value:+.2f}%p (전주 대비)" if delta_value is not None else "데이터 없음")
        weekly_stockout = (df_c2.groupby("주차").apply(lambda g: ((g["발주금액"].sum() - g["출하금액"].sum()) / g["발주금액"].sum() * 100) if g["발주금액"].sum() > 0 else 0)).reset_index(name="결품율_실적")
        weekly_stockout_full = all_weeks.merge(weekly_stockout, on="주차", how="left").fillna(0)
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=weekly_stockout_full["주차"], y=weekly_stockout_full["결품율_실적"], mode='lines', line=dict(color='#EF4444', width=2.5, shape='spline'), fill='tozeroy', fillcolor='rgba(239, 68, 68, 0.1)'))
        fig2.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=CHART_HEIGHT, yaxis=dict(range=[0, 30]))
        st.plotly_chart(fig2, use_container_width=True)

# [칼럼3] 미오출율 KPI
df_c3 = all_data["c3"]
with row2_col1:
    current_df = df_c3[df_c3["주차"] == selected_week]
    current_total = current_df["출하금액"].sum()
    current_ontime = current_df["점포확정금액"].sum()
    current_avg = (current_ontime / current_total * 100) if current_total > 0 else None
    prev_df = df_c3[df_c3["주차"] == (selected_week - 1)]
    prev_total = prev_df["출하금액"].sum()
    prev_ontime = prev_df["점포확정금액"].sum()
    prev_avg = (prev_ontime / prev_total * 100) if prev_total > 0 else None
    delta_value = (current_avg - prev_avg) if (current_avg is not None and prev_avg is not None) else None

    with st.container(border=True):
        st.metric(label="미오출율", value=f"{current_avg:.2f}%" if current_avg is not None else "데이터 없음", delta=f"{delta_value:+.2f}%p (전주 대비)" if delta_value is not None else "데이터 없음")
        weekly_stockout3 = (df_c3.groupby("주차").apply(lambda g: ((g["출하금액"].sum() - g["점포확정금액"].sum()) / g["출하금액"].sum() * 100) if g["출하금액"].sum() > 0 else 0)).reset_index(name="미오출율_실적")
        weekly_stockout_full3 = all_weeks.merge(weekly_stockout3, on="주차", how="left").fillna(0)
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=weekly_stockout_full3["주차"], y=weekly_stockout_full3["미오출율_실적"], mode='lines', line=dict(color="#4563F7", width=2.5, shape='spline'), fill='tozeroy', fillcolor='rgba(69, 99, 247, 0.1)'))
        fig3.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=CHART_HEIGHT, yaxis=dict(range=[0, 30]))
        st.plotly_chart(fig3, use_container_width=True)

# [칼럼4] VOC KPI
df_c4 = all_data["c4"]
with row2_col2:
    current_sum_voc = df_c4.loc[df_c4["주차"] == selected_week, "VOC_건수"].sum()
    prev_sum_voc = df_c4.loc[df_c4["주차"] == (selected_week - 1), "VOC_건수"].sum()
    current_sum_voc = current_sum_voc if current_sum_voc > 0 else None
    prev_sum_voc = prev_sum_voc if prev_sum_voc > 0 else None
    delta_voc = (current_sum_voc - prev_sum_voc if current_sum_voc is not None and prev_sum_voc is not None else None)

    with st.container(border=True):
        st.metric(label="VOC 실적", value=f"{current_sum_voc:,.0f}건" if current_sum_voc is not None else "데이터 없음", delta=f"{delta_voc:+.0f}건 (전주 대비)" if delta_voc is not None else "데이터 없음", delta_color="inverse")
        weekly_voc = df_c4.groupby("주차")["VOC_건수"].sum().reset_index()
        weekly_voc_full = all_weeks.merge(weekly_voc, on="주차", how="left").fillna(0)
        fig4 = go.Figure()
        fig4.add_trace(go.Bar(x=weekly_voc_full["주차"], y=weekly_voc_full["VOC_건수"], name="VOC 건수", marker_color="rgba(138, 43, 226, 0.85)"))
        fig4.update_layout(margin=dict(l=50, r=50, t=50, b=50), height=CHART_HEIGHT, yaxis=dict(range=[0,60]))
        st.plotly_chart(fig4, use_container_width=True)

st.markdown("---")



# =========================================================
# 하단 영역
# =========================================================
st.markdown("### 🗺️ 전국 기준 주차별 실적")

# 좌측과 우측의 비율로 분할
bottom_col1, bottom_col2 = st.columns([6, 4])

# -----------------------------------------------------
# [좌측 컬럼 ]
# -----------------------------------------------------

df_c5 = all_data["c5"]

with bottom_col1:
    with st.container(border=True):
        st.markdown("📊 **주차별 전국 실적 현황**")

        # 1. 필요한 컬럼만 선택
        view_columns = ["주차", "정시배송율", "미납율", "미오출율", "VOC 실적"]
        df_view = df_c5[view_columns].copy()

        # 2. 주차 값에 '주차' 붙여서 문자열로 변환
        df_view["주차"] = df_view["주차"].astype(str) + "주차"

        # 3. 데이터프레임 내부에 혹시 존재할 수 있는 불필요한 맨 왼쪽 열(예: Unnamed: 0 등)이 있다면 완전히 삭제
        if "Unnamed: 0" in df_view.columns:
            df_view = df_view.drop(columns=["Unnamed: 0"])

        # 4. Streamlit의 column_config를 사용하여 모든 열의 값을 '가운데 정렬(center)'로 설정
        column_configurations = {
            col: st.column_config.Column(
                alignment="center"  # 값을 테이블 정중앙에 정렬
            )
            for col in df_view.columns
        }


        # 좌측 영역과 높이(324px)를 맞추고, 인덱스를 숨겨 테이블 출력
        st.dataframe(
            df_view,
            hide_index=True,                       # 맨 왼쪽의 행 번호(인덱스) 제거
            column_config=column_configurations,    # 전 컬럼 가운데 정렬 적용
            use_container_width=True,               # 컬럼 폭 균등 분배 및 부모 너비 맞춤
            height=324                             # 좌측 컴포넌트와 세로 높이 동기화
        )

        # CSV 다운로드 기능 구현
        csv_buffer = io.StringIO()
        df_view.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
        csv_bytes = csv_buffer.getvalue().encode("utf-8-sig")

        st.download_button(
            label="📥 주차별 실적 DB 다운로드 (CSV)",
            data=csv_bytes,
            file_name="주차별_실적_현황.csv",
            mime="text/csv",
            use_container_width=True
        )

# -----------------------------------------------------
# [우측 컬럼 ]
# -----------------------------------------------------

df_c5 = all_data["c5"]

with bottom_col2:
    # 선택한 주차에 해당하는 행 필터링
    current_week_avg = df_c5[df_c5["주차"] == selected_week]

# -----------------------------------------------------
# [우측 컬럼 : 평균값 카드]
# -----------------------------------------------------

df_c5 = all_data["c5"]

with bottom_col2:
    # 구글시트 특정 셀 값 가져오기
    avg_ontime = df_c5["정시배송율_평균"].iloc[0]
    avg_non_delivery = df_c5["미납율_평균"].iloc[0]
    avg_mis_delivery = df_c5["미오출율_평균"].iloc[0]
    avg_voc = df_c5["VOC실적_평균"].iloc[0]

    with st.container(border=False):
        card_row1_col1, card_row1_col2, card_row1_col3, card_row1_col4 = st.columns(4)

        with card_row1_col1:
            st.metric(
                label="🚚 정시배송율 (평균)",
                value=f"{avg_ontime:.1f}%" if isinstance(avg_ontime, (int, float)) else str(avg_ontime)
            )
        with card_row1_col2:
            st.metric(
                label="⚠️ 미납율 (평균)",
                value=f"{avg_non_delivery:.1f}%" if isinstance(avg_non_delivery, (int, float)) else str(avg_non_delivery)
            )
        with card_row1_col3:
            st.metric(
                label="🚨 미오출율 (평균)",
                value=f"{avg_mis_delivery:.1f}%" if isinstance(avg_mis_delivery, (int, float)) else str(avg_mis_delivery)
            )
        with card_row1_col4:
            st.metric(
                label="📞 VOC 실적 (평균)",
                value=f"{avg_voc}건" if isinstance(avg_voc, (int, float)) else str(avg_voc)
            )

# -----------------------------------------------------
# [우측 컬럼 : Best / Worst 카드]
# -----------------------------------------------------

# CSS 스타일 정의 (가독성과 테마를 위한 스타일)
st.markdown("""
<style>
    .metric-card-best {
        background-color: #E8F5E9; 
        border-left: 5px solid #2E7D32; 
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .metric-card-worst {
        background-color: #FFEBEE; 
        border-left: 5px solid #C62828; 
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .card-title {
        font-size: 14px;
        color: #555555;
        font-weight: bold;
        margin-bottom: 5px;
    }
    .card-value {
        font-size: 24px;
        font-weight: 800;
        color: #111111;
        margin-bottom: 5px; /* 주차와의 간격을 위해 약간 늘림 */
    }
    /* 📅 주차 폰트 스타일 수정 완료! */
    .card-week {
        font-size: 24px;       /* 12px -> 15px로 확대 */
        font-weight: bold;     /* 볼드체 추가 */
        color: #444444;       /* 글자색을 약간 더 선명하게 조정 */
    }
</style>
""", unsafe_allow_html=True)

with bottom_col2:
    # 1. 데이터 가져오기 (단위 중복 % 방지를 위해 필요시 데이터 값 확인 권장)
    best_1 = df_c5["정시배송율_Best"].iloc[0]
    best_2 = df_c5["미납율_Best"].iloc[0]
    best_3 = df_c5["미오출율_Best"].iloc[0]
    best_4 = df_c5["VOC실적_Best"].iloc[0]

    worst_1 = df_c5["정시배송율_Worst"].iloc[0]
    worst_2 = df_c5["미납율_Worst"].iloc[0]
    worst_3 = df_c5["미오출율_Worst"].iloc[0]
    worst_4 = df_c5["VOC실적_Worst"].iloc[0]

    best_1_1 = df_c5["정시배송율_Best"].iloc[1]
    best_2_1 = df_c5["미납율_Best"].iloc[1]
    best_3_1 = df_c5["미오출율_Best"].iloc[1]
    best_4_1 = df_c5["VOC실적_Best"].iloc[1]

    worst_1_1 = df_c5["정시배송율_Worst"].iloc[1]
    worst_2_1 = df_c5["미납율_Worst"].iloc[1]
    worst_3_1 = df_c5["미오출율_Worst"].iloc[1]
    worst_4_1 = df_c5["VOC실적_Worst"].iloc[1]

    # 4개 열 레이아웃 구성
    col1, col2, col3, col4 = st.columns(4)

    # --- 열 1: 정시배송율 ---
    with col1:
        # Best 카드 (높을수록 좋으므로 초록색)
        st.markdown(f"""
        <div class="metric-card-best">
            <div class="card-title">🚚 정시배송율 Best</div>
            <div class="card-value">{best_1}</div>
            <div class="card-week">📅 {best_1_1}주차</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Worst 카드 (낮으므로 빨간색)
        st.markdown(f"""
        <div class="metric-card-worst">
            <div class="card-title">🚚 정시배송율 Worst</div>
            <div class="card-value">{worst_1}</div>
            <div class="card-week">📅 {worst_1_1}주차</div>
        </div>
        """, unsafe_allow_html=True)

    # --- 열 2: 미납율 ---
    with col2:
        # 미납율은 '낮을수록' 좋은 지표이므로 Best(낮은 값)에 초록색 카드 적용
        st.markdown(f"""
        <div class="metric-card-best">
            <div class="card-title">⚠️ 미납율 Best</div>
            <div class="card-value">{best_2}</div>
            <div class="card-week">📅 {best_2_1}주차</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="metric-card-worst">
            <div class="card-title">⚠️ 미납율 Worst</div>
            <div class="card-value">{worst_2}</div>
            <div class="card-week">📅 {worst_2_1}주차</div>
        </div>
        """, unsafe_allow_html=True)

    # --- 열 3: 미오출율 ---
    with col3:
        # 미오출율 역시 '낮을수록' 좋은 지표
        st.markdown(f"""
        <div class="metric-card-best">
            <div class="card-title">🚨 미오출율 Best</div>
            <div class="card-value">{best_3}</div>
            <div class="card-week">📅 {best_3_1}주차</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="metric-card-worst">
            <div class="card-title">🚨 미오출율 Worst</div>
            <div class="card-value">{worst_3}</div>
            <div class="card-week">📅 {worst_3_1}주차</div>
        </div>
        """, unsafe_allow_html=True)

    # --- 열 4: VOC 실적 ---
    with col4:
        # VOC 건수는 적을수록 좋음
        st.markdown(f"""
        <div class="metric-card-best">
            <div class="card-title">📞 VOC 실적 Best</div>
            <div class="card-value">{best_4}건</div>
            <div class="card-week">📅 {best_4_1}주차</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="metric-card-worst">
            <div class="card-title">📞 VOC 실적 Worst</div>
            <div class="card-value">{worst_4}건</div>
            <div class="card-week">📅 {worst_4_1}주차</div>
        </div>
        """, unsafe_allow_html=True)
