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
# 오늘 기준 주차 계산
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

        # 기본값 범위 안전 처리
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
            unique_regions = sorted(list(raw_regions))
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

        # 선택된 권역 수에 따른 뱃지
        if len(selected_regions) == len(unique_regions) and len(unique_regions) > 0:
            st.success(f"🌐 **전체 {len(selected_regions)}개 권역 관제 중**")
        elif len(selected_regions) == 0:
            st.error("⚠️ 최소 하나 이상의 권역을 선택해야 합니다.")
        else:
            st.info(f"🔍 **{len(selected_regions)}개 권역 선택됨**")


# =========================================================
# 상부영역: 주차별 전국 평균 (사이드바 주차 범위 연동)
# =========================================================

selected_weeks = list(range(start_w, end_w + 1))

# 주차 범위 필터링
c1_range = c1_df[(c1_df["주차"] >= start_w) & (c1_df["주차"] <= end_w)]
c2_range = c2_df[(c2_df["주차"] >= start_w) & (c2_df["주차"] <= end_w)]
c3_range = c3_df[(c3_df["주차"] >= start_w) & (c3_df["주차"] <= end_w)]
c4_range = c4_df[(c4_df["주차"] >= start_w) & (c4_df["주차"] <= end_w)]

# 1. 정시배송율 (%)
c1_agg = c1_range.groupby("주차")[["정시배송", "총배송"]].sum()
on_time_rate = ((c1_agg["정시배송"] / c1_agg["총배송"]) * 100).fillna(0).reindex(selected_weeks, fill_value=0)

# 2. 미납율 (%) -> [수정] (발주 - 출하) / 발주 기준
c2_agg = c2_range.groupby("주차")[["발주금액", "출하금액"]].sum()
non_payment_rate = (((c2_agg["발주금액"] - c2_agg["출하금액"]) / c2_agg["발주금액"]) * 100).fillna(0).reindex(selected_weeks, fill_value=0)

# 3. 미오출율 (%) -> [수정] (출하 - 점포확정) / 출하 기준
c3_agg = c3_range.groupby("주차")[["출하금액", "점포확정금액"]].sum()
non_shipment_rate = (((c3_agg["출하금액"] - c3_agg["점포확정금액"]) / c3_agg["출하금액"]) * 100).fillna(0).reindex(selected_weeks, fill_value=0)

# 4. VOC 실적 (건)
voc_count = c4_range.groupby("주차")["VOC_건수"].sum().reindex(selected_weeks, fill_value=0)

# 5. 합치기
summary_df = pd.DataFrame({
    "정시배송율": on_time_rate,
    "미납율": non_payment_rate,
    "미오출율": non_shipment_rate,
    "VOC 실적": voc_count
}).reset_index().rename(columns={"index": "주차"})

# 6. long → pivot 변환
summary_long = summary_df.melt(id_vars=["주차"], var_name="항목", value_name="값")
summary_long.insert(0, "대상", "전국평균")
summary_pivot = summary_long.pivot(index=["대상", "항목"], columns="주차", values="값").reset_index()

# 7. 주차 열 이름에 "주차" 붙이기
summary_pivot.columns = [col if isinstance(col, str) else f"{col}주차" for col in summary_pivot.columns]

# 8. 항목 순서 재정렬
order = ["정시배송율", "미납율", "미오출율", "VOC 실적"]
summary_pivot["항목"] = pd.Categorical(summary_pivot["항목"], categories=order, ordered=True)
summary_pivot = summary_pivot.sort_values("항목")

# 9. 값 포맷팅 -> [수정] 소수점 1자리 실수 반영 및 VOC 정수 처리
for col in summary_pivot.columns:
    if "주차" in col:
        summary_pivot[col] = summary_pivot.apply(
            lambda row: f"{row[col]:.1f}%" if row["항목"] != "VOC 실적" 
            else (f"{int(row[col])}" if row[col] % 1 == 0 else f"{row[col]:.0f}"),
            axis=1
        )


# =========================================================
# [최종 완성] 멀티인덱스 해제를 통한 에러 차단 + 병합 효과 완료본
# =========================================================

# 10. 상단 전국평균 테이블 구조화
# 인덱스로 묶지 않고 일반 컬럼 형태로 정렬과 스타일을 처리합니다.
summary_pivot_aligned = summary_pivot.rename(columns={"대상": "팀"})

# 컬럼 설정 공유 (주차별 너비 고정 및 값 정렬)
col_config = {
    "팀": st.column_config.TextColumn("팀", width=120, alignment="center"),
    "항목": st.column_config.TextColumn("항목", width=120, alignment="center"),
}

