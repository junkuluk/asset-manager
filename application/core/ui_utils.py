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