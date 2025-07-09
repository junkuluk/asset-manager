import streamlit as st

def apply_common_styles():
    """모든 페이지에 공통적으로 적용될 CSS 스타일"""
    st.markdown("""
        <style>
            .block-container {
                padding-top: 2rem !important;
            }
        </style>
    """, unsafe_allow_html=True)


def authenticate_user():
    if 'password_correct' not in st.session_state:
        st.session_state.password_correct = False

    if not st.session_state.password_correct:
        with st.form("password_form"):
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Enter")
            if submitted:
                if password == st.secrets.get("password", ""):
                    st.session_state.password_correct = True
                    st.rerun()
                else:
                    st.error("The password you entered is incorrect.")
        return False
    else:
        return True