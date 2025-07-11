import streamlit as st
import datetime
from streamlit_local_storage import LocalStorage


def apply_common_styles():
    """모든 페이지에 공통적으로 적용될 CSS 스타일"""
    st.markdown(
        """
        <style>
            .block-container {
                padding-top: 2rem !important;
            }
        </style>
    """,
        unsafe_allow_html=True,
    )


# 모듈 수준에서 LocalStorage 인스턴스를 한 번만 생성합니다.
localS = LocalStorage()


def authenticate_user():
    # LocalStorage에서 'username' 값을 가져옵니다.
    username = localS.getItem("username")

    # get_item의 반환값은 {'value': '실제값'} 형태의 딕셔너리일 수 있으므로,
    # 실제 값을 안전하게 추출합니다.
    actual_username = username.get("value") if isinstance(username, dict) else username

    if not actual_username:
        with st.form("login_form"):
            st.write("### 로그인이 필요합니다.")
            username_input = st.text_input("Username")
            password_input = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")

            if submitted:
                if password_input == st.secrets.get("password", ""):
                    # 로그인 성공 시 LocalStorage에 사용자 이름을 저장합니다.
                    localS.setItem("username", username_input)
                    st.rerun()
                else:
                    st.error("사용자 이름 또는 비밀번호가 올바르지 않습니다.")

        st.stop()

    return actual_username


def logout_button():
    """
    사이드바에 로그아웃 버튼을 표시하고, 클릭 시 LocalStorage에서 사용자 정보를 삭제합니다.
    """
    username = localS.getItem("username")
    actual_username = username.get("value") if isinstance(username, dict) else username

    if actual_username:
        st.sidebar.write(f"환영합니다, **{actual_username}** 님")
        if st.sidebar.button("Logout"):
            localS.deleteItem("username")
            st.rerun()
