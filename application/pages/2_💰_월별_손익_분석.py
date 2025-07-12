import streamlit as st
import pandas as pd
import plotly.express as px
from core.db_queries import load_income_expense_summary, load_monthly_category_summary
from core.ui_utils import apply_common_styles, authenticate_user, logout_button
from datetime import date

apply_common_styles()

if not authenticate_user():
    st.stop()

logout_button()


st.set_page_config(layout="wide", page_title="월별 손익 분석")
st.title("💰 월별 손익 분석")
st.markdown("---")


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


summary_df = load_income_expense_summary(start_date, end_date)

if summary_df.empty:
    st.warning("선택된 기간에 해당하는 수입 또는 지출 데이터가 없습니다.")
else:

    summary_df["순수익"] = summary_df["수입"] - summary_df["지출"]

    st.subheader(f"월별 수입-지출 현황 ({start_date} ~ {end_date})")

    df_melted = pd.melt(
        summary_df,
        id_vars=["연월"],
        value_vars=["수입", "지출"],
        var_name="구분",
        value_name="금액",
    )

    fig_compare = px.bar(
        df_melted,
        x="연월",
        y="금액",
        color="구분",
        barmode="group",
        color_discrete_map={"수입": "#636EFA", "지출": "#EF553B"},
    )
    fig_compare.update_traces(texttemplate="%{y:,.0f}", textposition="outside")
    st.plotly_chart(fig_compare, use_container_width=True)

    st.markdown("---")

    st.subheader("월별 순수익(저축액) 추이")

    summary_df["색상"] = summary_df["순수익"].apply(
        lambda x: "긍정" if x >= 0 else "부정"
    )

    fig_net = px.bar(
        summary_df,
        x="연월",
        y="순수익",
        text="순수익",
        color="색상",
        color_discrete_map={"긍정": "green", "부정": "red"},
    )
    fig_net.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig_net.update_layout(showlegend=False)
    st.plotly_chart(fig_net, use_container_width=True)

    st.markdown("---")
    st.subheader("월별 주요 지출 항목 히트맵")

    heatmap_df = load_monthly_category_summary(start_date, end_date, "EXPENSE")

    if not heatmap_df.empty:

        pivot_df = heatmap_df.pivot_table(
            index="카테고리", columns="연월", values="금액", fill_value=0
        )

        fig_heatmap = px.imshow(
            pivot_df,
            labels=dict(x="연월", y="카테고리", color="지출액"),
            text_auto=":,.0f",  # type: ignore
            aspect="auto",
            color_continuous_scale="Reds",
        )
        fig_heatmap.update_traces(texttemplate="%{z:,.0f}")
        st.plotly_chart(fig_heatmap, use_container_width=True)

    st.markdown("---")
    st.subheader("요약 테이블")
    st.dataframe(
        summary_df.set_index("연월").style.format(
            "{:,.0f}", subset=["수입", "지출", "순수익"]
        )
    )
