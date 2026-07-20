import json
import folium
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
    store_list = df_c6["점포명"].tolist()
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
# 2. 주차 범위 자동 계산 (1주차 ~ 전주차/최대주차)
# =========================================================
# c1_df의 '주차' 컬럼을 기준으로 1주차부터 가장 최근(전주차) 주차까지 자동 지정
start_w = 1

if not c1_df.empty and "주차" in c1_df.columns:
    latest_w = int(c1_df["주차"].max())
else:
    latest_w = 1

selected_weeks = list(range(start_w, latest_w + 1))

# =========================================================
# 3. 사이드바 UI (점포 선택만 제공)
# =========================================================
st.sidebar.header("🏢 점포 검색")

selected_store_name = st.sidebar.selectbox(
    "점포 선택",
    options=["선택 안함"] + store_list,
    index=0,
    help="선택 시 해당 점포 위치 및 KPI 데이터가 표시됩니다.",
)

# 현재 집계 범위 안내 표시
st.sidebar.info(f"📅 **현재 분석 범위:** 1주차 ~ {latest_w}주차 (누적)")

# =========================================================
# 4. KPI 계산 함수 (1주차 ~ 전주차 자동 계산)
# =========================================================


def calculate_kpi(c1, c2, c3, c4, store_name=None):
    # 점포 필터링
    if store_name and store_name != "선택 안함":
        c1_sub = c1[c1["점포명"] == store_name] if "점포명" in c1 else c1
        c2_sub = c2[c2["점포명"] == store_name] if "점포명" in c2 else c2
        c3_sub = c3[c3["점포명"] == store_name] if "점포명" in c3 else c3
        c4_sub = c4[c4["점포명"] == store_name] if "점포명" in c4 else c4
    else:
        c1_sub, c2_sub, c3_sub, c4_sub = c1, c2, c3, c4

    # 1주차 ~ 전주차(latest_w) 범위 필터링
    c1_range = c1_sub[
        (c1_sub["주차"] >= start_w) & (c1_sub["주차"] <= latest_w)
    ]
    c2_range = c2_sub[
        (c2_sub["주차"] >= start_w) & (c2_sub["주차"] <= latest_w)
    ]
    c3_range = c3_sub[
        (c3_sub["주차"] >= start_w) & (c3_sub["주차"] <= latest_w)
    ]
    c4_range = c4_sub[
        (c4_sub["주차"] >= start_w) & (c4_sub["주차"] <= latest_w)
    ]

    # 1. 정시배송율 (%)
    c1_agg = c1_range.groupby("주차")[["정시배송", "총배송"]].sum()
    on_time = (
        ((c1_agg["정시배송"] / c1_agg["총배송"]) * 100)
        .fillna(0)
        .reindex(selected_weeks, fill_value=0)
    )

    # 2. 미납율 (%)
    c2_agg = c2_range.groupby("주차")[["발주금액", "출하금액"]].sum()
    non_pay = (
        (
            ((c2_agg["발주금액"] - c2_agg["출하금액"]) / c2_agg["발주금액"])
            * 100
        )
        .fillna(0)
        .reindex(selected_weeks, fill_value=0)
    )

    # 3. 미오출율 (%)
    c3_agg = c3_range.groupby("주차")[
        ["출하금액", "점포확정금액"]
    ].sum()
    non_ship = (
        (
            (
                (c3_agg["출하금액"] - c3_agg["점포확정금액"])
                / c3_agg["출하금액"]
            )
            * 100
        )
        .fillna(0)
        .reindex(selected_weeks, fill_value=0)
    )

    # 4. VOC 실적 (건)
    voc = (
        c4_range.groupby("주차")["VOC_건수"]
        .sum()
        .reindex(selected_weeks, fill_value=0)
    )

    return pd.DataFrame(
        {
            "주차": selected_weeks,
            "정시배송율": on_time.values,
            "미납율": non_pay.values,
            "미오출율": non_ship.values,
            "VOC실적": voc.values,
        }
    )


