import datetime
import io
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st

# =========================================================
# 데이터 로드 (세션 상태 확인)
# =========================================================
if "all_data" in st.session_state:
    db = st.session_state["all_data"]
    # C1 ~ C7 데이터 프레임 불러오기
    c1_df = db.get("c1", pd.DataFrame())
    c2_df = db.get("c2", pd.DataFrame())
    c3_df = db.get("c3", pd.DataFrame())
    c4_df = db.get("c4", pd.DataFrame())
    c5_df = db.get("c5", pd.DataFrame())
    c7_df = db.get("c7", pd.DataFrame())
else:
    st.error("⚠️ 데이터가 로드되지 않았습니다. 메인 페이지에서 데이터를 먼저 불러오세요.")
    st.stop()

# =========================================================
# 모바일 반응형 CSS 코드
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


# =========================================================
# 헬퍼 함수: 주차 컬럼명 매핑 및 필터별 Sum 연산
# =========================================================
def get_week_col_name(df, week):
    """주차 숫자(예: 10)를 받아 데이터프레임 내 매칭되는 컬럼명 반환"""
    if df.empty:
        return None
    possible_names = [f"{week}주차", f"W{week:02d}", f"W{week}", week, str(week)]
    for col in df.columns:
        if str(col).strip() in [str(p).strip() for p in possible_names]:
            return col
    return None

def get_filtered_sum(df, week, region_filter=None, team_filter=None):
    """조건 필터링 후 지정 주차의 합계 산출"""
    if df.empty:
        return np.nan
    
    filtered_df = df.copy()
    if region_filter:
        if isinstance(region_filter, list):
            if "권역" in filtered_df.columns:
                filtered_df = filtered_df[filtered_df["권역"].isin(region_filter)]
        elif isinstance(region_filter, str):
            if "권역" in filtered_df.columns:
                filtered_df = filtered_df[filtered_df["권역"] == region_filter]
                
    if team_filter and "팀" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["팀"] == team_filter]
        
    col = get_week_col_name(filtered_df, week)
    if not col or col not in filtered_df.columns:
        return np.nan

    s = pd.to_numeric(filtered_df[col], errors='coerce')
    val = s.sum(min_count=1)
    return val if pd.notna(val) else np.nan

def calc_kpi_metrics(week, region_filter=None, team_filter=None):
    """
    4대 KPI 산출 공식을 일괄 적용하여 반환하는 함수
    1. 정시배송율 = (C1 / C2) * 100
    2. 미납율 = (C5 - C3) / C5 * 100
    3. 미오출율 = (C3 - C7) / C3 * 100
    4. VOC실적 = C4
    """
    c1_sum = get_filtered_sum(c1_df, week, region_filter, team_filter)
    c2_sum = get_filtered_sum(c2_df, week, region_filter, team_filter)
    c3_sum = get_filtered_sum(c3_df, week, region_filter, team_filter)
    c4_sum = get_filtered_sum(c4_df, week, region_filter, team_filter)
    c5_sum = get_filtered_sum(c5_df, week, region_filter, team_filter)
    c7_sum = get_filtered_sum(c7_df, week, region_filter, team_filter)

    # 1. 정시배송율
    otd = (c1_sum / c2_sum * 100) if (pd.notna(c1_sum) and pd.notna(c2_sum) and c2_sum != 0) else np.nan
    # 2. 미납율
    nonpay = ((c5_sum - c3_sum) / c5_sum * 100) if (pd.notna(c5_sum) and pd.notna(c3_sum) and c5_sum != 0) else np.nan
    # 3. 미오출율
    mis = ((c3_sum - c7_sum) / c3_sum * 100) if (pd.notna(c3_sum) and pd.notna(c7_sum) and c3_sum != 0) else np.nan
    # 4. VOC
    voc = c4_sum if pd.notna(c4_sum) else np.nan

    return {
        "정시배송율": otd,
        "미납율": nonpay,
        "미오출율": mis,
        "VOC 실적": voc
    }

def format_value(val, is_pct=True):
    """
    🎯 None, NaN, 빈값을 일괄 '-'로 표시하고, 값이 있을 경우 지정 포맷 적용하는 함수
    """
    if pd.isna(val) or val is None or str(val).strip() in ["", "None", "nan", "NaN"]:
        return "-"
    try:
        float_val = float(val)
        if is_pct:
            return f"{float_val:.2f}%"
        else:
            return f"{int(float_val)}"
    except (ValueError, TypeError):
        return "-"

# =========================================================
# 오늘 기준 주차 계산 & 주차 범위 설정
# =========================================================
today_week = datetime.datetime.now().isocalendar()[1]
weeks_list = list(range(1, 54))

