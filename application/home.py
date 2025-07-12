import streamlit as st
import config
import time

# 애플리케이션의 핵심 기능을 담당하는 모듈들을 임포트
from core.db_manager import run_migrations  # 데이터베이스 스키마 마이그레이션 실행
from core.seeder import (  # 초기 데이터 삽입 함수들
    seed_initial_categories,
    seed_initial_parties,
    seed_initial_rules,
    seed_initial_accounts,
    seed_initial_transfer_rules,
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

print(f"APP_DIR:{config.APP_DIR}")
print(f"BASE_DIR:{config.BASE_DIR}")
print(f"STATIC_DIR:{config.STATIC_DIR}")
print(f"SCHEMA_PATH:{config.SCHEMA_PATH}")


# Streamlit 페이지 설정 (페이지 제목, 아이콘, 레이아웃 등)
st.set_page_config(layout="wide", page_title="나의 자산 관리 대시보드", page_icon="💰")

message_placeholder = st.empty()

with message_placeholder.container():
    try:
        # 데이터베이스 마이그레이션 실행 (스키마 최신화)
        run_migrations()
        # 초기 계좌 데이터 삽입 (존재하지 않을 경우)
        seed_initial_accounts()
        # 초기 거래처 데이터 삽입 (존재하지 않을 경우)
        seed_initial_parties()
        # 초기 카테고리 데이터 삽입 (존재하지 않을 경우)
        seed_initial_categories()
        # 초기 분류 규칙 데이터 삽입 (JSON 파일 기반)
        seed_initial_rules()
        # 초기 이체 규칙 데이터 삽입 (JSON 파일 기반)
        seed_initial_transfer_rules()
    except Exception as e:
        # 초기 데이터 생성 중 오류 발생 시 에러 메시지 출력 후 앱 실행 중단
        st.error(f"초기 데이터 생성 중 오류 발생: {e}")
        st.stop()

time.sleep(1)

message_placeholder.empty()

# 대시보드 메인 페이지 UI 구성
st.title("💰 나의 자산 관리 대시보드")  # 메인 제목
st.markdown("---")  # 구분선
st.header("환영합니다! 👋")  # 환영 메시지 헤더
st.markdown(  # 대시보드 소개 및 기능 안내
    """
이 대시보드는 뽀잉과 준꾸럭의 소비 및 투자 내역을 관리하고 분석하기 위해 만들어졌습니다.
왼쪽 사이드바 메뉴를 통해 기능을 사용해 보세요.

- **업로드**: 카드사 엑셀 파일을 업로드하여 거래 내역을 저장합니다.
- **통계 대시보드**: 지출 내역을 다양한 차트로 분석합니다.
- **거래내역 수정**: 카테고리 등 거래 내역을 직접 수정합니다.
"""
)

# 애니메이션 GIF 이미지 표시
st.image(
    "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3bnU4ZGVmaXJvdnJqdHY5NDgxaW15NDBsYWc4eTJvazNoaDB1c3I2bCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/ZqlvCTNHpqrio/giphy.gif"
)
