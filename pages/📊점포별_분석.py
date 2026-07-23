import json
from datetime import datetime
import folium
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

# =========================================================
# 0. 페이지 설정
# =========================================================
st.set_page_config(layout="wide", page_title="전국 점포 및 KPI 종합 분석")

# =========================================================
# 모바일 반응형 CSS 코드
# =========================================================
st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)


# =========================================================
# 1. 데이터 로드 (세션 상태 확인)
# =========================================================
if "all_data" in st.session_state:
  db = st.session_state["all_data"]
  c1_df = db.get("c1", pd.DataFrame())
  c2_df = db.get("c2", pd.DataFrame())
  c3_df = db.get("c3", pd.DataFrame())
  c4_df = db.get("c4", pd.DataFrame())
  c5_df = db.get("c5", pd.DataFrame())
  c6_df = db.get("c6", pd.DataFrame())
  c7_df = db.get("c7", pd.DataFrame())  # C7 추가
else:
  st.error(
      "⚠️ 데이터가 로드되지 않았습니다. 메인 페이지에서 데이터를 먼저 불러오세요."
  )
  st.stop()

# C6 데이터 전처리
df_c6 = c6_df.copy()
if not df_c6.empty and all(
    col in df_c6.columns for col in ["점포명", "위도", "경도"]
):
  df_c6["위도"] = pd.to_numeric(df_c6["위도"], errors="coerce")
  df_c6["경도"] = pd.to_numeric(df_c6["경도"], errors="coerce")
  df_c6 = df_c6.dropna(subset=["위도", "경도"])
  store_list = df_c6["점포명"].unique().tolist()
else:
  store_list = []


# GeoJSON 불러오기
@st.cache_data
def load_geojson():
  try:
    with open("korea_sigungoo.geo.json", encoding="utf-8") as f:
      return json.load(f)
  except Exception as e:
    st.error(f"❌ GeoJSON 파일 로드 오류: {e}")
    return None


geojson_data = load_geojson()


# =========================================================
# 헬퍼 함수: C1~C7 주차 컬럼 정확한 명칭 찾기
# =========================================================
def get_week_col_name(df, week):
  if df.empty:
    return None
  possible_names = [f"{week}주차", f"W{week:02d}", f"W{week}", week, str(week)]
  for col in df.columns:
    if str(col).strip() in [str(p).strip() for p in possible_names]:
      return col
  return None


# =========================================================
# 2. 주차 범위 자동 계산 (오늘 날짜 기준 ISO 주차 - 1주차)
# =========================================================
start_w = 1
current_iso_week = datetime.now().isocalendar()[1]
latest_w = max(1, current_iso_week - 1)  # 오늘 기준 (ISO 주차 - 1주차)

selected_weeks = list(range(start_w, latest_w + 1))


# =========================================================
# 3. 사이드바 UI
# =========================================================
st.sidebar.header("🏢 점포 검색")

selected_store_name = st.sidebar.selectbox(
    "점포 선택",
    options=["선택 안함"] + store_list,
    index=0,
    help="선택 시 해당 점포 위치 및 KPI 데이터가 표시됩니다.",
)

st.sidebar.info(f"📅 **현재 분석 범위:** 1주차 ~ {latest_w}주차 (전주차 누적)")


