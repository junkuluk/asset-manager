import os
from datetime import datetime
import streamlit as st
import pandas as pd
import psycopg2  # PostgreSQL 예외 처리를 위해 import

import config
from analysis import run_rule_engine, identify_transfers

LATEST_DB_VERSION = 4
SUCCESS_MSG = "성공적으로 추가되었습니다."


def run_migrations(migrations_path='migrations'):
    """
    PostgreSQL 데이터베이스 마이그레이션을 실행합니다.
    세션(session)을 통해 execute를 호출하도록 수정되었습니다.
    """
    conn = st.connection("supabase", type="sql")
    
    # conn.session을 사용하여 세션 객체를 가져옵니다.
    s = conn.session

    try:
        # 1. 스키마 버전 관리 테이블 생성 (세션을 통해 실행)
        s.execute('''
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER NOT NULL PRIMARY KEY
            );
        ''')
        
        # 2. 현재 버전 확인 (conn.query는 그대로 사용 가능)
        result = conn.query("SELECT version FROM schema_version LIMIT 1;", ttl=0)
        current_version = result['version'].iloc[0] if not result.empty else 0
        
        print(f"현재 DB 버전: {current_version}, 최신 버전: {LATEST_DB_VERSION}")

        if current_version < LATEST_DB_VERSION:
            print("데이터베이스 마이그레이션을 시작합니다...")

            for v in range(current_version + 1, LATEST_DB_VERSION + 1):
                script_path = os.path.join(migrations_path, f"v{v}.sql")
                
                with open(script_path, 'r', encoding='utf-8') as f:
                    sql_script = f.read()
                    # 세미콜론으로 구분된 각 문장을 세션을 통해 실행
                    sql_commands = [cmd.strip() for cmd in sql_script.split(';') if cmd.strip()]
                    
                    for command in sql_commands:
                        s.execute(command)

                # 버전 정보 업데이트 또는 삽입 (세션을 통해 실행)
                if current_version == 0 and len(result) == 0:
                     # 테이블이 아예 비어있을 때
                    s.execute("INSERT INTO schema_version (version) VALUES (%s)", (v,))
                else:
                    s.execute("UPDATE schema_version SET version = %s", (v,))
                
                s.commit() # 각 버전의 마이그레이션이 성공하면 커밋
                print(f"버전 {v} 마이그레이션 성공.")
                current_version = v # 다음 루프를 위해 현재 버전 업데이트
        
        else:
            print("데이터베이스가 이미 최신 버전입니다.")

    except Exception as e:
        print(f"마이그레이션 중 오류 발생: {e}")
        s.rollback() # 오류 발생 시 롤백
    finally:
        s.close() # 세션 닫기


def update_transaction_category(transaction_id, new_category_id):
    """거래 내역의 카테고리를 업데이트합니다."""
    conn = st.connection("supabase", type="sql")
    conn.execute(
        'UPDATE "transaction" SET category_id = %s, is_manual_category = 1 WHERE id = %s',
        (new_category_id, transaction_id)
    )


def update_transaction_description(transaction_id, new_description):
    """거래 내역의 설명을 업데이트합니다."""
    conn = st.connection("supabase", type="sql")
    conn.execute(
        'UPDATE "transaction" SET description = %s WHERE id = %s',
        (new_description, transaction_id)
    )


def update_transaction_party(transaction_id, new_party_id):
    """거래 내역의 거래처를 업데이트합니다."""
    conn = st.connection("supabase", type="sql")
    conn.execute(
        'UPDATE "transaction" SET transaction_party_id = %s WHERE id = %s',
        (new_party_id, transaction_id)
    )


def add_new_party(party_code, description):
    """새로운 거래처를 추가합니다."""
    conn = st.connection("supabase", type="sql")
    try:
        conn.execute(
            'INSERT INTO "transaction_party" (party_code, description) VALUES (%s, %s)',
            (party_code, description)
        )
        return True, SUCCESS_MSG
    except psycopg2.Error as e: # PostgreSQL의 IntegrityError는 psycopg2.Error의 하위 클래스
        conn.session.rollback()
        if e.pgcode == '23505': # Unique violation
             return False, f"오류: 거래처 코드 '{party_code}'가 이미 존재합니다."
        return False, f"오류 발생: {e}"
    except Exception as e:
        conn.session.rollback()
        return False, f"오류 발생: {e}"