# =========================================================
# 사이드바 설정
# =========================================================
with st.sidebar:
    # -------------------- 주차 선택 --------------------
    with st.container(border=True):
        st.subheader("📅 전국평균 기간 선택 (범위)")
        st.caption("조회하고자 하는 시작 주차와 종료 주차를 드래그하세요.")

        start_default = max(1, today_week - 4)
        end_default = min(53, today_week + 4)

        start_w, end_w = st.select_slider(
            "주차 타임라인 범위 지정을 하세요",
            options=weeks_list,
            value=(start_default, end_default),
            format_func=lambda x: f"W{x:02d}"
        )

        total_selected_weeks = end_w - start_w + 1
        st.info(f"📊 **선택 구간:** 제 {start_w}주차 ~ 제 {end_w}주차 (총 {total_selected_weeks}주간)")

    # -------------------- 권역 선택 (최대 3개 제한) --------------------
    with st.container(border=True):
        st.subheader("🗺️ 분석 권역 선택 (최대 3개)")

        if "권역" in c1_df.columns:
            raw_regions = c1_df["권역"].dropna().unique()
            unique_regions = sorted([r for r in raw_regions if str(r).strip() != ""])
        else:
            unique_regions = []

        if unique_regions:
            # 기본값으로 상위 최대 3개까지만 선택
            default_regions = unique_regions[:min(3, len(unique_regions))]
            
            selected_regions = st.multiselect(
                "분석 대상 권역 (최대 3개 선택 가능)",
                options=unique_regions,
                default=default_regions,
                max_selections=3,  # 🎯 *** 여기가 권역수 제한 코드 *** 
                placeholder="권역을 선택하세요 (최대 3개)"
            )
        else:
            st.warning("⚠️ 권역 데이터가 없습니다.")
            selected_regions = []

        if len(selected_regions) == 0:
            st.error("⚠️ 최소 하나 이상의 권역을 선택해야 합니다.")
        else:
            st.info(f"🔍 **{len(selected_regions)}개 권역 선택됨** (최대 3개 제한)")


# =========================================================
# 상부영역: 주차별 전국 평균 (소수점 2째 자리 적용)
# =========================================================
selected_weeks = list(range(start_w, end_w + 1))

# 주차별 전국 평균 산출
nat_metrics = [calc_kpi_metrics(w) for w in selected_weeks]

summary_df = pd.DataFrame({
    "주차": selected_weeks,
    "정시배송율": [m["정시배송율"] for m in nat_metrics],
    "미납율": [m["미납율"] for m in nat_metrics],
    "미오출율": [m["미오출율"] for m in nat_metrics],
    "VOC 실적": [m["VOC 실적"] for m in nat_metrics]
})

# 피벗 변환 (전국평균)
summary_long = summary_df.melt(id_vars=["주차"], var_name="항목", value_name="값")
summary_long.insert(0, "팀", "전국평균")
summary_pivot = summary_long.pivot(index=["팀", "항목"], columns="주차", values="값").reset_index()

# 컬럼명에 '주차' 명시
summary_pivot.columns = [f"{col}주차" if isinstance(col, int) else col for col in summary_pivot.columns]

# 항목 순서 지정
order = ["정시배송율", "미납율", "미오출율", "VOC 실적"]
summary_pivot["항목"] = pd.Categorical(summary_pivot["항목"], categories=order, ordered=True)
summary_pivot = summary_pivot.sort_values("항목")

# 컬럼 설정 공유 (주차별 너비 고정 및 중앙 정렬)
col_config = {
    "팀": st.column_config.TextColumn("팀", width=120, alignment="center"),
    "권역": st.column_config.TextColumn("권역", width=120, alignment="center"),
    "항목": st.column_config.TextColumn("항목", width=120, alignment="center"),
}
for w in selected_weeks:
    col_config[f"{w}주차"] = st.column_config.TextColumn(f"{w}주차", width=100, alignment="center")

# 화면 표시용 서식 지정 (소수점 2째 자리 .2f 적용)
summary_display = summary_pivot.copy()
for col in summary_display.columns:
    if "주차" in col:
        summary_display[col] = summary_display.apply(
            lambda r: (
                f"{r[col]:.2f}%" if pd.notna(r[col]) and r["항목"] != "VOC 실적"
                else (f"{int(r[col])}" if pd.notna(r[col]) else "-")
            ), axis=1
        )

st.markdown(f"## 📊 {start_w}주차 ~ {end_w}주차 전국 평균 요약")
st.dataframe(summary_display, use_container_width=True, hide_index=True, column_config=col_config)