# =========================================================
# 4. KPI 및 Top 5 계산 함수 (C1~C7 공식 반영)
# =========================================================
def calculate_kpi(c1, c2, c3, c4, c5, c7, store_name=None):
  def get_single_store_row(df):
    if store_name and store_name != "선택 안함" and not df.empty:
      for col in ["점포명", "점포"]:
        if col in df.columns:
          filtered = df[df[col] == store_name]
          if not filtered.empty:
            return filtered
    return df

  c1_sub = get_single_store_row(c1)
  c2_sub = get_single_store_row(c2)
  c3_sub = get_single_store_row(c3)
  c4_sub = get_single_store_row(c4)
  c5_sub = get_single_store_row(c5)
  c7_sub = get_single_store_row(c7)

  on_time, non_pay, non_ship, voc = [], [], [], []

  for w in selected_weeks:
    col1 = get_week_col_name(c1_sub, w)
    col2 = get_week_col_name(c2_sub, w)
    col3 = get_week_col_name(c3_sub, w)
    col4 = get_week_col_name(c4_sub, w)
    col5 = get_week_col_name(c5_sub, w)
    col7 = get_week_col_name(c7_sub, w)

    sum_c1 = (
        pd.to_numeric(c1_sub[col1], errors="coerce").sum()
        if (col1 and col1 in c1_sub.columns and not c1_sub.empty)
        else np.nan
    )
    sum_c2 = (
        pd.to_numeric(c2_sub[col2], errors="coerce").sum()
        if (col2 and col2 in c2_sub.columns and not c2_sub.empty)
        else np.nan
    )
    sum_c3 = (
        pd.to_numeric(c3_sub[col3], errors="coerce").sum()
        if (col3 and col3 in c3_sub.columns and not c3_sub.empty)
        else np.nan
    )
    sum_c4 = (
        pd.to_numeric(c4_sub[col4], errors="coerce").sum()
        if (col4 and col4 in c4_sub.columns and not c4_sub.empty)
        else np.nan
    )
    sum_c5 = (
        pd.to_numeric(c5_sub[col5], errors="coerce").sum()
        if (col5 and col5 in c5_sub.columns and not c5_sub.empty)
        else np.nan
    )
    sum_c7 = (
        pd.to_numeric(c7_sub[col7], errors="coerce").sum()
        if (col7 and col7 in c7_sub.columns and not c7_sub.empty)
        else np.nan
    )

    # 1. 정시배송율: (C1 합계 / C2 합계) * 100
    if pd.notna(sum_c1) and pd.notna(sum_c2) and sum_c2 > 0:
      on_time.append((sum_c1 / sum_c2) * 100)
    else:
      on_time.append(np.nan)

    # 2. 미납율: (C5 합계 - C3 합계) / C5 합계 * 100
    if pd.notna(sum_c5) and pd.notna(sum_c3) and sum_c5 > 0:
      non_pay.append(((sum_c5 - sum_c3) / sum_c5) * 100)
    else:
      non_pay.append(np.nan)

    # 3. 미오출율: (C3 합계 - C7 합계) / C3 합계 * 100
    if pd.notna(sum_c3) and pd.notna(sum_c7) and sum_c3 > 0:
      non_ship.append(((sum_c3 - sum_c7) / sum_c3) * 100)
    else:
      non_ship.append(np.nan)

    # 4. VOC 실적: C4 합계
    voc.append(sum_c4 if pd.notna(sum_c4) else np.nan)

  return pd.DataFrame({
      "주차": selected_weeks,
      "정시배송율": on_time,
      "미납율": non_pay,
      "미오출율": non_ship,
      "VOC실적": voc,
  })


# 🌟 VOC 인입 Top 5 점포 계산 함수
def get_top_5_voc_stores(c4_df, weeks):
  if c4_df.empty:
    return pd.DataFrame(columns=["순위", "점포명", "총 VOC 건수"])

  store_col = next(
      (col for col in ["점포명", "점포"] if col in c4_df.columns), None
  )
  if not store_col:
    return pd.DataFrame(columns=["순위", "점포명", "총 VOC 건수"])

  week_cols = [
      get_week_col_name(c4_df, w)
      for w in weeks
      if get_week_col_name(c4_df, w)
  ]

  temp_df = c4_df.copy()
  for col in week_cols:
    temp_df[col] = pd.to_numeric(temp_df[col], errors="coerce").fillna(0)

  temp_df["총_VOC"] = temp_df[week_cols].sum(axis=1)

  grouped = (
      temp_df.groupby(store_col)["총_VOC"]
      .sum()
      .reset_index()
      .sort_values(by="총_VOC", ascending=False)
  )

  top_5 = grouped.head(5).reset_index(drop=True)
  top_5.index = top_5.index + 1
  top_5 = top_5.reset_index().rename(
      columns={"index": "순위", store_col: "점포명", "총_VOC": "총 VOC 건수"}
  )
  top_5["총 VOC 건수"] = top_5["총 VOC 건수"].astype(int)

  return top_5


