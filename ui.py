import streamlit as st
import pandas as pd
import sqlite3
import os
import plotly.express as px
from core.data_processor import insert_card_transactions_from_excel

DB_PATH = 'asset_data.db'

def load_data_from_db(db_path=DB_PATH):

    conn = sqlite3.connect(db_path)
    query = """
        SELECT t.*, c.description as category_name 
        FROM "transaction" t
        LEFT JOIN "category" c ON t.category_id = c.id
        ORDER BY t.transaction_date DESC
    """
    try:
        df = pd.read_sql_query(query, conn)
    except Exception as e:
        print(f"DB 데이터 로드 오류: {e}")
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

def main_ui():
    st.title("📊 개인 자산 관리 대시보드 <JUNKULUK>")

    st.subheader("📈 신규 거래내역 업로드")

    uploaded_files = st.file_uploader(
        "신한카드, 국민카드 엑셀 파일을 업로드하세요 (예: shinhan_2025_07.xlsx)",
        type=["xlsx","xls"], accept_multiple_files=True
    )

    if uploaded_files:
        total_inserted = 0
        for file in uploaded_files:
            inserted_count = insert_card_transactions_from_excel(file, db_path=DB_PATH)
            total_inserted += inserted_count
        if total_inserted > 0:
            st.success(f"총 {total_inserted}개의 신규 거래 내역을 성공적으로 저장했습니다!")

    st.markdown("---")


    st.subheader("통계 및 분석")

    display_df = load_data_from_db()

    if display_df.empty:
        st.warning("표시할 데이터가 없습니다. 먼저 엑셀 파일을 업로드해주세요.")
    else:
        display_df['transaction_date'] = pd.to_datetime(display_df['transaction_date'])

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("카테고리별 지출 현황")
            # category_name이 없는 경우 '미분류'로 처리
            display_df['category_name'] = display_df['category_name'].fillna('미분류')
            category_spending = display_df[display_df['type'] == 'EXPENSE'].groupby('category_name')[
                'transaction_amount'].sum().reset_index()
            fig = px.pie(category_spending, names='category_name', values='transaction_amount', title='카테고리별 지출 비율')
            st.plotly_chart(fig)

        with col2:
            st.subheader("월별 지출 추이")
            monthly_spending = \
            display_df[display_df['type'] == 'EXPENSE'].set_index('transaction_date').groupby(pd.Grouper(freq='M'))[
                'transaction_amount'].sum()
            st.bar_chart(monthly_spending)

        st.subheader("전체 거래 내역")
        st.dataframe(display_df)