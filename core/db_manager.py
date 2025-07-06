import os
import sqlite3
from datetime import datetime

import pandas as pd

import config

LATEST_DB_VERSION = 3
SUCCESS_MSG = "성공적으로 추가되었습니다."


def run_migrations(db_path=config.DB_PATH, migrations_path='migrations'):
    conn = sqlite3.connect(db_path)
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
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE \"transaction\" SET category_id = ? WHERE id = ?", (new_category_id, transaction_id))
    conn.commit()
    conn.close()


def update_transaction_description(transaction_id, new_description, db_path=config.DB_PATH):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE \"transaction\" SET description = ? WHERE id = ?",
            (new_description, transaction_id)
        )


def update_transaction_party(transaction_id, new_party_id, db_path=config.DB_PATH):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE \"transaction\" SET transaction_party_id = ? WHERE id = ?",
            (new_party_id, transaction_id)
        )


def add_new_party(party_code, description, db_path=config.DB_PATH):
    with sqlite3.connect(db_path) as conn:
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
    conn = sqlite3.connect(db_path)
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
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query("SELECT id, parent_id FROM category", conn)
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
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        try:
            # 1. 변경할 거래의 금액과 현재 타입을 확인
            cursor.execute("SELECT transaction_amount, type FROM \"transaction\" WHERE id = ?", (int(transaction_id),))
            trans_result = cursor.fetchone()
            cursor.execute("SELECT account_type FROM accounts WHERE id = ?", (int(linked_account_id),))
            linked_account_result = cursor.fetchone()

            if not trans_result or not linked_account_result:
                return False, "거래 또는 대상 계좌 정보를 찾을 수 없습니다."

            amount, current_type = trans_result
            linked_account_type = linked_account_result[0]

            if current_type != 'EXPENSE':
                return False, f"'{current_type}' 타입의 거래는 '이체'로 변경할 수 없습니다."

            # 2. 거래 타입을 'TRANSFER'로, 카테고리를 'TRANSFER'로 업데이트
            cursor.execute("SELECT id FROM category WHERE category_code = 'TRANSFER'")
            new_category_id = cursor.fetchone()[0]
            cursor.execute(
                "UPDATE \"transaction\" SET type = ?, category_id = ?, account_id = ? WHERE id = ?",
                ('TRANSFER', new_category_id, int(linked_account_id), int(transaction_id))
            )

            # 3. 카드 계좌의 부채(balance)를 거래 금액만큼 차감
            cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, linked_account_id))

            # 4. 은행 계좌의 잔액은 변경할 필요 없음 (이미 출금 시 반영됨)

            conn.commit()
            return True, f"ID {transaction_id}가 '이체'로 성공적으로 변경되었습니다."
        except Exception as e:
            conn.rollback()
            return False, f"작업 중 오류 발생: {e}"


def add_new_account(name, account_type, is_asset, initial_balance, db_path=config.DB_PATH):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO accounts (name, account_type, is_asset, balance) VALUES (?, ?, ?, ?)",
                (name, account_type, is_asset, initial_balance)
            )

            if initial_balance != 0:
                new_account_id = cursor.lastrowid
                now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("""
                               INSERT INTO account_balance_history (account_id, change_date, previous_balance,
                                                                    change_amount, new_balance, reason)
                               VALUES (?, ?, ?, ?, ?, ?)
                               """,
                               (new_account_id, now_str, 0, initial_balance, initial_balance, "신규 계좌 생성 및 초기 잔액 설정"))

            conn.commit()
            return True, SUCCESS_MSG
        except sqlite3.IntegrityError:
            return False, f"오류: 계좌 이름 '{name}'이(가) 이미 존재합니다."
        except Exception as e:
            conn.rollback()
            return False, f"오류 발생: {e}"
