import sqlite3
import pandas as pd

def init_database(db_path='asset_data.db', schema_path='schema.sql'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()

    cursor.executescript(schema_sql)

    conn.commit()
    conn.close()
    print("데이터베이스 스키마가 성공적으로 초기화/업데이트되었습니다.")

def load_data_from_db(db_path='asset_data.db'):
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
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

def update_transaction_category(transaction_id, new_category_id, db_path='asset_data.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE \"transaction\" SET category_id = ? WHERE id = ?", (new_category_id, transaction_id))
    conn.commit()
    conn.close()

def get_all_categories(db_path='asset_data.db'):
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query("SELECT id, description FROM category", conn)
        return pd.Series(df.description.values, index=df.id).to_dict()
    except Exception:
        return {}
    finally:
        conn.close()


def load_hierarchical_spending_data(start_date, end_date, db_path='asset_data.db'):
    conn = sqlite3.connect(db_path)
    try:
        # 1. 모든 카테고리 정보 로드
        categories_df = pd.read_sql_query("SELECT * FROM category", conn)

        # 2. 지정된 기간의 지출 내역만 불러와 카테고리별로 합산
        query = """
                SELECT category_id, SUM(transaction_amount) as direct_amount
                FROM "transaction"
                WHERE type = 'EXPENSE'
                  AND DATE(transaction_date) BETWEEN ? AND ? -- <<< 날짜 필터 추가
                GROUP BY category_id 
                """
        direct_spending = pd.read_sql_query(query, conn, params=(start_date, end_date))

        # 3. 카테고리 정보에 직접 지출액 병합
        df = pd.merge(categories_df, direct_spending, left_on='id', right_on='category_id', how='left')

        df['direct_amount'] = df['direct_amount'].fillna(0)

        # 4. 'Bottom-up' 방식으로 total_amount 계산 (이전과 동일한 안정적인 로직)
        total_amounts = df.set_index('id')['direct_amount'].to_dict()
        sorted_df = df.sort_values(by='depth', ascending=False)
        for _, row in sorted_df.iterrows():
            cat_id, parent_id = row['id'], row['parent_id']
            if pd.notna(parent_id) and parent_id in total_amounts:
                total_amounts[parent_id] += total_amounts[cat_id]
        df['total_amount'] = df['id'].map(total_amounts)

        # 5. 지출이 발생한 계층의 모든 노드만 필터링
        spending_nodes_ids = set(df[df['direct_amount'] > 0]['id'])
        required_ids = set()
        df_indexed = df.set_index('id')
        for node_id in spending_nodes_ids:
            current_id = node_id
            while pd.notna(current_id) and current_id in df_indexed.index:
                required_ids.add(current_id)
                current_id = df_indexed.loc[current_id, 'parent_id']
        final_df = df[df['id'].isin(required_ids)].copy()

        # 6. 시각화를 위한 최종 정리
        parent_map = final_df.set_index('id')['description']
        final_df['parent_description'] = final_df['parent_id'].map(parent_map).fillna("")

        return final_df

    finally:
        conn.close()


def load_simple_spending_data(start_date, end_date, db_path='asset_data.db'):
    conn = sqlite3.connect(db_path)
    try:
        query = """
            SELECT 
                c.description as category_name,
                SUM(t.transaction_amount) as total_amount
            FROM "transaction" t
            JOIN "category" c ON t.category_id = c.id
            WHERE t.type = 'EXPENSE'
              AND DATE(t.transaction_date) BETWEEN ? AND ?
            GROUP BY c.description
            HAVING total_amount > 0
            ORDER BY total_amount DESC
        """
        # start_date와 end_date를 쿼리에 안전하게 전달
        df = pd.read_sql_query(query, conn, params=(start_date, end_date))
        return df
    except Exception as e:
        print(f"단순 데이터 로드 오류: {e}")
        return pd.DataFrame()
    finally:
        conn.close()