def add_new_category(parent_id, new_code, new_desc, new_type):
    """새로운 카테고리를 추가하고 materialized_path를 업데이트합니다."""
    conn = st.connection("supabase", type="sql")
    try:
        # 1. 부모 카테고리 정보 가져오기
        parent_df = conn.query("SELECT depth, materialized_path_desc FROM category WHERE id = %s", params=(parent_id,), ttl=0)
        if parent_df.empty:
            return False, "선택된 부모 카테고리가 존재하지 않습니다."
        
        parent = parent_df.iloc[0]
        parent_depth, parent_path = parent['depth'], parent['materialized_path_desc']
        new_depth = parent_depth + 1

        # 2. 새로운 카테고리 삽입 (RETURNING id 사용)
        insert_query = """
            INSERT INTO category (category_code, category_type, description, depth, parent_id, materialized_path_desc)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id;
        """
        result_df = conn.query(insert_query, params=(new_code, new_type, new_desc, new_depth, parent_id, 'TEMP'), ttl=0)
        new_id = result_df['id'].iloc[0]

        # 3. materialized_path 업데이트
        new_path = f"{parent_path}-{new_id}"
        conn.execute("UPDATE category SET materialized_path_desc = %s WHERE id = %s", (new_path, new_id))
        
        conn.session.commit()
        return True, SUCCESS_MSG
    except psycopg2.Error as e:
        conn.session.rollback()
        if e.pgcode == '23505':
            return False, f"오류: 카테고리 코드 '{new_code}'가 이미 존재할 수 있습니다."
        return False, f"데이터베이스 오류: {e}"
    except Exception as e:
        conn.session.rollback()
        return False, f"알 수 없는 오류 발생: {e}"


def rebuild_category_paths():
    """모든 카테고리의 materialized_path를 다시 계산하여 업데이트합니다."""
    conn = st.connection("supabase", type="sql")
    try:
        df = conn.query("SELECT id, parent_id FROM category", ttl=0)
        if df.empty:
            return 0, "처리할 카테고리가 없습니다."

        parent_map = pd.Series(df.parent_id.values, index=df.id).to_dict()
        
        update_data = []
        for cat_id in df['id']:
            path_segments = []
            current_id = cat_id
            
            while pd.notna(current_id) and current_id in parent_map:
                path_segments.insert(0, str(int(current_id)))
                current_id = parent_map.get(current_id)
            
            new_path = "-".join(path_segments)
            update_data.append((new_path, cat_id))
            
        # executemany 대신 for loop 사용
        updated_count = 0
        for path, cat_id in update_data:
            result = conn.execute("UPDATE category SET materialized_path_desc = %s WHERE id = %s", (path, cat_id))
            updated_count += result.rowcount

        conn.session.commit()
        return updated_count, "모든 카테고리 경로를 성공적으로 재계산했습니다."
    except Exception as e:
        conn.session.rollback()
        return 0, f"오류 발생: {e}"

def update_init_balance_and_log(account_id, change_amount, conn):
    """계좌의 초기 잔액을 업데이트합니다. (conn 객체를 인자로 받음)"""
    result = conn.query("SELECT initial_balance FROM accounts WHERE id = %s", params=(account_id,), ttl=0)
    if result.empty:
        raise ValueError(f"Account with ID {account_id} not found.")
    
    conn.execute("UPDATE accounts SET initial_balance = %s WHERE id = %s", (change_amount, account_id))