for col in summary_pivot_aligned.columns:
    if "주차" in col:
        col_config[col] = st.column_config.TextColumn(col, width=100, alignment="center")

# 11. 전국 평균 출력 (hide_index=True를 주어 기본 정수 인덱스를 숨깁니다)
st.markdown(f"##  {start_w}주차 ~ {end_w}주차 전국 평균 요약")
styled_summary = (
    summary_pivot_aligned.style
    .set_properties(**{'text-align': 'center'})
    .set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}])
)
st.dataframe(styled_summary, use_container_width=True, hide_index=True, column_config=col_config)


# -------------------- 팀별 묶기 --------------------
filtered_teams = c1_df[c1_df["권역"].isin(selected_regions)]["팀"].dropna().unique().tolist()

def calc_on_time_rate(team, week):
    df = c1_df[(c1_df["권역"].isin(selected_regions)) & (c1_df["팀"] == team) & (c1_df["주차"] == week)]
    if df.empty: return 0
    return (df["정시배송"].sum() / df["총배송"].sum() * 100)

def calc_non_payment_rate(team, week):
    df = c2_df[(c2_df["권역"].isin(selected_regions)) & (c2_df["팀"] == team) & (c2_df["주차"] == week)]
    if df.empty: return 0
    return ((df["발주금액"].sum() - df["출하금액"].sum()) / df["발주금액"].sum() * 100)

def calc_non_shipment_rate(team, week):
    df = c3_df[(c3_df["권역"].isin(selected_regions)) & (c3_df["팀"] == team) & (c3_df["주차"] == week)]
    if df.empty: return 0
    return ((df["출하금액"].sum() - df["점포확정금액"].sum()) / df["출하금액"].sum() * 100)

def calc_voc_count(team, week):
    df = c4_df[(c4_df["권역"].isin(selected_regions)) & (c4_df["팀"] == team) & (c4_df["주차"] == week)]
    if df.empty: return 0
    return df["VOC_건수"].sum()

# 3. 팀별 요약 테이블 생성
rows = []
for team in filtered_teams:
    for metric in ["정시배송율","미납율","미오출율","VOC실적"]:
        row = {"팀": team, "항목": metric}
        for week in selected_weeks:
            if metric == "정시배송율": row[week] = calc_on_time_rate(team, week)
            elif metric == "미납율": row[week] = calc_non_payment_rate(team, week)
            elif metric == "미오출율": row[week] = calc_non_shipment_rate(team, week)
            elif metric == "VOC실적": row[week] = calc_voc_count(team, week)
        rows.append(row)

team_summary = pd.DataFrame(rows)

metric_order = ["정시배송율","미납율","미오출율","VOC실적"]
team_summary["항목"] = pd.Categorical(team_summary["항목"], categories=metric_order, ordered=True)
team_summary = team_summary.sort_values(["팀","항목"])

# 5. 출력 및 하이라이트 스타일링
st.markdown("###  팀별 요약")

display_df = team_summary.copy()
display_df.columns = [f"{col}주차" if isinstance(col, int) else col for col in display_df.columns]
avg_dict = summary_df.set_index("주차").to_dict()

# [중요] 지표(metric) 판별용 리스트를 생성해 둡니다.
metrics_list = display_df["항목"].tolist()

# [병합 트릭] 팀 열을 문자열로 바꾸고 중복되는 팀명은 빈칸("")으로 변경합니다.
display_df["팀"] = display_df["팀"].astype(str)
display_df.loc[display_df.duplicated(subset=["팀"], keep="first"), "팀"] = ""

# 중요: .set_index()를 하지 않고 기본 일련번호 인덱스(고유함)를 그대로 유지합니다.
# 대신 hide_index=True로 출력하여 화면에서는 인덱스를 숨길 겁니다.

def highlight_cells(col_data):
    column_name = col_data.name
    if "주차" not in column_name: return [""] * len(col_data)
    
    week_num = int(column_name.replace("주차", ""))
    styles = []
    
    # row_idx 대신 미리 확보해 둔 지표 리스트(metrics_list)와 연동하여 정확하게 비교합니다.
    for idx, val in enumerate(col_data):
        metric = metrics_list[idx]
        avg_metric = "VOC 실적" if metric == "VOC실적" else metric
        target_avg = avg_dict.get(avg_metric, {}).get(week_num, None)
        
        if target_avg is not None:
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
# subset 지정 시 컬럼 리스트만 명시하여 전체 행에 적용되도록 유연하게 대처합니다.
weeks_cols = [col for col in display_df.columns if "주차" in col]

