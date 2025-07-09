import streamlit as st
import numpy as np
import pandas as pd

import config

def load_data_from_db(start_date, end_date, transaction_types: list = None, cat_types: list = None):
    """기간과 타입에 맞는 거래 내역을 데이터베이스에서 불러옵니다."""
    conn = st.connection("supabase", type="sql")
    
    # 기본 쿼리
    query_parts = ["""
        SELECT 
            t.id, t.transaction_type, t.transaction_date, t.content, t.transaction_amount, t.description, t.type, 
            c.description as category_name,
            p.description as party_description
        FROM "transaction" t
        LEFT JOIN "category" c ON t.category_id = c.id
        LEFT JOIN "transaction_party" p ON t.transaction_party_id = p.id
        WHERE t.transaction_date::date BETWEEN %s AND %s
    """]
    params = [start_date, end_date]

    # 동적 필터 조건 추가
    if transaction_types:
        query_parts.append("AND t.type IN %s")
        params.append(tuple(transaction_types))

    if cat_types:
        query_parts.append("AND t.transaction_type IN %s")
        params.append(tuple(cat_types))

    query_parts.append("ORDER BY t.transaction_date DESC")
    
    # 전체 쿼리 조합
    final_query = " ".join(query_parts)

    try:
        df = conn.query(final_query, params=params, ttl=0)
    except Exception as e:
        st.error(f"데이터 로드 오류: {e}")
        df = pd.DataFrame()
        
    return df


def get_all_categories(category_type: str = None, include_top_level: bool = False):
    """조건에 맞는 모든 카테고리를 사전 형태로 반환합니다."""
    conn = st.connection("supabase", type="sql")
    query_parts = ["SELECT id, description FROM category"]
    conditions = []
    params = []

    if not include_top_level:
        conditions.append("depth > 1")
    if category_type:
        conditions.append("category_type = %s")
        params.append(category_type)
    
    if conditions:
        query_parts.append("WHERE " + " AND ".join(conditions))

    query_parts.append("ORDER BY description")
    final_query = " ".join(query_parts)

    try:
        df = conn.query(final_query, params=params, ttl=0)
        return pd.Series(df.description.values, index=df.id).to_dict()
    except Exception as e:
        st.error(f"카테고리 로드 오류: {e}")
        return {}


def load_data_for_sunburst(start_date, end_date, transaction_type='EXPENSE'):
    """Sunburst 차트를 위한 데이터를 로드하고 계층적으로 금액을 집계합니다."""
    conn = st.connection("supabase", type="sql")
    try:
        categories_df = conn.query("SELECT * FROM category", ttl=0)
        query = """
            SELECT category_id, SUM(transaction_amount) as direct_amount 
            FROM "transaction" 
            WHERE type = %s AND transaction_date::date BETWEEN %s AND %s 
            GROUP BY category_id
        """
        direct_spending = conn.query(query, params=(transaction_type, start_date, end_date), ttl=0)

        df = pd.merge(categories_df, direct_spending, left_on='id', right_on='category_id', how='left')
        df['direct_amount'] = df['direct_amount'].fillna(0)
        df['parent_id'] = pd.to_numeric(df['parent_id'], errors='coerce').fillna(0).astype(int)

        # 계층적 합계 계산
        total_amounts = df.set_index('id')['direct_amount'].to_dict()
        sorted_df = df.sort_values(by='depth', ascending=False)
        for _, row in sorted_df.iterrows():
            cat_id, parent_id = row['id'], row['parent_id']
            if parent_id != 0 and parent_id in total_amounts:
                total_amounts[parent_id] += total_amounts.get(cat_id, 0)

        df['total_amount'] = df['id'].map(total_amounts)
        return df[df['total_amount'] > 0].copy()
    except Exception as e:
        st.error(f"Sunburst 데이터 로드 오류: {e}")
        return pd.DataFrame()


