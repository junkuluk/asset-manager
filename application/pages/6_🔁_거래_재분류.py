import calendar
import time
from datetime import date

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder  # AG Grid 테이블 및 옵션 빌더 임포트

from core.db_manager import (  # 데이터베이스 관리 함수 임포트
    reclassify_expense,  # 지출 거래를 이체/투자로 재분류하는 함수
)
from core.db_queries import (  # 데이터베이스 쿼리 함수 임포트
    get_bank_expense_transactions,  # 은행 지출 거래 조회
    get_all_accounts,  # 모든 계좌 정보 조회
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
st.set_page_config(layout="wide", page_title="거래 재분류")

# 세션 상태에 저장된 다이얼로그 메시지가 있으면 토스트 메시지로 표시 후 삭제
if "dialog_message" in st.session_state and st.session_state.dialog_message:
    st.toast(st.session_state.dialog_message)
    del st.session_state.dialog_message

if "reclassify_initialized" not in st.session_state:
    today = date.today()
    # 데이터 로직용 상태
    st.session_state.reclassify_start_date = today.replace(day=1)
    st.session_state.reclassify_end_date = today

    # 위젯 표시용 상태 (데이터 상태와 동일하게 초기화)
    st.session_state.widget_reclassify_start_date = (
        st.session_state.reclassify_start_date
    )
    st.session_state.widget_reclassify_end_date = st.session_state.reclassify_end_date

    # 초기화 플래그 설정
    st.session_state.reclassify_initialized = True


def sync_reclassify_dates():
    """위젯의 날짜 값을 데이터 로직용 날짜 상태로 복사합니다."""
    st.session_state.reclassify_start_date = (
        st.session_state.widget_reclassify_start_date
    )
    st.session_state.reclassify_end_date = st.session_state.widget_reclassify_end_date


st.title("🔁 거래 성격 변경 (지출 → 이체/투자)")  # 페이지 메인 제목
st.markdown(  # 페이지 설명
    "은행 출금 내역 중 '지출'로 잘못 분류된 항목을 카드값 납부나 투자 이체 등으로 변경합니다."
)
st.markdown("---")  # 구분선


# 날짜 선택 위젯 설정
today = date.today()  # 오늘 날짜
default_start_date = today.replace(day=1)  # 기본 조회 시작일: 현재 월의 1일
col1, col2 = st.columns(2)
with col1:
    st.date_input(
        "조회 시작일",
        value=st.session_state.reclassify_start_date,  # 표시될 값 (데이터 상태)
        key="widget_reclassify_start_date",  # 위젯 고유 키
        on_change=sync_reclassify_dates,  # 콜백 함수
    )
with col2:
    st.date_input(
        "조회 종료일",
        value=st.session_state.reclassify_end_date,
        key="widget_reclassify_end_date",
        on_change=sync_reclassify_dates,
    )


st.markdown("---")  # 구분선

# 선택된 기간의 은행 지출 거래 내역 로드
candidate_df = get_bank_expense_transactions(
    str(st.session_state.reclassify_start_date),
    str(st.session_state.reclassify_end_date),
)


exclude_keywords = ["신한체", "체크카드", "CMS지급", "CM보험", "FB보험", "CMS지"]
with st.expander("ℹ️ 자동 필더링 항목 보기"):
    st.markdown(
        """        
        - 미분류 항목이 아닌 건들이 필터링 대상입니다.
        - **신한체**:  은행계좌에서 빠져나간 체크카드 항목은 이체로 변경하지 않도록 자동 필터링됩니다.
        - **체크카드**:  은행계좌에서 빠져나간 체크카드 항목은 이체로 변경하지 않도록 자동 필터링됩니다.    
        - **CMS지급**:  은행계좌에서 빠져나간 "CMS지급" 내용은 보험 지출임으로 이체로 변경하지 않도록 자동 필터링됩니다.
        - **CMS지**:  은행계좌에서 빠져나간 "CMS지" 내용은 보험 지출임으로 이체로 변경하지 않도록 자동 필터링됩니다.
        - **CM보험**:  은행계좌에서 빠져나간 "CMS지급" 내용은 보험 지출임으로 이체로 변경하지 않도록 자동 필터링됩니다.
        - **FB보험**:  은행계좌에서 빠져나간 "FB보험" 내용은 보험 지출임으로 이체로 변경하지 않도록 자동 필터링됩니다.
        """
    )

condition_to_exclude = candidate_df["summary_content"].str.contains(
    "|".join(exclude_keywords), na=False
)

# 3. '~' 연산자로 조건을 뒤집어 원하는 행만 필터링
filtered_df = candidate_df[~condition_to_exclude]

# 조회된 거래 내역이 비어있지 않은 경우 AG Grid 표시
if not filtered_df.empty:
    # AG Grid 컬럼 정의 및 옵션 설정
    gridOptions = {
        "columnDefs": [
            {
                "field": "transaction_date",  # 거래일시 컬럼
                "headerName": "거래일시",
                "width": 180,
                "checkboxSelection": True,  # 체크박스 선택 활성화
                "headerCheckboxSelection": False,  # 헤더 체크박스 비활성화
            },
            {"field": "content", "headerName": "내용", "width": 300},  # 내용 컬럼
            {"field": "transaction_type", "headerName": "타입", "width": 100},
            {"field": "summary_content", "headerName": "적요", "width": 100},
            {
                "field": "transaction_amount",  # 금액 컬럼
                "headerName": "금액",
                "type": "numericColumn",  # 숫자 컬럼 타입
                "valueFormatter": "x.toLocaleString()",  # 금액을 현지 통화 형식으로 포맷
            },
            {"field": "id", "hide": True},  # ID 컬럼은 숨김
        ],
        "defaultColDef": {
            "sortable": True,
            "filter": True,
        },  # 기본 컬럼 설정: 정렬, 필터링 가능
        "rowSelection": "single",  # 단일 행 선택만 허용
        "pagination": True,  # 페이지네이션 활성화
        "paginationPageSize": 10,  # 페이지당 10개 행 표시
    }

    st.write("##### 1. 이체로 변경할 거래 선택")  # 안내 메시지
    st.write(
        "###### 신한체크카드 사용내역은 자동 필터링하였으나, 혹시 모르니 변경시 주의바람"
    )  # 안내 메시지
    # AG Grid 테이블 표시 및 사용자 상호작용에 따른 응답 받기
    candidate_grid_response = AgGrid(
        filtered_df,  # 표시할 데이터프레임
        gridOptions=gridOptions,  # 그리드 옵션 적용
        height=300,  # 그리드 높이
        width="100%",  # 그리드 너비
        theme="alpine",  # AG Grid 테마
        key="candidate_grid_final",  # Streamlit 세션 상태를 위한 고유 키
    )
    # ----------------------------

    selected_candidate = candidate_grid_response[
        "selected_rows"
    ]  # AG Grid에서 선택된 행 가져오기

    # 선택된 행이 존재하는 경우 재분류 폼 표시
    if selected_candidate is not None and not selected_candidate.empty:
        selected_row_data = selected_candidate.iloc[0]  # 선택된 첫 번째 행의 데이터

        st.write("##### 2. 이체 대상 계좌 선택 및 실행")  # 안내 메시지
        st.write("###### 중요 체크카드 결재는 이체대상이 아닙니다.!!!")  # 안내 메시지
        col_form, col_info = st.columns(2)  # 폼과 정보 표시를 위한 두 개의 컬럼
        with col_form:
            with st.form("reclassify_form"):  # 재분류 폼 생성
                all_accounts_map = (
                    get_all_accounts()
                )  # 모든 계좌 정보 (이름:ID 딕셔너리) 로드

                source_bank_account_name = (
                    "신한은행-110-227-963599"  # 현재 은행 계좌 이름 (하드코딩)
                )
                # 이체 대상 계좌 목록에서 현재 은행 계좌 제외 (자기 자신에게 이체할 수 없으므로)
                if source_bank_account_name in all_accounts_map:
                    del all_accounts_map[source_bank_account_name]

                # 이체/투자될 계좌를 선택하는 드롭다운 메뉴
                linked_account_name = st.selectbox(
                    "이 돈이 어디로 이체/투자되었나요?",
                    options=list(all_accounts_map.keys()),  # 계좌 이름 목록 표시
                )

                # '거래 성격 변경하기' 버튼
                submitted = st.form_submit_button(
                    "거래 성격 변경하기",
                    use_container_width=True,
                    type="primary",  # 버튼 너비 최대, 강조 스타일
                )
                if submitted:
                    transaction_id = int(selected_row_data["id"])  # 선택된 거래의 ID
                    linked_account_id = int(
                        all_accounts_map[linked_account_name]
                    )  # 선택된 계좌 이름으로 ID 조회

                    # reclassify_expense 함수 호출하여 거래 재분류 및 결과 메시지 받기
                    success, message = reclassify_expense(
                        transaction_id, linked_account_id
                    )

                    # 재분류 성공/실패에 따라 토스트 메시지 설정
                    if success:
                        st.session_state.dialog_message = f"✅ {message}"
                    else:
                        st.session_state.dialog_message = f"❌ {message}"
                    st.rerun()  # 앱 재실행하여 변경사항 반영 및 메시지 표시

        with col_info:
            # 선택된 거래 정보 요약 표시
            st.info(
                f"""
            **선택된 거래 정보:**
            - **내용:** {selected_row_data['content']}
            - **금액:** {selected_row_data['transaction_amount']:,}원
            """
            )
    else:
        st.info("변경할 거래를 위 표에서 선택해주세요.")  # 거래 선택을 기다리는 메시지
else:
    st.info(
        "선택된 기간에 이체로 변경할 '은행 지출' 내역이 없습니다."
    )  # 조회된 거래가 없는 경우 메시지
