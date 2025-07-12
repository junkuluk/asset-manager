from datetime import date  # 날짜 처리를 위함

import pandas as pd  # 데이터 처리 및 분석
import plotly.express as px  # 대화형 차트 생성
import streamlit as st  # 웹 애플리케이션 프레임워크
from st_aggrid import AgGrid  # AG Grid 테이블 표시

from core.db_queries import (  # 데이터베이스 쿼리 함수 임포트
    load_data_for_sunburst,  # 선버스트 차트용 데이터 로드
    load_data_for_pivot_grid,  # 피벗 그리드용 데이터 로드
    load_monthly_total_spending,  # 월별 총 지출(수입) 데이터 로드
)
from core.ui_utils import (
    apply_common_styles,
    authenticate_user,
    logout_button,
)  # UI 및 인증 유틸리티

# 모든 페이지에 공통 CSS 스타일 적용
apply_common_styles()

# 사용자 인증. 인증에 실패하면 앱 실행 중단.
if not authenticate_user():
    st.stop()

# 로그아웃 버튼 표시 (인증된 경우에만 보임)
logout_button()

# Streamlit 페이지 설정 (페이지 제목 및 레이아웃)
st.set_page_config(layout="wide", page_title="계층별 지출 분석")
st.title("📊 계층별 지출 분석")  # 페이지 메인 제목
st.markdown("---")  # 구분선


# AG Grid 테이블의 헤더 셀 텍스트를 굵게 표시하는 커스텀 CSS 스타일 적용
st.markdown(
    """
<style>
    .ag-header-cell-label { font-weight: bold !important; } /* 헤더 폰트 굵게 */
    .ag-row-hover { background-color: #f5f5f5 !important; } /* 행에 마우스 오버 시 배경색 변경 */
</style>
""",
    unsafe_allow_html=True,  # HTML 사용 허용
)


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


# 차트 영역을 두 개의 컬럼으로 분할
col_chart1, col_chart2 = st.columns(2)
with col_chart1:
    # --- 전체 기간 지출 현황 (선버스트 차트) ---
    st.subheader(f"전체 기간 지출 현황 ({start_date} ~ {end_date})")  # 서브 헤더

    # 선버스트 차트용 데이터 로드 (transaction_type 기본값이 'EXPENSE'이므로 생략 가능)
    sunburst_df = load_data_for_sunburst(str(start_date), str(end_date))

    # 데이터가 없는 경우 경고 메시지 표시
    if sunburst_df.empty:
        st.warning("선택된 기간에 해당하는 지출 데이터가 없습니다.")
    else:
        # 선버스트 차트 생성을 위한 데이터 전처리
        sunburst_df["id"] = sunburst_df["id"].astype(str)  # id를 문자열로 변환
        sunburst_df[
            "parent_id"
        ] = (  # parent_id를 숫자형 -> NaN 0 채움 -> 정수형 -> 문자열로 변환
            pd.to_numeric(sunburst_df["parent_id"], errors="coerce")
            .fillna(0)
            .astype(int)
            .astype(str)
        )
        # parent_id가 '0'인 경우 (최상위 노드) 빈 문자열로 설정 (Plotly sunburst에서 최상위 루트를 나타냄)
        sunburst_df.loc[sunburst_df["parent_id"] == "0", "parent_id"] = ""

        # Plotly Express를 사용하여 선버스트 차트 생성
        fig = px.sunburst(
            sunburst_df,
            ids="id",  # 각 노드의 고유 ID
            parents="parent_id",  # 부모 노드의 ID
            names="description",  # 노드에 표시될 이름
            values="total_amount",  # 노드의 크기를 결정하는 값
            branchvalues="total",  # 부모 노드 값이 자식 노드 값의 총합을 포함하도록 설정
            color="depth",  # 깊이에 따라 색상 구분
            color_continuous_scale=px.colors.sequential.Blues,  # 연속 색상 스케일
            hover_name="description",  # 마우스 오버 시 표시될 이름
            hover_data={
                "total_amount": ":,d"
            },  # 마우스 오버 시 총 금액 표시 (천 단위 구분)
        )
        fig.update_layout(
            margin=dict(t=10, l=10, r=10, b=10), font_size=14
        )  # 레이아웃 여백 및 폰트 크기 조정
        fig.update_traces(
            textinfo="label+percent parent"
        )  # 노드에 라벨과 부모 대비 백분율 표시
        st.plotly_chart(
            fig, use_container_width=True
        )  # Streamlit에 차트 표시 (컨테이너 너비에 맞춤)