def load_data_for_pivot_grid(start_date, end_date, transaction_type='EXPENSE'):
    """피벗 그리드를 위한 데이터를 로드하고 카테고리 경로를 생성합니다."""
    conn = st.connection("supabase", type="sql")
    try:
        all_categories_df = conn.query("SELECT id, parent_id, description FROM category", ttl=0)
        all_categories_df['parent_id'] = pd.to_numeric(all_categories_df['parent_id'], errors='coerce').fillna(0).astype(int)
        id_to_desc_map = all_categories_df.set_index('id')['description'].to_dict()
        id_to_parent_map = all_categories_df.set_index('id')['parent_id'].to_dict()

        query = """
            SELECT 
                to_char(transaction_date, 'YYYY/MM') as "연월",
                t.transaction_amount as "금액",
                c.id, c.depth
            FROM "transaction" t
            JOIN "category" c ON t.category_id = c.id
            WHERE t.type = %s AND t.transaction_date::date BETWEEN %s AND %s
        """
        df = conn.query(query, params=(transaction_type, start_date, end_date), ttl=0)
        if df.empty: return pd.DataFrame()

        # 카테고리 경로 생성
        paths = []
        for cat_id in df['id']:
            path_names = []
            temp_id = cat_id
            while temp_id != 0 and temp_id in id_to_parent_map:
                path_names.insert(0, id_to_desc_map.get(temp_id, ""))
                temp_id = id_to_parent_map.get(temp_id, 0)
            paths.append(path_names)

        max_depth = df['depth'].max()
        for i in range(1, int(max_depth) + 1):
            df[f'L{i}'] = [p[i-1] if len(p) >= i else None for p in paths]
            
        return df
    except Exception as e:
        st.error(f"피벗 그리드 데이터 로드 오류: {e}")
        return pd.DataFrame()

def get_all_parties():
    """모든 거래처 정보를 사전 형태로 반환합니다."""
    conn = st.connection("supabase", type="sql")
    try:
        df = conn.query("SELECT id, description FROM transaction_party ORDER BY description", ttl=0)
        return pd.Series(df.description.values, index=df.id).to_dict()
    except Exception as e:
        st.error(f"거래처 로드 오류: {e}")
        return {}


def load_monthly_total_spending(start_date, end_date, transaction_type='EXPENSE'):
    """월별 총 지출/수입 내역을 반환합니다."""
    conn = st.connection("supabase", type="sql")
    query = """
        SELECT 
            to_char(transaction_date, 'YYYY/MM') AS year_month,
            SUM(transaction_amount) AS total_spending
        FROM "transaction"
        WHERE type = %s AND transaction_date::date BETWEEN %s AND %s
        GROUP BY year_month
        ORDER BY year_month;
    """
    return conn.query(query, params=(transaction_type, start_date, end_date))


def get_all_parties_df():
    """모든 거래처 정보를 데이터프레임으로 반환합니다."""
    conn = st.connection("supabase", type="sql")
    return conn.query("SELECT * FROM transaction_party ORDER BY id")


def get_all_categories_with_hierarchy():
    """계층 구조를 포함한 모든 카테고리 정보를 반환합니다."""
    conn = st.connection("supabase", type="sql")
    df = conn.query("SELECT * FROM category ORDER BY materialized_path_desc", ttl=0)
    if df.empty: return pd.DataFrame()

    id_to_desc_map = df.set_index('id')['description'].to_dict()
    id_to_parent_map = pd.to_numeric(df.set_index('id')['parent_id'], errors='coerce').fillna(0).astype(int).to_dict()

    path_names_list = []
    for cat_id in df['id']:
        path_names = []
        temp_id = cat_id
        while temp_id != 0 and temp_id in id_to_parent_map:
            path_names.insert(0, id_to_desc_map.get(temp_id, ""))
            temp_id = id_to_parent_map.get(temp_id, 0)
        path_names_list.append("/".join(path_names))

    df['name_path'] = path_names_list
    return df


def load_income_expense_summary(start_date, end_date):
    """월별 수입/지출 요약 데이터를 반환합니다."""
    conn = st.connection("supabase", type="sql")
    query = """
        SELECT 
            to_char(transaction_date, 'YYYY/MM') as "연월",
            SUM(CASE WHEN type = 'INCOME' THEN transaction_amount ELSE 0 END) as "수입",
            SUM(CASE WHEN type = 'EXPENSE' THEN transaction_amount ELSE 0 END) as "지출"
        FROM "transaction"
        WHERE transaction_date::date BETWEEN %s AND %s AND type IN ('INCOME', 'EXPENSE')
        GROUP BY "연월"
        ORDER BY "연월"
    """
    return conn.query(query, params=(start_date, end_date))


def load_monthly_category_summary(start_date, end_date, transaction_type):
    """월별, 카테고리별 요약 데이터를 반환합니다. (최하위 카테고리 기준)"""
    conn = st.connection("supabase", type="sql")
    query = """
        SELECT 
            to_char(t.transaction_date, 'YYYY/MM') as "연월",
            c.description as "카테고리",
            SUM(t.transaction_amount) as "금액"
        FROM "transaction" t
        JOIN "category" c ON t.category_id = c.id
        WHERE t.type = %s AND t.transaction_date::date BETWEEN %s AND %s
          AND c.id NOT IN (SELECT DISTINCT parent_id FROM category WHERE parent_id IS NOT NULL)
        GROUP BY "연월", "카테고리"
        ORDER BY "연월", "금액" DESC
    """
    return conn.query(query, params=(transaction_type, start_date, end_date))