# 스타일 및 포맷팅 적용
styled_table = (
    display_df.style
    .set_properties(**{'text-align': 'center'})
    .set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}])
    .apply(highlight_cells, axis=0)
    .format(lambda v: f"{float(v):.1f}%", subset=(ratio_idx, weeks_cols))
    .format(lambda v: f"{int(float(v))}" if float(v) % 1 == 0 else f"{float(v):.0f}", subset=(~ratio_idx, weeks_cols))
)

# 최종 출력 (두 테이블 모두 hide_index=True 구조로 열 너비 정렬선이 완벽하게 일치합니다!)
st.dataframe(styled_table, use_container_width=True, hide_index=True, column_config=col_config)

# =========================================================
# 📊 [시각화 확장] 전국평균 vs 선택 팀 4대 지표 트렌드 비교 차트
# =========================================================
st.markdown("---")
st.markdown("<h3 style='font-size: 1.5rem; font-weight: bold; margin-bottom: 0rem;'>📈 주요 지표별 추이 상세 분석</h3>", unsafe_allow_html=True)
if filtered_teams:
    # 1. 팀 선택 (여기서 한 번만 고르면 아래 4개 차트에 모두 반영됩니다)
    selected_team_for_chart = st.selectbox(
        "🎯 트렌드 분석을 진행할 팀을 선택하세요", 
        options=filtered_teams,
        key="global_team_chart_selector"
    )
    
    # 전국 평균 매핑 데이터 사전 준비
    avg_trend_df = summary_df.set_index("주차")
    
    # 차트 생성을 위한 반복 설정 (지표명, Y축 타이틀, 퍼센트 여부, 차트 색상)
    metrics_config = [
        {"name": "정시배송율", "title": "정시배송율 (%)", "is_pct": True, "color": "#1E3A8A"},   # 신뢰감 높은 블루
        {"name": "미납율", "title": "미납율 (%)", "is_pct": True, "color": "#EA580C"},       # 오렌지
        {"name": "미오출율", "title": "미오출율 (%)", "is_pct": True, "color": "#D97706"},     # 옐로우 브라운
        {"name": "VOC실적", "title": "VOC 건수 (건)", "is_pct": False, "color": "#DC2626"}    # 경고 레드 (원 데이터의 'VOC실적' 매칭)
    ]
    
    # 2. 4개 항목 반복 돌며 차트 생성
    for m in metrics_config:
        
        # [A] 전국 평균 데이터 추출
        # 평균 데이터프레임의 지표명이 VOC만 'VOC 실적'으로 되어 있어 예외 처리 적용
        avg_metric_name = "VOC 실적" if m['name'] == "VOC실적" else m['name']
        avg_series = avg_trend_df[avg_metric_name]
        
        # [B] 선택된 팀의 주차별 데이터 계산
        team_trend_vals = []
        for week in selected_weeks:
            if m['name'] == "정시배송율":
                val = calc_on_time_rate(selected_team_for_chart, week)
            elif m['name'] == "미납율":
                val = calc_non_payment_rate(selected_team_for_chart, week)
            elif m['name'] == "미오출율":
                val = calc_non_shipment_rate(selected_team_for_chart, week)
            elif m['name'] == "VOC실적":
                val = calc_voc_count(selected_team_for_chart, week)
            team_trend_vals.append(val)
            
        # [C] Plotly 시각화 구성
        fig = go.Figure()
        
        # 트렌드 라인 1: 전국 평균 (점선)
        fig.add_trace(go.Scatter(
            x=[f"W{w:02d}" for w in selected_weeks],
            y=[avg_series.get(w, 0) for w in selected_weeks],
            mode='lines+markers',
            name='전국 평균',
            line=dict(color='gray', dash='dash', width=2)
        ))
        
        # 트렌드 라인 2: 선택 팀 (실선 + 데이터 레이블)
        text_labels = [f"{v:.1f}%" if m['is_pct'] else f"{int(v)}건" for v in team_trend_vals]
        fig.add_trace(go.Scatter(
            x=[f"W{w:02d}" for w in selected_weeks],
            y=team_trend_vals,
            mode='lines+markers+text',
            name=selected_team_for_chart,
            text=text_labels,
            textposition="top center",
            line=dict(color=m['color'], width=3)
        ))
        
        # 레이아웃 정밀 튜닝
        fig.update_layout(
            title=f"<b>[{selected_team_for_chart}] vs 전국 평균 {m['name']} 비교</b>",
            xaxis_title="조회 주차",
            yaxis_title=m['title'],
            hovermode="x unified",
            height=350, # 4개가 들어가므로 높이를 기존보다 살짝 줄여 쾌적하게 구성
            margin=dict(l=20, r=20, t=50, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
else:
    st.warning("조회된 팀 데이터가 없어 차트를 생성할 수 없습니다.")