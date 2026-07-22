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
    # 키 존재 여부 확인
    c1_df = db.get("c1", pd.DataFrame())
    c2_df = db.get("c2", pd.DataFrame())
    c3_df = db.get("c3", pd.DataFrame())
    c4_df = db.get("c4", pd.DataFrame())
    c5_df = db.get("c5", pd.DataFrame())
else:
    st.error("⚠️ 데이터가 로드되지 않았습니다. 메인 페이지에서 데이터를 먼저 불러오세요.")
    st.stop()


# =========================================================
# 헬퍼 함수: 주차 컬럼명 자동 매핑 및 유효 데이터 계산
# =========================================================
def get_week_col_name(df, week):
    """주차 숫자(예: 10)를 받아 데이터프레임 내 매칭되는 컬럼명(예: '10주차', 'W10', 10)을 반환"""
    if df.empty:
        return None
    possible_names = [f"{week}주차", f"W{week:02d}", f"W{week}", week, str(week)]
    for col in df.columns:
        if str(col).strip() in [str(p).strip() for p in possible_names]:
            return col
    return None

def calc_metric_val(df, week, metric_type, region_filter=None, team_filter=None):
    """
    지정된 주차, 권역, 팀 조건에 따라 수치 산출 (NaN 자동 변환 및 미출력 처리)
    """
    if df.empty:
        return np.nan
    
    # 조건 필터링
    filtered_df = df.copy()
    if region_filter and "권역" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["권역"].isin(region_filter)]
    if team_filter and "팀" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["팀"] == team_filter]
        
    col = get_week_col_name(filtered_df, week)
    if not col or col not in filtered_df.columns:
        return np.nan

    s = pd.to_numeric(filtered_df[col], errors='coerce')
    
    # 지표 종류에 따른 합계/평균 연산
    if metric_type == "sum":
        val = s.sum(min_count=1)  # 전체가 NaN이면 0이 아닌 NaN 반환
    else:
        val = s.mean()
        
    return val if pd.notna(val) else np.nan


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

    # -------------------- 권역 선택 --------------------
    with st.container(border=True):
        st.subheader("🗺️ 분석 권역 선택 ")

        if "권역" in c1_df.columns:
            raw_regions = c1_df["권역"].dropna().unique()
            unique_regions = sorted([r for r in raw_regions if str(r).strip() != ""])
        else:
            unique_regions = []

        all_selected = st.checkbox("⚙️ 전체 권역 일괄 선택", value=True)

        if unique_regions:
            if all_selected:
                selected_regions = st.multiselect(
                    "분석 대상 권역 (다중 선택 가능)",
                    options=unique_regions,
                    default=unique_regions,
                    placeholder="권역을 검색하거나 선택하세요."
                )
            else:
                selected_regions = st.multiselect(
                    "분석 대상 권역 (다중 선택 가능)",
                    options=unique_regions,
                    default=[unique_regions[0]],
                    placeholder="권역을 검색하거나 선택하세요."
                )
        else:
            st.warning("⚠️ 권역 데이터가 없습니다.")
            selected_regions = []

        if len(selected_regions) == len(unique_regions) and len(unique_regions) > 0:
            st.success(f"🌐 **전체 {len(selected_regions)}개 권역 관제 중**")
        elif len(selected_regions) == 0:
            st.error("⚠️ 최소 하나 이상의 권역을 선택해야 합니다.")
        else:
            st.info(f"🔍 **{len(selected_regions)}개 권역 선택됨**")


# =========================================================
# 상부영역: 주차별 전국 평균 (선택 범위 연동 & NaN 미출력)
# =========================================================
selected_weeks = list(range(start_w, end_w + 1))

# 전국 평균 데이터 수집
nat_otd = [calc_metric_val(c1_df, w, "mean") for w in selected_weeks]
nat_stockout = [calc_metric_val(c2_df, w, "mean") for w in selected_weeks]
nat_mis = [calc_metric_val(c3_df, w, "mean") for w in selected_weeks]
nat_voc = [calc_metric_val(c4_df, w, "sum") for w in selected_weeks]