# =========================================================
# 🌐 중간영역: 권역별 요약 (선택 권역 기준 - 최대 3개)
# =========================================================
if selected_regions:
    st.markdown("---")
    st.markdown("### 🌐 권역별 요약")

    region_rows = []
    for region in selected_regions:
        for metric_label in ["정시배송율", "미납율", "미오출율", "VOC 실적"]:
            row = {"권역": region, "항목": metric_label}
            for w in selected_weeks:
                m_val = calc_kpi_metrics(w, region_filter=region)
                row[f"{w}주차"] = m_val[metric_label]
            region_rows.append(row)

    region_summary = pd.DataFrame(region_rows)

    if not region_summary.empty:
        metric_order = ["정시배송율", "미납율", "미오출율", "VOC 실적"]
        region_summary["항목"] = pd.Categorical(region_summary["항목"], categories=metric_order, ordered=True)
        region_summary = region_summary.sort_values(["권역", "항목"])

        reg_display_df = region_summary.copy()
        avg_dict = summary_df.set_index("주차").to_dict()
        reg_metrics_list = reg_display_df["항목"].tolist()

        # 권역명 중복 병합 시각화 처리
        reg_display_df["권역"] = reg_display_df["권역"].astype(str)
        reg_display_df.loc[reg_display_df.duplicated(subset=["권역"], keep="first"), "권역"] = ""

        def highlight_region_cells(col_data):
            column_name = col_data.name
            if "주차" not in column_name:
                return [""] * len(col_data)
            
            week_num = int(column_name.replace("주차", ""))
            styles = []
            
            for idx, val in enumerate(col_data):
                metric = reg_metrics_list[idx]
                target_avg = avg_dict.get(metric, {}).get(week_num, np.nan)
                
                if pd.notna(val) and pd.notna(target_avg):
                    val_f = float(val)
                    avg_f = float(target_avg)
                    if metric == "정시배송율" and val_f < avg_f:
                        styles.append("background-color: #FEE2E2; color: #991B1B; text-align: center;")
                    elif metric in ["미납율", "미오출율", "VOC 실적"] and val_f > avg_f:
                        styles.append("background-color: #FEE2E2; color: #991B1B; text-align: center;")
                    else: 
                        styles.append("text-align: center;")
                else: 
                    styles.append("text-align: center;")
            return styles

        reg_ratio_idx = reg_display_df["항목"].isin(["정시배송율", "미납율", "미오출율"])
        weeks_cols = [col for col in reg_display_df.columns if "주차" in col]

        # 포맷팅 적용 (비율은 .2f%, VOC는 정수)
        styled_reg_table = (
            reg_display_df.style
            .set_properties(**{'text-align': 'center'})
            .set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}])
            .apply(highlight_region_cells, axis=0)
            .format(lambda v: f"{float(v):.2f}%" if pd.notna(v) else "-", subset=(reg_ratio_idx, weeks_cols))
            .format(lambda v: f"{int(float(v))}" if pd.notna(v) else "-", subset=(~reg_ratio_idx, weeks_cols))
        )

        st.dataframe(styled_reg_table, use_container_width=True, hide_index=True, column_config=col_config)


# =========================================================
# 하부영역: 팀별 요약 및 하이라이트
# =========================================================
filtered_teams = []
if "팀" in c1_df.columns:
    if selected_regions:
        filtered_teams = c1_df[c1_df["권역"].isin(selected_regions)]["팀"].dropna().unique().tolist()
    else:
        filtered_teams = c1_df["팀"].dropna().unique().tolist()

rows = []
for team in filtered_teams:
    for metric_label in ["정시배송율", "미납율", "미오출율", "VOC 실적"]:
        row = {"팀": team, "항목": metric_label}
        for w in selected_weeks:
            m_val = calc_kpi_metrics(w, region_filter=selected_regions, team_filter=team)
            row[f"{w}주차"] = m_val[metric_label]
        rows.append(row)

team_summary = pd.DataFrame(rows)

