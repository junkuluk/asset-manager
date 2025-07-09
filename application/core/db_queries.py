import sqlite3
import streamlit as st

import numpy as np
import pandas as pd

import config


def load_data_from_db(start_date, end_date, transaction_types: list = None, cat_types: list = None, db_path=config.DB_PATH):
    #conn = sqlite3.connect(db_path)
    conn = st.connection("supabase", type="sql")
    query = """
            SELECT 
            t.id, t.transaction_type, t.transaction_date, t.content, t.transaction_amount, t.description, t.type, 
            c.description as category_name,
            p.description as party_description
        FROM "transaction" t
        LEFT JOIN "category" c ON t.category_id = c.id
        LEFT JOIN "transaction_party" p ON t.transaction_party_id = p.id
        WHERE DATE(t.transaction_date) BETWEEN ? AND ?        
            """

    params = (start_date, end_date)

    if transaction_types:
        placeholders = ', '.join(['?'] * len(transaction_types))
        query += f" AND t.type IN ({placeholders})"
        params += tuple(transaction_types)

    if cat_types:
        placeholders = ', '.join(['?'] * len(cat_types))
        query += f" AND t.transaction_type IN ({placeholders})"
        params += tuple(cat_types)


    query += " ORDER BY t.transaction_date DESC"

    try:
        df = conn.query(query, params=params)
    except Exception as e:
        print(f"데이터 로드 오류: {e}")
        df = pd.DataFrame()
    finally:
        conn.close()
    return df


def get_all_categories(category_type: str = None, include_top_level: bool = False, db_path=config.DB_PATH):
    #with sqlite3.connect(db_path) as conn:
    conn = st.connection("supabase", type="sql")
    base_query = "SELECT id, description FROM category"
    conditions = []
    params = []
    if not include_top_level:
        conditions.append("depth > 1")
    if category_type:
        conditions.append("category_type = ?")
        params.append(category_type)
    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)

    base_query += " ORDER BY description"

    try:
        df = conn.query(base_query, params=params)
        return pd.Series(df.description.values, index=df.id).to_dict()
    except Exception as e:
        print(f"카테고리 로드 오류: {e}")
        return {}


def load_data_for_sunburst(start_date, end_date, db_path=config.DB_PATH, transaction_type='EXPENSE'):
    #conn = sqlite3.connect(db_path)
    conn = st.connection("supabase", type="sql")
    try:
        categories_df = conn.query("SELECT * FROM category")
        query = "SELECT category_id, SUM(transaction_amount) as direct_amount FROM \"transaction\" WHERE type = ? AND DATE(transaction_date) BETWEEN ? AND ? GROUP BY category_id"
        direct_spending = conn.query(query, params=(transaction_type, start_date, end_date))

        df = pd.merge(categories_df, direct_spending, left_on='id', right_on='category_id', how='left', validate="one_to_one" )
        df['direct_amount'] = df['direct_amount'].fillna(0)
        df['parent_id'] = pd.to_numeric(df['parent_id'], errors='coerce').fillna(0).astype(int)

        total_amounts = df.set_index('id')['direct_amount'].to_dict()
        sorted_df = df.sort_values(by='depth', ascending=False)
        for _, row in sorted_df.iterrows():
            cat_id, parent_id = row['id'], row['parent_id']
            if parent_id != 0 and parent_id in total_amounts:
                total_amounts[parent_id] += total_amounts[cat_id]

        df['total_amount'] = df['id'].map(total_amounts)

        final_df = df[df['total_amount'] > 0].copy()
        return final_df
    finally:
        conn.close()