summary_df = pd.DataFrame({
    "주차": selected_weeks,
    "정시배송율": nat_otd,
    "미납율": nat_stockout,
    "미오출율": nat_mis,
    "VOC 실적": nat_voc
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
    "항목": st.column_config.TextColumn("항목", width=120, alignment="center"),
}
for w in selected_weeks:
    col_config[f"{w}주차"] = st.column_config.TextColumn(f"{w}주차", width=100, alignment="center")

# 화면 표시용 서식 지정 (NaN은 '-'로 미출력)
summary_display = summary_pivot.copy()
for col in summary_display.columns:
    if "주차" in col:
        summary_display[col] = summary_display.apply(
            lambda r: (
                f"{r[col]:.1f}%" if pd.notna(r[col]) and r["항목"] != "VOC 실적"
                else (f"{int(r[col])}" if pd.notna(r[col]) else "-")
            ), axis=1
        )

st.markdown(f"## 📊 {start_w}주차 ~ {end_w}주차 전국 평균 요약")
st.dataframe(summary_display, use_container_width=True, hide_index=True, column_config=col_config)


# =========================================================
# 하부영역: 팀별 요약 및 하이라이트 (NaN 자동 제외)
# =========================================================
filtered_teams = []
if "팀" in c1_df.columns:
    if selected_regions:
        filtered_teams = c1_df[c1_df["권역"].isin(selected_regions)]["팀"].dropna().unique().tolist()
    else:
        filtered_teams = c1_df["팀"].dropna().unique().tolist()

rows = []
for team in filtered_teams:
    for metric_label, df_ref, m_type in [
        ("정시배송율", c1_df, "mean"),
        ("미납율", c2_df, "mean"),
        ("미오출율", c3_df, "mean"),
        ("VOC실적", c4_df, "sum")
    ]:
        row = {"팀": team, "항목": metric_label}
        for w in selected_weeks:
            row[f"{w}주차"] = calc_metric_val(df_ref, w, m_type, region_filter=selected_regions, team_filter=team)
        rows.append(row)

team_summary = pd.DataFrame(rows)

if not team_summary.empty:
    metric_order = ["정시배송율", "미납율", "미오출율", "VOC실적"]
    team_summary["항목"] = pd.Categorical(team_summary["항목"], categories=metric_order, ordered=True)
    team_summary = team_summary.sort_values(["팀", "항목"])

    st.markdown("### 🏢 팀별 요약")

    display_df = team_summary.copy()
    avg_dict = summary_df.set_index("주차").to_dict()

    metrics_list = display_df["항목"].tolist()

    # 팀명 중복 병합 시각화 처리
    display_df["팀"] = display_df["팀"].astype(str)
    display_df.loc[display_df.duplicated(subset=["팀"], keep="first"), "팀"] = ""

    # 하이라이트 스타일 함수 (NaN 안전 처리)
    def highlight_cells(col_data):
        column_name = col_data.name
        if "주차" not in column_name:
            return [""] * len(col_data)
        
        week_num = int(column_name.replace("주차", ""))
        styles = []
        
        for idx, val in enumerate(col_data):
            metric = metrics_list[idx]
            avg_metric = "VOC 실적" if metric == "VOC실적" else metric
            target_avg = avg_dict.get(avg_metric, {}).get(week_num, np.nan)
            
            # 수치가 둘 다 존재(NaN이 아님)하는 경우에만 비교 수행
            if pd.notna(val) and pd.notna(target_avg):
                val_f = float(val)
                avg_f = float(target_avg)
                if metric == "정시배송율" and val_f < avg_f:
                    styles.append("background-color: #FEE2E2; color: #991B1B; text-align: center;")
                elif metric in ["미납율", "미오출율", "VOC실적"] and val_f > avg_f:
                    styles.append("background-color: #FEE2E2; color: #991B1B; text-align: center;")
                else: 
                    styles.append("text-align: center;")
            else: 
                styles.append("text-align: center;")
        return styles

    ratio_idx = display_df["항목"].isin(["정시배송율", "미납율", "미오출율"])
    weeks_cols = [col for col in display_df.columns if "주차" in col]

    # 포맷팅 적용 (NaN은 '-' 로 출력)
    styled_table = (
        display_df.style
        .set_properties(**{'text-align': 'center'})
        .set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}])
        .apply(highlight_cells, axis=0)
        .format(lambda v: f"{float(v):.1f}%" if pd.notna(v) else "-", subset=(ratio_idx, weeks_cols))
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
        {"name": "정시배송율", "df": c1_df, "type": "mean", "title": "정시배송율 (%)", "is_pct": True, "unit": "%", "color": "#1E3A8A"},
        {"name": "미납율", "df": c2_df, "type": "mean", "title": "미납율 (%)", "is_pct": True, "unit": "%", "color": "#EA580C"},
        {"name": "미오출율", "df": c3_df, "type": "mean", "title": "미오출율 (%)", "is_pct": True, "unit": "%", "color": "#D97706"},
        {"name": "VOC실적", "df": c4_df, "type": "sum", "title": "VOC 건수 (건)", "is_pct": False, "unit": "건", "color": "#DC2626"}
    ]
    
    for m in metrics_config:
        avg_metric_name = "VOC 실적" if m['name'] == "VOC실적" else m['name']
        avg_series = avg_trend_df[avg_metric_name]
        
        team_trend_vals = [
            calc_metric_val(m['df'], w, m['type'], region_filter=selected_regions, team_filter=selected_team_for_chart)
            for w in selected_weeks
        ]
            
        fig = go.Figure()
        
        # 단위 지정 (% 또는 건)
        unit = m['unit']
        
        # 1. 전국 평균 선 (호버 포맷 추가: % / 건 단위 명시)
        avg_vals = [avg_series.get(w, np.nan) for w in selected_weeks]
        avg_fmt = "%{y:.1f}" + unit if m['is_pct'] else "%{y:.0f}" + unit
        
        fig.add_trace(go.Scatter(
            x=[f"W{w:02d}" for w in selected_weeks],
            y=avg_vals,
            mode='lines+markers',
            name='전국 평균',
            line=dict(color='gray', dash='dash', width=2),
            hovertemplate=f"전국 평균: <b>{avg_fmt}</b><extra></extra>"
        ))
        
        # 2. 선택 팀 선 (중복 출력 제거: hovertemplate으로 지정하여 1번만 노출)
        text_labels = [
            (f"{v:.1f}%" if m['is_pct'] else f"{int(v)}건") if pd.notna(v) else ""
            for v in team_trend_vals
        ]
        
        team_fmt = "%{y:.1f}" + unit if m['is_pct'] else "%{y:.0f}" + unit
        
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
            title=f"<b>[{selected_team_for_chart}] vs 전국 평균 {m['name']} 비교</b>",
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
