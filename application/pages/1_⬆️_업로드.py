import streamlit as st

import config
from core.data_processor import (
    insert_card_transactions_from_excel,
    insert_bank_transactions_from_excel,
)
from core.ui_utils import apply_common_styles, authenticate_user, logout_button

apply_common_styles()

if not authenticate_user():
    st.stop()

logout_button()

st.set_page_config(layout="wide", page_title="📈 신규 거래내역 업로드")

st.subheader("💳 카드 거래내역 업로드")

uploaded_files = st.file_uploader(
    "신한, 국민카드 엑셀 파일을 업로드하세요",
    type=["xlsx", "xls"],
    accept_multiple_files=True,
)

if uploaded_files:
    total_inserted = 0
    total_skipped = 0
    with st.spinner("파일을 처리하고 있습니다..."):
        for file in uploaded_files:
            inserted_count, skipped_count = insert_card_transactions_from_excel(file)
            total_inserted += inserted_count
            total_skipped += skipped_count
    if total_inserted > 0 or total_skipped > 0:
        st.success(f"총 {total_inserted}개의 신규 거래 내역을 성공적으로 저장했습니다!")
        st.success(f"총 {total_skipped}개의 신규 거래 내역을 스킵하였습니다.!")

st.markdown("---")

st.subheader("🏦 은행 입출금내역 업로드")
uploaded_bank_files = st.file_uploader(
    "은행 엑셀 파일을 업로드하세요 (신한)",
    type=["xlsx", "xls"],
    accept_multiple_files=True,
    key="bank_uploader",
)
if uploaded_bank_files:
    total_inserted = 0
    total_skipped = 0
    with st.spinner("은행 파일을 처리하고 있습니다..."):
        for file in uploaded_bank_files:
            inserted_count, skipped_count = insert_bank_transactions_from_excel(file)
            total_inserted += inserted_count
            total_skipped += skipped_count
    if total_inserted > 0 or total_skipped > 0:
        st.success(
            f"총 {total_inserted}개의 신규 은행 거래 내역을 성공적으로 저장했습니다!"
        )
        st.success(f"총 {total_skipped}개의 신규 거래 내역을 스킵하였습니다.!")