def update_balance_and_log(account_id, change_amount, reason, conn):
    """계좌 잔액을 업데이트하고 히스토리를 기록합니다. (conn 객체를 인자로 받음)"""
    # 1. 현재 잔액 가져오기
    result = conn.query("SELECT balance FROM accounts WHERE id = %s", params=(account_id,), ttl=0)
    if result.empty:
        raise ValueError(f"Account with ID {account_id} not found.")

    previous_balance = result['balance'].iloc[0]
    new_balance = previous_balance + change_amount

    # 2. 잔액 업데이트
    conn.execute("UPDATE accounts SET balance = %s WHERE id = %s", (new_balance, account_id))

    # 3. 변경 이력 기록
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    history_query = """
        INSERT INTO account_balance_history 
            (account_id, change_date, previous_balance, change_amount, new_balance, reason)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    conn.execute(history_query, (account_id, now_str, previous_balance, change_amount, new_balance, reason))


def reclassify_expense(transaction_id, linked_account_id):
    """'지출' 거래를 '이체' 또는 '투자'로 재분류합니다."""
    conn = st.connection("supabase", type="sql")
    try:
        # 1. 거래 정보 조회
        trans_df = conn.query('SELECT transaction_amount, type FROM "transaction" WHERE id = %s', params=(int(transaction_id),), ttl=0)
        linked_account_df = conn.query("SELECT account_type, is_investment FROM accounts WHERE id = %s", params=(int(linked_account_id),), ttl=0)

        if trans_df.empty or linked_account_df.empty:
            return False, "거래 또는 대상 계좌 정보를 찾을 수 없습니다."

        amount, current_type = trans_df.iloc[0]
        linked_account_type, is_investment = linked_account_df.iloc[0]

        if current_type != 'EXPENSE':
            return False, f"'{current_type}' 타입의 거래는 '이체'로 변경할 수 없습니다."

        # 2. 새로운 타입과 카테고리 결정
        if is_investment:
            new_type = 'INVEST'
            cat_df = conn.query("SELECT id FROM category WHERE category_code = %s", params=(linked_account_type,), ttl=0)
        else:
            new_type = 'TRANSFER'
            cat_df = conn.query("SELECT id FROM category WHERE category_code = 'CARD_PAYMENT'", ttl=0)
        
        if cat_df.empty:
            return False, "재분류에 필요한 카테고리를 찾을 수 없습니다."
        new_category_id = cat_df['id'].iloc[0]

        # 3. 거래 내역 업데이트
        update_query = 'UPDATE "transaction" SET type = %s, category_id = %s, linked_account_id = %s WHERE id = %s'
        conn.execute(update_query, (new_type, new_category_id, int(linked_account_id), int(transaction_id)))

        # 4. 잔액 업데이트 및 로그 기록
        reason = f"거래 ID {transaction_id}: '{new_type}'(으)로 재분류"
        update_balance_and_log(int(linked_account_id), amount, reason, conn)

        conn.session.commit()
        return True, f"ID {transaction_id}가 '{new_type}'(으)로 성공적으로 재분류되었습니다."
    except Exception as e:
        conn.session.rollback()
        return False, f"작업 중 오류 발생: {e}"


def add_new_account(name, account_type, is_asset, initial_balance):
    """새로운 계좌를 추가합니다."""
    conn = st.connection("supabase", type="sql")
    try:
        conn.execute(
            "INSERT INTO accounts (name, account_type, is_asset, initial_balance, balance) VALUES (%s, %s, %s, %s, %s)",
            (name, account_type, is_asset, initial_balance, initial_balance) # 초기 잔액을 현재 잔액에도 설정
        )
        # 초기 잔액 설정에 대한 히스토리 로그는 필요 시 추가 구현
        conn.session.commit()
        return True, SUCCESS_MSG
    except psycopg2.Error as e:
        conn.session.rollback()
        if e.pgcode == '23505':
            return False, f"오류: 계좌 이름 '{name}'이(가) 이미 존재합니다."
        return False, f"데이터베이스 오류: {e}"
    except Exception as e:
        conn.session.rollback()
        return False, f"오류 발생: {e}"


def reclassify_all_transfers():
    """모든 은행 지출 내역을 검사하여 이체 거래를 자동으로 재분류합니다."""
    conn = st.connection("supabase", type="sql")
    
    df = conn.query("SELECT * FROM \"transaction\" WHERE transaction_type = 'BANK' AND type = 'EXPENSE'", ttl=0)
    if df.empty:
        return "재분류할 은행 지출 내역이 없습니다."

    linked_account_id_series = identify_transfers(df) # db_path 인자 제거
    is_transfer_mask = (linked_account_id_series != 0) & (linked_account_id_series.notna())

    df_to_update = df[is_transfer_mask].copy()
    if df_to_update.empty:
        return "이체로 재분류할 거래를 찾지 못했습니다."
        
    df_to_update['linked_account_id'] = linked_account_id_series[is_transfer_mask]

    card_payment_cat_df = conn.query("SELECT id FROM category WHERE category_code = 'CARD_PAYMENT'", ttl=0)
    if card_payment_cat_df.empty:
        return "카드 대금 카테고리를 찾을 수 없습니다."
    card_payment_cat_id = card_payment_cat_df['id'].iloc[0]

    # DB 업데이트 (for loop 사용)
    update_count = 0
    for _, row in df_to_update.iterrows():
        result = conn.execute(
            "UPDATE \"transaction\" SET type = 'TRANSFER', category_id = %s, linked_account_id = %s WHERE id = %s",
            (card_payment_cat_id, int(row['linked_account_id']), int(row['id']))
        )
        update_count += result.rowcount
    
    conn.session.commit()
    return f"총 {update_count}건의 거래를 '이체'로 재분류했습니다."


def recategorize_uncategorized():
    """미분류된 거래 내역에 대해 규칙 엔진을 다시 실행하여 카테고리를 재분류합니다."""
    conn = st.connection("supabase", type="sql")

    uncategorized_df = conn.query("""
        SELECT t.*
        FROM "transaction" t
        JOIN category c ON t.category_id = c.id
        WHERE c.category_code = 'UNCATEGORIZED' AND t.is_manual_category = false
    """, ttl=0)

    if uncategorized_df.empty:
        return "카테고리를 재분류할 대상이 없습니다."

    # 규칙 엔진 실행
    default_cat_id = uncategorized_df['category_id'].iloc[0]
    categorized_df = run_rule_engine(uncategorized_df, default_cat_id) # db_path 인자 제거

    # 변경된 부분만 업데이트 (for loop 사용)
    update_count = 0
    for _, row in categorized_df.iterrows():
        result = conn.execute(
            "UPDATE \"transaction\" SET category_id = %s WHERE id = %s",
            (int(row['category_id']), int(row['id']))
        )
        update_count += result.rowcount
    
    conn.session.commit()
    return f"총 {update_count}건의 거래에 카테고리 규칙을 재적용했습니다."