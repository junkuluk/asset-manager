import os
import sqlite3
from datetime import datetime
import streamlit as st

import pandas as pd



import config
from analysis import run_rule_engine, identify_transfers

LATEST_DB_VERSION = 4
SUCCESS_MSG = "성공적으로 추가되었습니다."


def run_migrations(db_path=config.DB_PATH, migrations_path='migrations'):
    #conn = sqlite3.connect(db_path)
    conn = st.connection("supabase", type="sql")
    cursor = conn.cursor()

    current_version = cursor.execute("PRAGMA user_version").fetchone()[0]
    print(f"현재 DB 버전: {current_version}, 최신 버전: {LATEST_DB_VERSION}")

    if current_version < LATEST_DB_VERSION:
        print("데이터베이스 마이그레이션을 시작합니다...")

        for v in range(current_version + 1, LATEST_DB_VERSION + 1):
            script_path = os.path.join(migrations_path, f"v{v}.sql")
            try:
                with open(script_path, 'r', encoding='utf-8') as f:
                    sql_script = f.read()
                cursor.executescript(sql_script)

                cursor.execute(f"PRAGMA user_version = {v}")
                conn.commit()
                print(f"버전 {v} 마이그레이션 성공.")
            except Exception as e:
                print(f"버전 {v} 마이그레이션 실패: {e}")
                conn.rollback()
                conn.close()
                return
    else:
        print("데이터베이스가 이미 최신 버전입니다.")

    conn.close()


def update_transaction_category(transaction_id, new_category_id, db_path=config.DB_PATH):
    #conn = sqlite3.connect(db_path)
    conn = st.connection("supabase", type="sql")
    cursor = conn.cursor()
    cursor.execute("UPDATE \"transaction\" SET category_id = ?, is_manual_category = 1 WHERE id = ?", (new_category_id, transaction_id))
    conn.commit()
    conn.close()


def update_transaction_description(transaction_id, new_description, db_path=config.DB_PATH):
    #with sqlite3.connect(db_path) as conn:
    conn = st.connection("supabase", type="sql")
    conn.execute(
        "UPDATE \"transaction\" SET description = ? WHERE id = ?",
        (new_description, transaction_id)
    )


def update_transaction_party(transaction_id, new_party_id, db_path=config.DB_PATH):
    #with sqlite3.connect(db_path) as conn:
    conn = st.connection("supabase", type="sql")
    conn.execute(
        "UPDATE \"transaction\" SET transaction_party_id = ? WHERE id = ?",
        (new_party_id, transaction_id)
    )


def add_new_party(party_code, description, db_path=config.DB_PATH):
    #with sqlite3.connect(db_path) as conn:
    conn = st.connection("supabase", type="sql")
    try:
        conn.execute(
            "INSERT INTO \"transaction_party\" (party_code, description) VALUES (?, ?)",
            (party_code, description)
        )
        return True, SUCCESS_MSG
    except sqlite3.IntegrityError:
        return False, f"오류: 거래처 코드 '{party_code}'가 이미 존재합니다."
    except Exception as e:
        return False, f"오류 발생: {e}"


def add_new_category(parent_id, new_code, new_desc, new_type, db_path=config.DB_PATH):
    #conn = sqlite3.connect(db_path)
    conn = st.connection("supabase", type="sql")
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT depth, materialized_path_desc FROM category WHERE id = ?", (parent_id,))
        parent = cursor.fetchone()
        if not parent:
            return False, "선택된 부모 카테고리가 존재하지 않습니다."

        parent_depth, parent_path = parent
        new_depth = parent_depth + 1

        cursor.execute("""
                       INSERT INTO category (category_code, category_type, description, depth, parent_id,
                                             materialized_path_desc)
                       VALUES (?, ?, ?, ?, ?, ?)
                       """, (new_code, new_type, new_desc, new_depth, parent_id, 'TEMP'))

        new_id = cursor.lastrowid

        new_path = f"{parent_path}-{new_id}"
        cursor.execute("UPDATE category SET materialized_path_desc = ? WHERE id = ?", (new_path, new_id))

        conn.commit()
        return True, SUCCESS_MSG
    except sqlite3.IntegrityError:
        conn.rollback()
        return False, f"오류: 카테고리 코드 '{new_code}'가 이미 존재할 수 있습니다."
    except Exception as e:
        conn.rollback()
        return False, f"오류 발생: {e}"
    finally:
        conn.close()


