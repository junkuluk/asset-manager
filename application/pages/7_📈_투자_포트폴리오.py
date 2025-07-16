import streamlit as st
import pandas as pd
import plotly.express as px  # 대화형 차트 생성
from core.db_manager import (
    update_init_balance_and_log,
)  # 초기 잔액 업데이트 및 로그 기록 함수 임포트
from core.db_queries import (  # 데이터베이스 쿼리 함수 임포트
    get_investment_accounts,  # 투자 계좌 정보 조회
    get_balance_history,  # 잔액 변경 이력 조회
    get_init_balance,  # 계좌 초기 잔액 및 현재 잔액 조회
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
st.set_page_config(layout="wide", page_title="투자 포트폴리오")
st.title("📈 투자 포트폴리오")  # 페이지 메인 제목
st.markdown("---")  # 구분선


# 투자 계좌 정보 로드
investment_df = get_investment_accounts()

# 등록된 투자 자산이 없는 경우 경고 메시지 표시
if investment_df.empty:
    st.warning(
        "등록된 투자 자산이 없습니다. '기준정보 관리'에서 먼저 계좌를 추가해주세요."
    )
else:
    selected_asset_name = st.selectbox("투자계좌", options=investment_df["name"])
    selected_asset_id = investment_df[investment_df["name"] == selected_asset_name][
        "id"
    ].iloc[0]

    st.subheader(f"'{selected_asset_name}' 변동 이력")  # 서브 헤더

    # 선택된 계좌의 현재 잔액 및 초기 잔액 상세 정보 조회
    result = get_init_balance(int(selected_asset_id))
    if result is not None:
        balance, init_balance = result
        # 상세 잔액 정보 출력
        st.write(f"**선택된 계좌의 현 잔액:** `{int(balance) + int(init_balance):,}`")
    else:
        st.error(
            f"계좌(ID: {selected_asset_id})에 대한 잔액 정보를 가져올 수 없습니다."
        )

    # 선택된 자산의 잔액 변경 이력 로드
    history_df = get_balance_history(int(selected_asset_id))

    # 변동 이력이 있는 경우 시각화 및 테이블 표시
    if not history_df.empty:

        # 1. 날짜순으로 정렬 (누적합 계산을 위해 필수)
        history_df.sort_values("change_date", inplace=True)
        history_df["change_date"] = pd.to_datetime(history_df["change_date"])

        # 2. 초기 잔액에 변동액의 누적 합계를 더해 '누적 잔고' 컬럼 생성
        if result is not None:
            _, init_balance = result
            history_df["cumulative_balance"] = (
                int(init_balance) + history_df["change_amount"].cumsum()
            )
        else:
            # 초기 잔액이 없는 경우, 첫 변동액부터 시작
            history_df["cumulative_balance"] = history_df["change_amount"].cumsum()

        fig = px.line(
            history_df,
            x="change_date",  # x축: 날짜
            y="cumulative_balance",  # y축을 누적 잔고로 변경
            title=f"'{selected_asset_name}' 가치 변동 그래프",  # 차트 제목
            labels={"change_date": "날짜", "cumulative_balance": "자산 가치"},
            markers=True,  # 데이터 포인트에 마커 표시
        )
        fig.update_traces(
            hovertemplate="<b>날짜:</b> %{x|%Y-%m-%d}<br><b>누적 자산:</b> %{y:,.0f}원<extra></extra>"
        )
        fig.update_layout(
            yaxis_title="자산 가치 (원)", xaxis_title="날짜"
        )  # 축 제목 업데이트
        fig.update_xaxes(
            dtick="M1",
            tickformat="%Y/%m",
        )

        st.plotly_chart(fig, use_container_width=True)

        st.write("상세 이력")  # 상세 이력 테이블 제목
        # 잔액 변경 상세 이력을 데이터프레임으로 표시
        display_df = history_df[
            ["change_date", "reason", "change_amount", "cumulative_balance"]
        ]

        display_df = display_df.rename(
            columns={
                "change_date": "날짜",
                "reason": "사유",
                "change_amount": "변동 금액",
                "cumulative_balance": "누적 잔고",
            }
        )

        # Pandas Styler를 사용하여 데이터프레임 꾸미기
        styled_df = (
            display_df.style.format(
                {
                    "변동 금액": "{:,.0f}원",
                    "누적 잔고": "{:,.0f}원",  # 'new_balance' -> '누적 잔고'로 키 변경
                    "날짜": "{:%Y-%m-%d}",
                }
            )
            .apply(
                lambda x: ["color: #1f77b4" if v > 0 else "color: #d62728" for v in x],
                subset=["변동 금액"],
            )
            .bar(subset=["변동 금액"], align="mid", color=["#d62728", "#1f77b4"])
            .set_properties(**{"text-align": "center"})
        )

        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True,  # 인덱스 숨기기
        )

        st.subheader("전체 투자 포트폴리오 자산 배분 (최종 잔고 기준)")

        # 1. 각 자산의 최종 잔고를 계산하여 저장할 리스트 생성
        portfolio_final_balances = []

        # 2. 등록된 모든 투자 계좌를 순회
        for index, row in investment_df.iterrows():
            account_id = row["id"]
            account_name = row["name"]
            final_balance = 0  # 기본값 설정

            # 3. 각 계좌의 초기 잔액과 거래 이력 조회
            init_result = get_init_balance(int(account_id))
            history_df = get_balance_history(int(account_id))

            if init_result is not None:
                balance, init_balance = init_result

                # 거래 이력이 없는 경우, 초기 잔액이 현재 가치
                final_balance = int(init_balance) + int(balance)

                # 거래 이력이 있는 경우, 누적 합산의 마지막 값을 현재 가치로 사용
                if not history_df.empty:
                    history_df.sort_values("change_date", inplace=True)
                    cumulative_series = (
                        int(init_balance) + history_df["change_amount"].cumsum()
                    )
                    final_balance = cumulative_series.iloc[-1]

            # 계산된 최종 잔고를 리스트에 추가
            portfolio_final_balances.append(final_balance)

        # 4. 기존 investment_df에 'current_value' 컬럼으로 최종 잔고를 추가
        assets_with_values_df = investment_df.copy()
        assets_with_values_df["current_value"] = portfolio_final_balances

        # 5. 최종 잔고가 0보다 큰 자산만 필터링하여 차트에 표시
        assets_with_values_df = assets_with_values_df[
            assets_with_values_df["current_value"] > 0
        ]

        # 6. 자산 배분 도넛 차트 생성
        fig_pie = px.pie(
            assets_with_values_df,
            names="name",  # 계좌 이름
            values="current_value",  # 계산된 현재 가치 (최종 잔고)
            title="계좌별 자산 비중",
            hole=0.4,  # 가운데 구멍을 만들어 도넛 형태로
            color_discrete_sequence=px.colors.sequential.RdBu,  # 색상 테마 적용
        )

        # 차트 조각 위에 표시될 텍스트 형식 지정
        fig_pie.update_traces(
            textposition="inside",
            textinfo="percent+label",
            # 현재 보고있는 자산만 살짝 강조하는 효과
            pull=[
                0.05 if name == selected_asset_name else 0
                for name in assets_with_values_df["name"]
            ],
        )

        # 차트 레이아웃 조정
        fig_pie.update_layout(
            showlegend=False, uniformtext_minsize=12, uniformtext_mode="hide"
        )

        st.plotly_chart(fig_pie, use_container_width=True)

    else:
        st.info("해당 자산의 변동 이력이 없습니다.")  # 변동 이력이 없는 경우 메시지
