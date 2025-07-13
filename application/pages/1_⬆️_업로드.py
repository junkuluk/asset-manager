import streamlit as st

from core.data_processor import (  # 데이터 처리 및 DB 삽입 함수들을 임포트
    insert_card_transactions_from_excel,  # 카드 엑셀 파일 처리 함수
    insert_bank_transactions_from_excel,  # 은행 엑셀 파일 처리 함수
)
from core import ui_utils

# 모든 페이지에 공통 CSS 스타일 적용
ui_utils.apply_common_styles()

# 사용자 인증. 인증에 실패하면 앱 실행 중단.
if not ui_utils.authenticate_user():
    st.stop()

# 로그아웃 버튼 표시 (인증된 경우에만 보임)
ui_utils.logout_button()

# Streamlit 페이지 설정 (페이지 제목)
st.set_page_config(layout="wide", page_title="📈 신규 거래내역 업로드")

# 카드 거래내역 업로드 섹션 시작
st.subheader("💳 카드 거래내역 업로드")

# 카드 엑셀 파일 업로더 위젯
# - "신한, 국민카드 엑셀 파일을 업로드하세요"라는 메시지 표시
# - 허용되는 파일 타입: xlsx, xls
# - 여러 파일 동시 업로드 허용
uploaded_files = st.file_uploader(
    "신한, 국민카드 엑셀 파일을 업로드하세요",
    type=["xlsx", "xls"],
    accept_multiple_files=True,
)

# 파일이 업로드된 경우 처리 로직
if uploaded_files:
    total_inserted = 0  # 총 삽입된 거래 수 초기화
    total_skipped = 0  # 총 건너뛴 거래 수 초기화
    # 파일 처리 중 스피너 표시
    with st.spinner("파일을 처리하고 있습니다..."):
        # 업로드된 각 파일에 대해 반복 처리
        for file in uploaded_files:
            # 카드 거래내역 삽입 함수 호출 및 결과 저장
            inserted_count, skipped_count = insert_card_transactions_from_excel(file)
            total_inserted += inserted_count  # 삽입된 수 누적
            total_skipped += skipped_count  # 건너뛴 수 누적
    # 처리 결과 메시지 표시
    if total_inserted > 0 or total_skipped > 0:
        st.success(f"총 {total_inserted}개의 신규 거래 내역을 성공적으로 저장했습니다!")
        st.success(f"총 {total_skipped}개의 신규 거래 내역을 스킵하였습니다.!")

st.markdown("---")  # 구분선

# 은행 입출금내역 업로드 섹션 시작
st.subheader("🏦 은행 입출금내역 업로드")
# 은행 엑셀 파일 업로더 위젯
# - "은행 엑셀 파일을 업로드하세요 (신한)"라는 메시지 표시
# - 허용되는 파일 타입: xlsx, xls
# - 여러 파일 동시 업로드 허용
# - key="bank_uploader"를 사용하여 위젯 고유 식별 (동일 페이지에 여러 file_uploader 사용 시 필요)
uploaded_bank_files = st.file_uploader(
    "은행 엑셀 파일을 업로드하세요 (신한)",
    type=["xlsx", "xls"],
    accept_multiple_files=True,
    key="bank_uploader",
)
# 은행 파일이 업로드된 경우 처리 로직
if uploaded_bank_files:
    total_inserted = 0  # 총 삽입된 거래 수 초기화
    total_skipped = 0  # 총 건너뛴 거래 수 초기화
    # 파일 처리 중 스피너 표시
    with st.spinner("은행 파일을 처리하고 있습니다..."):
        # 업로드된 각 파일에 대해 반복 처리
        for file in uploaded_bank_files:
            # 은행 거래내역 삽입 함수 호출 및 결과 저장
            inserted_count, skipped_count = insert_bank_transactions_from_excel(file)
            total_inserted += inserted_count  # 삽입된 수 누적
            total_skipped += skipped_count  # 건너뛴 수 누적
    # 처리 결과 메시지 표시
    if total_inserted > 0 or total_skipped > 0:
        st.success(
            f"총 {total_inserted}개의 신규 은행 거래 내역을 성공적으로 저장했습니다!"
        )
        st.success(f"총 {total_skipped}개의 신규 거래 내역을 스킵하였습니다.!")
