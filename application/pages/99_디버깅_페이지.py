# pages/99_디버깅_페이지.py

import streamlit as st

st.set_page_config(page_title="Session State Debugger")

st.title("🐞 Session State 디버거")
st.markdown("---")
st.header("현재 `st.session_state`에 있는 모든 키 목록입니다.")

# st.session_state의 모든 키를 보기 좋게 출력합니다.
if st.session_state:
    st.json(st.session_state.to_dict())
else:
    st.warning("`st.session_state`가 비어있습니다.")
