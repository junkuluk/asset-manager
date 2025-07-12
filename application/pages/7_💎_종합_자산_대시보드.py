import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from core.db_queries import get_monthly_summary_for_dashboard
from core.ui_utils import apply_common_styles, authenticate_user, logout_button

apply_common_styles()

if not authenticate_user():
    st.stop()

logout_button()

st.set_page_config(layout="wide", page_title="종합 자산 대시보드")
st.title("💎 종합 자산 대시보드")
st.markdown("월별 현금흐름과 그에 따른 순자산의 변화를 추적합니다.")
st.markdown("---")

summary_df = get_monthly_summary_for_dashboard()

if summary_df.empty:
    st.warning("분석할 데이터가 충분하지 않습니다.")
else:

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(
            name="수입", x=summary_df["연월"], y=summary_df["수입"], marker_color="blue"
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(
            name="지출", x=summary_df["연월"], y=summary_df["지출"], marker_color="red"
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            name="총자산",
            x=summary_df["연월"],
            y=summary_df["총자산"],
            mode="lines+markers",
            line=dict(color="green"),
        ),
        secondary_y=True,
    )

    fig.update_layout(
        title_text="월별 현금흐름 및 총자산 추이",
        barmode="group",
        legend_title_text="항목",
    )
    fig.update_xaxes(title_text="연월")
    fig.update_yaxes(title_text="금액 (원)", secondary_y=False)
    fig.update_yaxes(title_text="총자산 (원)", secondary_y=True)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("월별 요약 데이터")
    st.dataframe(summary_df.set_index("연월"), use_container_width=True)
