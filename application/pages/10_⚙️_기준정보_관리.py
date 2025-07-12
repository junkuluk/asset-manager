import streamlit as st
import pandas as pd
from datetime import date
from st_aggrid import (
    AgGrid,
    JsCode,
)  # AG Grid 테이블 및 JavaScript 코드 실행 기능 임포트 (JsCode는 카테고리 트리에서 사용)

from core.db_manager import (  # 데이터베이스 관리 함수 임포트
    add_new_party,  # 새 거래처 추가
    add_new_category,  # 새 카테고리 추가
    rebuild_category_paths,  # 카테고리 경로 재구축
    add_new_account,  # 새 계좌 추가
    reclassify_all_transfers,  # 모든 이체 거래 재분류
    update_init_balance_and_log,  # 초기 잔액 업데이트 및 로그
)
from core.db_queries import (  # 데이터베이스 쿼리 함수 임포트
    get_all_parties_df,  # 모든 거래처 데이터프레임으로 조회
    get_all_categories,  # 모든 카테고리 조회 (딕셔너리 형태)
    get_all_categories_with_hierarchy,  # 계층 구조를 포함한 모든 카테고리 조회
    get_all_accounts,  # 모든 계좌 조회 (딕셔너리 형태)
    get_balance_history,  # 잔액 이력 조회
    get_all_accounts_df,  # 모든 계좌 데이터프레임으로 조회
    get_init_balance,  # 계좌 초기 잔액 조회
)
from core.ui_utils import (
    apply_common_styles,
    authenticate_user,
    logout_button,
)  # UI 및 인증 유틸리티

from analysis import (
    run_engine_and_update_db_final,
)  # 분류 규칙 엔진 전체 재적용 함수 임포트

# 모든 페이지에 공통 CSS 스타일 적용
apply_common_styles()

# 사용자 인증. 인증에 실패하면 앱 실행 중단.
if not authenticate_user():
    st.stop()

# 로그아웃 버튼 표시 (인증된 경우에만 보임)
logout_button()

# Streamlit 페이지 설정 (페이지 제목 및 레이아웃)
st.set_page_config(layout="wide", page_title="기준정보 관리")
st.title("⚙️ 기준정보 관리")  # 페이지 메인 제목
st.markdown("---")  # 구분선

# --- 거래처 관리 섹션 ---
st.subheader("🏢 거래처 관리")
col1, col2 = st.columns([1, 2])  # 거래처 추가 폼과 목록을 위한 컬럼 분할

with col1:
    with st.form(
        "new_party_form", clear_on_submit=True
    ):  # 새 거래처 추가 폼 (제출 후 필드 초기화)
        st.write("##### 새 거래처 추가")  # 폼 제목
        new_party_code = st.text_input(
            "거래처 코드 (예: STARBUCKS)"
        )  # 거래처 코드 입력
        new_party_desc = st.text_input("거래처 설명 (예: 스타벅스)")  # 거래처 설명 입력
        submitted = st.form_submit_button("거래처 추가")  # 제출 버튼
        if submitted:
            if (
                new_party_code and new_party_desc
            ):  # 코드와 설명이 모두 입력되었는지 확인
                # 새 거래처 추가 함수 호출
                success, message = add_new_party(new_party_code.upper(), new_party_desc)
                if success:
                    st.success(message)  # 성공 메시지
                else:
                    st.error(message)  # 실패 메시지
            else:
                st.warning("코드와 설명을 모두 입력해주세요.")  # 입력 누락 경고

with col2:
    st.write("##### 현재 거래처 목록")  # 현재 거래처 목록 제목
    # 모든 거래처 정보를 데이터프레임으로 가져와 표시
    st.dataframe(get_all_parties_df(), use_container_width=True)

st.markdown("---")  # 구분선

# --- 카테고리 관리 섹션 ---
st.subheader("🗂️ 카테고리 관리")

