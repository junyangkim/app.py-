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

# =========================================================
# 모바일 반응형 CSS 코드 ***** 문제시 여기 삭제 
# =========================================================
st.markdown("""
<style>
       @media (max-width: 768px) {
           .main .block-container {
               padding-left: 0.8rem !important;
               padding-right: 0.8rem !important;
               padding-top: 1rem !important;
           }
           [data-testid="column"] {
               width: 100% !important;
               flex: 1 1 100% !important;
               min-width: 100% !important;
               margin-bottom: 0.5rem;
           }
           h1 { font-size: 1.5rem !important; }
           h2 { font-size: 1.25rem !important; }
           h3 { font-size: 1.1rem !important; }
           [data-testid="stMetric"] {
               padding: 6px !important;
           }
       }
</style>
""", unsafe_allow_html=True)


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

# N-1 주차 계산
default_week = iso_week - 1 if iso_week > 1 else 52

with st.sidebar:
    st.markdown("## ⚙️ 분석 필터 셋팅")
    st.caption("대시보드에 표시될 데이터의 조회 조건을 설정하세요.")
    st.markdown("---")

    with st.container(border=True):
        st.markdown("### 기간 설정")

        selected_week = st.selectbox(
            "조회 주차 선택",
            options=list(range(1, 53)),
            index=default_week - 1,  # ← N-1 주차를 기본 선택
            format_func=lambda x: f" 제 {x}주차 (W{x:02d})"
        )

        if selected_week == default_week:
            st.info(
                f"✨ **기본 조회 주차(W{default_week:02d})** 데이터 조회 모드입니다."
            )
        else:
            st.warning(
                f"🔍 **선택 주차(W{selected_week:02d})** 데이터 조회 모드입니다. "
                f"(기본: W{default_week:02d})"
            )

    st.markdown("---")
    st.caption(f"📌 **마지막 동기화:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.caption("🔒 본 자료는 사내 공유용 보안 문서입니다.")

st.title("📦 물류 핵심 지표(KPI) 통합 대시보드")
st.caption("🚀 4대 지표 종합 모니터링 시스템")
st.markdown("")

CHART_HEIGHT = 280

# =========================================================
# 구글 시트 헤더 자동 대응 함수 (가로형 컬럼 찾기)
# =========================================================
def get_week_col_name(df, week_num):
    w_str = str(week_num)
    w_label = f"{week_num}주차"
    w_w = f"W{week_num:02d}"
    if w_str in df.columns:
        return w_str
    elif w_label in df.columns:
        return w_label
    elif w_w in df.columns:
        return w_w
    return None

# =========================================================
# 0. 기본 설정 및 데이터 준비
# =========================================================
# 차트 높이 설정
CHART_HEIGHT = 220

all_data = load_all_sheets()
st.session_state["all_data"] = all_data

# =========================================================
# 상단 KPI 카드 + 그래프 (전국 평균 기반)
# =========================================================
df_c1 = all_data["c1"]
df_c2 = all_data["c2"]
df_c3 = all_data["c3"]
df_c4 = all_data["c4"]

# =========================================================
# 상단 KPI 카드 + 그래프 (사각형 테두리 + 동일 폰트)
# =========================================================

# CSS 스타일 정의
st.markdown("""
<style>
    .metric-box {
        border: 2px solid #cccccc;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 20px;
        box-shadow: 2px 2px 8px rgba(0,0,0,0.1);
        background-color: #f9f9f9;
    }
    .metric-title {
        font-size:18px;
        font-weight:bold;
        margin-bottom:6px;
        text-align:center;
    }
    .metric-value {
        font-size:18px;
        font-weight:600;
        margin-bottom:10px;
        text-align:center;
    }
</style>
""", unsafe_allow_html=True)

# 주차 헤더 (폰트 크기 줄임)
st.markdown(f"<h5 style='font-size:24px; font-weight:600;'>📅 {selected_week}주차의 전국 실적</h5>", unsafe_allow_html=True)

# KPI 값 계산 함수
def calc_avg(df, week_num):
    col = get_week_col_name(df, week_num)
    return pd.to_numeric(df[col], errors="coerce").mean() if col else None

def calc_sum(df, week_num):
    col = get_week_col_name(df, week_num)
    return pd.to_numeric(df[col], errors="coerce").sum() if col else None

# 주차 리스트
weeks = [w for w in range(1, 53) if get_week_col_name(df_c1, w)]

# 이전 주차(전주) 번호 계산 (1주차인 경우 비교 대상이 없으므로 None)
prev_week = selected_week - 1 if selected_week > 1 else None

# =========================================================
# 상단 KPI 카드 + 그래프 (전주 대비 증감 포함)
# =========================================================

# 주차 리스트
weeks = [w for w in range(1, 53) if get_week_col_name(df_c1, w)]

# 이전 주차(전주) 번호 계산 (1주차인 경우 비교 대상이 없으므로 None)
prev_week = selected_week - 1 if selected_week > 1 else None

# 선택 주차 KPI 값 (현재)
current_avg_c1 = calc_avg(df_c1, selected_week)
current_avg_c2 = calc_avg(df_c2, selected_week)
current_avg_c3 = calc_avg(df_c3, selected_week)
current_sum_c4 = calc_sum(df_c4, selected_week)

# 이전 주차 KPI 값 (전주)
prev_avg_c1 = calc_avg(df_c1, prev_week) if prev_week else None
prev_avg_c2 = calc_avg(df_c2, prev_week) if prev_week else None
prev_avg_c3 = calc_avg(df_c3, prev_week) if prev_week else None
prev_sum_c4 = calc_sum(df_c4, prev_week) if prev_week else None

# 전주 대비 차이(Delta) 계산
delta_c1 = (current_avg_c1 - prev_avg_c1) if (current_avg_c1 is not None and prev_avg_c1 is not None) else None
delta_c2 = (current_avg_c2 - prev_avg_c2) if (current_avg_c2 is not None and prev_avg_c2 is not None) else None
delta_c3 = (current_avg_c3 - prev_avg_c3) if (current_avg_c3 is not None and prev_avg_c3 is not None) else None
delta_c4 = (current_sum_c4 - prev_sum_c4) if (current_sum_c4 is not None and prev_sum_c4 is not None) else None

# 주차별 전체 추이 데이터
avg_otd = [calc_avg(df_c1, w) for w in weeks]
avg_nonpay = [calc_avg(df_c2, w) for w in weeks]
avg_mis = [calc_avg(df_c3, w) for w in weeks]
sum_voc = [calc_sum(df_c4, w) for w in weeks] 

# --- KPI 카드 + 그래프 레이아웃 ---
row1_col1, row1_col2 = st.columns(2)
row2_col1, row2_col2 = st.columns(2)

# [C1] 정시배송율 (높을수록 좋음 -> 기본 색상)
with row1_col1:
    with st.container(border=True):
        st.metric(
            label="🚚 정시배송율",
            value=f"{current_avg_c1:.1f}%" if current_avg_c1 is not None else "N/A",
            delta=f"{delta_c1:+.1f}%p (전주 대비)" if delta_c1 is not None else "전주 데이터 없음"
        )
        fig1 = go.Figure(go.Scatter(
            x=weeks, 
            y=avg_otd, 
            mode="lines+markers",
            line=dict(color='#1E88E5', width=3),
            hovertemplate="주차:%{x}주차 , 실적:%{y:.1f}%<extra></extra>"
        ))
        fig1.update_layout(
            height=CHART_HEIGHT, 
            margin=dict(l=10, r=10, t=10, b=10),
            hovermode="x unified"
        )
        st.plotly_chart(fig1, use_container_width=True)

# [C2] 미납율 (낮을수록 좋음 -> delta_color="inverse")
with row1_col2:
    with st.container(border=True):
        st.metric(
            label="⚠️ 미납율",
            value=f"{current_avg_c2:.1f}%" if current_avg_c2 is not None else "N/A",
            delta=f"{delta_c2:+.1f}%p (전주 대비)" if delta_c2 is not None else "전주 데이터 없음",
            delta_color="inverse"
        )
        fig2 = go.Figure(go.Scatter(
            x=weeks, 
            y=avg_nonpay, 
            mode="lines+markers",
            line=dict(color='#E53935', width=3),
            hovertemplate="주차:%{x}주차 , 실적:%{y:.1f}%<extra></extra>"
        ))
        fig2.update_layout(
            height=CHART_HEIGHT, 
            margin=dict(l=10, r=10, t=10, b=10),
            hovermode="x unified"
        )
        st.plotly_chart(fig2, use_container_width=True)

# [C3] 미오출율 (낮을수록 좋음 -> delta_color="inverse")
with row2_col1:
    with st.container(border=True):
        st.metric(
            label="🚨 미오출율",
            value=f"{current_avg_c3:.1f}%" if current_avg_c3 is not None else "N/A",
            delta=f"{delta_c3:+.1f}%p (전주 대비)" if delta_c3 is not None else "전주 데이터 없음",
            delta_color="inverse"
        )
        fig3 = go.Figure(go.Scatter(
            x=weeks, 
            y=avg_mis, 
            mode="lines+markers",
            line=dict(color='#FB8C00', width=3),
            hovertemplate="주차:%{x}주차 , 실적:%{y:.1f}%<extra></extra>"
        ))
        fig3.update_layout(
            height=CHART_HEIGHT, 
            margin=dict(l=10, r=10, t=10, b=10),
            hovermode="x unified"
        )
        st.plotly_chart(fig3, use_container_width=True)

# [C4] VOC 실적 (낮을수록 좋음 -> delta_color="inverse")
with row2_col2:
    with st.container(border=True):
        st.metric(
            label="📞 VOC 건수",
            value=f"{int(current_sum_c4)}건" if current_sum_c4 is not None else "N/A",
            delta=f"{int(delta_c4):+d}건 (전주 대비)" if delta_c4 is not None else "전주 데이터 없음",
            delta_color="inverse"
        )
        fig4 = go.Figure(go.Bar(
            x=weeks, 
            y=sum_voc, 
            marker_color='#43A047',
            hovertemplate="주차:%{x}주차 , 실적:%{y:,}건<extra></extra>"
        ))
        fig4.update_layout(
            height=CHART_HEIGHT, 
            margin=dict(l=10, r=10, t=10, b=10),
            hovermode="x unified"
        )
        st.plotly_chart(fig4, use_container_width=True)



# =========================================================
# 하단 본문 영역
# =========================================================
st.markdown("---")
st.markdown("### 🗺️ 전국 기준 주차별 실적")

bottom_col1, bottom_col2 = st.columns([6, 4])

# 1. 시트 데이터 가져오기 및 공백/빈값을 NaN으로 자동 변환 처리
valid_weeks = weeks

def get_clean_series(df, week_list, is_sum=False):
    """시트의 공백/문자열/빈값을 NaN으로 다듬고 numeric으로 변환하는 함수"""
    data = []
    for w in week_list:
        col = get_week_col_name(df, w)
        if col and col in df.columns:
            # pd.to_numeric(errors='coerce')는 값이 없거나 숫자가 아닌 경우 모두 NaN으로 변환합니다.
            s = pd.to_numeric(df[col], errors='coerce')
            
            # min_count=1을 적용하여 전체가 NaN일 때는 0이 아닌 NaN을 반환 (VOC 0건 오류 방지)
            val = s.sum(min_count=1) if is_sum else s.mean()
            
            # 결측치(NaN/NaT)인 경우 None 처리
            data.append(val if pd.notna(val) else None)
        else:
            data.append(None)
    return data

weekly_otd = get_clean_series(df_c1, valid_weeks, is_sum=False)
weekly_stockout = get_clean_series(df_c2, valid_weeks, is_sum=False)
weekly_mis = get_clean_series(df_c3, valid_weeks, is_sum=False)
weekly_voc = get_clean_series(df_c4, valid_weeks, is_sum=True)

# ---------------------------------------------------------
# [좌측 컬럼 : 주차별 실적 테이블 (선택 주차 노란 형광색 강조)]
# ---------------------------------------------------------
with bottom_col1:
    with st.container(border=True):
        st.markdown(f"📊 **주차별 전국 실적 현황** (현재 선택: **{selected_week}주차**)")

    # 1. 데이터프레임 생성
    df_view = pd.DataFrame({
        "주차": [f"{w}주차" for w in valid_weeks],
        "정시배송율": [f"{v:.1f}%" if pd.notna(v) else "-" for v in weekly_otd],
        "미납율": [f"{v:.1f}%" if pd.notna(v) else "-" for v in weekly_stockout],
        "미오출율": [f"{v:.1f}%" if pd.notna(v) else "-" for v in weekly_mis],
        "VOC 실적": [f"{int(v)}건" if pd.notna(v) else "-" for v in weekly_voc]
    })

    # 2. 선택된 주차 행에 노란 형광색 스타일 적용 함수
    target_week_label = f"{selected_week}주차"
    
    def highlight_selected_row(row):
        # 현재 행의 '주차' 컬럼이 선택된 주차와 같으면 노란 형광색, 아니면 기본값
        if row["주차"] == target_week_label:
            # #FFF59D : 눈이 편안한 파스텔톤 노란색 (#FFFF00 으로 변경 시 선명한 형광노랑)
            return ['background-color: #FFF59D; font-weight: bold; color: #000000;'] * len(row)
        return [''] * len(row)

    # 3. 스타일 적용
    styled_df = df_view.style.apply(highlight_selected_row, axis=1)

    column_configurations = {col: st.column_config.Column(alignment="center") for col in df_view.columns}

    # 4. styled_df 전달
    st.dataframe(
        styled_df,
        hide_index=True,
        column_config=column_configurations,
        use_container_width=True,
        height=324
    )

    csv_buffer = io.StringIO()
    df_view.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
    st.download_button(
        label=f"📥 주차별 실적 DB 다운로드 (CSV)",
        data=csv_buffer.getvalue().encode("utf-8-sig"),
        file_name=f"주차별_실적_현황_W{selected_week:02d}.csv",
        mime="text/csv",
        use_container_width=True
    )

# ---------------------------------------------------------
# [우측 컬럼 : 평균값 & Best/Worst 카드 (NaN 자동 제외)]
# ---------------------------------------------------------
st.markdown("""
<style>
    .metric-card-best {
        background-color: #E8F5E9; border-left: 5px solid #2E7D32; 
        padding: 12px; border-radius: 8px; margin-bottom: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .metric-card-worst {
        background-color: #FFEBEE; border-left: 5px solid #C62828;
        padding: 12px; border-radius: 8px; margin-bottom: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .card-title { font-size: 13px; color: #555555; font-weight: bold; margin-bottom: 3px; }
    .card-value { font-size: 20px; font-weight: 800; color: #111111; margin-bottom: 3px; }
    .card-week { font-size: 13px; font-weight: bold; color: #444444; }
</style>
""", unsafe_allow_html=True)

with bottom_col2:
    # 💡 dropna()를 통해 NaN/None 값을 완벽하게 제거한 유효 데이터 Series 생성
    s_otd = pd.Series(weekly_otd, index=valid_weeks).dropna()
    s_stockout = pd.Series(weekly_stockout, index=valid_weeks).dropna()
    s_mis = pd.Series(weekly_mis, index=valid_weeks).dropna()
    s_voc = pd.Series(weekly_voc, index=valid_weeks).dropna()

    # 전체 기간 평균 (NaN이 제거된 상태에서 평균 계산)
    avg_ontime = s_otd.mean() if not s_otd.empty else 0
    avg_non_delivery = s_stockout.mean() if not s_stockout.empty else 0
    avg_mis_delivery = s_mis.mean() if not s_mis.empty else 0
    avg_voc = s_voc.mean() if not s_voc.empty else 0
    sum_voc_total = s_voc.sum() if not s_voc.empty else 0

    card_row1_col1, card_row1_col2, card_row1_col3, card_row1_col4 = st.columns(4)
    with card_row1_col1: st.metric("정시배송(전체평균)", f"{avg_ontime:.1f}%")
    with card_row1_col2: st.metric("미납율(전체평균)", f"{avg_non_delivery:.1f}%")
    with card_row1_col3: st.metric("미오출율(전체평균)", f"{avg_mis_delivery:.1f}%")
    with card_row1_col4: st.metric("VOC(전체합계)", f"{int(sum_voc_total):,}건")

    # 🚚 정시배송율 (높을수록 Best - idxmax/idxmin은 NaN을 알아서 제외함)
    if not s_otd.empty:
        b1_idx = s_otd.idxmax(); best_1 = f"{s_otd[b1_idx]:.1f}%"; best_1_1 = str(b1_idx)
        w1_idx = s_otd.idxmin(); worst_1 = f"{s_otd[w1_idx]:.1f}%"; worst_1_1 = str(w1_idx)
    else:
        best_1 = worst_1 = "N/A"; best_1_1 = worst_1_1 = "-"

    # ⚠️ 미납율 (낮을수록 Best)
    if not s_stockout.empty:
        b2_idx = s_stockout.idxmin(); best_2 = f"{s_stockout[b2_idx]:.1f}%"; best_2_1 = str(b2_idx)
        w2_idx = s_stockout.idxmax(); worst_2 = f"{s_stockout[w2_idx]:.1f}%"; worst_2_1 = str(w2_idx)
    else:
        best_2 = worst_2 = "N/A"; best_2_1 = worst_2_1 = "-"

    # 🚨 미오출율 (낮을수록 Best)
    if not s_mis.empty:
        b3_idx = s_mis.idxmin(); best_3 = f"{s_mis[b3_idx]:.1f}%"; best_3_1 = str(b3_idx)
        w3_idx = s_mis.idxmax(); worst_3 = f"{s_mis[w3_idx]:.1f}%"; worst_3_1 = str(w3_idx)
    else:
        best_3 = worst_3 = "N/A"; best_3_1 = worst_3_1 = "-"

    # 📞 VOC (적을수록 Best)
    if not s_voc.empty:
        b4_idx = s_voc.idxmin(); best_4 = f"{int(s_voc[b4_idx])}"; best_4_1 = str(b4_idx)
        w4_idx = s_voc.idxmax(); worst_4 = f"{int(s_voc[w4_idx])}"; worst_4_1 = str(w4_idx)
    else:
        best_4 = worst_4 = "N/A"; best_4_1 = worst_4_1 = "-"

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="metric-card-best"><div class="card-title"> 정시배송 Best</div><div class="card-value">{best_1}</div><div class="card-week">📅 {best_1_1}주차</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric-card-worst"><div class="card-title"> 정시배송 Worst</div><div class="card-value">{worst_1}</div><div class="card-week">📅 {worst_1_1}주차</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-card-best"><div class="card-title"> 미납율 Best</div><div class="card-value">{best_2}</div><div class="card-week">📅 {best_2_1}주차</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric-card-worst"><div class="card-title"> 미납율 Worst</div><div class="card-value">{worst_2}</div><div class="card-week">📅 {worst_2_1}주차</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-card-best"><div class="card-title"> 미오출율 Best</div><div class="card-value">{best_3}</div><div class="card-week">📅 {best_3_1}주차</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric-card-worst"><div class="card-title"> 미오출율 Worst</div><div class="card-value">{worst_3}</div><div class="card-week">📅 {worst_3_1}주차</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="metric-card-best"><div class="card-title"> VOC Best</div><div class="card-value">{best_4}건</div><div class="card-week">📅 {best_4_1}주차</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric-card-worst"><div class="card-title"> VOC Worst</div><div class="card-value">{worst_4}건</div><div class="card-week">📅 {worst_4_1}주차</div></div>', unsafe_allow_html=True)