def rebuild_category_paths(db_path=config.DB_PATH):
    #conn = sqlite3.connect(db_path)
    conn = st.connection("supabase", type="sql")
    try:
        df = conn.query("SELECT id, parent_id FROM category")
        if df.empty:
            return 0, "처리할 카테고리가 없습니다."

        parent_map = pd.Series(df.parent_id.values, index=df.id).to_dict()

        new_paths = {}
        for cat_id in df['id']:
            path_segments = []
            current_id = cat_id

            # 최상위 부모에 도달할 때까지 위로 올라감
            while pd.notna(current_id) and current_id in parent_map:
                path_segments.insert(0, str(int(current_id)))
                current_id = parent_map.get(current_id)

            new_paths[cat_id] = "-".join(path_segments)

        # 4. executemany를 사용해 모든 경로를 한번에 DB에 업데이트
        update_data = [(path, cat_id) for cat_id, path in new_paths.items()]

        cursor = conn.cursor()
        cursor.executemany("UPDATE category SET materialized_path_desc = ? WHERE id = ?", update_data)
        conn.commit()

        return cursor.rowcount, "모든 카테고리 경로를 성공적으로 재계산했습니다."

    except Exception as e:
        conn.rollback()
        return 0, f"오류 발생: {e}"
    finally:
        conn.close()

def update_init_balance_and_log(account_id, change_amount, conn):
    cursor = conn.cursor()

    cursor.execute("SELECT initial_balance FROM accounts WHERE id = ?", (account_id,))
    result = cursor.fetchone()
    if result is None:
        raise ValueError(f"Account with ID {account_id} not found.")

    # 2. accounts 테이블의 잔액을 업데이트
    cursor.execute("UPDATE accounts SET initial_balance = ? WHERE id = ?", (change_amount, account_id))


def update_balance_and_log(account_id, change_amount, reason, conn):
    cursor = conn.cursor()

    # 1. 현재 잔액을 가져옴
    cursor.execute("SELECT balance FROM accounts WHERE id = ?", (account_id,))
    result = cursor.fetchone()
    if result is None:
        raise ValueError(f"Account with ID {account_id} not found.")

    previous_balance = result[0]
    new_balance = previous_balance + change_amount

    # 2. accounts 테이블의 잔액을 업데이트
    cursor.execute("UPDATE accounts SET balance = ? WHERE id = ?", (new_balance, account_id))

    # 3. account_balance_history 테이블에 변경 이력 기록
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""
                   INSERT INTO account_balance_history (account_id, change_date, previous_balance, change_amount,
                                                        new_balance, reason)
                   VALUES (?, ?, ?, ?, ?, ?)
                   """, (account_id, now_str, previous_balance, change_amount, new_balance, reason))


def reclassify_expense(transaction_id, linked_account_id, db_path=config.DB_PATH):
    conn = st.connection("supabase", type="sql")
    #with sqlite3.connect(db_path) as conn:
    cursor = conn.cursor()
    try:
        # 1. 변경할 거래의 금액과 현재 타입을 확인
        cursor.execute("SELECT transaction_amount, type FROM \"transaction\" WHERE id = ?", (int(transaction_id),))
        trans_result = cursor.fetchone()
        cursor.execute("SELECT account_type, is_investment FROM accounts WHERE id = ?", (int(linked_account_id),))
        linked_account_result = cursor.fetchone()

        if not trans_result or not linked_account_result:
            return False, "거래 또는 대상 계좌 정보를 찾을 수 없습니다."

        amount, current_type = trans_result
        linked_account_type, is_investment = linked_account_result

        if current_type != 'EXPENSE':
            return False, f"'{current_type}' 타입의 거래는 '이체'로 변경할 수 없습니다."

        # 2. 연결 계좌의 타입에 따라 새로운 거래 타입과 카테고리 결정
        if is_investment:
            new_type = 'INVEST'
            # '주식' 카테고리 ID를 찾음 (seeder에 STOCKS 코드가 있다고 가정)
            cursor.execute("SELECT id FROM category WHERE category_code = ? ",(linked_account_type,))
            new_category_id = cursor.fetchone()[0]
        else:  # 카드 계좌 등
            new_type = 'TRANSFER'
            cursor.execute("SELECT id FROM category WHERE category_code = 'CARD_PAYMENT'")
            new_category_id = cursor.fetchone()[0]




        # 3. 거래 내역 업데이트
        cursor.execute(
            "UPDATE \"transaction\" SET type = ?, category_id = ?, linked_account_id = ? WHERE id = ?",
            (new_type, new_category_id, int(linked_account_id), int(transaction_id))
        )

        reason = f"거래 ID {transaction_id}: '{new_type}'(으)로 재분류"
        update_balance_and_log(int(linked_account_id), amount, reason, conn)

        # 4. 은행 계좌의 잔액은 변경할 필요 없음 (이미 출금 시 반영됨)

        conn.commit()
        return True, f"ID {transaction_id}가 '{new_type}'(으)로 성공적으로 재분류되었습니다."
    except Exception as e:
        conn.rollback()
        return False, f"작업 중 오류 발생: {e}"


def add_new_account(name, account_type, is_asset, initial_balance, db_path=config.DB_PATH):
    #with sqlite3.connect(db_path) as conn:
    conn = st.connection("supabase", type="sql")
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO accounts (name, account_type, is_asset, initial_balance) VALUES (?, ?, ?, ?)",
            (name, account_type, is_asset, initial_balance)
        )

        # if initial_balance != 0:
        #     new_account_id = cursor.lastrowid
        #     now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        #     cursor.execute("""
        #                    INSERT INTO account_balance_history (account_id, change_date, previous_balance,
        #                                                         change_amount, new_balance, reason)
        #                    VALUES (?, ?, ?, ?, ?, ?)
        #                    """,
        #                    (new_account_id, now_str, 0, initial_balance, initial_balance, "신규 계좌 생성 및 초기 잔액 설정"))

        conn.commit()
        return True, SUCCESS_MSG
    except sqlite3.IntegrityError:
        return False, f"오류: 계좌 이름 '{name}'이(가) 이미 존재합니다."
    except Exception as e:
        conn.rollback()
        return False, f"오류 발생: {e}"


