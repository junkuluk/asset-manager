import os

import streamlit as st

from core.db_manager import run_migrations
from core.seeder import (
    seed_initial_categories,
    seed_initial_parties,
    seed_initial_rules,
    seed_initial_accounts,
    seed_initial_transfer_rules,
)
from core.ui_utils import apply_common_styles, authenticate_user, logout_button

apply_common_styles()

if not authenticate_user():
    st.stop()

logout_button()

st.set_page_config(layout="wide", page_title="나의 자산 관리 대시보드", page_icon="💰")


try:
    run_migrations()
    seed_initial_accounts()
    seed_initial_parties()
    seed_initial_categories()
    seed_initial_rules()
    seed_initial_transfer_rules()
except Exception as e:
    st.error(f"초기 데이터 생성 중 오류 발생: {e}")
    st.stop()


st.title("💰 나의 자산 관리 대시보드")
st.markdown("---")
st.header("환영합니다! 👋")
st.markdown(
    """
이 대시보드는 뽀잉과 준꾸럭의 소비 및 투자 내역을 관리하고 분석하기 위해 만들어졌습니다.
왼쪽 사이드바 메뉴를 통해 기능을 사용해 보세요.

- **업로드**: 카드사 엑셀 파일을 업로드하여 거래 내역을 저장합니다.
- **통계 대시보드**: 지출 내역을 다양한 차트로 분석합니다.
- **거래내역 수정**: 카테고리 등 거래 내역을 직접 수정합니다.
"""
)

st.image(
    "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3bnU4ZGVmaXJvdnJqdHY5NDgxaW15NDBsYWc4eTJvazNoaDB1c3I2bCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/ZqlvCTNHpqrio/giphy.gif"
)
