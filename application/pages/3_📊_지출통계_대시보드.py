# pages/1_📊_통계_대시보드.py
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st
from st_aggrid import AgGrid

from core.db_queries import (
    load_data_for_sunburst,
    load_data_for_pivot_grid,
    load_monthly_total_spending,
)
from core.ui_utils import apply_common_styles, authenticate_user, logout_button

# 1. 공통 스타일 적용 (상단 여백 줄이기 등)
apply_common_styles()

logout_button()

if not authenticate_user():
    st.stop()

st.set_page_config(layout="wide", page_title="계층별 지출 분석")
st.title("📊 계층별 지출 분석")
st.markdown("---")

# 2. 그리드 전용 Custom CSS 추가 (헤더, 호버 등)
st.markdown(
    """
<style>
    .ag-header-cell-label { font-weight: bold !important; }
    .ag-row-hover { background-color: #f5f5f5 !important; }
</style>
""",
    unsafe_allow_html=True,
)


# --- 날짜 선택 UI ---
today = date.today()
default_start_date = today.replace(month=1, day=1)
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("조회 시작일", value=default_start_date)
with col2:
    end_date = st.date_input("조회 종료일", value=today)

if start_date > end_date:
    st.error("시작일은 종료일보다 늦을 수 없습니다.")
    st.stop()

# --- 차트 영역 분할 ---
col_chart1, col_chart2 = st.columns(2)
with col_chart1:
    # --- Sunburst 차트 (전체 기간 합계) ---
    st.subheader(f"전체 기간 지출 현황 ({start_date} ~ {end_date})")

    # 1. Sunburst 전용 데이터 로더 호출
    sunburst_df = load_data_for_sunburst(start_date, end_date)

    if sunburst_df.empty:
        st.warning("선택된 기간에 해당하는 지출 데이터가 없습니다.")
    else:
        # 데이터 타입 정리
        sunburst_df["id"] = sunburst_df["id"].astype(str)
        sunburst_df["parent_id"] = (
            pd.to_numeric(sunburst_df["parent_id"], errors="coerce")
            .fillna(0)
            .astype(int)
            .astype(str)
        )
        sunburst_df.loc[sunburst_df["parent_id"] == "0", "parent_id"] = ""

        # 3. Sunburst 차트 스타일링
        fig = px.sunburst(
            sunburst_df,
            ids="id",
            parents="parent_id",
            names="description",
            values="total_amount",
            branchvalues="total",
            color="depth",  # 깊이에 따라 색상 구분
            color_continuous_scale=px.colors.sequential.Blues,  # 파란색 계열로 통일
            hover_name="description",
            hover_data={"total_amount": ":,d"},
        )
        fig.update_layout(margin=dict(t=10, l=10, r=10, b=10), font_size=14)
        fig.update_traces(textinfo="label+percent parent")
        st.plotly_chart(fig, use_container_width=True)

    # --- 월별 총 지출액 바 차트 ---
    with col_chart2:
        st.subheader(f"월별 총 지출액 추이 ({start_date} ~ {end_date})")
        monthly_spending_df = load_monthly_total_spending(start_date, end_date)

        monthly_spending_df["text_label"] = monthly_spending_df["total_spending"].apply(
            lambda x: f"{x:,.0f}"
        )

        if monthly_spending_df.empty:
            st.info("해당 기간의 월별 지출 데이터가 없습니다.")
        else:
            fig_bar = px.bar(
                monthly_spending_df,
                x="year_month",
                y="total_spending",
                labels={"total_spending": "총 지출액", "year_month": "월"},
                title="월별 총 지출액",
                text="text_label",
            )
            fig_bar.update_traces(texttemplate="%{text}", textposition="outside")
            st.plotly_chart(fig_bar, use_container_width=True)


st.markdown("---")
# --- 트리맵 차트 ---
st.subheader("주요 지출 항목 비중 (Treemap)")

# 최하위 카테고리만 필터링
leaf_nodes_df = sunburst_df[
    ~sunburst_df["id"].isin(sunburst_df["parent_id"].unique())
].copy()

fig_treemap = px.treemap(
    leaf_nodes_df,
    path=[px.Constant("전체 지출"), "description"],
    values="total_amount",
    color="total_amount",
    color_continuous_scale="Reds",
)
fig_treemap.update_traces(texttemplate="%{label}<br>%{value:,.0f}")
fig_treemap.update_layout(margin=dict(t=25, l=0, r=0, b=0))
st.plotly_chart(fig_treemap, use_container_width=True)


# --- AgGrid 피벗 테이블 (최종 수정) ---
st.markdown("---")
st.subheader(f"월별/카테고리별 지출 내역 ({start_date} ~ {end_date})")

# 1. 그리드용 원본 데이터를 로드합니다. (pivot_table을 사용하지 않음)
grid_source_df = load_data_for_pivot_grid(start_date, end_date)

if not grid_source_df.empty:
    # --- 여기가 수정된 최종 로직입니다 ---
    max_depth = int(grid_source_df["depth"].max())
    level_cols = [f"L{i}" for i in range(1, max_depth + 1)]

    grid_source_df[level_cols] = grid_source_df[level_cols].fillna("")
    # 2. GridOptions 딕셔너리 직접 생성
    gridOptions = {
        "columnDefs": [
            # rowGroup: 이 컬럼들로 계층을 만듭니다.
            {"field": col, "hide": True, "rowGroup": True}
            for col in level_cols
        ]
        + [
            # pivot: 이 컬럼의 값들을 실제 그리드의 '열'로 만듭니다.
            {"field": "연월", "pivot": True},
            # aggFunc: 그룹핑 및 피벗 시, 이 컬럼의 값을 합산합니다.
            {
                "field": "금액",
                "aggFunc": "sum",
                "valueFormatter": "x > 0 ? x.toLocaleString() + ' 원' : ''",
            },
        ],
        "defaultColDef": {"width": 130, "sortable": True, "resizable": True},
        "autoGroupColumnDef": {
            "headerName": "카테고리 계층",
            "minWidth": 300,
            "cellRendererParams": {"suppressCount": True},
        },
        # 피벗 모드 활성화
        "pivotMode": True,
    }

    # 3. 가공하지 않은 원본 데이터를 AgGrid에 직접 전달
    AgGrid(
        grid_source_df,
        gridOptions=gridOptions,
        height=600,
        width="100%",
        theme="alpine",
        allow_unsafe_jscode=True,
        enable_enterprise_modules=True,
    )