# 🌟 미오출율 Top 5 점포 계산 함수 (누적 C3, C7 반영)
def get_top_5_non_ship_stores(c3_df, c7_df, weeks):
  if c3_df.empty or c7_df.empty:
    return pd.DataFrame(columns=["순위", "점포명", "미오출율"])

  store_col_c3 = next(
      (col for col in ["점포명", "점포"] if col in c3_df.columns), None
  )
  store_col_c7 = next(
      (col for col in ["점포명", "점포"] if col in c7_df.columns), None
  )

  if not store_col_c3 or not store_col_c7:
    return pd.DataFrame(columns=["순위", "점포명", "미오출율"])

  week_cols_c3 = [
      get_week_col_name(c3_df, w)
      for w in weeks
      if get_week_col_name(c3_df, w)
  ]
  week_cols_c7 = [
      get_week_col_name(c7_df, w)
      for w in weeks
      if get_week_col_name(c7_df, w)
  ]

  temp_c3 = c3_df.copy()
  temp_c7 = c7_df.copy()

  for col in week_cols_c3:
    temp_c3[col] = pd.to_numeric(temp_c3[col], errors="coerce").fillna(0)
  for col in week_cols_c7:
    temp_c7[col] = pd.to_numeric(temp_c7[col], errors="coerce").fillna(0)

  temp_c3["총_C3"] = temp_c3[week_cols_c3].sum(axis=1)
  temp_c7["총_C7"] = temp_c7[week_cols_c7].sum(axis=1)

  sum_c3 = temp_c3.groupby(store_col_c3)["총_C3"].sum().reset_index()
  sum_c7 = temp_c7.groupby(store_col_c7)["총_C7"].sum().reset_index()

  merged = pd.merge(
      sum_c3,
      sum_c7,
      left_on=store_col_c3,
      right_on=store_col_c7,
      how="inner",
  )

  merged = merged[merged["총_C3"] > 0].copy()
  merged["미오출율"] = (
      (merged["총_C3"] - merged["총_C7"]) / merged["총_C3"]
  ) * 100

  top_5 = (
      merged.sort_values(by="미오출율", ascending=False)
      .head(5)
      .reset_index(drop=True)
  )
  top_5.index = top_5.index + 1
  top_5 = top_5.reset_index().rename(
      columns={"index": "순위", store_col_c3: "점포명"}
  )

  return top_5[["순위", "점포명", "미오출율"]]


# 데이터 계산 수행 (C1~C7 활용)
df_all_kpi = calculate_kpi(c1_df, c2_df, c3_df, c4_df, c5_df, c7_df)
df_store_kpi = calculate_kpi(
    c1_df, c2_df, c3_df, c4_df, c5_df, c7_df, selected_store_name
)
df_top5_voc = get_top_5_voc_stores(c4_df, selected_weeks)
df_top5_non_ship = get_top_5_non_ship_stores(c3_df, c7_df, selected_weeks)


# =========================================================
# 5. 메인 화면 레이아웃 (좌: 지도 50%, 우: KPI 50%)
# =========================================================
map_col, right_col = st.columns([50, 50])


# ---------------------------------------------------------
# 🗺️ [좌측 컬럼] Folium 지도
# ---------------------------------------------------------
with map_col:
  st.markdown("### 🗺️ Store Location")

  target_row = None
  if selected_store_name != "선택 안함" and not df_c6.empty:
    selected_df = df_c6[df_c6["점포명"] == selected_store_name]
    if not selected_df.empty:
      target_row = selected_df.iloc[0]

  if target_row is not None:
    center_lat = target_row["위도"]
    center_lng = target_row["경도"]
    zoom_level = 7
  else:
    center_lat = 36.2
    center_lng = 127.8
    zoom_level = 7

  m = folium.Map(
      location=[center_lat, center_lng],
      zoom_start=zoom_level,
      tiles="CartoDB positron",
  )

  if geojson_data:
    folium.GeoJson(
        geojson_data,
        name="시군구 경계",
        style_function=lambda feature: {
            "fillColor": "#334155",
            "color": "#1e293b",
            "weight": 0.8,
            "fillOpacity": 0.35,
        },
        highlight_function=lambda feature: {
            "fillColor": "#38bdf8",
            "fillOpacity": 0.6,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["name"], aliases=["지역명:"], localize=True
        ),
    ).add_to(m)

  if target_row is not None:
    folium.CircleMarker(
        location=[target_row["위도"], target_row["경도"]],
        radius=18,
        color="#dc2626",
        fill=True,
        fill_color="#f87171",
        fill_opacity=0.8,
        tooltip=f"📍 {target_row['점포명']}",
    ).add_to(m)

    folium.Marker(
        location=[target_row["위도"], target_row["경도"]],
        popup=target_row["점포명"],
        icon=folium.Icon(color="red", icon="star", prefix="fa"),
    ).add_to(m)

  st_folium(m, width="100%", height=820, returned_objects=[])


