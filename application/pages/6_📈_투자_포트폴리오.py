import streamlit as st
import pandas as pd

import plotly.express as px
from core.db_manager import update_init_balance_and_log
from core.db_queries import (
    get_investment_accounts,
    get_balance_history,
    get_init_balance,
)
from core.ui_utils import apply_common_styles, authenticate_user, logout_button

apply_common_styles()

if not authenticate_user():
    st.stop()

logout_button()

st.set_page_config(layout="wide", page_title="투자 포트폴리오")
st.title("📈 투자 포트폴리오")
st.markdown("---")


investment_df = get_investment_accounts()

if investment_df.empty:
    st.warning(
        "등록된 투자 자산이 없습니다. '기준정보 관리'에서 먼저 계좌를 추가해주세요."
    )
else:
    col1, col2 = st.columns([1, 1.5])

    with col1:
        st.subheader("보유 자산 목록")
        selected_asset_name = st.radio(
            "상세 정보를 볼 자산을 선택하세요:",
            options=investment_df["name"],
            key="selected_asset",
        )
        selected_asset_id = investment_df[investment_df["name"] == selected_asset_name][
            "id"
        ].iloc[0]

        current_balance = investment_df[investment_df["name"] == selected_asset_name][
            "balance"
        ].iloc[0]
        initial_balance = investment_df[investment_df["name"] == selected_asset_name][
            "initial_balance"
        ].iloc[0]
        st.metric(
            label=f"'{selected_asset_name}' 현재 가치",
            value=f"{current_balance+initial_balance:,.0f} 원",
        )

        with st.form("update_balance_form"):
            st.write("##### 초기 투자금 업데이트")
            new_balance = st.number_input(
                "초기투자금 (원)", min_value=0, value=int(initial_balance), step=10000
            )

            submitted = st.form_submit_button("가치 업데이트 실행")
            if submitted:
                conn = st.connection("supabase", type="sql")
                update_init_balance_and_log(int(selected_asset_id), new_balance)
                st.success("자산 가치가 성공적으로 업데이트되었습니다.")
                st.rerun()

    with col2:
        st.subheader(f"'{selected_asset_name}' 변동 이력")

        result = get_init_balance(int(selected_asset_id))
        if result is not None:
            balance, init_balance = result
            st.write(
                f"**선택된 계좌의 초기/거래 금액:** `{int(init_balance):,}`/`{int(balance):,}` **선택된 계좌의 현 잔액:** `{int(balance) + int(init_balance):,}`"
            )
        else:
            st.error(
                f"계좌(ID: {selected_asset_id})에 대한 잔액 정보를 가져올 수 없습니다."
            )

        history_df = get_balance_history(int(selected_asset_id))

        if not history_df.empty:

            history_df["change_date"] = pd.to_datetime(history_df["change_date"])
            fig = px.line(
                history_df,
                x="change_date",
                y="new_balance",
                title=f"'{selected_asset_name}' 가치 변동 그래프",
                labels={"change_date": "날짜", "new_balance": "자산 가치"},
                markers=True,
            )
            fig.update_layout(yaxis_title="자산 가치 (원)", xaxis_title="날짜")
            st.plotly_chart(fig, use_container_width=True)

            st.write("상세 이력")
            st.dataframe(
                history_df[["change_date", "reason", "change_amount", "new_balance"]],
                use_container_width=True,
            )
        else:
            st.info("해당 자산의 변동 이력이 없습니다.")
