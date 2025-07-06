import sqlite3

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

import config
from core.db_manager import update_balance_and_log
from core.db_queries import get_investment_accounts
from core.ui_utils import apply_common_styles

apply_common_styles()

st.set_page_config(layout="wide", page_title="투자 포트폴리오")
st.title("📈 투자 포트폴리오 관리")
st.markdown("`현재 잔액` 셀을 더블클릭하여 현재가치를 업데이트하고 `Enter`를 누르세요.")
st.markdown("---")

# 세션 상태를 이용해 데이터 관리
if 'investment_df' not in st.session_state:
    st.session_state.investment_df = get_investment_accounts()
if 'original_investment_df' not in st.session_state:
    st.session_state.original_investment_df = st.session_state.investment_df.copy()

if st.session_state.investment_df.empty:
    st.warning("등록된 투자 자산이 없습니다. '기준정보 관리'에서 먼저 계좌를 추가해주세요.")
else:
    # AgGrid 설정
    gb = GridOptionsBuilder.from_dataframe(st.session_state.investment_df)
    gb.configure_column("balance", header_name="현재 잔액 (가치)", editable=True,
                        type=["numericColumn", "customNumericFormat"], precision=0)
    # ... (다른 컬럼 설정) ...
    gridOptions = gb.build()

    grid_response = AgGrid(
        st.session_state.investment_df,
        gridOptions=gridOptions,
        update_mode=GridUpdateMode.MODEL_CHANGED,
        height=400, theme='streamlit',
        key='investment_grid'
    )

    updated_df = grid_response['data']
    if not st.session_state.original_investment_df.equals(updated_df):
        # 변경된 내용 찾기
        comparison_df = pd.merge(st.session_state.original_investment_df, updated_df, on='id',
                                 suffixes=('_orig', '_new'), how="inner", validate="one_to_one")
        changed_rows = comparison_df[comparison_df['balance_orig'] != comparison_df['balance_new']]

        if not changed_rows.empty:
            # DB 연결을 한번만 열어서 모든 변경사항을 처리
            with sqlite3.connect(config.DB_PATH) as conn:
                try:
                    for _, row in changed_rows.iterrows():
                        account_id = row['id']
                        change_amount = row['balance_new'] - row['balance_orig']
                        reason = "투자 포트폴리오 페이지에서 사용자 수동 가치 업데이트"

                        # 최종 통합 함수 호출
                        update_balance_and_log(account_id, change_amount, reason, conn)

                    conn.commit()  # 모든 변경사항을 한번에 커밋
                    st.toast("자산 가치가 업데이트되었습니다.")
                except Exception as e:
                    conn.rollback()
                    st.error(f"업데이트 중 오류 발생: {e}")

            # 데이터 다시 로드 및 페이지 새로고침
            st.session_state.investment_df = get_investment_accounts()
            st.session_state.original_investment_df = st.session_state.investment_df.copy()
            st.rerun()