# 생성할 카테고리의 타입을 선택하는 드롭다운
st.selectbox(
    "1. 생성할 카테고리의 타입을 먼저 선택하세요:",
    options=["EXPENSE", "INCOME", "INVEST"],  # 선택 가능한 카테고리 타입
    key="selected_category_type",  # 세션 상태 키
)

# 선택된 카테고리 타입에 따라 부모 카테고리 옵션 로드
selected_type = st.session_state.get("selected_category_type", "EXPENSE")
parent_category_options = get_all_categories(
    category_type=selected_type,
    include_top_level=True,  # 선택된 타입의 모든 카테고리 (최상위 포함)
)
parent_desc_to_id = {
    v: k for k, v in parent_category_options.items()
}  # 설명 -> ID 매핑 딕셔너리

col3, col4 = st.columns([1, 2])  # 새 카테고리 폼과 계층 구조 목록을 위한 컬럼 분할

with col3:
    st.write("##### 새 카테고리 정보 입력")  # 폼 제목
    with st.form(
        "new_category_form", clear_on_submit=True
    ):  # 새 카테고리 추가 폼 (제출 후 필드 초기화)
        # 상위 카테고리 선택 드롭다운
        parent_cat_desc = st.selectbox(
            "2. 상위 카테고리를 선택하세요:",
            options=list(
                parent_category_options.values()
            ),  # 선택 가능한 상위 카테고리 설명 목록
        )
        new_cat_code = st.text_input(
            "3. 카테고리 코드 (영문 대문자)"
        )  # 새 카테고리 코드 입력
        new_cat_desc = st.text_input("4. 카테고리 설명")  # 새 카테고리 설명 입력

        submitted_cat = st.form_submit_button("카테고리 추가")  # 제출 버튼
        if submitted_cat:
            parent_cat_id = parent_desc_to_id.get(
                parent_cat_desc
            )  # 선택된 상위 카테고리 설명으로 ID 조회
            final_cat_type = (
                st.session_state.selected_category_type
            )  # 세션 상태에서 최종 카테고리 타입 가져옴

            assert parent_cat_id is not None  # 상위 카테고리 ID가 None이 아닌지 확인
            if all(
                [parent_cat_id, new_cat_code, new_cat_desc, final_cat_type]
            ):  # 모든 항목이 입력되었는지 확인
                # 새 카테고리 추가 함수 호출
                success, message = add_new_category(
                    parent_cat_id, new_cat_code.upper(), new_cat_desc, final_cat_type
                )
                if success:
                    st.success(message)  # 성공 메시지
                else:
                    st.error(message)  # 실패 메시지
            else:
                st.warning("모든 항목을 입력해주세요.")  # 입력 누락 경고

with col4:
    st.write("##### 현재 카테고리 계층 구조")  # 카테고리 계층 구조 제목

    category_tree_df = (
        get_all_categories_with_hierarchy()
    )  # 계층 구조를 포함한 모든 카테고리 데이터 로드

    if not category_tree_df.empty:
        # AG Grid에 표시할 컬럼 선택 및 복사본 생성
        grid_df = category_tree_df[
            ["id", "category_code", "category_type", "name_path"]
        ].copy()

        # AG Grid의 트리 데이터 설정을 위한 옵션
        gridOptions = {
            "columnDefs": [
                {
                    "field": "name_path",
                    "hide": True,
                },  # 'name_path' 컬럼은 숨기고 트리 구조를 위해 사용
                {"field": "id", "headerName": "ID", "width": 80},
                {"field": "category_code", "headerName": "코드", "width": 150},
                {"field": "category_type", "headerName": "타입", "width": 120},
            ],
            "treeData": True,  # 트리 데이터 모드 활성화
            "animateRows": True,  # 행 애니메이션 활성화
            "groupDefaultExpanded": -1,  # 모든 그룹을 기본적으로 확장
            "getDataPath": JsCode(  # 데이터 경로를 가져오는 JavaScript 함수 (name_path를 '/'로 분할)
                "function(data) { return data.name_path.split('/'); }"
            ),
            "autoGroupColumnDef": {  # 자동 그룹 컬럼 정의 (트리 구조의 메인 컬럼)
                "headerName": "카테고리 계층",
                "minWidth": 400,
                "cellRendererParams": {
                    "suppressCount": True,  # 그룹 옆에 항목 수 표시 억제
                },
            },
        }

        # AG Grid 테이블 표시
        AgGrid(
            grid_df,
            gridOptions=gridOptions,
            height=600,
            width="100%",
            theme="streamlit",  # Streamlit 테마
            enable_enterprise_modules=True,  # 트리 데이터 등 엔터프라이즈 기능 활성화
            allow_unsafe_jscode=True,  # JavaScript 코드 실행 허용
            key="category_tree_final_v3",  # 세션 상태 키
        )