with col_chart2:
    # --- 월별 총 지출액 추이 (막대 그래프) ---
    st.subheader(f"월별 총 지출액 추이 ({start_date} ~ {end_date})")  # 서브 헤더
    # 월별 총 지출액 데이터 로드 (transaction_type 기본값이 'EXPENSE'이므로 생략 가능)
    monthly_spending_df = load_monthly_total_spending(str(start_date), str(end_date))

    # 막대 위에 표시할 텍스트 라벨 생성 (천 단위 구분)
    monthly_spending_df["text_label"] = monthly_spending_df["total_spending"].apply(
        lambda x: f"{x:,.0f}"
    )

    # 데이터가 없는 경우 정보 메시지 표시
    if monthly_spending_df.empty:
        st.info("해당 기간의 월별 지출 데이터가 없습니다.")
    else:
        # 월별 총 지출액 막대 그래프 생성
        fig_bar = px.bar(
            monthly_spending_df,
            x="year_month",  # x축: 연월
            y="total_spending",  # y축: 총 지출액
            labels={"total_spending": "총 지출액", "year_month": "월"},  # 축 라벨
            title="월별 총 지출액",  # 차트 제목
            text="text_label",  # 막대 위에 텍스트 라벨 표시
        )
        fig_bar.update_traces(
            texttemplate="%{text}", textposition="outside"
        )  # 막대 위에 텍스트 포맷 적용
        st.plotly_chart(fig_bar, use_container_width=True)  # Streamlit에 차트 표시


st.markdown("---")  # 구분선

# --- 주요 지출 항목 비중 (트리맵) ---
st.subheader("주요 지출 항목 비중 (Treemap)")

# 선버스트 데이터에서 리프 노드(가장 하위 카테고리)만 필터링하여 복사
# 이는 부모 ID에 속하지 않는 ID를 가진 노드들이 리프 노드라고 가정
leaf_nodes_df = sunburst_df[
    ~sunburst_df["id"].isin(sunburst_df["parent_id"].unique())
].copy()

# Plotly Express를 사용하여 트리맵 생성
fig_treemap = px.treemap(
    leaf_nodes_df,
    path=[
        px.Constant("전체 지출"),
        "description",
    ],  # 계층 경로 정의 ("전체 지출" -> 카테고리 설명)
    values="total_amount",  # 노드의 크기를 결정하는 값
    color="total_amount",  # 값에 따라 색상 구분
    color_continuous_scale="Reds",  # 연속 색상 스케일
)
fig_treemap.update_traces(
    texttemplate="%{label}<br>%{value:,.0f}"
)  # 노드에 라벨과 금액 표시
fig_treemap.update_layout(margin=dict(t=25, l=0, r=0, b=0))  # 레이아웃 여백 조정
st.plotly_chart(fig_treemap, use_container_width=True)  # Streamlit에 차트 표시


st.markdown("---")  # 구분선
# --- 월별/카테고리별 지출 내역 (AG Grid) ---
st.subheader(f"월별/카테고리별 지출 내역 ({start_date} ~ {end_date})")  # 서브 헤더


# 피벗 그리드용 데이터 로드 (transaction_type 기본값이 'EXPENSE'이므로 생략 가능)
grid_source_df = load_data_for_pivot_grid(str(start_date), str(end_date))

# 그리드 소스 데이터프레임이 비어있지 않은 경우
if not grid_source_df.empty:
    # 최대 카테고리 깊이 파악
    max_depth = int(grid_source_df["depth"].max())
    # 'L1', 'L2' 등 계층 레벨 컬럼 이름 생성
    level_cols = [f"L{i}" for i in range(1, max_depth + 1)]

    # 계층 레벨 컬럼의 NaN 값을 빈 문자열로 채움
    grid_source_df[level_cols] = grid_source_df[level_cols].fillna("")

    # AG Grid 옵션 설정
    gridOptions = {
        "columnDefs": [
            # 계층 레벨 컬럼들을 숨기고 행 그룹핑에 사용
            {"field": col, "hide": True, "rowGroup": True}
            for col in level_cols
        ]
        + [
            {"field": "연월", "pivot": True},  # '연월' 컬럼을 피벗 컬럼으로 사용
            {
                "field": "금액",
                "aggFunc": "sum",  # '금액' 컬럼은 합계로 집계
                "valueFormatter": "x > 0 ? x.toLocaleString() + ' 원' : ''",  # 금액 포맷터 (천 단위, '원' 추가)
            },
        ],
        "defaultColDef": {
            "width": 130,
            "sortable": True,
            "resizable": True,
        },  # 기본 컬럼 정의
        "autoGroupColumnDef": {  # 자동 그룹핑 컬럼 정의
            "headerName": "카테고리 계층",  # 헤더 이름
            "minWidth": 300,  # 최소 너비
            "cellRendererParams": {
                "suppressCount": True
            },  # 그룹 옆에 항목 수 표시 억제
        },
        "pivotMode": True,  # 피벗 모드 활성화
    }

    # AG Grid 테이블 표시
    AgGrid(
        grid_source_df,
        gridOptions=gridOptions,
        height=600,  # 그리드 높이
        width="100%",  # 그리드 너비
        theme="alpine",  # AG Grid 테마
        allow_unsafe_jscode=True,  # JavaScript 코드 허용 (valueFormatter 사용 시 필요)
        enable_enterprise_modules=True,  # 엔터프라이즈 모듈 활성화 (피벗 기능 등)
    )
