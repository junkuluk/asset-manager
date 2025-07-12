from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder

from core.db_queries import (
    load_data_for_sunburst,
    load_data_for_pivot_grid,
    load_monthly_total_spending,
)
from core.ui_utils import apply_common_styles, authenticate_user, logout_button


apply_common_styles()

if not authenticate_user():
    st.stop()

logout_button()

st.set_page_config(layout="wide", page_title="계층별 수입 분석")
st.title("📊 계층별 수입 분석")
st.markdown("---")

st.markdown(
    """
<style>
    .ag-header-cell-label { font-weight: bold !important; }
    .ag-row-hover { background-color: #f5f5f5 !important; }
</style>
""",
    unsafe_allow_html=True,
)


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


col_chart1, col_chart2 = st.columns(2)
with col_chart1:

    st.subheader(f"전체 기간 수입 현황 ({start_date} ~ {end_date})")

    sunburst_df = load_data_for_sunburst(
        start_date, end_date, transaction_type="INCOME"
    )

    if sunburst_df.empty:
        st.warning("선택된 기간에 해당하는 지출 데이터가 없습니다.")
    else:

        sunburst_df["id"] = sunburst_df["id"].astype(str)
        sunburst_df["parent_id"] = (
            pd.to_numeric(sunburst_df["parent_id"], errors="coerce")
            .fillna(0)
            .astype(int)
            .astype(str)
        )
        sunburst_df.loc[sunburst_df["parent_id"] == "0", "parent_id"] = ""

        fig = px.sunburst(
            sunburst_df,
            ids="id",
            parents="parent_id",
            names="description",
            values="total_amount",
            branchvalues="total",
            color="depth",
            color_continuous_scale=px.colors.sequential.Blues,
            hover_name="description",
            hover_data={"total_amount": ":,d"},
        )
        fig.update_layout(margin=dict(t=10, l=10, r=10, b=10), font_size=14)
        fig.update_traces(textinfo="label+percent parent")
        st.plotly_chart(fig, use_container_width=True)

    with col_chart2:
        st.subheader(f"월별 총 수입액 추이 ({start_date} ~ {end_date})")
        monthly_spending_df = load_monthly_total_spending(
            start_date, end_date, transaction_type="INCOME"
        )

        monthly_spending_df["text_label"] = monthly_spending_df["total_spending"].apply(
            lambda x: f"{x:,.0f}"
        )

        if monthly_spending_df.empty:
            st.info("해당 기간의 월별 수입 데이터가 없습니다.")
        else:
            fig_bar = px.bar(
                monthly_spending_df,
                x="year_month",
                y="total_spending",
                labels={"total_spending": "총 수입액", "year_month": "월"},
                title="월별 총 수입액",
                text="text_label",
            )
            fig_bar.update_traces(texttemplate="%{text}", textposition="outside")
            st.plotly_chart(fig_bar, use_container_width=True)

st.markdown("---")

st.subheader("주요 수입 항목 비중 (Treemap)")


leaf_nodes_df = sunburst_df[
    ~sunburst_df["id"].isin(sunburst_df["parent_id"].unique())
].copy()

fig_treemap = px.treemap(
    leaf_nodes_df,
    path=[px.Constant("전체 수입"), "description"],
    values="total_amount",
    color="total_amount",
    color_continuous_scale="Reds",
)
fig_treemap.update_layout(margin=dict(t=25, l=0, r=0, b=0))
fig_treemap.update_traces(texttemplate="%{label}<br>%{value:,.0f}")
st.plotly_chart(fig_treemap, use_container_width=True)


st.markdown("---")
st.subheader(f"월별/카테고리별 수입 내역 ({start_date} ~ {end_date})")


grid_source_df = load_data_for_pivot_grid(
    start_date, end_date, transaction_type="INCOME"
)

if not grid_source_df.empty:

    max_depth = int(grid_source_df["depth"].max())
    level_cols = [f"L{i}" for i in range(1, max_depth + 1)]

    grid_source_df[level_cols] = grid_source_df[level_cols].fillna("")

    gridOptions = {
        "columnDefs": [
            {"field": col, "hide": True, "rowGroup": True} for col in level_cols
        ]
        + [
            {"field": "연월", "pivot": True},
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
        "pivotMode": True,
    }

    AgGrid(
        grid_source_df,
        gridOptions=gridOptions,
        height=600,
        width="100%",
        theme="alpine",
        allow_unsafe_jscode=True,
        enable_enterprise_modules=True,
    )