def reclassify_all_transfers(db_path=config.DB_PATH):

    #with sqlite3.connect(db_path) as conn:
    conn = st.connection("supabase", type="sql")
    df = conn.query("SELECT * FROM \"transaction\" WHERE transaction_type = 'BANK' AND type = 'EXPENSE'")                   
    if df.empty: return "재분류할 은행 지출 내역이 없습니다."

    # 1. 규칙 엔진이 필요로 하는 '적요', '내용' 컬럼을 'content'에서 다시 분리
    #    ' / '가 없는 경우를 대비해 예외 처리
    if 'content' in df.columns:
        split_content = df['content'].str.split(' / ', n=1, expand=True)
        df['적요'] = split_content[0]
        # 내용 컬럼이 없는 경우(split 결과가 1개 컬럼일 때)를 대비
        if split_content.shape[1] > 1:
            df['내용'] = split_content[1]
        else:
            df['내용'] = ''
    # ------------------------------------

    # 엔진 실행
    linked_account_id_series = identify_transfers(df, db_path)
    is_transfer_mask = (linked_account_id_series != 0) & (linked_account_id_series.notna())

    # 변경 대상 ID와 연결 계좌 ID 추출
    df_to_update = df[is_transfer_mask].copy()
    df_to_update['linked_account_id'] = linked_account_id_series[is_transfer_mask]

    card_payment_cat_id = conn.execute("SELECT id FROM category WHERE category_code = 'CARD_PAYMENT'").fetchone()[0]

    # DB 업데이트
    update_data = [(card_payment_cat_id, int(row['linked_account_id']), int(row['id'])) for _, row in
                   df_to_update.iterrows()]
    conn.executemany(
        "UPDATE \"transaction\" SET type = 'TRANSFER', category_id = ?, linked_account_id = ? WHERE id = ?",
        update_data)

    return f"총 {len(df_to_update)}건의 거래를 '이체'로 재분류했습니다."


def recategorize_uncategorized(db_path=config.DB_PATH):

    #with sqlite3.connect(db_path) as conn:
    conn = st.connection("supabase", type="sql")

    uncategorized_df = conn.query("""
                                         SELECT *
                                         FROM "transaction"
                                         WHERE category_id IN
                                               (SELECT id FROM category WHERE category_code = 'UNCATEGORIZED')
                                           AND is_manual_category = 0 -- 수동 수정 제외
                                         """)

    if uncategorized_df.empty: return "카테고리를 재분류할 대상이 없습니다."

    # 규칙 엔진 실행
    default_cat_id = uncategorized_df['category_id'].iloc[0]  # 임의의 미분류 ID
    categorized_df = run_rule_engine(uncategorized_df, default_cat_id, db_path)

    # 변경된 부분만 업데이트
    update_data = [(int(row['category_id']), int(row['id'])) for _, row in categorized_df.iterrows()]
    conn.executemany("UPDATE \"transaction\" SET category_id = ? WHERE id = ?", update_data)

    return f"총 {len(categorized_df)}건의 거래에 카테고리 규칙을 재적용했습니다."