def get_account_id_by_name(account_name):
    """계좌 이름으로 ID를 조회합니다."""
    conn = st.connection("supabase", type="sql")
    df = conn.query("SELECT id FROM accounts WHERE name = %s", params=(account_name,), ttl=0)
    return df['id'].iloc[0] if not df.empty else None


def get_all_accounts(account_type: str = None):
    """계좌 목록을 사전 형태로 반환합니다."""
    conn = st.connection("supabase", type="sql")
    query = "SELECT id, name FROM accounts"
    params = ()
    if account_type:
        query += " WHERE account_type = %s"
        params = (account_type,)
    query += " ORDER BY name"
    
    try:
        df = conn.query(query, params=params, ttl=0)
        return pd.Series(df.id.values, index=df.name).to_dict()
    except Exception as e:
        st.error(f"계좌 목록 로드 오류: {e}")
        return {}


def get_bank_expense_transactions(start_date, end_date):
    """기간 내 은행 지출 거래 내역을 반환합니다."""
    conn = st.connection("supabase", type="sql")
    query = """
        SELECT id, transaction_date, content, transaction_amount
        FROM "transaction"
        WHERE type = 'EXPENSE' AND transaction_type = 'BANK'
          AND transaction_date::date BETWEEN %s AND %s
        ORDER BY transaction_date DESC
    """
    return conn.query(query, params=(start_date, end_date))


def get_balance_history(account_id):
    """특정 계좌의 잔액 변경 이력을 반환합니다."""
    conn = st.connection("supabase", type="sql")
    query = """
        SELECT change_date, reason, previous_balance, change_amount, new_balance 
        FROM account_balance_history 
        WHERE account_id = %s ORDER BY change_date DESC
    """
    return conn.query(query, params=(account_id,))


def get_init_balance(account_id):
    """특정 계좌의 현재 잔액과 초기 잔액을 반환합니다."""
    conn = st.connection("supabase", type="sql")
    df = conn.query("SELECT balance, initial_balance FROM accounts WHERE id = %s", params=(account_id,), ttl=0)
    return df.iloc[0] if not df.empty else None


def get_investment_accounts():
    """모든 투자 계좌 목록을 반환합니다."""
    conn = st.connection("supabase", type="sql")
    return conn.query("SELECT * FROM accounts WHERE is_investment = true")


def get_all_accounts_df():
    """모든 계좌 정보를 데이터프레임으로 반환합니다."""
    conn = st.connection("supabase", type="sql")
    query = """
        SELECT 
            id, name, account_type, initial_balance, balance,
            CASE WHEN is_asset = true THEN '자산' ELSE '부채' END as type, 
            CASE WHEN is_investment = true THEN '투자' ELSE '비투자' END as investment
        FROM accounts 
        ORDER BY type, name
    """
    return conn.query(query)


def get_monthly_summary_for_dashboard():
    """대시보드를 위한 월별 요약 데이터를 생성합니다."""
    conn = st.connection("supabase", type="sql")
    
    flow_query = """
        SELECT
            to_char(transaction_date, 'YYYY/MM') as "연월",
            SUM(CASE WHEN type = 'INCOME' THEN transaction_amount ELSE 0 END) as "수입", 
            SUM(CASE WHEN type = 'EXPENSE' THEN transaction_amount ELSE 0 END) as "지출", 
            SUM(CASE WHEN type = 'INVEST' THEN transaction_amount ELSE 0 END) as "투자"
        FROM "transaction"
        GROUP BY "연월"
    """
    flow_df = conn.query(flow_query, ttl=0)

    # 초기 자산 총합 계산
    initial_total_asset_df = conn.query("SELECT SUM(initial_balance) as total FROM accounts WHERE is_asset = true", ttl=0)
    initial_total_asset = initial_total_asset_df['total'].iloc[0] if not initial_total_asset_df.empty else 0

    # 월별 자산 변동액 계산
    history_query = """
        SELECT 
            to_char(change_date, 'YYYY/MM') as "연월",
            SUM(change_amount) as change_amount
        FROM account_balance_history abh
        JOIN accounts a ON a.id = abh.account_id
        WHERE a.is_asset = true
        GROUP BY "연월"
    """
    history_df = conn.query(history_query, ttl=0)
    
    if not history_df.empty:
        history_df = history_df.sort_values('연월').set_index('연월')
        # cumsum()으로 누적 변동액 계산 후 초기 자산 더하기
        asset_balance_df = (history_df['change_amount'].cumsum() + initial_total_asset).reset_index(name="총자산")
    else:
        asset_balance_df = pd.DataFrame(columns=['연월', '총자산'])

    # 데이터 병합
    if not flow_df.empty and not asset_balance_df.empty:
        summary_df = pd.merge(flow_df, asset_balance_df, on="연월", how="outer")
    elif not flow_df.empty:
        summary_df = flow_df
    else:
        summary_df = asset_balance_df
    
    summary_df = summary_df.sort_values("연월").fillna(method='ffill').fillna(0)
    return summary_df


