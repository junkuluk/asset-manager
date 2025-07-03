import streamlit as st
import pandas as pd
import plotly.express as px
from core.database import load_data_from_db
from core.database import load_hierarchical_spending_data, load_simple_spending_data
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
from datetime import datetime, date


st.set_page_config(layout="wide", page_title="계층별 통계 분석")
st.title("📊 계층별 통계 분석")
st.markdown("---")

# --- 날짜 선택 UI (그대로 유지) ---
today = date.today()
default_start_date = today.replace(day=1)
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("조회 시작일", value=default_start_date, max_value=today)
with col2:
    end_date = st.date_input("조회 종료일", value=today, max_value=today)

if start_date > end_date:
    st.error("시작일은 종료일보다 늦을 수 없습니다.")
    st.stop()

# --- 계층 데이터 로드 및 시각화 ---
hierarchical_df = load_hierarchical_spending_data(start_date, end_date)

if hierarchical_df.empty:
    st.warning("선택된 기간에 해당하는 지출 데이터가 없습니다.")
else:
    # --- 데이터 타입 정리 (안정성을 위해) ---
    df = hierarchical_df.copy()
    df['id'] = df['id'].astype(str)
    df['parent_id'] = pd.to_numeric(df['parent_id'], errors='coerce').fillna(0).astype(int).astype(str)
    df.loc[df['parent_id'] == '0', 'parent_id'] = ""

    # --- Sunburst 차트 ---
    st.subheader("계층별 지출 현황")
    fig = px.sunburst(
        df, ids='id', parents='parent_id', names='description',
        values='total_amount', branchvalues='total'
    )
    fig.update_traces(textinfo='label+percent parent', insidetextorientation='radial')
    fig.update_layout(margin=dict(t=40, l=0, r=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

    # --- AgGrid 트리 그리드 ---
    st.markdown("---")
    st.subheader("계층별 지출 내역 (표)")
    grid_df = df[['description', 'total_amount', 'materialized_path_desc']].copy()
    grid_df.rename(columns={'description': '카테고리', 'total_amount': '총 지출액'}, inplace=True)

    gridOptions = {
        "columnDefs": [
            {"field": "카테고리", "cellRenderer": "agGroupCellRenderer", "minWidth": 330},
            {"field": "총 지출액", "valueFormatter": "x.toLocaleString() + ' 원'", "type": "numericColumn"},
        ],
        "treeData": True, "animateRows": True, "groupDefaultExpanded": -1,
        "getDataPath": JsCode("function(data) { return data.materialized_path_desc.split('-'); }"),
    }
    AgGrid(grid_df, gridOptions=gridOptions, allow_unsafe_jscode=True, enable_enterprise_modules=True, height=500,
           width='100%', theme='streamlit')





st.markdown("---")
st.subheader("계층별 지출 내역 (표) old")
display_df = load_data_from_db()

if display_df.empty:
    st.warning("표시할 데이터가 없습니다. 먼저 데이터를 업로드해주세요.")
else:
    display_df['transaction_date'] = pd.to_datetime(display_df['transaction_date'])

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("카테고리별 지출 현황")
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