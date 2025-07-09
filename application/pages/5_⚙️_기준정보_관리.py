import sqlite3

import streamlit as st
from st_aggrid import AgGrid, JsCode

import config
from core.db_manager import add_new_party, add_new_category, rebuild_category_paths, update_balance_and_log, \
    add_new_account, reclassify_all_transfers, recategorize_uncategorized, update_init_balance_and_log
from core.db_queries import get_all_parties_df, get_all_categories, get_all_categories_with_hierarchy, get_all_accounts, \
    get_balance_history, get_all_accounts_df, get_init_balance
from core.ui_utils import apply_common_styles

apply_common_styles()
st.set_page_config(layout="wide", page_title="기준정보 관리")
st.title("⚙️ 기준정보 관리")
st.markdown("---")

st.subheader("🏢 거래처 관리")
col1, col2 = st.columns([1, 2])

with col1:
    with st.form("new_party_form", clear_on_submit=True):
        st.write("##### 새 거래처 추가")
        new_party_code = st.text_input("거래처 코드 (예: STARBUCKS)")
        new_party_desc = st.text_input("거래처 설명 (예: 스타벅스)")
        submitted = st.form_submit_button("거래처 추가")
        if submitted:
            if new_party_code and new_party_desc:
                success, message = add_new_party(new_party_code.upper(), new_party_desc)
                if success:
                    st.success(message)
                else:
                    st.error(message)
            else:
                st.warning("코드와 설명을 모두 입력해주세요.")

with col2:
    st.write("##### 현재 거래처 목록")
    st.dataframe(get_all_parties_df(), use_container_width=True)

st.markdown("---")

st.subheader("🗂️ 카테고리 관리")

st.selectbox(
    "1. 생성할 카테고리의 타입을 먼저 선택하세요:",
    options=['EXPENSE', 'INCOME', 'INVEST'],
    key='selected_category_type'
)

selected_type = st.session_state.get('selected_category_type', 'EXPENSE')
parent_category_options = get_all_categories(
    category_type=selected_type,
    include_top_level=True
)
parent_desc_to_id = {v: k for k, v in parent_category_options.items()}

col3, col4 = st.columns([1, 2])

with col3:
    st.write("##### 새 카테고리 정보 입력")
    with st.form("new_category_form", clear_on_submit=True):

        parent_cat_desc = st.selectbox(
            "2. 상위 카테고리를 선택하세요:",
            options=list(parent_category_options.values())
        )
        new_cat_code = st.text_input("3. 카테고리 코드 (영문 대문자)")
        new_cat_desc = st.text_input("4. 카테고리 설명")

        submitted_cat = st.form_submit_button("카테고리 추가")
        if submitted_cat:
            parent_cat_id = parent_desc_to_id.get(parent_cat_desc)
            # 타입은 session_state에서 직접 가져옴
            final_cat_type = st.session_state.selected_category_type

            if all([parent_cat_id, new_cat_code, new_cat_desc, final_cat_type]):
                success, message = add_new_category(parent_cat_id, new_cat_code.upper(), new_cat_desc, final_cat_type)
                if success:
                    st.success(message)
                else:
                    st.error(message)
            else:
                st.warning("모든 항목을 입력해주세요.")

with col4:
    st.write("##### 현재 카테고리 계층 구조")

    category_tree_df = get_all_categories_with_hierarchy()

    if not category_tree_df.empty:
        # 그리드에 표시할 최종 컬럼 선택
        grid_df = category_tree_df[['id', 'category_code', 'category_type', 'name_path']].copy()

        # --- 여기가 수정되었습니다 ---
        # GridOptions 딕셔너리를 직접 생성하는 가장 안정적인 방식 사용
        gridOptions = {
            "columnDefs": [
                # 경로 계산에만 사용되므로 숨김
                {"field": "name_path", "hide": True},
                {"field": "id", "headerName": "ID", "width": 80},
                {"field": "category_code", "headerName": "코드", "width": 150},
                {"field": "category_type", "headerName": "타입", "width": 120},
            ],
            # Tree Data를 위한 핵심 설정
            "treeData": True,
            "animateRows": True,
            "groupDefaultExpanded": -1,
            # 'name_path' 컬럼을 '/' 기준으로 잘라 경로를 만듦
            "getDataPath": JsCode("function(data) { return data.name_path.split('/'); }"),
            # 자동으로 생성될 그룹 컬럼의 모양 정의
            "autoGroupColumnDef": {
                "headerName": "카테고리 계층",
                "minWidth": 400,
                "cellRendererParams": {
                    "suppressCount": True,
                },
            },
        }

        AgGrid(
            grid_df,
            gridOptions=gridOptions,
            height=600,
            width='100%',
            theme='streamlit',
            enable_enterprise_modules=True,
            allow_unsafe_jscode=True,
            key='category_tree_final_v3'
        )