st.markdown("---")  # 구분선

# --- 계좌 초기 잔액 수동 조정 섹션 ---
st.subheader("💰 계좌 초기 잔액 수동 조정")
st.write("초기 잔액 설정, 추적하지 않은 현금 사용 등 잔액을 직접 맞출 때 사용합니다.")

accounts_map = get_all_accounts()  # 모든 계좌 정보 (이름:ID 딕셔너리) 로드
account_names = list(accounts_map.keys())  # 계좌 이름 목록

if account_names:  # 등록된 계좌가 있는 경우에만 표시
    col1, col2 = st.columns(2)  # 계좌 선택 폼과 조정 이력 목록을 위한 컬럼 분할
    with col1:
        selected_account_name = st.selectbox(  # 조정할 계좌 선택 드롭다운
            "조정할 계좌 선택",
            options=account_names,
            key="selected_account_for_adj",  # 세션 상태 키
        )
        with st.form("adjustment_form"):  # 잔액 조정 폼
            adjustment_amount = st.number_input(
                "설정 금액", step=1000, value=0
            )  # 조정 금액 입력

            submitted = st.form_submit_button("잔액 조정 실행")  # 제출 버튼
            if submitted:
                account_id = accounts_map[
                    selected_account_name
                ]  # 선택된 계좌 이름으로 ID 조회
                conn = st.connection(
                    "supabase", type="sql"
                )  # Supabase 연결 (여기서는 불필요할 수 있음, 함수 내에서 처리)
                try:
                    # 초기 잔액 업데이트 함수 호출
                    update_init_balance_and_log(account_id, adjustment_amount)
                    st.success(
                        f"'{selected_account_name}' 계좌의 잔액 조정이 완료되었습니다."
                    )  # 성공 메시지
                except Exception as e:
                    st.error(f"오류 발생: {e}")  # 오류 메시지

                st.rerun()  # 앱 재실행하여 변경사항 반영

    with col2:
        st.write("##### 거래 내역 조정 이력")  # 조정 이력 제목
        # 선택된 계좌의 ID 가져옴
        selected_id = accounts_map[st.session_state.selected_account_for_adj]

        # 계좌의 잔액 및 초기 잔액 상세 정보 조회
        result = get_init_balance(selected_id)

        if result is not None:
            balance, init_balance = result
            st.write(  # 현재 잔액 정보 출력
                f"**선택된 계좌의 초기/거래 금액:** `{int(init_balance):,}`/`{int(balance):,}` **선택된 계좌의 현 잔액:** `{int(balance) + int(init_balance):,}`"
            )
            history_df = get_balance_history(selected_id)  # 잔액 변경 이력 로드
            st.dataframe(history_df, use_container_width=True)  # 이력 데이터프레임 표시
        else:
            st.error(
                f"계좌(ID: {selected_id})에 대한 잔액 정보를 가져올 수 없습니다."
            )  # 정보 없음 오류
else:
    st.warning("먼저 계좌를 등록해주세요.")  # 등록된 계좌가 없을 때 경고

st.subheader("🏦 계좌 관리")
col1, col2 = st.columns([1, 2])  # 새 계좌 추가 폼과 계좌 목록을 위한 컬럼 분할

