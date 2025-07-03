import streamlit as st
import pandas as pd
from core.database import load_data_from_db, update_transaction_category, get_all_categories
from analysis import run_engine_and_update_db

DB_PATH = 'asset_data.db'

st.set_page_config(layout="wide", page_title="거래내역 수정")
st.title("📝 거래 내역 조회 및 수정")

st.markdown("---")
# --- 기능 버튼 추가 ---
st.subheader("⚙️ 데이터 관리")
if st.button("모든 거래내역 규칙에 따라 재분류하기"):
    with st.spinner("규칙 엔진을 실행하여 전체 데이터를 다시 분류하고 있습니다..."):
        updated_count = run_engine_and_update_db()
    st.success(f"작업 완료! 총 {updated_count}건의 데이터가 업데이트되었습니다.")




st.markdown("---")

display_df = load_data_from_db()

if display_df.empty:
    st.warning("수정할 데이터가 없습니다. 먼저 데이터를 업로드해주세요.")
else:
    category_options = get_all_categories(db_path=DB_PATH)
    options_list = list(category_options.keys())

    st.dataframe(display_df)  # 전체 데이터프레임을 먼저 보여줌

    st.markdown("---")
    st.subheader("개별 거래 카테고리 수정")

    # 수정할 ID를 직접 입력받는 방식
    target_id = st.number_input("수정할 거래 ID를 입력하세요", min_value=1, step=1)

    # 입력된 ID에 해당하는 거래를 찾음
    target_transaction = display_df[display_df['id'] == target_id]

    if not target_transaction.empty:
        current_category_id = target_transaction.iloc[0]['category_id']
        current_index = options_list.index(current_category_id) if current_category_id in options_list else 0

        new_category_id = st.selectbox(
            f"ID {target_id}의 새 카테고리 선택:",
            options=options_list,
            format_func=lambda x: category_options.get(x, '알 수 없음'),
            index=current_index
        )

        if st.button("카테고리 저장"):
            update_transaction_category(target_id, new_category_id, db_path=DB_PATH)
            st.success(f"ID {target_id}의 카테고리가 '{category_options.get(new_category_id)}'(으)로 변경되었습니다.")
            st.experimental_rerun()
    else:
        st.error("해당 ID의 거래를 찾을 수 없습니다.")