def load_data_for_pivot_grid(start_date, end_date, db_path=config.DB_PATH, transaction_type='EXPENSE'):
    #conn = sqlite3.connect(db_path)
    conn = st.connection("supabase", type="sql")
    try:
        # 1. 카테고리 테이블 전체 로드
        all_categories_df = conn.query("SELECT id, parent_id, description FROM category")

        # 2. parent_id의 타입을 int로 강제 변환하여 타입 불일치 문제 해결
        all_categories_df['parent_id'] = pd.to_numeric(all_categories_df['parent_id'], errors='coerce').fillna(
            0).astype(int)

        # 3. 이제 id와 parent_id의 타입이 동일하므로, 맵이 정확하게 생성됨
        id_to_desc_map = all_categories_df.set_index('id')['description'].to_dict()
        id_to_parent_map = all_categories_df.set_index('id')['parent_id'].to_dict()
        # ------------------------------------

        # 4. 거래 내역 로드
        query = """
                SELECT 
                       to_char(transaction_date, 'YYYY/MM') as "연월",
                       t.transaction_amount                  as "금액",
                       c.id, \
                       c.depth
                FROM "transaction" t
                         JOIN "category" c ON t.category_id = c.id
                WHERE t.type = ? \
                  AND DATE(t.transaction_date) BETWEEN ? AND ? \
                """
        df = conn.query(query, params=(transaction_type, start_date, end_date))
        if df.empty: return pd.DataFrame()

        # 5. 경로 생성
        max_depth = int(df['depth'].max())
        for i in range(1, max_depth + 1): df[f'L{i}'] = None

        for index, row in df.iterrows():
            path_names = []
            temp_id = row['id']
            while temp_id != 0 and temp_id in id_to_parent_map:
                path_names.insert(0, id_to_desc_map.get(temp_id, ""))
                temp_id = id_to_parent_map.get(temp_id, 0)
            for i in range(len(path_names)):
                df.loc[index, f'L{i + 1}'] = path_names[i]
        return df
    finally:
        conn.close()


def get_all_parties(db_path=config.DB_PATH):
    #with sqlite3.connect(db_path) as conn:
    conn = st.connection("supabase", type="sql")
    try:
        df = pd.read_sql_query("SELECT id, description FROM transaction_party ORDER BY description", conn)
        df['description'] = df['description'].fillna(df['id'].astype(str))
        return pd.Series(df.description.values, index=df.id).to_dict()
    except Exception as e:
        print(f"거래처 로드 오류: {e}")
        return {}


def load_monthly_total_spending(start_date, end_date, db_path=config.DB_PATH, transaction_type='EXPENSE'):
    #conn = sqlite3.connect(db_path)
    conn = st.connection("supabase", type="sql")
    query = """
    SELECT        
        to_char(transaction_date, 'YYYY/MM') AS year_month,
        SUM(transaction_amount) AS total_spending
    FROM "transaction"
    WHERE type = ? AND DATE(transaction_date) BETWEEN ? AND ?
    GROUP BY year_month
    ORDER BY year_month;
    """
    df = conn.query(query, params=(transaction_type, start_date, end_date))
    conn.close()
    return df


def get_all_parties_df(db_path=config.DB_PATH):
    #with sqlite3.connect(db_path) as conn:
    conn = st.connection("supabase", type="sql")
    return conn.query("SELECT * FROM transaction_party ORDER BY id")


def get_all_categories_with_hierarchy(db_path=config.DB_PATH):
    #with sqlite3.connect(db_path) as conn:
    conn = st.connection("supabase", type="sql")
    df = conn.query("SELECT * FROM category ORDER BY materialized_path_desc")
    if df.empty: return pd.DataFrame()

    id_to_desc_map = df.set_index('id')['description'].to_dict()
    id_to_parent_map = pd.to_numeric(df.set_index('id')['parent_id'], errors='coerce').fillna(0).astype(
        int).to_dict()

    path_names_list = []
    for index, row in df.iterrows():
        path_names = []
        temp_id = row['id']
        while temp_id != 0 and temp_id in id_to_parent_map:
            path_names.insert(0, id_to_desc_map.get(temp_id, ""))
            temp_id = id_to_parent_map.get(temp_id, 0)
        # --- 여기가 수정되었습니다 ---
        # 각 행에 대한 이름 경로를 리스트에 저장
        path_names_list.append("/".join(path_names))

    # DataFrame에 새로운 'name_path' 컬럼을 한 번에 추가
    df['name_path'] = path_names_list
    # ----------------------------
    return df