# 데이터 계산 수행
df_all_kpi = calculate_kpi(c1_df, c2_df, c3_df, c4_df)  # 전체 점포
df_store_kpi = calculate_kpi(
    c1_df, c2_df, c3_df, c4_df, selected_store_name
)  # 선택 점포

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

    # 👇 [수정 위치] 점포를 선택해도 zoom_level을 7로 고정하여 지도 형태 변경 방지!
    if target_row is not None:
        center_lat = target_row["위도"]
        center_lng = target_row["경도"]
        zoom_level = 7  # 지도 비율/형태 유지 (줌 확대 안 함)
    else:
        center_lat = 36.2
        center_lng = 127.8
        zoom_level = 7

    m = folium.Map(
        location=[center_lat, center_lng],
        zoom_start=zoom_level,
        tiles="CartoDB positron",  # 지도 타일 스타일 유지
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
        # 확대하지 않고도 멀리서 점포 위치가 잘 보이도록 마커 반지름(radius) 증대
        folium.CircleMarker(
            location=[target_row["위도"], target_row["경도"]],
            radius=18,  # 강조를 위해 살짝 크게 변경
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
# 📊 [우측 컬럼] KPI 실적 비교 (상단: 전체 점포 / 하단: 선택 점포)
# ---------------------------------------------------------
with right_col:
    # =====================================================
    # ① [우측 상단] 전체 점포 누적 평균
    # =====================================================
    st.markdown(f"### 🌐 전체 점포 누적 평균 (1 ~ {latest_w}주차)")

    # 전체 요약 카드 (높이 컴팩트하게)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("정시배송율", f"{df_all_kpi['정시배송율'].mean():.1f}%")
    col2.metric("미납율", f"{df_all_kpi['미납율'].mean():.1f}%")
    col3.metric("미오출율", f"{df_all_kpi['미오출율'].mean():.1f}%")
    col4.metric("VOC 실적(합계)", f"{df_all_kpi['VOC실적'].sum():,.0f}건")

    # 전체 점포 주차별 추이 차트
    fig_all = px.line(
        df_all_kpi,
        x="주차",
        y=["정시배송율", "미납율", "미오출율"],
        markers=True,
        title="전체 점포 주차별 물류 지표 추이 (%)",
    )
    fig_all.update_layout(
        height=200,  # 지도 높이에 맞춰 높이 조절
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
        ),
    )
    st.plotly_chart(fig_all, use_container_width=True)

    st.divider()  # 깔끔한 구분선

    # =====================================================
    # ② [우측 하단] 선택 점포 실적 추이 (right_col 내부 배치!)
    # =====================================================
    if selected_store_name != "선택 안함":
        st.markdown(f"### 🎯 [{selected_store_name}] 누적 평균(1 ~ {latest_w}주차)")

        # 선택 점포 요약 카드
        col1_s, col2_s, col3_s, col4_s = st.columns(4)

        diff_on_time = (
            df_store_kpi["정시배송율"].mean() - df_all_kpi["정시배송율"].mean()
        )
        diff_non_pay = (
            df_store_kpi["미납율"].mean() - df_all_kpi["미납율"].mean()
        )
        diff_non_ship = (
            df_store_kpi["미오출율"].mean() - df_all_kpi["미오출율"].mean()
        )

        col1_s.metric(
            "정시배송율",
            f"{df_store_kpi['정시배송율'].mean():.1f}%",
            delta=f"{diff_on_time:+.1f}%p",
        )
        col2_s.metric(
            "미납율",
            f"{df_store_kpi['미납율'].mean():.1f}%",
            delta=f"{diff_non_pay:+.1f}%p",
            delta_color="inverse",
        )
        col3_s.metric(
            "미오출율",
            f"{df_store_kpi['미오출율'].mean():.1f}%",
            delta=f"{diff_non_ship:+.1f}%p",
            delta_color="inverse",
        )
        col4_s.metric(
            "VOC 실적(합계)", f"{df_store_kpi['VOC실적'].sum():,.0f}건"
        )

        # 탭을 이용해 비율 지표 / VOC 지표 깔끔하게 정리
        tab1, tab2 = st.tabs(["📈 비율 지표 추이 (%)", "🚨 VOC 발생 추이 (건)"])

        with tab1:
            fig_store_rates = go.Figure()
            fig_store_rates.add_trace(
                go.Scatter(
                    x=df_store_kpi["주차"],
                    y=df_store_kpi["정시배송율"],
                    mode="lines+markers",
                    name="정시배송율",
                    line=dict(color="#22c55e", width=2),
                )
            )
            fig_store_rates.add_trace(
                go.Scatter(
                    x=df_store_kpi["주차"],
                    y=df_store_kpi["미납율"],
                    mode="lines+markers",
                    name="미납율",
                    line=dict(color="#f97316", width=2),
                )
            )
            fig_store_rates.add_trace(
                go.Scatter(
                    x=df_store_kpi["주차"],
                    y=df_store_kpi["미오출율"],
                    mode="lines+markers",
                    name="미오출율",
                    line=dict(color="#ef4444", width=2),
                )
            )

            fig_store_rates.update_layout(
                height=200,  # 지도 높이에 맞춤
                margin=dict(l=10, r=10, t=25, b=10),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1,
                ),
                yaxis=dict(range=[0, 105]),
            )
            st.plotly_chart(fig_store_rates, use_container_width=True)

        with tab2:
            fig_store_voc = px.bar(
                df_store_kpi,
                x="주차",
                y="VOC실적",
                text_auto=True,
                color_discrete_sequence=["#8b5cf6"],
            )
            fig_store_voc.update_layout(
                height=200, margin=dict(l=10, r=10, t=25, b=10)
            )
            st.plotly_chart(fig_store_voc, use_container_width=True)

    else:
        st.info(
            "👈 사이드바에서 점포를 선택하시면 해당 점포의 전체 실적 추이 그래프가 표시됩니다."
        )
