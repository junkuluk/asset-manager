import calendar
import time
from datetime import date

import pandas as pd
import streamlit as st
from st_aggrid import (
    AgGrid,
    GridUpdateMode,
    JsCode,
)  # AG Grid 테이블, 업데이트 모드, JavaScript 코드 실행 기능 임포트

from core.db_manager import (  # 데이터베이스 관리 함수 임포트
    update_transaction_category,  # 거래 카테고리 업데이트
    update_transaction_description,  # 거래 설명 업데이트
    update_transaction_party,  # 거래처 업데이트
)
from core.db_queries import (  # 데이터베이스 쿼리 함수 임포트
    load_data_from_db,  # DB에서 거래 데이터 로드
    get_all_categories,  # 모든 카테고리 로드
    get_all_parties,  # 모든 거래처 로드
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
st.set_page_config(layout="wide", page_title="거래내역 상세 수정")

# AG Grid의 글꼴 크기와 행 높이를 조절하는 커스텀 CSS 스타일 적용
st.markdown(
    """
<style>
    /* AgGrid의 글꼴 크기와 행 높이를 강제로 지정 */
    .ag-theme-streamlit .ag-cell, .ag-theme-streamlit .ag-header-cell-label {
        font-size: 15px !important;
    }
    .ag-theme-streamlit .ag-root-wrapper {
        --ag-row-height: 40px !important; /* 행 높이 설정 */
    }
</style>
""",
    unsafe_allow_html=True,  # HTML 사용 허용
)


def load_data():
    """
    Streamlit 세션 상태에 저장된 필터(날짜, 거래 유형, 카테고리 종류)에 따라
    데이터베이스에서 거래 데이터를 로드하고 세션 상태를 업데이트하는 함수.
    """
    # load_data_from_db 함수를 사용하여 데이터 로드
    st.session_state.editor_df = load_data_from_db(
        st.session_state.editor_start_date,  # 세션 상태에서 시작일 가져옴
        st.session_state.editor_end_date,  # 세션 상태에서 종료일 가져옴
        st.session_state.editor_selected_types,  # 세션 상태에서 선택된 거래 유형 가져옴
        st.session_state.editor_selected_cat,  # 세션 상태에서 선택된 카테고리 종류 가져옴
    )
    # 원본 데이터프레임 복사본을 저장하여 변경사항 비교에 사용
    st.session_state.original_editor_df = st.session_state.editor_df.copy()


# Streamlit 세션 상태 초기화 (앱 최초 로드 시 한 번만 실행)
if "editor_initialized" not in st.session_state:
    today = date.today()
    # 기본 조회 기간: 현재 연도의 1월 1일부터 오늘까지
    st.session_state.editor_start_date = today.replace(month=1, day=1)
    st.session_state.editor_end_date = today
    # 기본 선택 필터: 모든 거래 유형, 은행/카드 종류
    st.session_state.editor_selected_types = ["EXPENSE", "INCOME", "INVEST", "TRANSFER"]
    st.session_state.editor_selected_cat = ["BANK", "CARD"]
    load_data()  # 초기 데이터 로드
    st.session_state.editor_initialized = True  # 초기화 플래그 설정


st.title("📝 거래 내역 상세 수정")  # 페이지 메인 제목
st.markdown(
    """
- **카테고리/메모/거래처 변경**: 해당 셀을 **더블클릭**하여 수정 후 Enter를 누르세요.
 <span style='background-color: #fff9e6; border: 1px solid #e0e0e0; border-radius: 3px; padding: 2px 5px;'>노란 배경</span>의 셀만 수정 가능합니다.
""",
    unsafe_allow_html=True,  # HTML 사용 허용하여 스타일이 적용된 텍스트 표시
)
st.markdown("---")  # 구분선


# 데이터 필터링을 위한 날짜 및 멀티셀렉트 위젯
col1, col2, col3, col4 = st.columns([1, 1, 3, 2])  # 컬럼 레이아웃 정의
with col1:
    # 조회 시작일 입력 필드. 변경 시 load_data 함수 호출.
    st.date_input("조회 시작일", key="editor_start_date", on_change=load_data)
with col2:
    # 조회 종료일 입력 필드. 변경 시 load_data 함수 호출.
    st.date_input("조회 종료일", key="editor_end_date", on_change=load_data)
with col3:
    # 거래 구분 필터 멀티셀렉트. 변경 시 load_data 함수 호출.
    st.multiselect(
        "거래 구분 필터",
        options=["EXPENSE", "INCOME", "INVEST", "TRANSFER", "ADJUSTMENT"],
        key="editor_selected_types",
        on_change=load_data,
    )
with col4:
    # 종류 필터 멀티셀렉트. 변경 시 load_data 함수 호출.
    st.multiselect(
        "종류 필터",
        options=["BANK", "CARD"],
        key="editor_selected_cat",
        on_change=load_data,
    )


# 카테고리 및 거래처 정보 로드
# 각 거래 유형별 카테고리 로드
expense_categories = get_all_categories(category_type="EXPENSE")
income_categories = get_all_categories(category_type="INCOME")
invest_categories = get_all_categories(category_type="INVEST")
transfer_categories = get_all_categories(category_type="TRANSFER")
# 모든 수정 가능한 카테고리를 하나의 딕셔너리로 합침
all_editable_categories = {
    **expense_categories,
    **income_categories,
    **invest_categories,
    **transfer_categories,
}
# 카테고리 이름 -> ID 매핑 딕셔너리 생성 (수정 시 ID 조회를 위함)
category_name_to_id_map = {v: k for k, v in all_editable_categories.items()}
# 모든 거래처 정보 로드
party_map = get_all_parties()
# 거래처 설명 -> ID 매핑 딕셔너리 생성 (수정 시 ID 조회를 위함)
party_desc_to_id_map = {v: k for k, v in party_map.items()}


# 로드된 거래 데이터가 비어있는 경우 경고 메시지 표시
if st.session_state.editor_df.empty:
    st.warning("선택된 기간/구분에 해당하는 데이터가 없습니다.")
else:
    # AG Grid의 '카테고리' 컬럼 셀 에디터에서 사용될 JavaScript 코드
    # 거래의 'type' (구분)에 따라 드롭다운 목록을 동적으로 변경
    jscode = JsCode(
        f"""
    function(params) {{
        var transactionType = params.data.type; // 현재 행의 거래 구분 (EXPENSE, INCOME 등)
        if (transactionType === 'EXPENSE') {{ return {{'values': {list(expense_categories.values())} }}; }} /* 지출 카테고리 목록 */
        else if (transactionType === 'INCOME') {{ return {{'values': {list(income_categories.values())} }}; }} /* 수입 카테고리 목록 */
        else if (transactionType === 'INVEST') {{ return {{'values': {list(invest_categories.values())} }}; }} /* 투자 카테고리 목록 */
        else if (transactionType === 'TRANSFER') {{ return {{'values': {list(transfer_categories.values())} }}; }} /* 이체 카테고리 목록 */
        else {{ return {{'values': [] }}; }} /* 그 외의 경우 빈 목록 */
    }}
    """
    )
    # 수정 가능한 셀의 배경색 스타일 정의
    editable_cell_style = {"backgroundColor": "#fff9e6"}  # 연한 노란색 배경

    # AG Grid 컬럼 정의 및 옵션 설정
    gridOptions = {
        "columnDefs": [
            {
                "field": "id",
                "headerName": "ID",
                "width": 50,
                "editable": False,
            },  # ID 컬럼: 수정 불가
            {
                "field": "transaction_type",  # 거래 종류 (BANK, CARD)
                "headerName": "종류",
                "width": 50,
                "editable": False,
            },
            {
                "field": "type",
                "headerName": "구분",
                "width": 80,
                "editable": False,
            },  # 거래 구분 (EXPENSE, INCOME 등)
            {
                "field": "transaction_date",  # 거래 일시
                "headerName": "거래일시",
                "width": 180,
                "sort": "desc",  # 기본 정렬: 내림차순
                "editable": False,  # 날짜 수정 불가
            },
            {
                "field": "content",
                "headerName": "내용",
                "width": 200,
                "editable": False,
            },  # 거래 내용: 수정 불가
            {
                "field": "summary_content",
                "headerName": "적요",
                "width": 100,
                "editable": False,
            },
            {
                "field": "party_description",  # 거래처 설명
                "headerName": "거래처",
                "width": 150,
                "cellEditor": "agSelectCellEditor",  # 드롭다운 선택 에디터
                "cellEditorParams": {
                    "values": list(party_map.values())
                },  # 거래처 목록 드롭다운에 추가
                "cellStyle": editable_cell_style,  # 수정 가능한 셀 스타일 적용
            },
            {
                "field": "category_name",  # 카테고리 이름
                "headerName": "카테고리",
                "width": 150,
                "cellEditor": "agSelectCellEditor",  # 드롭다운 선택 에디터
                "cellEditorParams": jscode,  # 동적 카테고리 목록을 위한 JavaScript 코드 적용
                "cellStyle": editable_cell_style,  # 수정 가능한 셀 스타일 적용
            },
            {
                "field": "transaction_amount",  # 금액
                "headerName": "금액",
                "width": 120,
                "valueFormatter": "x.toLocaleString()",  # 금액을 현지 통화 형식으로 포맷
                "type": "numericColumn",  # 숫자 컬럼 타입
                "editable": False,  # 금액 수정 불가
            },
            {
                "field": "description",  # 메모
                "headerName": "메모",
                "width": 300,
                "cellStyle": editable_cell_style,  # 수정 가능한 셀 스타일 적용
            },
        ],
        "defaultColDef": {
            "sortable": True,
            "resizable": True,
            "editable": True,
        },  # 기본 컬럼 설정: 정렬, 크기 조절, 편집 가능
        "pagination": True,  # 페이지네이션 활성화
        "paginationPageSize": 20,  # 페이지당 20개 행 표시
        "rowHeight": 35,  # 행 높이 설정
    }

    # AG Grid 테이블 표시 및 사용자 상호작용에 따른 응답 받기
    grid_response = AgGrid(
        st.session_state.editor_df,  # 표시할 데이터프레임
        gridOptions=gridOptions,  # 그리드 옵션 적용
        key="transaction_editor_grid",  # Streamlit 세션 상태를 위한 고유 키
        update_mode=GridUpdateMode.MODEL_CHANGED,  # 모델이 변경될 때마다 업데이트
        allow_unsafe_jscode=True,  # JavaScript 코드 실행 허용
        height=700,  # 그리드 높이
        theme="streamlit",  # AG Grid 테마 (Streamlit 기본 테마와 어울리게)
    )

    updated_df = grid_response["data"]  # AG Grid로부터 업데이트된 데이터프레임 가져오기
    # 원본 데이터프레임과 업데이트된 데이터프레임이 다른 경우 (수정사항이 있는 경우)
    if updated_df is not None and not st.session_state.original_editor_df.equals(
        updated_df
    ):
        try:
            # 원본과 새 데이터를 병합하여 변경된 행만 식별
            comparison_df = pd.merge(
                st.session_state.original_editor_df,
                updated_df,
                on="id",  # ID를 기준으로 병합
                suffixes=("_orig", "_new"),  # 원본/새 컬럼 접미사
                how="inner",  # 공통 ID만 포함
                validate="one_to_one",  # 1:1 관계 검증
            )
            # 카테고리, 거래처, 설명 컬럼의 변경 여부 확인
            # NaN 값은 빈 문자열로 처리하여 비교 (fillna)
            cat_changed = comparison_df["category_name_orig"].fillna(
                ""
            ) != comparison_df["category_name_new"].fillna("")
            party_changed = comparison_df["party_description_orig"].fillna(
                ""
            ) != comparison_df["party_description_new"].fillna("")
            desc_changed = comparison_df["description_orig"].fillna(
                ""
            ) != comparison_df["description_new"].fillna("")
            # 변경된 모든 행 필터링
            changed_rows = comparison_df[cat_changed | party_changed | desc_changed]

            # 변경된 행이 존재하는 경우 데이터베이스 업데이트
            if not changed_rows.empty:
                for _, row in changed_rows.iterrows():
                    transaction_id = row["id"]  # 거래 ID

                    # 카테고리 변경 감지 및 업데이트
                    if row["category_name_orig"] != row["category_name_new"]:
                        new_category_id = (
                            category_name_to_id_map.get(  # 새 카테고리 이름으로 ID 조회
                                row["category_name_new"]
                            )
                        )
                        if new_category_id:  # ID가 유효한 경우 업데이트
                            update_transaction_category(transaction_id, new_category_id)

                    # 거래처 변경 감지 및 업데이트
                    if row["party_description_orig"] != row["party_description_new"]:
                        new_party_id = (
                            party_desc_to_id_map.get(  # 새 거래처 설명으로 ID 조회
                                row["party_description_new"]
                            )
                        )
                        if new_party_id:  # ID가 유효한 경우 업데이트
                            update_transaction_party(transaction_id, new_party_id)

                    # 메모 변경 감지 및 업데이트
                    if row["description_orig"] != row["description_new"]:
                        update_transaction_description(  # 새 메모로 업데이트
                            transaction_id, row["description_new"]
                        )

                st.toast("변경사항이 저장되었습니다.")  # 성공 토스트 메시지
                time.sleep(1)  # 잠시 대기하여 메시지 확인 시간 제공
                load_data()  # 데이터 다시 로드하여 그리드 새로고침
                # st.rerun()

        except Exception as e:
            st.error(
                f"데이터 업데이트 중 오류 발생: {e}"
            )  # 오류 발생 시 에러 메시지 출력