def load_income_expense_summary(start_date, end_date, db_path=config.DB_PATH):
    #conn = sqlite3.connect(db_path)
    conn = st.connection("supabase", type="sql")
    try:
        query = """
            SELECT                
                to_char(transaction_date, 'YYYY/MM') as "연월",
                SUM(CASE WHEN type = 'INCOME' THEN transaction_amount ELSE 0 END) as "수입",
                SUM(CASE WHEN type = 'EXPENSE' THEN transaction_amount ELSE 0 END) as "지출"
            FROM "transaction"
            WHERE DATE(transaction_date) BETWEEN ? AND ?
              AND type IN ('INCOME', 'EXPENSE')
            GROUP BY "연월"
            ORDER BY "연월"
        """
        df = conn.query(query, params=(start_date, end_date))
        return df
    finally:
        conn.close()


def load_monthly_category_summary(start_date, end_date, transaction_type, db_path=config.DB_PATH):

    #conn = sqlite3.connect(db_path)
    conn = st.connection("supabase", type="sql")
    try:
        # 최하위 카테고리(depth가 가장 높은)의 지출/수입만 집계
        query = """
            SELECT                
                to_char(transaction_date, 'YYYY/MM') as "연월",
                c.description as "카테고리",
                SUM(t.transaction_amount) as "금액"
            FROM "transaction" t
            JOIN "category" c ON t.category_id = c.id
            WHERE t.type = ? AND DATE(t.transaction_date) BETWEEN ? AND ?
              AND c.id NOT IN (SELECT DISTINCT parent_id FROM category WHERE parent_id IS NOT NULL)
            GROUP BY "연월", "카테고리"
        """
        df = conn.query(query, params=(transaction_type, start_date, end_date))
        return df
    finally:
        conn.close()


def get_account_id_by_name(account_name, db_path=config.DB_PATH):
    #with sqlite3.connect(db_path) as conn:
    conn = st.connection("supabase", type="sql")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM accounts WHERE name = ?", (account_name,))
    result = cursor.fetchone()
    return result[0] if result else None

def get_all_accounts(account_type: str = None, db_path=config.DB_PATH):
    #with sqlite3.connect(db_path) as conn:
    conn = st.connection("supabase", type="sql")
    query = "SELECT id, name FROM accounts"
    params = ()
    if account_type:
        query += " WHERE account_type = ?"
        params = (account_type,)
    query += " ORDER BY name"

    try:
        df = conn.query(query, params=params)
        return pd.Series(df.id.values, index=df.name).to_dict()
    except Exception as e:
        print(f"계좌 목록 로드 오류: {e}")
        return {}

def get_bank_expense_transactions(start_date, end_date, db_path=config.DB_PATH):
    #with sqlite3.connect(db_path) as conn:
    conn = st.connection("supabase", type="sql")
    query = """
        SELECT id, transaction_date, content, transaction_amount
        FROM "transaction"
        WHERE type = 'EXPENSE' 
            AND transaction_type = 'BANK'
            AND DATE(transaction_date) BETWEEN ? AND ?
        ORDER BY transaction_date DESC
    """
    params = (start_date, end_date)
    return conn.query(query, params=params)

def get_balance_history(account_id, db_path=config.DB_PATH):
    #with sqlite3.connect(db_path) as conn:
    conn = st.connection("supabase", type="sql")
    query = "SELECT change_date, reason, previous_balance, change_amount, new_balance FROM account_balance_history WHERE account_id = ? ORDER BY change_date DESC"
    return conn.query(query, params=(account_id,))

def get_init_balance(account_id, db_path=config.DB_PATH):
    #with sqlite3.connect(db_path) as conn:
    conn = st.connection("supabase", type="sql")
    cursor = conn.cursor()
    cursor.execute("SELECT balance, initial_balance FROM accounts WHERE id = ?",(account_id,))
    result = cursor.fetchone()
    return result if result else None

def get_investment_accounts(db_path=config.DB_PATH):
    #with sqlite3.connect(db_path) as conn:
    conn = st.connection("supabase", type="sql")
    # STOCK_ASSET, FUND, CRYPTO 등 투자와 관련된 타입만 선택
    query = "SELECT * FROM accounts WHERE is_investment = 1"
    return conn.query(query)

