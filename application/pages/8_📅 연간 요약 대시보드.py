import streamlit as st
import pandas as pd
from datetime import date
from core.db_queries import get_annual_summary_data, get_annual_asset_summary
from core.ui_utils import apply_common_styles, authenticate_user, logout_button
import numpy as np
from pandas import Series

# --- 페이지 기본 설정 ---
apply_common_styles()

if not authenticate_user():
    st.stop()

logout_button()

st.set_page_config(layout="wide", page_title="연간 재무 요약")
st.title("📅 연간 재무 요약")
st.markdown("선택된 연도의 수입, 지출, 투자 현황과 현금 흐름을 요약합니다.")
st.markdown("---")

# --- 연도 선택 UI ---
current_year = date.today().year
selected_year = st.selectbox(
    "조회 연도", options=range(current_year, 2019, -1), index=0
)
st.markdown("---")

# --- 데이터 로드 ---
source_df = get_annual_summary_data(selected_year)

if source_df.empty:
    st.warning(f"{selected_year}년에는 분석할 데이터가 없습니다.")
else:
    # --- 데이터 가공 (고정된 '틀' 방식) ---

    # 1. 월별 데이터를 포함한 기본 피벗 테이블 생성
    all_months_of_year = [f"{selected_year}/{str(m).zfill(2)}" for m in range(1, 13)]
    source_df["연월"] = pd.Categorical(
        source_df["연월"], categories=all_months_of_year, ordered=True
    )

    pivot_df = pd.pivot_table(
        source_df,
        index=["구분", "항목"],
        columns="연월",
        values="금액",
        aggfunc="sum",
        fill_value=0,
        dropna=False,
    )

    # 2. 최종 보고서에 표시될 행의 순서와 구조를 직접 정의
    report_structure = [
        ("수입", "고정 수입"),
        ("수입", "변동 수입"),
        ("수입", "미분류 수입"),
        ("수입", "수입 소계"),
        ("지출", "고정 지출"),
        ("지출", "변동 지출"),
        ("지출", "미분류 지출"),
        ("지출", "지출 소계"),
        ("투자", "투자"),
        ("투자", "투자 소계"),
        ("현금흐름", "투자가능금액 (수입-지출)"),
        ("현금흐름", "최종 현금 변동"),
    ]
    report_index = pd.MultiIndex.from_tuples(report_structure, names=["구분", "항목"])

    # 3. 정의된 구조를 가진 빈 보고서 '틀' 생성 및 실제 데이터 채우기
    report_df = pd.DataFrame(0, index=report_index, columns=pivot_df.columns)
    report_df.update(pivot_df)

    # 4. 요약 행(소계, 현금흐름)을 직접 계산하여 채워넣기
    report_df.loc[("수입", "수입 소계"), :] = (
        report_df.loc["수입"].drop("수입 소계").sum()
    )
    report_df.loc[("지출", "지출 소계"), :] = (
        report_df.loc["지출"].drop("지출 소계").sum()
    )
    report_df.loc[("투자", "투자 소계"), :] = (
        report_df.loc["투자"].drop("투자 소계").sum()
    )

    # report_df.loc[("현금흐름", "투자가능금액 (수입-지출)")] = (report_df.loc[("수입", "수입 소계")] - report_df.loc[("지출", "지출 소계")])
    # report_df.loc[("현금흐름", "최종 현금 변동")] = (report_df.loc[("현금흐름", "투자가능금액 (수입-지출)")]- report_df.loc[("투자", "투자 소계")])

    income = pd.to_numeric(report_df.loc[("수입", "수입 소계")], errors="coerce")
    expense = pd.to_numeric(report_df.loc[("지출", "지출 소계")], errors="coerce")

    if isinstance(income, Series):
        income = income.fillna(0)
    elif pd.isna(income):
        income = 0

    if isinstance(expense, Series):
        expense = expense.fillna(0)
    elif pd.isna(expense):
        expense = 0

    report_df.loc[("현금흐름", "투자가능금액 (수입-지출)")] = income - expense

    # --- 두 번째 계산 (수정된 부분) ---
    # 1. 값을 가져옵니다.
    cash_flow = pd.to_numeric(
        report_df.loc[("현금흐름", "투자가능금액 (수입-지출)")], errors="coerce"
    )
    investment = pd.to_numeric(report_df.loc[("투자", "투자 소계")], errors="coerce")

    # 2. cash_flow도 숫자 타입으로 변환하고 NaN을 처리합니다. (이 부분이 중요)
    if isinstance(cash_flow, Series):
        cash_flow = cash_flow.fillna(0)
    elif pd.isna(cash_flow):
        cash_flow = 0

    # 3. investment도 동일하게 처리합니다.
    if isinstance(investment, Series):
        investment = investment.fillna(0)
    elif pd.isna(investment):
        investment = 0

    # 4. 이제 두 변수 모두 숫자 타입이므로 안전하게 계산합니다.
    report_df.loc[("현금흐름", "최종 현금 변동")] = cash_flow - investment

    # 5. 'Total' 컬럼 추가 및 인덱스 리셋
    report_df["Total"] = report_df.sum(axis=1)
    final_df_to_style = report_df.reset_index()

    # --- 여기가 수정된 최종 로직입니다 (모든 스타일 통합) ---

    # 6. Pandas 스타일링 함수 정의
    def apply_report_styles(df):
        numeric_cols = df.select_dtypes(include=np.number).columns.tolist()

        # 행별 스타일을 결정하는 함수
        def get_row_style(row):
            styles = ["" for _ in row]
            group = row["구분"]
            item = row["항목"]

            # 기본 배경색 설정
            color_map = {"수입": "#fffbe6", "지출": "#f8f9fa", "투자": "#e6f4ea"}
            total_color_map = {"수입": "#fff3cd", "지출": "#e9ecef", "투자": "#cce8d4"}

            is_total_row = "소계" in item or "금액" in item

            if group in color_map:
                bgcolor = total_color_map[group] if is_total_row else color_map[group]
                styles = [f"background-color: {bgcolor}" for _ in styles]

            # 폰트 굵게
            if is_total_row:
                styles = [f"{s}; font-weight: bold" for s in styles]

            # 현금흐름 행 숫자 색상 변경
            if group == "현금흐름":
                for i, col_name in enumerate(row.index):
                    if col_name in numeric_cols:
                        value = row[col_name]
                        if value > 0:
                            styles[i] += "; color: blue;"
                        elif value < 0:
                            styles[i] += "; color: red;"
            return styles

        # 스타일 적용
        styled = (
            df.style.apply(get_row_style, axis=1)
            .format("{:,.0f}", na_rep="-", subset=numeric_cols)
            .set_properties(
                subset=numeric_cols, **{"text-align": "right", "width": "120px"}
            )
            .set_table_styles(
                [
                    {"selector": "th.row_heading", "props": [("text-align", "left")]},
                    {"selector": "th.col_heading", "props": [("text-align", "center")]},
                ]
            )
            .hide(axis="index")
        )
        return styled

    # 7. 스타일링 함수 적용
    styled_df = apply_report_styles(final_df_to_style)

    # 8. 최종 결과물 표시
    st.subheader(f"{selected_year}년 월별 요약")
    st.dataframe(
        styled_df,
        use_container_width=True,
        height=(len(final_df_to_style) + 1) * 35 + 3,
    )


#########################################################


# --- 2. 월별 자산 현황표 ---
st.markdown("---")
st.subheader(f"{selected_year}년 월말 자산 현황")

asset_df = get_annual_asset_summary(selected_year)

if asset_df.empty:
    st.info("해당 기간의 자산 변동 내역이 없습니다.")
else:
    asset_df.loc["총 자산"] = asset_df.sum()

    styled_asset_df = (
        asset_df.style.format("{:,.0f}원", na_rep="-")
        # .set_properties(**{"text-align": "right"})
        .set_properties(text_align="right").apply(
            lambda row: [
                (
                    "font-weight: bold; background-color: #f7f7f7"
                    if row.name == "총 자산"
                    else ""
                )
                for _ in row
            ],
            axis=1,
        )
    )

    st.dataframe(
        styled_asset_df, use_container_width=True, height=(len(asset_df) + 1) * 35 + 3
    )
