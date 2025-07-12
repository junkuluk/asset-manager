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


localS = LocalStorage()


def authenticate_user():

    username = localS.getItem("username")

    actual_username = username.get("value") if isinstance(username, dict) else username

    if not actual_username:
        with st.form("login_form"):
            st.write("### 로그인이 필요합니다.")
            username_input = st.text_input("Username")
            password_input = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")

            if submitted:
                if password_input == st.secrets.get("password", ""):

                    localS.setItem("username", username_input)
                    st.rerun()
                else:
                    st.error("사용자 이름 또는 비밀번호가 올바르지 않습니다.")

        st.stop()

    return actual_username


def logout_button():

    username = localS.getItem("username")
    actual_username = username.get("value") if isinstance(username, dict) else username

    if actual_username:
        st.sidebar.write(f"환영합니다, **{actual_username}** 님")
        if st.sidebar.button("Logout"):
            localS.deleteItem("username")
            st.rerun()