def get_all_accounts_df(db_path=config.DB_PATH):
    #with sqlite3.connect(db_path) as conn:
    conn = st.connection("supabase", type="sql")
    try:
        # is_asset 컬럼을 '자산'/'부채' 텍스트로 변환하여 가독성 높임
        query = """
            SELECT 
                id, 
                name, 
                account_type, 
                initial_balance,
                balance,
                CASE WHEN is_asset = 1 THEN '자산' ELSE '부채' END as type, 
                CASE WHEN is_investment = 1 THEN '투자' ELSE '비투자' END as investment
            FROM accounts 
            ORDER BY type, name
        """
        return conn.query(query)
    except Exception as e:
        print(f"전체 계좌 목록 로드 오류: {e}")
        return pd.DataFrame()


def get_monthly_summary_for_dashboard(db_path=config.DB_PATH):
    
    #with sqlite3.connect(db_path) as conn:
    conn = st.connection("supabase", type="sql")
    # 1. 월별 수입, 지출, 투자액 집계
    flow_query = """
                    SELECT
                        to_char(transaction_date, 'YYYY/MM') as "연월",
                        SUM(CASE WHEN type = 'INCOME' THEN transaction_amount ELSE 0 END)  as "수입", 
                        SUM(CASE WHEN type = 'EXPENSE' THEN transaction_amount ELSE 0 END) as "지출", 
                        SUM(CASE WHEN type = 'INVEST' THEN transaction_amount ELSE 0 END)  as "투자"
                    FROM "transaction"
                    GROUP BY "연월" \
                    """
    flow_df = conn.query(flow_query)

    # 2. 월별 기말 자산 잔액 계산 (가장 어려운 부분)
    # 모든 잔액 변경 이력을 가져와 월별로 누적 합계를 계산
    history_query = """                    
                    to_char(transaction_date, 'YYYY/MM') as "연월",
                    change_amount
                    FROM account_balance_history
                                JOIN accounts ON accounts.id = account_balance_history.account_id
                    WHERE accounts.is_asset = 1 -- 자산 계좌의 변동만 추적 \
                    """
    history_df = conn.query(history_query)
    if not history_df.empty:
        monthly_change = history_df.groupby('연월')['change_amount'].sum()
        asset_balance_df = monthly_change.cumsum().reset_index(name="총자산")
    else:
        asset_balance_df = pd.DataFrame(columns=['연월', '총자산'])

    # 3. 두 데이터프레임을 '연월' 기준으로 병합
    if not flow_df.empty and not asset_balance_df.empty:
        summary_df = pd.merge(flow_df, asset_balance_df, on="연월", how="outer").fillna(0)
    elif not flow_df.empty:
        summary_df = flow_df
    else:
        summary_df = asset_balance_df

    summary_df = summary_df.sort_values("연월").fillna(method='ffill')  # 빈 달의 자산은 전월 자산으로 채움
    return summary_df


def get_annual_summary_data(year: int, db_path=config.DB_PATH):    
    #with sqlite3.connect(db_path) as conn:
    conn = st.connection("supabase", type="sql")
    try:
        # 1. 모든 카테고리 정보를 미리 로드 (경로 생성을 위한 지도)
        all_categories_df = conn.query("SELECT id, parent_id, description FROM category")
        all_categories_df['parent_id'] = pd.to_numeric(all_categories_df['parent_id'], errors='coerce').fillna(
            0).astype(int)
        id_to_desc_map = all_categories_df.set_index('id')['description'].to_dict()
        id_to_parent_map = all_categories_df.set_index('id')['parent_id'].to_dict()

        # 2. 지정된 연도의 거래 내역만 가져옴
        query = """
                SELECT 
                        to_char(transaction_date, 'YYYY/MM') as "연월",
                        transaction_amount                  as "금액",
                        category_id
                FROM "transaction"
                WHERE type IN ('INCOME', 'EXPENSE', 'INVEST')                    
                    AND to_char(transaction_date, 'YYYY') = ?
                """
        df = conn.query(query, params=(str(year),))
        if df.empty:
            return pd.DataFrame()

        # 3. Python에서 각 거래의 카테고리 경로(L1, L2)를 직접 생성
        l1_list = []
        l2_list = []
        for cat_id in df['category_id']:
            path_names = []
            temp_id = cat_id
            while temp_id != 0 and temp_id in id_to_parent_map:
                path_names.insert(0, id_to_desc_map.get(temp_id, ""))
                temp_id = id_to_parent_map.get(temp_id, 0)

            # 경로 길이에 따라 L1, L2 할당
            l1 = path_names[0] if len(path_names) > 0 else '미분류'
            l2 = path_names[1] if len(path_names) > 1 else l1  # L2가 없으면 L1 이름 사용

            l1_list.append(l1)
            l2_list.append(l2)

        # 4. 최종 DataFrame에 '구분'(L1)과 '항목'(L2) 컬럼 추가
        df['구분'] = l1_list
        df['항목'] = l2_list

        return df[['구분', '항목', '연월', '금액']]

    except Exception as e:
        print(f"연간 요약 데이터 로드 오류: {e}")
        return pd.DataFrame()




