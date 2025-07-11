# pages/3_🔁_거래_재분류.py
import streamlit as st
import pandas as pd
import config
from core.db_manager import reclassify_expense
from core.db_queries import get_bank_expense_transactions, get_all_accounts
from st_aggrid import AgGrid, GridOptionsBuilder
from datetime import date
from core.ui_utils import apply_common_styles, authenticate_user, logout_button

# --- 페이지 기본 설정 ---
apply_common_styles()

if not authenticate_user():
    st.stop()

logout_button()

st.set_page_config(layout="wide", page_title="거래 재분류")

# --- 메시지 표시 로직 ---
if "dialog_message" in st.session_state and st.session_state.dialog_message:
    st.toast(st.session_state.dialog_message)
    del st.session_state.dialog_message

st.title("🔁 거래 성격 변경 (지출 → 이체/투자)")
st.markdown(
    "은행 출금 내역 중 '지출'로 잘못 분류된 항목을 카드값 납부나 투자 이체 등으로 변경합니다."
)
st.markdown("---")

# --- 날짜 선택 UI ---
today = date.today()
default_start_date = today.replace(day=1)
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("조회 시작일", value=default_start_date)
with col2:
    end_date = st.date_input("조회 종료일", value=today)

st.markdown("---")

# --- 변경 대상 거래 목록 표시 ---
candidate_df = get_bank_expense_transactions(start_date, end_date)

if not candidate_df.empty:
    # --- 여기가 수정되었습니다 ---
    # GridOptions 딕셔너리를 직접 생성
    gridOptions = {
        "columnDefs": [
            {
                "field": "transaction_date",
                "headerName": "거래일시",
                "width": 180,
                "checkboxSelection": True,  # <<< 체크박스를 여기에 직접 지정
                "headerCheckboxSelection": False,  # 헤더 체크박스는 비활성화
            },
            {"field": "content", "headerName": "내용", "width": 300},
            {
                "field": "transaction_amount",
                "headerName": "금액",
                "type": "numericColumn",
                "valueFormatter": "x.toLocaleString()",
            },
            {"field": "id", "hide": True},
        ],
        "defaultColDef": {"sortable": True, "filter": True},
        "rowSelection": "single",
        "pagination": True,
        "paginationPageSize": 10,
    }

    st.write("##### 1. 이체로 변경할 거래 선택")
    candidate_grid_response = AgGrid(
        candidate_df,
        gridOptions=gridOptions,
        height=300,
        width="100%",
        theme="alpine",
        key="candidate_grid_final",
    )
    # ----------------------------

    selected_candidate = candidate_grid_response["selected_rows"]

    # --- 대상 계좌 선택 및 실행 UI ---
    if selected_candidate is not None and not selected_candidate.empty:
        # DataFrame의 첫 번째 행을 가져옵니다.
        selected_row_data = selected_candidate.iloc[0]

        st.write("##### 2. 이체 대상 계좌 선택 및 실행")
        col_form, col_info = st.columns(2)
        with col_form:
            with st.form("reclassify_form"):
                all_accounts_map = get_all_accounts()
                # 출금 계좌는 목록에서 제외
                source_bank_account_name = "신한은행-110-227-963599"
                if source_bank_account_name in all_accounts_map:
                    del all_accounts_map[source_bank_account_name]

                linked_account_name = st.selectbox(
                    "이 돈이 어디로 이체/투자되었나요?",
                    options=list(all_accounts_map.keys()),
                )

                submitted = st.form_submit_button(
                    "거래 성격 변경하기", use_container_width=True, type="primary"
                )
                if submitted:
                    transaction_id = int(selected_row_data["id"])
                    linked_account_id = int(all_accounts_map[linked_account_name])

                    success, message = reclassify_expense(
                        transaction_id, linked_account_id
                    )

                    if success:
                        st.session_state.dialog_message = f"✅ {message}"
                    else:
                        st.session_state.dialog_message = f"❌ {message}"
                    st.rerun()

        with col_info:
            st.info(
                f"""
            **선택된 거래 정보:**
            - **내용:** {selected_row_data['content']}
            - **금액:** {selected_row_data['transaction_amount']:,}원
            """
            )
    else:
        st.info("변경할 거래를 위 표에서 선택해주세요.")
else:
    st.info("선택된 기간에 이체로 변경할 '은행 지출' 내역이 없습니다.")
