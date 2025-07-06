import sqlite3

import pandas as pd

import config


def load_data_from_db(start_date, end_date, transaction_types: list = None, cat_types: list = None, db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
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
        df = pd.read_sql_query(query, conn, params=params)
    except Exception as e:
        print(f"데이터 로드 오류: {e}")
        df = pd.DataFrame()
    finally:
        conn.close()
    return df


def get_all_categories(category_type: str = None,  include_top_level: bool = False, db_path=config.DB_PATH):
    with sqlite3.connect(db_path) as conn:
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
            df = pd.read_sql_query(base_query, conn, params=params)
            return pd.Series(df.description.values, index=df.id).to_dict()
        except Exception as e:
            print(f"카테고리 로드 오류: {e}")
            return {}


def load_data_for_sunburst(start_date, end_date, db_path=config.DB_PATH, transaction_type='EXPENSE'):
    conn = sqlite3.connect(db_path)
    try:
        categories_df = pd.read_sql_query("SELECT * FROM category", conn)
        query = "SELECT category_id, SUM(transaction_amount) as direct_amount FROM \"transaction\" WHERE type = ? AND DATE(transaction_date) BETWEEN ? AND ? GROUP BY category_id"
        direct_spending = pd.read_sql_query(query, conn, params=(transaction_type, start_date, end_date))

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
    conn = sqlite3.connect(db_path)
    try:
        # 1. 카테고리 테이블 전체 로드
        all_categories_df = pd.read_sql_query("SELECT id, parent_id, description FROM category", conn)

        # 2. parent_id의 타입을 int로 강제 변환하여 타입 불일치 문제 해결
        all_categories_df['parent_id'] = pd.to_numeric(all_categories_df['parent_id'], errors='coerce').fillna(
            0).astype(int)

        # 3. 이제 id와 parent_id의 타입이 동일하므로, 맵이 정확하게 생성됨
        id_to_desc_map = all_categories_df.set_index('id')['description'].to_dict()
        id_to_parent_map = all_categories_df.set_index('id')['parent_id'].to_dict()
        # ------------------------------------

        # 4. 거래 내역 로드
        query = """
                SELECT strftime('%Y-%m', t.transaction_date) as "연월",
                       t.transaction_amount                  as "금액",
                       c.id, \
                       c.depth
                FROM "transaction" t
                         JOIN "category" c ON t.category_id = c.id
                WHERE t.type = ? \
                  AND DATE(t.transaction_date) BETWEEN ? AND ? \
                """
        df = pd.read_sql_query(query, conn, params=(transaction_type, start_date, end_date))
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
    with sqlite3.connect(db_path) as conn:
        try:
            df = pd.read_sql_query("SELECT id, description FROM transaction_party ORDER BY description", conn)
            df['description'] = df['description'].fillna(df['id'].astype(str))
            return pd.Series(df.description.values, index=df.id).to_dict()
        except Exception as e:
            print(f"거래처 로드 오류: {e}")
            return {}


def load_monthly_total_spending(start_date, end_date, db_path=config.DB_PATH, transaction_type='EXPENSE'):
    conn = sqlite3.connect(db_path)
    query = """
    SELECT
        strftime('%Y-%m', transaction_date) AS year_month,
        SUM(transaction_amount) AS total_spending
    FROM "transaction"
    WHERE type = ? AND DATE(transaction_date) BETWEEN ? AND ?
    GROUP BY year_month
    ORDER BY year_month;
    """
    df = pd.read_sql_query(query, conn, params=(transaction_type, start_date, end_date))
    conn.close()
    return df


def get_all_parties_df(db_path=config.DB_PATH):
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query("SELECT * FROM transaction_party ORDER BY id", conn)


def get_all_categories_with_hierarchy(db_path=config.DB_PATH):
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query("SELECT * FROM category ORDER BY materialized_path_desc", conn)
        if df.empty:
            return pd.DataFrame()

        id_to_desc_map = df.set_index('id')['description'].to_dict()
        id_to_parent_map = df.set_index('id')['parent_id'].to_dict()

        max_depth = int(df['depth'].max())
        for i in range(1, max_depth + 1):
            df[f'L{i}'] = None

        for index, row in df.iterrows():
            path_names = []
            temp_id = row['id']
            while pd.notna(temp_id) and temp_id in id_to_parent_map:
                path_names.insert(0, id_to_desc_map.get(temp_id, ""))
                temp_id = id_to_parent_map.get(temp_id)
            for i in range(len(path_names)):
                df.loc[index, f'L{i + 1}'] = path_names[i]

        return df


def load_income_expense_summary(start_date, end_date, db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    try:
        query = """
            SELECT
                strftime('%Y-%m', transaction_date) as "연월",
                SUM(CASE WHEN type = 'INCOME' THEN transaction_amount ELSE 0 END) as "수입",
                SUM(CASE WHEN type = 'EXPENSE' THEN transaction_amount ELSE 0 END) as "지출"
            FROM "transaction"
            WHERE DATE(transaction_date) BETWEEN ? AND ?
              AND type IN ('INCOME', 'EXPENSE')
            GROUP BY "연월"
            ORDER BY "연월"
        """
        df = pd.read_sql_query(query, conn, params=(start_date, end_date))
        return df
    finally:
        conn.close()


def load_monthly_category_summary(start_date, end_date, transaction_type, db_path=config.DB_PATH):

    conn = sqlite3.connect(db_path)
    try:
        # 최하위 카테고리(depth가 가장 높은)의 지출/수입만 집계
        query = """
            SELECT
                strftime('%Y-%m', t.transaction_date) as "연월",
                c.description as "카테고리",
                SUM(t.transaction_amount) as "금액"
            FROM "transaction" t
            JOIN "category" c ON t.category_id = c.id
            WHERE t.type = ? AND DATE(t.transaction_date) BETWEEN ? AND ?
              AND c.id NOT IN (SELECT DISTINCT parent_id FROM category WHERE parent_id IS NOT NULL)
            GROUP BY "연월", "카테고리"
        """
        df = pd.read_sql_query(query, conn, params=(transaction_type, start_date, end_date))
        return df
    finally:
        conn.close()


def get_account_id_by_name(account_name, db_path=config.DB_PATH):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM accounts WHERE name = ?", (account_name,))
        result = cursor.fetchone()
        return result[0] if result else None

def get_all_accounts(account_type: str = None, db_path=config.DB_PATH):
    with sqlite3.connect(db_path) as conn:
        query = "SELECT id, name FROM accounts"
        params = ()
        if account_type:
            query += " WHERE account_type = ?"
            params = (account_type,)
        query += " ORDER BY name"

        try:
            df = pd.read_sql_query(query, conn, params=params)
            return pd.Series(df.id.values, index=df.name).to_dict()
        except Exception as e:
            print(f"계좌 목록 로드 오류: {e}")
            return {}

def get_bank_expense_transactions(start_date, end_date, db_path=config.DB_PATH):
    with sqlite3.connect(db_path) as conn:
        query = """
            SELECT id, transaction_date, content, transaction_amount
            FROM "transaction"
            WHERE type = 'EXPENSE' 
              AND transaction_type = 'BANK'
              AND DATE(transaction_date) BETWEEN ? AND ?
            ORDER BY transaction_date DESC
        """
        params = (start_date, end_date)
        return pd.read_sql_query(query, conn, params=params)

def get_balance_history(account_id, db_path=config.DB_PATH):
    with sqlite3.connect(db_path) as conn:
        query = "SELECT change_date, reason, previous_balance, change_amount, new_balance FROM account_balance_history WHERE account_id = ? ORDER BY change_date DESC"
        return pd.read_sql_query(query, conn, params=(account_id,))

def get_investment_accounts(db_path=config.DB_PATH):
    with sqlite3.connect(db_path) as conn:
        # STOCK_ASSET, FUND, CRYPTO 등 투자와 관련된 타입만 선택
        query = "SELECT * FROM accounts WHERE account_type IN ('STOCK_ASSET', 'FUND', 'CRYPTO', 'REAL_ESTATE')"
        return pd.read_sql_query(query, conn)

def get_all_accounts_df(db_path=config.DB_PATH):
    with sqlite3.connect(db_path) as conn:
        try:
            # is_asset 컬럼을 '자산'/'부채' 텍스트로 변환하여 가독성 높임
            query = """
                SELECT 
                    id, 
                    name, 
                    account_type, 
                    balance, 
                    CASE WHEN is_asset = 1 THEN '자산' ELSE '부채' END as type 
                FROM accounts 
                ORDER BY type, name
            """
            return pd.read_sql_query(query, conn)
        except Exception as e:
            print(f"전체 계좌 목록 로드 오류: {e}")
            return pd.DataFrame()
