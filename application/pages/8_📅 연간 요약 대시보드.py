import calendar
import time
from datetime import date

import pandas as pd
import streamlit as st
from st_aggrid import (
    AgGrid,
    GridUpdateMode,
    JsCode,
)  # AG Grid 관련 모듈 (이 파일에서는 직접 사용되지 않음)

from core.db_queries import (
    get_annual_summary_data,
    get_annual_asset_summary,
)  # 연간 요약 데이터를 위한 DB 쿼리 함수 임포트
from core.ui_utils import (
    apply_common_styles,
    authenticate_user,
    logout_button,
)  # UI 및 인증 유틸리티
import numpy as np  # 숫자형 데이터 처리
from pandas import Series  # Pandas Series 타입 힌트를 위함

# 모든 페이지에 공통 CSS 스타일 적용
apply_common_styles()

# 사용자 인증. 인증에 실패하면 앱 실행 중단.
if not authenticate_user():
    st.stop()

# 로그아웃 버튼 표시 (인증된 경우에만 보임)
logout_button()

# Streamlit 페이지 설정 (페이지 제목 및 레이아웃)
st.set_page_config(layout="wide", page_title="연간 재무 요약")
st.title("📅 연간 재무 요약")  # 페이지 메인 제목
st.markdown(
    "선택된 연도의 수입, 지출, 투자 현황과 현금 흐름을 요약합니다."
)  # 페이지 설명
st.markdown("---")  # 구분선


# 연도 선택 드롭다운
current_year = date.today().year  # 현재 연도
selected_year = st.selectbox(  # 현재 연도부터 2020년까지 역순으로 옵션 제공
    "조회 연도",
    options=range(current_year, 2019, -1),
    index=0,  # 기본값은 가장 최신 연도
)
st.markdown("---")  # 구분선


# 선택된 연도의 월별 수입, 지출, 투자 데이터 로드
source_df = get_annual_summary_data(selected_year)

# 분석할 데이터가 없는 경우 경고 메시지 표시
if source_df.empty:
    st.warning(f"{selected_year}년에는 분석할 데이터가 없습니다.")