def get_annual_summary_data(year: int):
    """연간 요약 데이터를 생성합니다."""
    conn = st.connection("supabase", type="sql")
    try:
        all_categories_df = conn.query("SELECT id, parent_id, description FROM category", ttl=0)
        all_categories_df['parent_id'] = pd.to_numeric(all_categories_df['parent_id'], errors='coerce').fillna(0).astype(int)
        id_to_desc_map = all_categories_df.set_index('id')['description'].to_dict()
        id_to_parent_map = all_categories_df.set_index('id')['parent_id'].to_dict()

        query = """
            SELECT 
                to_char(transaction_date, 'YYYY/MM') as "연월",
                transaction_amount as "금액",
                category_id
            FROM "transaction"
            WHERE type IN ('INCOME', 'EXPENSE', 'INVEST')
              AND to_char(transaction_date, 'YYYY') = %s
        """
        df = conn.query(query, params=(str(year),), ttl=0)
        if df.empty: return pd.DataFrame()

        l1_list, l2_list = [], []
        for cat_id in df['category_id']:
            path_names = []
            temp_id = cat_id
            while temp_id != 0 and temp_id in id_to_parent_map:
                path_names.insert(0, id_to_desc_map.get(temp_id, ""))
                temp_id = id_to_parent_map.get(temp_id, 0)
            
            l1 = path_names[0] if len(path_names) > 0 else '미분류'
            l2 = path_names[1] if len(path_names) > 1 else l1
            l1_list.append(l1)
            l2_list.append(l2)

        df['구분'] = l1_list
        df['항목'] = l2_list
        return df[['구분', '항목', '연월', '금액']]
    except Exception as e:
        st.error(f"연간 요약 데이터 로드 오류: {e}")
        return pd.DataFrame()


def get_annual_asset_summary(year: int):
    """연간 자산 요약 데이터를 생성합니다."""
    conn = st.connection("supabase", type="sql")
    
    # PostgreSQL은 DATETIME 함수 대신 타입 캐스팅 사용
    accounts_df = conn.query("""
        SELECT id, name, initial_balance, '1777-01-11 01:01:01'::timestamp as initial_balance_date 
        FROM accounts
    """, parse_dates=['initial_balance_date'], ttl=0)
    if accounts_df.empty: return pd.DataFrame()

    query = """
        SELECT account_id, transaction_date,
               CASE WHEN type IN ('INCOME') THEN transaction_amount ELSE -transaction_amount END as change
        FROM "transaction" WHERE account_id IS NOT NULL
        UNION ALL
        SELECT linked_account_id, transaction_date,
               CASE WHEN type IN ('INVEST', 'TRANSFER') AND type != 'EXPENSE' THEN transaction_amount
                    ELSE transaction_amount END as change
        FROM "transaction" WHERE linked_account_id IS NOT NULL
    """
    all_changes_df = conn.query(query, parse_dates=['transaction_date'], ttl=0)

    initial_balances_df = accounts_df.rename(columns={
        'id': 'account_id', 'initial_balance_date': 'transaction_date', 'initial_balance': 'change'
    })[['account_id', 'transaction_date', 'change']]

    full_history = pd.concat([all_changes_df, initial_balances_df]).sort_values('transaction_date')
    full_history['change'] = full_history['change'].fillna(0)
    full_history['balance'] = full_history.groupby('account_id')['change'].cumsum()
    
    full_history.set_index('transaction_date', inplace=True)
    monthly_balances = full_history.groupby('account_id')['balance'].resample('M').last()

    report_df = monthly_balances.reset_index().pivot_table(
        index='account_id', columns='transaction_date', values='balance'
    )

    id_to_name_map = accounts_df.set_index('id')['name'].to_dict()
    report_df.rename(index=id_to_name_map, inplace=True)
    report_df.ffill(axis=1, inplace=True)
    report_df.columns = report_df.columns.strftime('%Y/%m')

    all_months_of_year = [f"{year}/{m:02d}" for m in range(1, 13)]
    report_df = report_df.reindex(columns=all_months_of_year).fillna(method='ffill', axis=1).fillna(0)
    
    return report_df.astype('int64')