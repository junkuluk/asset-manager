import os
import streamlit as st
from core.database import init_database
from core.seeder import seed_initial_categories, seed_initial_parties, seed_initial_rules
from core.data_processor import insert_card_transactions_from_excel
DB_PATH = 'asset_data.db'
SCHEMA_PATH = 'schema.sql'
RULES_PATH = 'initial_rules.json'

st.set_page_config(layout="wide", page_title="자산 관리 대시보드")


if not os.path.exists(DB_PATH):
    st.info("최초 실행입니다. 데이터베이스를 초기화합니다...")
    try:
        init_database(db_path=DB_PATH, schema_path=SCHEMA_PATH)
        st.success("데이터베이스 초기화 완료!")
    except Exception as e:
        st.error(f"데이터베이스 초기화 중 오류 발생: {e}")
        st.stop()


try:
    seed_initial_parties(db_path=DB_PATH)
    seed_initial_categories(db_path=DB_PATH)
    seed_initial_rules(db_path=DB_PATH, rules_path=RULES_PATH)
except Exception as e:
    st.error(f"초기 데이터 생성 중 오류 발생: {e}")
    st.stop()


st.title("📈 신규 거래내역 업로드")
st.markdown("---")

uploaded_files = st.file_uploader(
    "신한, 국민카드 엑셀 파일을 업로드하세요",
    type=["xlsx", "xls"],
    accept_multiple_files=True
)

if uploaded_files:
    total_inserted = 0
    total_skipped = 0
    with st.spinner('파일을 처리하고 있습니다...'):
        for file in uploaded_files:
            inserted_count, skipped_count = insert_card_transactions_from_excel(file, db_path=DB_PATH)
            total_inserted += inserted_count
            total_skipped += skipped_count
    if total_inserted > 0 or total_skipped > 0:
        st.success(f"총 {total_inserted}개의 신규 거래 내역을 성공적으로 저장했습니다!")
        st.success(f"총 {total_skipped}개의 신규 거래 내역을 스킵하였습니다.!")