if not team_summary.empty:
    st.markdown("---")
    st.markdown("### 🏢 팀별 요약")

    metric_order = ["정시배송율", "미납율", "미오출율", "VOC 실적"]
    team_summary["항목"] = pd.Categorical(team_summary["항목"], categories=metric_order, ordered=True)
    team_summary = team_summary.sort_values(["팀", "항목"])

    display_df = team_summary.copy()
    avg_dict = summary_df.set_index("주차").to_dict()
    metrics_list = display_df["항목"].tolist()

    # 팀명 중복 병합 시각화 처리
    display_df["팀"] = display_df["팀"].astype(str)
    display_df.loc[display_df.duplicated(subset=["팀"], keep="first"), "팀"] = ""

    # 하이라이트 스타일 함수
    def highlight_cells(col_data):
        column_name = col_data.name
        if "주차" not in column_name:
            return [""] * len(col_data)
        
        week_num = int(column_name.replace("주차", ""))
        styles = []
        
        for idx, val in enumerate(col_data):
            metric = metrics_list[idx]
            target_avg = avg_dict.get(metric, {}).get(week_num, np.nan)
            
            if pd.notna(val) and pd.notna(target_avg):
                val_f = float(val)
                avg_f = float(target_avg)
                if metric == "정시배송율" and val_f < avg_f:
                    styles.append("background-color: #FEE2E2; color: #991B1B; text-align: center;")
                elif metric in ["미납율", "미오출율", "VOC 실적"] and val_f > avg_f:
                    styles.append("background-color: #FEE2E2; color: #991B1B; text-align: center;")
                else: 
                    styles.append("text-align: center;")
            else: 
                styles.append("text-align: center;")
        return styles

    ratio_idx = display_df["항목"].isin(["정시배송율", "미납율", "미오출율"])
    weeks_cols = [col for col in display_df.columns if "주차" in col]

    # 포맷팅 적용 (비율은 .2f%, VOC는 정수)
    styled_table = (
        display_df.style
        .set_properties(**{'text-align': 'center'})
        .set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}])
        .apply(highlight_cells, axis=0)
        .format(lambda v: f"{float(v):.2f}%" if pd.notna(v) else "-", subset=(ratio_idx, weeks_cols))
        .format(lambda v: f"{int(float(v))}" if pd.notna(v) else "-", subset=(~ratio_idx, weeks_cols))
    )

    st.dataframe(styled_table, use_container_width=True, hide_index=True, column_config=col_config)


# =========================================================
# 📊 [시각화] 전국평균 vs 선택 팀 4대 지표 트렌드 비교 차트
# =========================================================
st.markdown("---")
st.markdown("<h3 style='font-size: 1.5rem; font-weight: bold; margin-bottom: 0rem;'>📈 주요 지표별 추이 상세 분석</h3>", unsafe_allow_html=True)

if filtered_teams:
    selected_team_for_chart = st.selectbox(
        "🎯 트렌드 분석을 진행할 팀을 선택하세요", 
        options=filtered_teams,
        key="global_team_chart_selector"
    )
    
    avg_trend_df = summary_df.set_index("주차")
    
    metrics_config = [
        {"name": "정시배송율", "title": "정시배송율 (%)", "is_pct": True, "unit": "%", "color": "#1E3A8A"},
        {"name": "미납율", "title": "미납율 (%)", "is_pct": True, "unit": "%", "color": "#EA580C"},
        {"name": "미오출율", "title": "미오출율 (%)", "is_pct": True, "unit": "%", "color": "#D97706"},
        {"name": "VOC 실적", "title": "VOC 건수 (건)", "is_pct": False, "unit": "건", "color": "#DC2626"}
    ]
    
    for m in metrics_config:
        m_key = m['name']
        avg_series = avg_trend_df[m_key]
        
        team_trend_vals = [
            calc_kpi_metrics(w, region_filter=selected_regions, team_filter=selected_team_for_chart)[m_key]
            for w in selected_weeks
        ]
            
        fig = go.Figure()
        unit = m['unit']
        
        # 1. 전국 평균 선
        avg_vals = [avg_series.get(w, np.nan) for w in selected_weeks]
        avg_fmt = "%{y:.2f}" + unit if m['is_pct'] else "%{y:.0f}" + unit
        
        fig.add_trace(go.Scatter(
            x=[f"W{w:02d}" for w in selected_weeks],
            y=avg_vals,
            mode='lines+markers',
            name='전국 평균',
            line=dict(color='gray', dash='dash', width=2),
            hovertemplate=f"전국 평균: <b>{avg_fmt}</b><extra></extra>"
        ))
        
        # 2. 선택 팀 선
        text_labels = [
            (f"{v:.2f}%" if m['is_pct'] else f"{int(v)}건") if pd.notna(v) else ""
            for v in team_trend_vals
        ]
        
        team_fmt = "%{y:.2f}" + unit if m['is_pct'] else "%{y:.0f}" + unit
        
        fig.add_trace(go.Scatter(
            x=[f"W{w:02d}" for w in selected_weeks],
            y=team_trend_vals,
            mode='lines+markers+text',
            name=selected_team_for_chart,
            text=text_labels,
            textposition="top center",
            line=dict(color=m['color'], width=3),
            hovertemplate=f"{selected_team_for_chart}: <b>{team_fmt}</b><extra></extra>"
        ))
        
        fig.update_layout(
            title=f"<b>[{selected_team_for_chart}] vs 전국 평균 {m_key} 비교</b>",
            xaxis_title="조회 주차",
            yaxis_title=m['title'],
            hovermode="x unified",
            height=350,
            margin=dict(l=20, r=20, t=50, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
else:
    st.warning("조회된 팀 데이터가 없어 차트를 생성할 수 없습니다.")