else:
    # 해당 연도의 모든 월에 대한 카테고리(범주형) 순서 정의
    all_months_of_year = [f"{selected_year}/{str(m).zfill(2)}" for m in range(1, 13)]
    # '연월' 컬럼을 정의된 순서의 범주형으로 변환 (정렬 및 누락 월 처리 위함)
    source_df["연월"] = pd.Categorical(
        source_df["연월"], categories=all_months_of_year, ordered=True
    )

    # 피벗 테이블 생성: 인덱스는 '구분'과 '항목', 컬럼은 '연월', 값은 '금액'
    # aggfunc='sum': 금액 합계, fill_value=0: NaN 값을 0으로 채움, dropna=False: 모든 컬럼 유지
    pivot_df = pd.pivot_table(
        source_df,
        index=["구분", "항목"],
        columns="연월",
        values="금액",
        aggfunc="sum",
        fill_value=0,
        dropna=False,
    )

    # 보고서의 행 구조 정의 (MultiIndex 튜플 리스트)
    report_structure = [
        ("수입", "고정 수입"),
        ("수입", "변동 수입"),
        ("수입", "미분류 수입"),
        ("수입", "수입 소계"),  # 계산될 소계 항목
        ("지출", "고정 지출"),
        ("지출", "변동 지출"),
        ("지출", "미분류 지출"),
        ("지출", "지출 소계"),  # 계산될 소계 항목
        ("투자", "투자"),
        ("투자", "투자 소계"),  # 계산될 소계 항목
        ("현금흐름", "투자가능금액 (수입-지출)"),  # 계산될 현금 흐름 항목 1
        ("현금흐름", "최종 현금 변동"),  # 계산될 현금 흐름 항목 2
    ]
    # Pandas MultiIndex 객체 생성
    report_index = pd.MultiIndex.from_tuples(report_structure, names=["구분", "항목"])

    # 정의된 구조로 빈 데이터프레임 생성 (모든 값 0으로 초기화)
    report_df = pd.DataFrame(0, index=report_index, columns=pivot_df.columns)
    # 실제 피벗 테이블 데이터를 보고서 데이터프레임에 업데이트 (매칭되는 인덱스/컬럼만 업데이트)
    report_df.update(pivot_df)

    # 소계 행 계산
    report_df.loc[("수입", "수입 소계"), :] = (
        report_df.loc["수입"]
        .drop("수입 소계")
        .sum()  # '수입' 그룹에서 '수입 소계'를 제외하고 합계 계산
    )
    report_df.loc[("지출", "지출 소계"), :] = (
        report_df.loc["지출"]
        .drop("지출 소계")
        .sum()  # '지출' 그룹에서 '지출 소계'를 제외하고 합계 계산
    )
    report_df.loc[("투자", "투자 소계"), :] = (
        report_df.loc["투자"]
        .drop("투자 소계")
        .sum()  # '투자' 그룹에서 '투자 소계'를 제외하고 합계 계산
    )

    # --- 현금흐름 계산 ---
    # 수입 소계와 지출 소계 가져오기 (Series 또는 단일 값일 수 있으므로 to_numeric과 fillna 처리)
    income = pd.to_numeric(report_df.loc[("수입", "수입 소계")], errors="coerce")
    expense = pd.to_numeric(report_df.loc[("지출", "지출 소계")], errors="coerce")

    # Series 타입이거나 NaN인 경우 0으로 처리 (누락된 월에 대한 계산 안전성 확보)
    if isinstance(income, Series):
        income = income.fillna(0)
    elif pd.isna(income):
        income = 0

    if isinstance(expense, Series):
        expense = expense.fillna(0)
    elif pd.isna(expense):
        expense = 0

    # '투자가능금액 (수입-지출)' 계산
    report_df.loc[("현금흐름", "투자가능금액 (수입-지출)")] = income - expense

    # '최종 현금 변동' 계산을 위한 값 가져오기
    cash_flow = pd.to_numeric(
        report_df.loc[("현금흐름", "투자가능금액 (수입-지출)")], errors="coerce"
    )
    investment = pd.to_numeric(report_df.loc[("투자", "투자 소계")], errors="coerce")

    # Series 타입이거나 NaN인 경우 0으로 처리
    if isinstance(cash_flow, Series):
        cash_flow = cash_flow.fillna(0)
    elif pd.isna(cash_flow):
        cash_flow = 0

    if isinstance(investment, Series):
        investment = investment.fillna(0)
    elif pd.isna(investment):
        investment = 0

    # '최종 현금 변동' 계산
    report_df.loc[("현금흐름", "최종 현금 변동")] = cash_flow - investment

    # 전체 행에 대한 'Total' 컬럼 (연간 총합) 계산
    report_df["Total"] = report_df.sum(axis=1)
    # 스타일링을 위해 MultiIndex를 일반 컬럼으로 변환
    final_df_to_style = report_df.reset_index()

    def apply_report_styles(df):
        """
        연간 재무 요약 데이터프레임에 커스텀 스타일을 적용하는 함수.
        배경색, 폰트 굵기, 텍스트 정렬, 숫자 포맷 등을 설정.
        """
        # 숫자형 컬럼 목록 가져오기
        numeric_cols = df.select_dtypes(include=np.number).columns.tolist()

        def get_row_style(row):
            """각 행에 대한 스타일을 반환하는 내부 함수."""
            styles = ["" for _ in row]  # 각 셀에 적용될 스타일 리스트 초기화
            group = row["구분"]  # '구분' 컬럼 값 (수입, 지출, 투자, 현금흐름)
            item = row["항목"]  # '항목' 컬럼 값 (세부 카테고리, 소계 등)

            # 그룹별 기본 배경색 정의
            color_map = {"수입": "#fffbe6", "지출": "#f8f9fa", "투자": "#e6f4ea"}
            # 소계 행을 위한 배경색 정의 (기본색보다 진하게)
            total_color_map = {"수입": "#fff3cd", "지출": "#e9ecef", "투자": "#cce8d4"}

            # 소계 또는 현금흐름 요약 행인지 확인
            is_total_row = "소계" in item or "금액" in item  # '투자가능금액' 포함

            # 그룹에 따른 배경색 설정
            if group in color_map:
                bgcolor = total_color_map[group] if is_total_row else color_map[group]
                styles = [f"background-color: {bgcolor}" for _ in styles]

            # 소계 행은 폰트 굵게 설정
            if is_total_row:
                styles = [f"{s}; font-weight: bold" for s in styles]

            # '현금흐름' 그룹의 값에 따라 텍스트 색상 변경 (양수는 파랑, 음수는 빨강)
            if group == "현금흐름":
                for i, col_name in enumerate(row.index):
                    if col_name in numeric_cols:  # 숫자 컬럼에 대해서만 적용
                        value = row[col_name]
                        if value > 0:
                            styles[i] += "; color: blue;"
                        elif value < 0:
                            styles[i] += "; color: red;"
            return styles  # 각 셀의 스타일 리스트 반환

        # Pandas Styler 객체를 사용하여 데이터프레임에 스타일 적용
        styled = (
            df.style.apply(get_row_style, axis=1)  # 행별 스타일 적용
            .format(
                "{:,.0f}", na_rep="-", subset=numeric_cols
            )  # 숫자 컬럼 포맷 (천 단위, NaN은 '-')
            .set_properties(  # 숫자 컬럼의 텍스트 정렬 및 너비 설정
                subset=numeric_cols, **{"text-align": "right", "width": "120px"}
            )
            .set_table_styles(  # 테이블 헤더 스타일 설정
                [
                    {
                        "selector": "th.row_heading",
                        "props": [("text-align", "left")],
                    },  # 행 헤더 왼쪽 정렬
                    {
                        "selector": "th.col_heading",
                        "props": [("text-align", "center")],
                    },  # 열 헤더 가운데 정렬
                ]
            )
            .hide(axis="index")  # 기본 인덱스 숨기기
        )
        return styled

    styled_df = apply_report_styles(
        final_df_to_style
    )  # 스타일 적용된 데이터프레임 생성

    st.subheader(f"{selected_year}년 월별 요약")  # 월별 요약 테이블 서브 헤더
    st.dataframe(  # 스타일이 적용된 데이터프레임 표시
        styled_df,
        use_container_width=True,  # 컨테이너 너비에 맞춤
        height=(len(final_df_to_style) + 1) * 35 + 3,  # 테이블 높이 동적 설정
    )