st.markdown("---")
st.subheader("💰 계좌 초기 잔액 수동 조정")
st.write("초기 잔액 설정, 추적하지 않은 현금 사용 등 잔액을 직접 맞출 때 사용합니다.")

accounts_map = get_all_accounts()
account_names = list(accounts_map.keys())

if account_names:
    col1, col2 = st.columns(2)
    with col1:
        selected_account_name = st.selectbox(
            "조정할 계좌 선택",
            options=account_names,
            key="selected_account_for_adj"  # key는 그대로 유지하여 session_state를 사용
        )
        with st.form("adjustment_form"):

            adjustment_amount = st.number_input("설정 금액", step=1000, value=0)

            submitted = st.form_submit_button("잔액 조정 실행")
            if submitted:
                account_id = accounts_map[selected_account_name]
                # DB 연결 및 함수 호출
                with sqlite3.connect(config.DB_PATH) as conn:
                    try:
                        update_init_balance_and_log(account_id, adjustment_amount, conn)
                        st.success(f"'{selected_account_name}' 계좌의 잔액 조정이 완료되었습니다.")
                    except Exception as e:
                        st.error(f"오류 발생: {e}")

                st.rerun()

    with col2:
        st.write("##### 거래 내역 조정 이력")
        # 선택된 계좌의 조정 히스토리를 보여줌
        selected_id = accounts_map[st.session_state.selected_account_for_adj]
        print(selected_id)
        balance, init_balance = get_init_balance(selected_id)
        st.write(f"**선택된 계좌의 초기/거래 금액:** `{int(init_balance):,}`/`{int(balance):,}` **선택된 계좌의 현 잔액:** `{int(balance) + int(init_balance):,}`")
        history_df = get_balance_history(selected_id)
        st.dataframe(history_df, use_container_width=True)
else:
    st.warning("먼저 계좌를 등록해주세요.")

st.subheader("🏦 계좌 관리")
col1, col2 = st.columns([1, 2])

with col1:
    with st.form("new_account_form", clear_on_submit=True):
        st.write("##### 새 계좌 추가")
        acc_name = st.text_input("계좌 이름 (예: 카카오뱅크, 미래에셋증권)")
        acc_type = st.selectbox("계좌 타입", ["BANK_ACCOUNT", "CREDIT_CARD", "CASH", "STOCK_ASSET", "FUND", "REAL_ESTATE"])
        is_asset = st.radio("자산/부채 구분", [True, False], format_func=lambda x: "자산" if x else "부채")
        is_invest = st.radio("투자 구분", [True, False], format_func=lambda x: "투자" if x else "비투자")
        initial_balance = st.number_input("초기 잔액 (없으면 0)", value=0, step=10000)

        submitted = st.form_submit_button("계좌 추가")
        if submitted and acc_name:
            success, message = add_new_account(acc_name, acc_type, is_asset, initial_balance)
            if success:
                st.success(message)
            else:
                st.error(message)

with col2:
    st.write("##### 현재 계좌 목록")
    st.dataframe(get_all_accounts_df(), use_container_width=True)

with st.expander("🧰 데이터 보정 도구"):
    st.warning("주의: 이 기능은 데이터 구조를 직접 수정합니다. 필요할 때만 사용하세요.")

    if st.button("모든 카테고리 경로 재계산 실행"):
        with st.spinner("경로를 재계산하는 중입니다..."):
            updated_count, message = rebuild_category_paths()
        st.success(f"작업 완료: {message} ({updated_count}개 행 업데이트)")

st.markdown("---")
st.subheader("⚙️ 데이터 일괄 처리 도구")

with st.expander("규칙 엔진 전체 재적용"):
    st.info("이 기능은 전체 거래 내역을 대상으로 규칙을 다시 실행합니다. 시간이 다소 걸릴 수 있습니다.")

    if st.button("은행 거래 '이체' 규칙 재적용"):
        with st.spinner("모든 은행 지출 내역을 확인 중입니다..."):
            message = reclassify_all_transfers()
            st.success(message)

    if st.button("'미분류' 거래 카테고리 재적용"):
        with st.spinner("미분류 거래에 대해 카테고리 규칙을 실행 중입니다..."):
            message = recategorize_uncategorized()
            st.success(message)