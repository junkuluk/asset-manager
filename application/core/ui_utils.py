import streamlit as st
import datetime
import bcrypt
from streamlit_local_storage import LocalStorage


def apply_common_styles():
    """
    모든 Streamlit 페이지에 공통 CSS 스타일을 적용.
    `block-container` 클래스의 상단 패딩을 조정하여 콘텐츠가 페이지 상단에 더 가깝게 위치하도록 함.
    """
    st.markdown(
        """
        <style>
            .block-container {
                padding-top: 2rem !important; /* 상단 패딩을 2rem으로 설정, !important로 우선순위 높임 */
            }
        </style>
    """,
        unsafe_allow_html=True,  # HTML 사용을 허용하여 스타일 적용
    )


def authenticate_user():

    localS = (
        LocalStorage()
    )  # Streamlit 애플리케이션에서 로컬 스토리지에 접근하기 위한 객체 생성

    username = localS.getItem("username")
    actual_username = username.get("value") if isinstance(username, dict) else username

    if not actual_username:
        with st.form("login_form"):
            st.write("### 로그인이 필요합니다.")
            username_input = st.text_input("Username")
            password_input = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")

            if submitted:
                # secrets.toml에서 저장된 해시된 비밀번호 가져오기
                stored_password_hash = st.secrets.get("password_hash", "")

                # 입력된 비밀번호를 바이트 문자열로 인코딩
                password_bytes = password_input.encode("utf-8")
                # 저장된 해시 값도 바이트 문자열로 인코딩
                stored_hash_bytes = stored_password_hash.encode("utf-8")

                # bcrypt.checkpw()를 사용하여 비밀번호 검증
                # 이 함수는 입력된 비밀번호의 해시와 저장된 해시를 안전하게 비교합니다.
                if bcrypt.checkpw(password_bytes, stored_hash_bytes):
                    localS.setItem("username", username_input)
                    st.rerun()
                else:
                    st.error("사용자 이름 또는 비밀번호가 올바르지 않습니다.")

        st.stop()

    return actual_username


def logout_button():
    """
    로그아웃 버튼을 사이드바에 표시하고, 클릭 시 사용자 세션 종료.
    로컬 스토리지에서 사용자 이름 정보를 삭제하고 앱을 재실행.
    """

    localS = (
        LocalStorage()
    )  # Streamlit 애플리케이션에서 로컬 스토리지에 접근하기 위한 객체 생성

    # 로컬 스토리지에서 현재 로그인된 사용자 이름 가져오기
    username = localS.getItem("username")
    actual_username = username.get("value") if isinstance(username, dict) else username

    # 사용자 이름이 로컬 스토리지에 존재하는 경우 (로그인된 상태)
    if actual_username:
        st.sidebar.write(
            f"환영합니다, **{actual_username}** 님"
        )  # 사이드바에 환영 메시지 표시
        if st.sidebar.button("Logout"):  # 사이드바에 로그아웃 버튼 표시
            localS.deleteItem("username")  # 로컬 스토리지에서 사용자 이름 삭제
            st.rerun()  # 앱을 다시 실행하여 로그아웃 상태 반영