# ---------------------------------------------------------
# 📊 [우측 컬럼] KPI 실적 및 Top 5
# ---------------------------------------------------------
with right_col:
  week_labels = [str(w) for w in df_all_kpi["주차"]]

  # =====================================================
  # ① [우측 상단] 전체 점포 누적 평균 & Top 5 탭 선택형 UI
  # =====================================================
  st.markdown(f"### 🌐 전체 점포 누적 평균 (1 ~ {latest_w}주차)")

  col1, col2, col3, col4 = st.columns(4)
  avg_otd = df_all_kpi["정시배송율"].mean(skipna=True)
  avg_np = df_all_kpi["미납율"].mean(skipna=True)
  avg_ns = df_all_kpi["미오출율"].mean(skipna=True)
  sum_voc = df_all_kpi["VOC실적"].sum(skipna=True)

  col1.metric("정시배송율", f"{avg_otd:.2f}%" if pd.notna(avg_otd) else "-")
  col2.metric("미납율", f"{avg_np:.2f}%" if pd.notna(avg_np) else "-")
  col3.metric("미오출율", f"{avg_ns:.2f}%" if pd.notna(avg_ns) else "-")
  col4.metric(
      "VOC 실적(합계)", f"{int(sum_voc):,}건" if pd.notna(sum_voc) else "-"
  )

  # 🌟 Top 5 선택형 탭 UI (VOC Top 5 / 미오출율 Top 5)
  with st.expander(
      f"🏆 **[누적 Top 5] 주요 관리 점포 현황 (1 ~ {latest_w}주차)**",
      expanded=True,
  ):
    top5_tab1, top5_tab2 = st.tabs(
        ["🚨 VOC 접수 Top 5", "⚠️ 미오출율 최고  Top 5"]
    )

    with top5_tab1:
      if not df_top5_voc.empty:
        st.dataframe(
            df_top5_voc,
            use_container_width=True,
            hide_index=True,
            column_config={
                "순위": st.column_config.NumberColumn(
                    "순위", format="%d위", alignment="center"
                ),
                "점포명": st.column_config.TextColumn(
                    "점포명", alignment="center"
                ),
                "총 VOC 건수": st.column_config.NumberColumn(
                    "총 VOC 건수", format="%d 건", alignment="center"
                ),
            },
        )
      else:
        st.write("표시할 VOC 데이터가 없습니다.")

    with top5_tab2:
      if not df_top5_non_ship.empty:
        st.dataframe(
            df_top5_non_ship,
            use_container_width=True,
            hide_index=True,
            column_config={
                "순위": st.column_config.NumberColumn(
                    "순위", format="%d위", alignment="center"
                ),
                "점포명": st.column_config.TextColumn(
                    "점포명", alignment="center"
                ),
                "미오출율": st.column_config.NumberColumn(
                    "미오출율", format="%.2f%%", alignment="center"
                ),
            },
        )
      else:
        st.write("표시할 미오출율 데이터가 없습니다.")

  st.divider()

  # =====================================================
  # ② [우측 하단] 선택 점포 실적 추이
  # =====================================================
  if selected_store_name != "선택 안함":
    st.markdown(
        f"### 🎯 [{selected_store_name}] 누적 평균(1 ~ {latest_w}주차)"
    )

    col1_s, col2_s, col3_s, col4_s = st.columns(4)

    s_avg_otd = df_store_kpi["정시배송율"].mean(skipna=True)
    s_avg_np = df_store_kpi["미납율"].mean(skipna=True)
    s_avg_ns = df_store_kpi["미오출율"].mean(skipna=True)
    s_sum_voc = df_store_kpi["VOC실적"].sum(skipna=True)

    diff_on_time = (
        s_avg_otd - avg_otd
        if (pd.notna(s_avg_otd) and pd.notna(avg_otd))
        else None
    )
    diff_non_pay = (
        s_avg_np - avg_np if (pd.notna(s_avg_np) and pd.notna(avg_np)) else None
    )
    diff_non_ship = (
        s_avg_ns - avg_ns if (pd.notna(s_avg_ns) and pd.notna(avg_ns)) else None
    )

    col1_s.metric(
        "정시배송율",
        f"{s_avg_otd:.2f}%" if pd.notna(s_avg_otd) else "-",
        delta=f"{diff_on_time:+.2f}%p" if diff_on_time is not None else None,
    )
    col2_s.metric(
        "미납율",
        f"{s_avg_np:.2f}%" if pd.notna(s_avg_np) else "-",
        delta=f"{diff_non_pay:+.2f}%p" if diff_non_pay is not None else None,
        delta_color="inverse",
    )
    col3_s.metric(
        "미오출율",
        f"{s_avg_ns:.2f}%" if pd.notna(s_avg_ns) else "-",
        delta=f"{diff_non_ship:+.2f}%p" if diff_non_ship is not None else None,
        delta_color="inverse",
    )
    col4_s.metric(
        "VOC 실적(합계)",
        f"{int(s_sum_voc):,}건" if pd.notna(s_sum_voc) else "0건",
    )

    tab1, tab2 = st.tabs(["📈 비율 지표 추이 (%)", "🚨 VOC 발생 추이 (건)"])

    with tab1:
      fig_store_rates = go.Figure()
      fig_store_rates.add_trace(
          go.Scatter(
              x=week_labels,
              y=df_store_kpi["정시배송율"],
              mode="lines+markers",
              name="정시배송율",
              line=dict(color="#22c55e", width=2),
              hovertemplate="정시배송율: <b>%{y:.2f}%</b><extra></extra>",
          )
      )
      fig_store_rates.add_trace(
          go.Scatter(
              x=week_labels,
              y=df_store_kpi["미납율"],
              mode="lines+markers",
              name="미납율",
              line=dict(color="#f97316", width=2),
              hovertemplate="미납율: <b>%{y:.2f}%</b><extra></extra>",
          )
      )
      fig_store_rates.add_trace(
          go.Scatter(
              x=week_labels,
              y=df_store_kpi["미오출율"],
              mode="lines+markers",
              name="미오출율",
              line=dict(color="#ef4444", width=2),
              hovertemplate="미오출율: <b>%{y:.2f}%</b><extra></extra>",
          )
      )

      fig_store_rates.update_layout(
          height=180,
          margin=dict(l=10, r=10, t=25, b=10),
          hovermode="x unified",
          legend=dict(
              orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
          ),
          yaxis=dict(range=[0, 105]),
          xaxis=dict(type="category", tickangle=0, dtick=1),
      )
      st.plotly_chart(fig_store_rates, use_container_width=True)

    with tab2:
      fig_store_voc = go.Figure()
      text_voc = [
          f"{int(v)}건" if (pd.notna(v) and v > 0) else ""
          for v in df_store_kpi["VOC실적"]
      ]

      fig_store_voc.add_trace(
          go.Bar(
              x=week_labels,
              y=df_store_kpi["VOC실적"],
              text=text_voc,
              textposition="auto",
              marker_color="#8b5cf6",
              hovertemplate="VOC 합계: <b>%{y:,.0f}건</b><extra></extra>",
          )
      )

      fig_store_voc.update_layout(
          height=180,
          margin=dict(l=10, r=10, t=25, b=10),
          hovermode="x unified",
          xaxis=dict(type="category", tickangle=0, dtick=1),
      )
      st.plotly_chart(fig_store_voc, use_container_width=True)

  else:
    st.info(
        "👈 사이드바에서 점포를 선택하시면 해당 점포의 전체 실적 추이 그래프가"
        " 표시됩니다."
    )