with col1:
    with st.form(
        "new_account_form", clear_on_submit=True
    ):  # 새 계좌 추가 폼 (제출 후 필드 초기화)
        st.write("##### 새 계좌 추가")  # 폼 제목
        acc_name = st.text_input(
            "계좌 이름 (예: 카카오뱅크, 미래에셋증권)"
        )  # 계좌 이름 입력
        acc_type = st.selectbox(  # 계좌 타입 선택
            "계좌 타입",
            [
                "BANK_ACCOUNT",
                "CREDIT_CARD",
                "CASH",
                "STOCK_ASSET",
                "FUND",
                "REAL_ESTATE",
            ],
        )
        is_asset = st.radio(  # 자산/부채 구분 라디오 버튼
            "자산/부채 구분",
            [True, False],
            format_func=lambda x: "자산" if x else "부채",  # 표시 형식
        )
        is_invest = st.radio(  # 투자/비투자 구분 라디오 버튼
            "투자 구분", [True, False], format_func=lambda x: "투자" if x else "비투자"
        )
        initial_balance = st.number_input(
            "초기 잔액 (없으면 0)", value=0, step=10000
        )  # 초기 잔액 입력

        submitted = st.form_submit_button("계좌 추가")  # 제출 버튼
        if submitted and acc_name:  # 제출되었고 계좌 이름이 있는 경우
            # 새 계좌 추가 함수 호출
            success, message = add_new_account(
                acc_name, acc_type, is_asset, initial_balance
            )
            if success:
                st.success(message)  # 성공 메시지
            else:
                st.error(message)  # 실패 메시지

with col2:
    st.write("##### 현재 계좌 목록")  # 현재 계좌 목록 제목
    st.dataframe(
        get_all_accounts_df(), use_container_width=True
    )  # 모든 계좌 정보 데이터프레임으로 표시

st.markdown("---")  # 구분선
# --- 데이터 보정 도구 섹션 ---
st.subheader("🧰 데이터 보정 도구")

# 경고 메시지 (접을 수 있는 Expander 안에)
with st.expander(
    "주의: 이 기능은 데이터 구조를 직접 수정합니다. 필요할 때만 사용하세요."
):
    st.warning("주의: 이 기능은 데이터 구조를 직접 수정합니다. 필요할 때만 사용하세요.")

    # 모든 카테고리 경로 재계산 버튼
    if st.button("모든 카테고리 경로 재계산 실행"):
        with st.spinner("경로를 재계산하는 중입니다..."):
            updated_count, message = (
                rebuild_category_paths()
            )  # 카테고리 경로 재구축 함수 호출
        st.success(
            f"작업 완료: {message} ({updated_count}개 행 업데이트)"
        )  # 결과 메시지

st.markdown("---")  # 구분선
# --- 데이터 일괄 처리 도구 섹션 ---
st.subheader("⚙️ 데이터 일괄 처리 도구")

# 전체 재적용 규칙 엔진 관련 설명 (접을 수 있는 Expander 안에)
with st.expander("규칙 엔진 전체 재적용"):
    st.info(
        "이 기능은 전체 거래 내역을 대상으로 규칙을 다시 실행합니다. 시간이 다소 걸릴 수 있습니다."
    )

    # 은행 거래 '이체' 규칙 재적용 버튼
    if st.button("은행 거래 '이체' 규칙 재적용"):
        with st.spinner("모든 은행 지출 내역을 확인 중입니다..."):
            message = reclassify_all_transfers()  # 모든 이체 거래 재분류 함수 호출
            st.success(message)  # 결과 메시지

    # '미분류' 거래 카테고리 재적용 버튼
    if st.button("'미분류' 거래 카테고리 재적용"):
        with st.spinner("미분류 거래에 대해 카테고리 규칙을 실행 중입니다..."):
            message = (
                run_engine_and_update_db_final()
            )  # 미분류 거래에 규칙 엔진 재적용 함수 호출
            st.success(message)  # 결과 메시지