def get_annual_asset_summary(year: int, db_path=config.DB_PATH):

    #with sqlite3.connect(db_path) as conn:
    # 1. 모든 자산 계좌의 기본 정보(초기 잔액 포함)를 가져옴
    conn = st.connection("supabase", type="sql")
    accounts_df = conn.query(
        "SELECT id, name, initial_balance, DATETIME('1777-01-11 01:01:01') as initial_balance_date FROM accounts ",        
        parse_dates=['initial_balance_date']
    )
    if accounts_df.empty:
        return pd.DataFrame()


    # 2. 모든 거래 내역을 통합하여 계좌별 증감 내역을 만듦
    query = """
            -- 모든 거래를 (계좌ID, 날짜, 변동액) 형태로 통합
            SELECT account_id, 
                    transaction_date,
                    CASE WHEN type IN ('INCOME') THEN transaction_amount ELSE -transaction_amount END as change
            FROM "transaction" 
            WHERE account_id IS NOT NULL
            UNION ALL
            SELECT linked_account_id, 
                    transaction_date,
                    CASE WHEN type = 'INVEST' THEN transaction_amount ELSE -transaction_amount END as change
            FROM "transaction" 
            WHERE linked_account_id IS NOT NULL AND type IN ('INVEST', 'TRANSFER')
            """

    all_changes_df = conn.query(query, parse_dates=['transaction_date'])

    # 초기 잔액 데이터를 거래 변동 데이터와 동일한 형태로 만듦
    initial_balances_df = accounts_df.rename(columns={
        'id': 'account_id',
        'initial_balance_date': 'transaction_date',
        'initial_balance': 'change'
    })[['account_id', 'transaction_date', 'change']]

    # 모든 변동 내역을 하나로 합침
    full_history = pd.concat([all_changes_df, initial_balances_df]).sort_values('transaction_date')
    full_history['change'].fillna(0, inplace=True)

    # --- 여기가 수정된 최종 로직입니다 ---
    # 1. 계좌별로 누적 합계를 계산하여, 각 거래 시점의 잔액을 구함
    full_history['balance'] = full_history.groupby('account_id')['change'].cumsum()

    # 2. 날짜를 인덱스로 설정하고, 월말(Month-End) 기준으로 리샘플링
    full_history.set_index('transaction_date', inplace=True)
    monthly_balances = full_history.groupby('account_id')['balance'].resample('M').last()

    # 3. pivot_table을 사용해 최종 보고서 형태로 변환
    report_df = monthly_balances.reset_index().pivot_table(
        index='account_id',
        columns='transaction_date',
        values='balance'
    )

    # 4. 계좌 ID를 계좌 이름으로 변경
    id_to_name_map = accounts_df.set_index('id')['name'].to_dict()
    report_df.rename(index=id_to_name_map, inplace=True)

    # 5. 거래가 없던 달의 잔액을 이전 달 잔액으로 채우기
    report_df.ffill(axis=1, inplace=True)
    report_df.columns = report_df.columns.strftime('%Y/%m')

    # 6. 해당 연도의 모든 월 컬럼이 표시되도록 reindex
    all_months_of_year = [f"{year}/{str(m).zfill(2)}" for m in range(1, 13)]
    report_df = report_df.reindex(columns=all_months_of_year).fillna(0)

    return report_df.astype(np.int64)