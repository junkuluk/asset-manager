import streamlit as st
import pandas as pd
import plotly.express as px
from core.db_queries import (
    load_income_expense_summary,
    load_monthly_category_summary,
    load_all_categories,  # 새로 추가해야 할 함수입니다.
)
from core.ui_utils import (
    apply_common_styles,
    authenticate_user,
    logout_button,
)
from datetime import date

# --- 기본 설정 및 인증 ---
apply_common_styles()
if not authenticate_user():
    st.stop()
logout_button()

st.set_page_config(layout="wide", page_title="맞춤형 월별 손익 분석")
st.title("📊 맞춤형 월별 손익 분석")
st.markdown(
    """
이 페이지에서는 특정 수입 또는 지출 항목을 **제외**하고 월별 손익을 분석할 수 있습니다.
아래에서 제외할 항목을 선택해 주세요.
"""
)
st.markdown("---")

# --- 데이터 조회 기간 설정 ---
today = date.today()
default_start_date = today.replace(month=1, day=1)
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input(
        "조회 시작일", value=default_start_date, key="custom_start_date"
    )
with col2:
    end_date = st.date_input("조회 종료일", value=today, key="custom_end_date")

if start_date > end_date:
    st.error("시작일은 종료일보다 늦을 수 없습니다.")
    st.stop()

# --- 제외 항목 선택 UI ---
st.subheader("분석에서 제외할 항목 선택")

# 데이터베이스에서 모든 수입/지출 카테고리 불러오기
# 이 기능은 db_queries.py에 새로 추가해야 합니다.
try:
    income_categories, expense_categories = load_all_categories()
except Exception as e:
    st.error(f"카테고리를 불러오는 중 오류가 발생했습니다: {e}")
    st.info(
        "core/db_queries.py 파일에 load_all_categories 함수를 추가했는지 확인해주세요."
    )
    st.stop()


col1, col2 = st.columns(2)
with col1:
    # '기타수입'을 기본값으로 설정하는 예시
    excluded_income = st.multiselect(
        "제외할 수입 항목",
        options=income_categories,
        default=["기타수입 일회성"] if "기타수입 일회성" in income_categories else [],
    )
with col2:
    excluded_expense = st.multiselect(
        "제외할 지출 항목", options=expense_categories, default=[]
    )

# 제외할 모든 카테고리 리스트 통합
all_excluded_categories = excluded_income + excluded_expense

# --- 데이터 로딩 및 분석 (선택된 항목 제외) ---
st.markdown("---")
st.header(f"분석 결과 ({start_date} ~ {end_date})")

# 선택된 기간의 월별 수입 및 지출 요약 데이터 로드 (제외 항목 포함)
# load_income_expense_summary 함수가 제외 목록을 인자로 받도록 수정해야 합니다.
summary_df = load_income_expense_summary(
    str(start_date), str(end_date), all_excluded_categories
)

if summary_df.empty:
    st.warning("선택된 기간과 조건에 해당하는 데이터가 없습니다.")
else:
    # ⭐️ [추가할 코드 1] 총 과소비 지수 계산 및 표시
    st.subheader("기간 내 총 과소비 분석")
    total_income = summary_df["수입"].sum()
    total_expense = summary_df["지출"].sum()

    # 수입이 0일 경우를 대비
    if total_income > 0:
        total_overconsumption_index = (total_expense / total_income) * 100
        delta_text = "수입의 {:.1f}%를 지출했습니다.".format(
            total_overconsumption_index
        )
    else:
        total_overconsumption_index = 0
        delta_text = "기간 내 수입이 없습니다."

    st.metric(
        label="총 과소비 지수",
        value=f"{total_overconsumption_index:.1f}%",
        help="(총 지출 / 총 수입) * 100",
        delta=delta_text,
        delta_color="inverse",  # 값이 높을수록 부정적 의미
    )
    st.markdown("---")  # 시각적 구분을 위한 라인 추가

    # 순수익 계산
    summary_df["순수익"] = summary_df["수입"] - summary_df["지출"]

    # ⭐️ [추가할 코드 2] 월별 과소비 지수 컬럼 추가
    # 수입이 0인 경우를 대비하여 apply와 lambda 함수 사용
    summary_df["과소비지수"] = summary_df.apply(
        lambda row: (row["지출"] / row["수입"]) if row["수입"] > 0 else 0,
        axis=1,
    )

    # --- 월별 수입-지출 현황 차트 ---
    st.subheader("월별 수입-지출 현황")
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

    # --- 월별 순수익(저축액) 추이 차트 ---
    st.subheader("월별 순수익(저축액) 추이")
    summary_df["색상"] = summary_df["순수익"].apply(
        lambda x: "긍정" if x >= 0 else "부정"
    )
    summary_df["연월"] = pd.to_datetime(summary_df["연월"])
    summary_df = summary_df.sort_values(by="연월")

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

    # --- 월별 주요 지출 항목 히트맵 ---
    st.subheader("월별 주요 지출 항목 히트맵")
    # load_monthly_category_summary 함수도 제외 목록을 인자로 받도록 수정해야 합니다.
    heatmap_df = load_monthly_category_summary(
        str(start_date), str(end_date), "EXPENSE", excluded_expense
    )

    if not heatmap_df.empty:
        # 카테고리 정렬 로직 (기존과 동일)
        sorted_categories = (
            heatmap_df[["카테고리패스", "카테고리"]]
            .drop_duplicates()
            .sort_values("카테고리패스")["카테고리"]
            .tolist()
        )
        heatmap_df["카테고리"] = pd.Categorical(
            heatmap_df["카테고리"], categories=sorted_categories, ordered=True
        )

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
    else:
        st.info(
            "선택된 조건에 해당하는 지출 데이터가 없어 히트맵을 표시할 수 없습니다."
        )

    st.markdown("---")

    # --- 요약 테이블 ---
    st.subheader("요약 테이블")
    # 스타일링 로직 (기존과 동일)
    summary_df["색상"] = summary_df["순수익"].apply(lambda x: "▲" if x >= 0 else "▼")

    def style_arrow_color(row):
        color = "blue" if row["순수익"] >= 0 else "red"
        styles = [""] * len(row)
        color_col_idx = row.index.get_loc("색상")
        styles[color_col_idx] = f"color: {color}; font-weight: bold;"
        return styles

    st.dataframe(
        summary_df.set_index("연월")
        .style.format(
            {
                "수입": "{:,.0f}",
                "지출": "{:,.0f}",
                "순수익": "{:,.0f}",
                "과소비지수": "{:.2%}",  # 퍼센트 형식으로 변경
            }
        )
        .apply(style_arrow_color, axis=1)
    )
