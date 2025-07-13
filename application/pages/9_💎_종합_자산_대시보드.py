import streamlit as st
import plotly.graph_objects as go  # Plotly의 저수준 그래프 객체 생성
from plotly.subplots import make_subplots  # 다중 축을 가진 서브플롯 생성
from core.db_queries import (
    get_monthly_summary_for_dashboard,
)  # 대시보드 요약 데이터 로드 함수 임포트
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
st.set_page_config(layout="wide", page_title="종합 자산 대시보드")
st.title("💎 종합 자산 대시보드")  # 페이지 메인 제목
st.markdown("월별 현금흐름과 그에 따른 순자산의 변화를 추적합니다.")  # 페이지 설명
st.markdown("---")  # 구분선

# 월별 요약 데이터를 데이터베이스에서 로드
summary_df = get_monthly_summary_for_dashboard()

# 분석할 데이터가 충분하지 않은 경우 경고 메시지 표시
if summary_df.empty:
    st.warning("분석할 데이터가 충분하지 않습니다.")
else:
    # 다중 Y축을 가진 서브플롯 생성 (수입/지출과 총자산 스케일이 다를 수 있기 때문)
    # secondary_y=True: 두 번째 Y축을 활성화
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 수입 막대 그래프 추가 (기본 Y축 사용)
    fig.add_trace(
        go.Bar(
            name="수입",  # 범례 이름
            x=summary_df["연월"],  # x축: 연월
            y=summary_df["수입"],  # y축: 수입 금액
            marker_color="blue",  # 막대 색상
        ),
        secondary_y=False,  # 기본 Y축 사용
    )
    # 지출 막대 그래프 추가 (기본 Y축 사용)
    fig.add_trace(
        go.Bar(
            name="지출",  # 범례 이름
            x=summary_df["연월"],  # x축: 연월
            y=summary_df["지출"],  # y축: 지출 금액
            marker_color="red",  # 막대 색상
        ),
        secondary_y=False,  # 기본 Y축 사용
    )

    # 총자산 선 그래프 추가 (보조 Y축 사용)
    fig.add_trace(
        go.Scatter(
            name="총자산",  # 범례 이름
            x=summary_df["연월"],  # x축: 연월
            y=summary_df["총자산"],  # y축: 총자산 금액
            mode="lines+markers",  # 선과 마커로 표시
            line=dict(color="green"),  # 선 색상
        ),
        secondary_y=True,  # 보조 Y축 사용
    )

    # 차트 레이아웃 업데이트
    fig.update_layout(
        title_text="월별 현금흐름 및 총자산 추이",  # 차트 제목
        barmode="group",  # 막대 그래프 그룹화
        legend_title_text="항목",  # 범례 제목
    )
    # X축 제목 설정
    fig.update_xaxes(title_text="연월")
    # 기본 Y축 제목 설정
    fig.update_yaxes(title_text="금액 (원)", secondary_y=False)
    # 보조 Y축 제목 설정
    fig.update_yaxes(title_text="총자산 (원)", secondary_y=True)
    # Streamlit에 Plotly 차트 표시 (컨테이너 너비에 맞춤)
    st.plotly_chart(fig, use_container_width=True)

    # 월별 요약 데이터 테이블 표시
    st.subheader("월별 요약 데이터")  # 서브 헤더
    # 데이터프레임을 '연월'을 인덱스로 설정하여 표시
    st.dataframe(
        summary_df.set_index("연월").style.format(
            {
                "수입": "{:,.0f}",
                "지출": "{:,.0f}",
                "총자산": "{:,.0f}",
            }
        ),
        use_container_width=True,
    )
