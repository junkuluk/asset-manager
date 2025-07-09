import calendar
import time
from datetime import date

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridUpdateMode, JsCode

from core.db_manager import update_transaction_category, update_transaction_description, update_transaction_party, \
    reclassify_expense
from core.db_queries import load_data_from_db, get_all_categories, get_all_parties, get_bank_expense_transactions, \
    get_all_accounts
from core.ui_utils import apply_common_styles, authenticate_user

# 1. 공통 스타일 적용
apply_common_styles()

if not authenticate_user():
    st.stop()

st.set_page_config(layout="wide", page_title="거래내역 상세 수정")

# 2. Custom CSS (수정)
st.markdown("""
<style>
    /* AgGrid의 글꼴 크기와 행 높이를 강제로 지정 */
    .ag-theme-streamlit .ag-cell, .ag-theme-streamlit .ag-header-cell-label {
        font-size: 15px !important;
    }
    .ag-theme-streamlit .ag-root-wrapper {
        --ag-row-height: 40px !important;
    }
</style>
""", unsafe_allow_html=True)


# 3. 데이터 로딩 및 상태 관리 함수
def load_data():
    """선택된 필터 값을 기준으로 데이터를 로드하여 세션 상태에 저장합니다."""
    st.session_state.editor_df = load_data_from_db(
        st.session_state.editor_start_date,
        st.session_state.editor_end_date,
        st.session_state.editor_selected_types,
        st.session_state.editor_selected_cat
    )
    st.session_state.original_editor_df = st.session_state.editor_df.copy()

# 4. 세션 상태 초기화 (페이지 첫 로딩 시 딱 한 번 실행)
if 'editor_initialized' not in st.session_state:
    today = date.today()
    st.session_state.editor_start_date = today.replace(month=1, day=1)
    st.session_state.editor_end_date = today
    st.session_state.editor_selected_types = ['EXPENSE', 'INCOME', 'INVEST', 'TRANSFER']
    st.session_state.editor_selected_cat = ['BANK','CARD']
    load_data()  # 초기 데이터 로드
    st.session_state.editor_initialized = True # 초기화 완료 플래그 설정


# --- UI 렌더링 ---
st.title("📝 거래 내역 상세 수정")
st.markdown("""
- **카테고리/메모/거래처 변경**: 해당 셀을 **더블클릭**하여 수정 후 Enter를 누르세요.
 <span style='background-color: #fff9e6; border: 1px solid #e0e0e0; border-radius: 3px; padding: 2px 5px;'>노란 배경</span>의 셀만 수정 가능합니다.
""", unsafe_allow_html=True)
st.markdown("---")

# 5. 필터 UI
col1, col2, col3, col4 = st.columns([1, 1, 3, 2])
with col1:
    st.date_input("조회 시작일", key="editor_start_date", on_change=load_data)
with col2:
    st.date_input("조회 종료일", key="editor_end_date", on_change=load_data)
with col3:
    st.multiselect(
        "거래 구분 필터",
        options=['EXPENSE', 'INCOME', 'INVEST', 'TRANSFER', 'ADJUSTMENT'],
        key="editor_selected_types",
        on_change=load_data
    )
with col4:
    st.multiselect(
        "종류 필터",
        options=['BANK', 'CARD'],
        key="editor_selected_cat",
        on_change=load_data
    )

# 5. 드롭다운 메뉴를 위한 데이터 로드
expense_categories = get_all_categories(category_type='EXPENSE')
income_categories = get_all_categories(category_type='INCOME')
invest_categories = get_all_categories(category_type='INVEST')
transfer_categories = get_all_categories(category_type='TRANSFER')
all_editable_categories = {**expense_categories, **income_categories, **invest_categories, **transfer_categories}
category_name_to_id_map = {v: k for k, v in all_editable_categories.items()}
party_map = get_all_parties()
party_desc_to_id_map = {v: k for k, v in party_map.items()}

# 6. 메인 그리드 표시
if st.session_state.editor_df.empty:
    st.warning("선택된 기간/구분에 해당하는 데이터가 없습니다.")
