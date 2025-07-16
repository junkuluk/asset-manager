import streamlit as st
import pandas as pd
import plotly.express as px
from core.db_queries import (
    load_income_expense_summary,
    load_monthly_category_summary,
)  # 데이터베이스 쿼리 함수 임포트
from core.ui_utils import (
    apply_common_styles,
    authenticate_user,
    logout_button,
)  # UI 및 인증 유틸리티 임포트
from datetime import date  # 날짜 처리를 위함

# 모든 페이지에 공통 CSS 스타일 적용
apply_common_styles()

# 사용자 인증. 인증에 실패하면 앱 실행 중단.
if not authenticate_user():
    st.stop()

# 로그아웃 버튼 표시 (인증된 경우에만 보임)
logout_button()

# Streamlit 페이지 설정 (페이지 제목)
st.set_page_config(layout="wide", page_title="월별 손익 분석")
st.title("💰 월별 손익 분석")  # 페이지 메인 제목
st.markdown("---")  # 구분선

# 날짜 선택 위젯 설정
today = date.today()  # 오늘 날짜
default_start_date = today.replace(
    month=1, day=1
)  # 기본 조회 시작일: 현재 연도의 1월 1일
col1, col2 = st.columns(2)  # 두 개의 컬럼으로 레이아웃 분할
with col1:
    start_date = st.date_input(
        "조회 시작일", value=default_start_date
    )  # 조회 시작일 입력 필드
with col2:
    end_date = st.date_input("조회 종료일", value=today)  # 조회 종료일 입력 필드

# 시작일이 종료일보다 늦은 경우 오류 처리
if start_date > end_date:
    st.error("시작일은 종료일보다 늦을 수 없습니다.")  # 오류 메시지 출력
    st.stop()  # 앱 실행 중단

# 선택된 기간의 월별 수입 및 지출 요약 데이터 로드
summary_df = load_income_expense_summary(
    str(start_date), str(end_date)
)  # 날짜를 문자열로 변환하여 함수에 전달

# 요약 데이터가 없는 경우 경고 메시지 표시
if summary_df.empty:
    st.warning("선택된 기간에 해당하는 수입 또는 지출 데이터가 없습니다.")