st.markdown("---")  # 구분선
st.subheader(f"{selected_year}년 월말 자산 현황")  # 월말 자산 현황 서브 헤더

# 선택된 연도의 월말 자산 현황 데이터 로드
asset_df = get_annual_asset_summary(selected_year)

# 자산 변동 내역이 없는 경우 정보 메시지 표시
if asset_df.empty:
    st.info("해당 기간의 자산 변동 내역이 없습니다.")
else:
    # 총 자산 행 추가 (모든 계좌의 합계)
    asset_df.loc["총 자산"] = asset_df.sum()

    # 자산 데이터프레임에 스타일 적용
    styled_asset_df = (
        asset_df.style.format(
            "{:,.0f}원", na_rep="-"
        )  # 숫자 포맷 (천 단위, '원' 추가, NaN은 '-')
        .set_properties(text_align="right")  # 모든 셀 텍스트 오른쪽 정렬
        .apply(
            # '총 자산' 행에 폰트 굵게, 배경색 지정 스타일 적용
            lambda row: [
                (
                    "font-weight: bold; background-color: #f7f7f7"
                    if row.name == "총 자산"
                    else ""
                )
                for _ in row
            ],
            axis=1,  # 행 단위로 스타일 적용
        )
    )

    st.dataframe(  # 스타일이 적용된 자산 데이터프레임 표시
        styled_asset_df, use_container_width=True, height=(len(asset_df) + 1) * 35 + 3
    )