else:
    # 동적 카테고리 드롭다운을 위한 JsCode
    jscode = JsCode(f"""
    function(params) {{
        var transactionType = params.data.type;
        if (transactionType === 'EXPENSE') {{ return {{'values': {list(expense_categories.values())} }}; }} 
        else if (transactionType === 'INCOME') {{ return {{'values': {list(income_categories.values())} }}; }} 
        else if (transactionType === 'INVEST') {{ return {{'values': {list(invest_categories.values())} }}; }}
        else if (transactionType === 'TRANSFER') {{ return {{'values': {list(transfer_categories.values())} }}; }}
        else {{ return {{'values': [] }}; }}
    }}
    """)
    editable_cell_style = {'backgroundColor': '#fff9e6'}

    # AgGrid 설정
    gridOptions = {
        "columnDefs": [
            {"field": "id", "headerName": "ID", "width": 80, "editable": False},
            {"field": "transaction_type", "headerName": "종류", "width": 80, "editable": False},
            {"field": "type", "headerName": "구분", "width": 100, "editable": False},
            {"field": "transaction_date", "headerName": "거래일시", "width": 180, "sort": 'desc'},
            {"field": "content", "headerName": "내용", "width": 250, "editable": False},
            {"field": "party_description", "headerName": "거래처", "width": 150, "cellEditor": 'agSelectCellEditor',
             "cellEditorParams": {'values': list(party_map.values())}, "cellStyle": editable_cell_style},
            {"field": "category_name", "headerName": "카테고리", "width": 150, "cellEditor": 'agSelectCellEditor',
             "cellEditorParams": jscode, "cellStyle": editable_cell_style},
            {"field": "transaction_amount", "headerName": "금액", "width": 120, "valueFormatter": "x.toLocaleString()",
             "type": "numericColumn", "editable": False},
            {"field": "description", "headerName": "메모", "width": 300, "cellStyle": editable_cell_style},
        ],
        "defaultColDef": {"sortable": True, "resizable": True, "editable": True},
        "pagination": True, "paginationPageSize": 20, "rowHeight": 35,
    }

    # AgGrid 실행
    grid_response = AgGrid(
        st.session_state.editor_df,
        gridOptions=gridOptions,
        key='transaction_editor_grid',
        update_mode=GridUpdateMode.MODEL_CHANGED,
        allow_unsafe_jscode=True, height=700, theme='streamlit'
    )

    # 변경사항 DB 업데이트 로직
    updated_df = grid_response['data']
    if updated_df is not None and not st.session_state.original_editor_df.equals(updated_df):
        try:
            comparison_df = pd.merge(st.session_state.original_editor_df, updated_df, on='id', suffixes=('_orig', '_new'), how='inner', validate="one_to_one")
            cat_changed = comparison_df['category_name_orig'].fillna('') != comparison_df['category_name_new'].fillna(
                '')
            party_changed = comparison_df['party_description_orig'].fillna('') != comparison_df[
                'party_description_new'].fillna('')
            desc_changed = comparison_df['description_orig'].fillna('') != comparison_df['description_new'].fillna('')
            changed_rows = comparison_df[cat_changed | party_changed | desc_changed]

            if not changed_rows.empty:
                for _, row in changed_rows.iterrows():
                    transaction_id = row['id']
                    if row['category_name_orig'] != row['category_name_new']:
                        new_category_id = category_name_to_id_map.get(row['category_name_new'])
                        if new_category_id: update_transaction_category(transaction_id, new_category_id)
                    if row['party_description_orig'] != row['party_description_new']:
                        new_party_id = party_desc_to_id_map.get(row['party_description_new'])
                        if new_party_id: update_transaction_party(transaction_id, new_party_id)
                    if row['description_orig'] != row['description_new']:
                        update_transaction_description(transaction_id, row['description_new'])

                st.toast("변경사항이 저장되었습니다.")
                time.sleep(1)
                load_data()
                st.rerun()

        except Exception as e:
            st.error(f"데이터 업데이트 중 오류 발생: {e}")

# --- 거래 타입 수동 변경 Expander ---
# st.markdown("---")
# with st.expander("🔁 거래 성격 변경 (지출 → 이체/투자)"):
#     st.write("은행 출금 내역 중 '지출'로 잘못 분류된 항목을 카드값 납부나 투자 이체 등으로 변경합니다.")
#
#     start_date, end_date = st.session_state.editor_start_date, st.session_state.editor_end_date
#     candidate_df = get_bank_expense_transactions(start_date, end_date)
#
#     if not candidate_df.empty:
#         candidate_df['display'] = candidate_df.apply(
#             lambda r: f"{r['transaction_date']} / {r['content']} / {r['transaction_amount']:,}원", axis=1)
#         options_map = pd.Series(candidate_df.id.values, index=candidate_df.display).to_dict()
#
#         with st.form("reclassify_form"):
#             selected_display = st.selectbox("변경할 '은행 지출' 거래를 선택하세요:", options=options_map.keys())
#             all_accounts_map = get_all_accounts()
#             # 현재 선택된 은행 계좌는 제외
#             # 이 로직은 현재 모든 은행 거래가 하나의 계좌에서 일어난다고 가정
#             # del all_accounts_map['신한은행-110-227-963599']
#
#             linked_account_name = st.selectbox("이 돈이 어디로 이체되었나요?", options=list(all_accounts_map.keys()))
#
#             submitted = st.form_submit_button("거래 성격 변경하기")
#             if submitted:
#                 transaction_id = int(options_map[selected_display])
#                 linked_account_id = all_accounts_map[linked_account_name]
#
#                 success, message = reclassify_expense(transaction_id, linked_account_id)
#                 if success:
#                     st.toast(f"✅ {message}")
#                     time.sleep(1)
#                     load_data()
#                     st.rerun()
#                 else:
#                     st.error(message)
#     else:
#         st.info("선택된 기간에 이체로 변경할 '은행 지출' 내역이 없습니다.")