else:
    # 순수익 계산 (수입 - 지출)
    summary_df["순수익"] = summary_df["수입"] - summary_df["지출"]

    # --- 월별 수입-지출 현황 차트 ---
    st.subheader(f"월별 수입-지출 현황 ({start_date} ~ {end_date})")  # 서브 헤더

    # Plotly Express를 위해 데이터프레임 재구성 (수입, 지출을 '구분' 컬럼으로 녹임)
    df_melted = pd.melt(
        summary_df,
        id_vars=["연월"],  # 기준 컬럼
        value_vars=["수입", "지출"],  # 녹일 컬럼
        var_name="구분",  # 녹인 후 변수명 컬럼명
        value_name="금액",  # 녹인 후 값 컬럼명
    )

    # 월별 수입-지출 비교 막대 그래프 생성
    fig_compare = px.bar(
        df_melted,
        x="연월",  # x축: 연월
        y="금액",  # y축: 금액
        color="구분",  # '구분'(수입/지출)에 따라 색상 구분
        barmode="group",  # 막대 그룹화
        color_discrete_map={"수입": "#636EFA", "지출": "#EF553B"},  # 색상 매핑
    )
    fig_compare.update_traces(
        texttemplate="%{y:,.0f}", textposition="outside"
    )  # 막대 위에 금액 표시
    st.plotly_chart(
        fig_compare, use_container_width=True
    )  # Streamlit에 차트 표시 (컨테이너 너비에 맞춤)

    st.markdown("---")  # 구분선

    # --- 월별 순수익(저축액) 추이 차트 ---
    st.subheader("월별 순수익(저축액) 추이")  # 서브 헤더

    # 순수익 값에 따라 색상(긍정/부정)을 결정하는 컬럼 추가
    summary_df["색상"] = summary_df["순수익"].apply(
        lambda x: "긍정" if x >= 0 else "부정"
    )

    summary_df["연월"] = pd.to_datetime(summary_df["연월"])

    summary_df = summary_df.sort_values(by="연월")

    # 월별 순수익 막대 그래프 생성
    fig_net = px.bar(
        summary_df,
        x="연월",  # x축: 연월
        y="순수익",  # y축: 순수익
        text="순수익",  # 막대 위에 텍스트로 순수익 값 표시
        color="색상",  # '색상'(긍정/부정)에 따라 색상 구분
        color_discrete_map={"긍정": "green", "부정": "red"},  # 색상 매핑
    )
    fig_net.update_traces(
        texttemplate="%{text:,.0f}", textposition="outside"
    )  # 막대 위에 텍스트 포맷 적용
    fig_net.update_layout(showlegend=False)  # 범례 숨기기
    st.plotly_chart(fig_net, use_container_width=True)  # Streamlit에 차트 표시

    st.markdown("---")  # 구분선

    # --- 월별 주요 지출 항목 히트맵 ---
    st.subheader("월별 주요 지출 항목 히트맵")  # 서브 헤더

    # 월별 카테고리별 지출 요약 데이터 로드
    heatmap_df = load_monthly_category_summary(
        str(start_date), str(end_date), "EXPENSE"
    )

    # 히트맵 데이터가 비어있지 않은 경우
    if not heatmap_df.empty:
        # 히트맵을 위한 피벗 테이블 생성 (인덱스: 카테고리, 컬럼: 연월, 값: 금액)

        sorted_categories = (
            heatmap_df[["카테고리패스", "카테고리"]]
            .drop_duplicates()
            .sort_values("카테고리패스")["카테고리"]
            .tolist()
        )

        # 2. '카테고리' 컬럼을 위에서 만든 순서를 따르는 Categorical 타입으로 변환
        heatmap_df["카테고리"] = pd.Categorical(
            heatmap_df["카테고리"], categories=sorted_categories, ordered=True
        )

        pivot_df = heatmap_df.pivot_table(
            index="카테고리", columns="연월", values="금액", fill_value=0
        )

        # 히트맵 생성
        fig_heatmap = px.imshow(
            pivot_df,
            labels=dict(x="연월", y="카테고리", color="지출액"),  # 라벨 설정
            text_auto=":,.0f",  # type: ignore 셀 위에 자동으로 금액 표시 (천 단위 구분)
            aspect="auto",  # 종횡비 자동 조절
            color_continuous_scale="Reds",  # 색상 스케일 (붉은색 계열)
        )
        fig_heatmap.update_traces(texttemplate="%{z:,.0f}")  # 셀 텍스트 포맷 적용
        st.plotly_chart(fig_heatmap, use_container_width=True)  # Streamlit에 차트 표시

    st.markdown("---")  # 구분선
    # --- 요약 테이블 ---
    st.subheader("요약 테이블")  # 서브 헤더
    # 요약 데이터프레임을 테이블로 표시하고 금액 포맷 적용

    summary_df["색상"] = summary_df["순수익"].apply(lambda x: "▲" if x >= 0 else "▼")

    def style_arrow_color(row):
        # 순수익이 0 이상이면 파란색, 미만이면 빨간색을 지정합니다.
        color = "blue" if row["순수익"] >= 0 else "red"

        # row의 다른 컬럼은 스타일을 적용하지 않고, '색상' 컬럼에만 스타일을 적용합니다.
        styles = [""] * len(row)  # 모든 컬럼의 스타일을 일단 비워둡니다.
        color_col_idx = row.index.get_loc("색상")  # '색상' 컬럼의 위치를 찾습니다.
        styles[color_col_idx] = (
            f"color: {color}; font-weight: bold;"  # 해당 위치에만 CSS 스타일을 적용합니다.
        )

        return styles

    st.dataframe(
        summary_df.set_index("연월")
        .style.format(
            "{:,.0f}",
            subset=["수입", "지출", "순수익"],  # 지정된 컬럼에 천 단위 구분 기호 적용
        )
        .apply(style_arrow_color, axis=1)
    )
