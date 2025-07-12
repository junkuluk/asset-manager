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
    # 페이지 레이아웃을 두 개의 컬럼으로 분할
    col1, col2 = st.columns([1, 1.5])  # 왼쪽 컬럼을 더 좁게 설정

    with col1:
        st.subheader("보유 자산 목록")  # 서브 헤더
        # 투자 자산 목록을 라디오 버튼으로 표시하여 선택하도록 함
        selected_asset_name = st.radio(
            "상세 정보를 볼 자산을 선택하세요:",
            options=investment_df["name"],  # 계좌 이름을 옵션으로 사용
            key="selected_asset",  # Streamlit 세션 상태를 위한 고유 키
        )
        # 선택된 자산 이름에 해당하는 ID 조회
        selected_asset_id = investment_df[investment_df["name"] == selected_asset_name][
            "id"
        ].iloc[0]

        # 선택된 자산의 현재 잔액(거래로 인한 변동)과 초기 투자금 조회
        current_balance = investment_df[investment_df["name"] == selected_asset_name][
            "balance"
        ].iloc[0]
        initial_balance = investment_df[investment_df["name"] == selected_asset_name][
            "initial_balance"
        ].iloc[0]
        # 현재 가치(초기 투자금 + 현재 잔액)를 메트릭으로 표시
        st.metric(
            label=f"'{selected_asset_name}' 현재 가치",
            value=f"{current_balance+initial_balance:,.0f} 원",  # 천 단위 구분, '원' 추가
        )

        # 초기 투자금 업데이트 폼
        with st.form("update_balance_form"):
            st.write("##### 초기 투자금 업데이트")  # 폼 제목
            # 초기 투자금 입력 필드. 현재 초기 투자금을 기본값으로 사용.
            new_balance = st.number_input(
                "초기투자금 (원)", min_value=0, value=int(initial_balance), step=10000
            )

            submitted = st.form_submit_button("가치 업데이트 실행")  # 폼 제출 버튼
            if submitted:
                conn = st.connection(
                    "supabase", type="sql"
                )  # Supabase 데이터베이스 연결 (여기서는 불필요할 수 있음, update_init_balance_and_log 함수 내부에서 연결 관리)
                # 초기 투자금 업데이트 함수 호출
                update_init_balance_and_log(int(selected_asset_id), new_balance)
                st.success("자산 가치가 성공적으로 업데이트되었습니다.")  # 성공 메시지
                st.rerun()  # 앱 재실행하여 변경사항 반영

    with col2:
        st.subheader(f"'{selected_asset_name}' 변동 이력")  # 서브 헤더

        # 선택된 계좌의 현재 잔액 및 초기 잔액 상세 정보 조회
        result = get_init_balance(int(selected_asset_id))
        if result is not None:
            balance, init_balance = result
            # 상세 잔액 정보 출력
            st.write(
                f"**선택된 계좌의 초기/거래 금액:** `{int(init_balance):,}`/`{int(balance):,}` **선택된 계좌의 현 잔액:** `{int(balance) + int(init_balance):,}`"
            )
        else:
            st.error(
                f"계좌(ID: {selected_asset_id})에 대한 잔액 정보를 가져올 수 없습니다."
            )

        # 선택된 자산의 잔액 변경 이력 로드
        history_df = get_balance_history(int(selected_asset_id))

        # 변동 이력이 있는 경우 시각화 및 테이블 표시
        if not history_df.empty:
            # 'change_date' 컬럼을 datetime 형식으로 변환
            history_df["change_date"] = pd.to_datetime(history_df["change_date"])
            # 시간 경과에 따른 'new_balance' (잔액) 변화를 선 그래프로 시각화
            fig = px.line(
                history_df,
                x="change_date",  # x축: 날짜
                y="new_balance",  # y축: 새로운 잔액
                title=f"'{selected_asset_name}' 가치 변동 그래프",  # 차트 제목
                labels={"change_date": "날짜", "new_balance": "자산 가치"},  # 축 라벨
                markers=True,  # 데이터 포인트에 마커 표시
            )
            fig.update_layout(
                yaxis_title="자산 가치 (원)", xaxis_title="날짜"
            )  # 축 제목 업데이트
            st.plotly_chart(fig, use_container_width=True)  # Streamlit에 차트 표시

            st.write("상세 이력")  # 상세 이력 테이블 제목
            # 잔액 변경 상세 이력을 데이터프레임으로 표시
            st.dataframe(
                history_df[["change_date", "reason", "change_amount", "new_balance"]],
                use_container_width=True,
            )
        else:
            st.info("해당 자산의 변동 이력이 없습니다.")  # 변동 이력이 없는 경우 메시지
