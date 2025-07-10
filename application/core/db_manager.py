import os
from datetime import datetime
import streamlit as st
import pandas as pd
import psycopg2
from sqlalchemy import text
from sqlalchemy.orm import Session  # 타입 힌트를 위해 import

import config
from analysis import run_rule_engine, identify_transfers

LATEST_DB_VERSION = 4
SUCCESS_MSG = "성공적으로 추가되었습니다."


def run_migrations(migrations_path=config.SCHEMA_PATH):
    """
    PostgreSQL 데이터베이스 마이그레이션을 실행합니다.
    모든 DB 작업을 단일 세션 내에서 일관되게 처리하도록 수정되었습니다.
    """
    conn = st.connection("supabase", type="sql")
    with conn.session as s:
        try:
            # 1. 스키마 버전 관리 테이블 생성 (없을 경우)
            s.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL PRIMARY KEY);"
                )
            )

            # 2. 현재 버전 확인
            current_version_result = s.execute(
                text("SELECT version FROM schema_version LIMIT 1;")
            ).scalar_one_or_none()

            if current_version_result is None:
                # 버전 정보가 아예 없으면 초기값(0) 삽입
                s.execute(text("INSERT INTO schema_version (version) VALUES (0)"))
                current_version = 0
            else:
                current_version = current_version_result

            print(f"현재 DB 버전: {current_version}, 최신 버전: {LATEST_DB_VERSION}")

            if current_version < LATEST_DB_VERSION:
                print("데이터베이스 마이그레이션을 시작합니다...")
                for v in range(current_version + 1, LATEST_DB_VERSION + 1):
                    # 각 버전별 마이그레이션을 하나의 트랜잭션으로 묶습니다.
                    with s.begin_nested():
                        script_path = os.path.normpath(
                            os.path.join(migrations_path, f"v{v}.sql")
                        )
                        print(f"마이그레이션 파일 실행: {script_path}")
                        with open(script_path, "r", encoding="utf-8") as f:
                            sql_script = f.read()

                        if sql_script.strip():
                            s.execute(text(sql_script))

                        s.execute(
                            text("UPDATE schema_version SET version = :version"),
                            {"version": v},
                        )
                print(f"버전 {LATEST_DB_VERSION}까지 마이그레이션 완료.")
            else:
                print("데이터베이스가 이미 최신 버전입니다.")

            s.commit()  # 모든 마이그레이션이 성공적으로 끝나면 최종 커밋
        except Exception as e:
            print(f"마이그레이션 중 오류 발생: {e}")
            s.rollback()  # 오류 발생 시 전체 롤백


def update_transaction_category(transaction_id: int, new_category_id: int):
    """거래 내역의 카테고리를 업데이트합니다."""
    conn = st.connection("supabase", type="sql")
    with conn.session as s:
        s.execute(
            text(
                'UPDATE "transaction" SET category_id = :new_category_id, is_manual_category = true WHERE id = :transaction_id'
            ),
            {"new_category_id": new_category_id, "transaction_id": transaction_id},
        )
        s.commit()


def update_transaction_description(transaction_id: int, new_description: str):
    """거래 내역의 설명을 업데이트합니다."""
    conn = st.connection("supabase", type="sql")
    with conn.session as s:
        s.execute(
            text(
                'UPDATE "transaction" SET description = :new_description WHERE id = :transaction_id'
            ),
            {"new_description": new_description, "transaction_id": transaction_id},
        )
        s.commit()


def update_transaction_party(transaction_id: int, new_party_id: int):
    """거래 내역의 거래처를 업데이트합니다."""
    conn = st.connection("supabase", type="sql")
    with conn.session as s:
        s.execute(
            text(
                'UPDATE "transaction" SET transaction_party_id = :new_party_id WHERE id = :transaction_id'
            ),
            {"new_party_id": new_party_id, "transaction_id": transaction_id},
        )
        s.commit()


def add_new_party(party_code: str, description: str):
    """새로운 거래처를 추가합니다."""
    conn = st.connection("supabase", type="sql")
    with conn.session as s:
        try:
            s.execute(
                text(
                    'INSERT INTO "transaction_party" (party_code, description) VALUES (:party_code, :description)'
                ),
                {"party_code": party_code, "description": description},
            )
            s.commit()
            return True, SUCCESS_MSG
        except psycopg2.Error as e:
            s.rollback()
            if e.pgcode == "23505":  # Unique violation
                return False, f"오류: 거래처 코드 '{party_code}'가 이미 존재합니다."
            return False, f"데이터베이스 오류: {e}"
        except Exception as e:
            s.rollback()
            return False, f"알 수 없는 오류 발생: {e}"


def add_new_category(parent_id: int, new_code: str, new_desc: str, new_type: str):
    """새로운 카테고리를 추가하고 materialized_path를 업데이트합니다."""
    conn = st.connection("supabase", type="sql")
    with conn.session as s:
        try:
            # 1. 부모 카테고리 정보 가져오기 (세션 사용)
            parent_info = s.execute(
                text(
                    "SELECT depth, materialized_path_desc FROM category WHERE id = :parent_id"
                ),
                {"parent_id": parent_id},
            ).first()

            if not parent_info:
                return False, "선택된 부모 카테고리가 존재하지 않습니다."

            parent_depth, parent_path = parent_info
            new_depth = parent_depth + 1

            # 2. 새로운 카테고리 삽입 (RETURNING id 사용)
            insert_query = text(
                """
                INSERT INTO category (category_code, category_type, description, depth, parent_id, materialized_path_desc)
                VALUES (:new_code, :new_type, :new_desc, :new_depth, :parent_id, 'TEMP')
                RETURNING id;
            """
            )
            new_id = s.execute(
                insert_query,
                {
                    "new_code": new_code,
                    "new_type": new_type,
                    "new_desc": new_desc,
                    "new_depth": new_depth,
                    "parent_id": parent_id,
                },
            ).scalar_one()

            # 3. materialized_path 업데이트
            new_path = f"{parent_path}-{new_id}"
            s.execute(
                text(
                    "UPDATE category SET materialized_path_desc = :new_path WHERE id = :new_id"
                ),
                {"new_path": new_path, "new_id": new_id},
            )
            s.commit()
            return True, SUCCESS_MSG
        except psycopg2.Error as e:
            s.rollback()
            if e.pgcode == "23505":
                return (
                    False,
                    f"오류: 카테고리 코드 '{new_code}'가 이미 존재할 수 있습니다.",
                )
            return False, f"데이터베이스 오류: {e}"
        except Exception as e:
            s.rollback()
            return False, f"알 수 없는 오류 발생: {e}"


def rebuild_category_paths():
    """모든 카테고리의 materialized_path를 다시 계산하여 업데이트합니다."""
    conn = st.connection("supabase", type="sql")
    with conn.session as s:
        try:
            # 세션을 통해 모든 카테고리 정보를 가져옵니다.
            all_categories = (
                s.execute(text("SELECT id, parent_id FROM category")).mappings().all()
            )
            if not all_categories:
                return 0, "처리할 카테고리가 없습니다."

            df = pd.DataFrame(all_categories)
            parent_map = pd.Series(df.parent_id.values, index=df.id).to_dict()

            update_data = []
            for cat_id in df["id"]:
                path_segments, current_id, visited = [], cat_id, set()
                while (
                    pd.notna(current_id)
                    and current_id in parent_map
                    and current_id not in visited
                ):
                    visited.add(current_id)
                    path_segments.insert(0, str(int(current_id)))
                    current_id = parent_map.get(current_id)

                new_path = "-".join(path_segments)
                update_data.append({"new_path": new_path, "cat_id": cat_id})

            # executemany로 성능 향상
            if update_data:
                s.execute(
                    text(
                        "UPDATE category SET materialized_path_desc = :new_path WHERE id = :cat_id"
                    ),
                    update_data,
                )
            s.commit()
            return len(update_data), "모든 카테고리 경로를 성공적으로 재계산했습니다."
        except Exception as e:
            s.rollback()
            return 0, f"오류 발생: {e}"


def update_init_balance_and_log(account_id: int, change_amount: int):
    """계좌의 초기 잔액을 업데이트합니다."""
    conn = st.connection("supabase", type="sql")
    with conn.session as s:
        try:
            # 동시성 문제를 방지하기 위해 FOR UPDATE 사용
            account_exists = s.execute(
                text("SELECT 1 FROM accounts WHERE id = :account_id FOR UPDATE"),
                {"account_id": account_id},
            ).scalar_one_or_none()

            if not account_exists:
                raise ValueError(f"Account with ID {account_id} not found.")

            s.execute(
                text(
                    "UPDATE accounts SET initial_balance = :change_amount WHERE id = :account_id"
                ),
                {"change_amount": change_amount, "account_id": account_id},
            )
            s.commit()
        except Exception as e:
            s.rollback()
            raise e


def update_balance_and_log(
    account_id: int, change_amount: int, reason: str, session: Session
):
    """
    계좌 잔액을 업데이트하고 히스토리를 기록합니다. (트랜잭션 세이프)
    외부에서 전달받은 세션 내에서 모든 작업을 수행합니다.
    """
    # 1. 현재 잔액 가져오기 (FOR UPDATE로 행을 잠가 동시성 문제 방지)
    select_query = text(
        "SELECT balance FROM accounts WHERE id = :account_id FOR UPDATE"
    )
    previous_balance = session.execute(
        select_query, {"account_id": account_id}
    ).scalar_one_or_none()

    if previous_balance is None:
        raise ValueError(f"Account with ID {account_id} not found.")

    new_balance = previous_balance + change_amount

    # 2. 잔액 업데이트
    update_query = text(
        "UPDATE accounts SET balance = :new_balance WHERE id = :account_id"
    )
    session.execute(
        update_query, {"new_balance": new_balance, "account_id": account_id}
    )

    # 3. 변경 이력 기록
    history_query = text(
        """
        INSERT INTO account_balance_history 
            (account_id, change_date, previous_balance, change_amount, new_balance, reason)
        VALUES (:account_id, :change_date, :previous_balance, :change_amount, :new_balance, :reason)
    """
    )
    session.execute(
        history_query,
        {
            "account_id": account_id,
            "change_date": datetime.now(),
            "previous_balance": previous_balance,
            "change_amount": change_amount,
            "new_balance": new_balance,
            "reason": reason,
        },
    )


def reclassify_expense(transaction_id: int, linked_account_id: int):
    """'지출' 거래를 '이체' 또는 '투자'로 재분류합니다."""
    conn = st.connection("supabase", type="sql")
    with conn.session as s:
        try:
            # 1. 거래 및 계좌 정보 조회 (세션 사용)
            trans_info = s.execute(
                text(
                    'SELECT transaction_amount, type FROM "transaction" WHERE id = :tid'
                ),
                {"tid": transaction_id},
            ).first()
            linked_account_info = s.execute(
                text(
                    "SELECT account_type, is_investment FROM accounts WHERE id = :lid"
                ),
                {"lid": linked_account_id},
            ).first()

            if not trans_info or not linked_account_info:
                return False, "거래 또는 대상 계좌 정보를 찾을 수 없습니다."

            amount, current_type = trans_info
            _, is_investment = linked_account_info

            if current_type != "EXPENSE":
                return (
                    False,
                    f"'{current_type}' 타입의 거래는 '이체'로 변경할 수 없습니다.",
                )

            # 2. 새로운 타입과 카테고리 결정
            new_type = "INVEST" if is_investment else "TRANSFER"
            category_code = "INVESTMENT" if is_investment else "CARD_PAYMENT"

            new_category_id = s.execute(
                text("SELECT id FROM category WHERE category_code = :code"),
                {"code": category_code},
            ).scalar_one_or_none()

            if not new_category_id:
                return (
                    False,
                    f"재분류에 필요한 '{category_code}' 카테고리를 찾을 수 없습니다.",
                )

            # 3. 거래 내역 업데이트
            s.execute(
                text(
                    'UPDATE "transaction" SET type = :new_type, category_id = :cat_id, linked_account_id = :link_id WHERE id = :trans_id'
                ),
                {
                    "new_type": new_type,
                    "cat_id": new_category_id,
                    "link_id": linked_account_id,
                    "trans_id": transaction_id,
                },
            )

            # 4. 잔액 업데이트 (수정된 update_balance_and_log 함수 호출)
            reason = f"거래 ID {transaction_id}: '{new_type}'(으)로 재분류"
            update_balance_and_log(linked_account_id, amount, reason, session=s)

            s.commit()
            return (
                True,
                f"ID {transaction_id}가 '{new_type}'(으)로 성공적으로 재분류되었습니다.",
            )
        except Exception as e:
            s.rollback()
            return False, f"작업 중 오류 발생: {e}"


def add_new_account(name: str, account_type: str, is_asset: bool, initial_balance: int):
    """새로운 계좌를 추가합니다."""
    conn = st.connection("supabase", type="sql")
    with conn.session as s:
        try:
            s.execute(
                text(
                    "INSERT INTO accounts (name, account_type, is_asset, initial_balance, balance) VALUES (:name, :type, :is_asset, :init, :balance)"
                ),
                {
                    "name": name,
                    "type": account_type,
                    "is_asset": is_asset,
                    "init": initial_balance,
                    "balance": initial_balance,
                },
            )
            s.commit()
            return True, SUCCESS_MSG
        except psycopg2.Error as e:
            s.rollback()
            if e.pgcode == "23505":
                return False, f"오류: 계좌 이름 '{name}'이(가) 이미 존재합니다."
            return False, f"데이터베이스 오류: {e}"
        except Exception as e:
            s.rollback()
            return False, f"오류 발생: {e}"


def reclassify_all_transfers():
    """모든 은행 지출 내역을 검사하여 이체 거래를 자동으로 재분류합니다."""
    conn = st.connection("supabase", type="sql")
    with conn.session as s:
        df = pd.DataFrame(
            s.execute(
                text(
                    "SELECT * FROM \"transaction\" WHERE transaction_type = 'BANK' AND type = 'EXPENSE'"
                )
            )
            .mappings()
            .all()
        )
        if df.empty:
            return "재분류할 은행 지출 내역이 없습니다."

        linked_account_id_series = identify_transfers(df)
        is_transfer_mask = (linked_account_id_series != 0) & (
            linked_account_id_series.notna()
        )
        df_to_update = df[is_transfer_mask].copy()

        if df_to_update.empty:
            return "이체로 재분류할 거래를 찾지 못했습니다."

        df_to_update["linked_account_id"] = linked_account_id_series[is_transfer_mask]

        card_payment_cat_id = s.execute(
            text("SELECT id FROM category WHERE category_code = 'CARD_PAYMENT'")
        ).scalar_one()

        update_params = [
            {
                "category_id": int(card_payment_cat_id),
                "linked_account_id": int(row["linked_account_id"]),
                "transaction_id": int(row["id"]),
            }
            for _, row in df_to_update.iterrows()
        ]

        if update_params:
            s.execute(
                text(
                    "UPDATE \"transaction\" SET type = 'TRANSFER', category_id = :category_id, linked_account_id = :linked_account_id WHERE id = :transaction_id"
                ),
                update_params,
            )
        s.commit()
        return f"총 {len(update_params)}건의 거래를 '이체'로 재분류했습니다."


def recategorize_uncategorized():
    """미분류된 거래 내역에 대해 규칙 엔진을 다시 실행하여 카테고리를 재분류합니다."""
    conn = st.connection("supabase", type="sql")
    with conn.session as s:
        query = text(
            """
            SELECT t.* FROM "transaction" t
            JOIN category c ON t.category_id = c.id
            WHERE c.category_code = 'UNCATEGORIZED' AND t.is_manual_category = false
        """
        )
        uncategorized_df = pd.DataFrame(s.execute(query).mappings().all())

        if uncategorized_df.empty:
            return "카테고리를 재분류할 대상이 없습니다."

        default_cat_id = uncategorized_df["category_id"].iloc[0]
        categorized_df = run_rule_engine(uncategorized_df, default_cat_id)

        # 실제로 카테고리가 변경된 내역만 추출
        updates_df = categorized_df[categorized_df["category_id"] != default_cat_id]

        if updates_df.empty:
            return "새롭게 분류된 거래가 없습니다."

        update_params = [
            {"category_id": int(row["category_id"]), "transaction_id": int(row["id"])}
            for _, row in updates_df.iterrows()
        ]

        if update_params:
            s.execute(
                text(
                    'UPDATE "transaction" SET category_id = :category_id WHERE id = :transaction_id'
                ),
                update_params,
            )
        s.commit()
        return f"총 {len(update_params)}건의 거래에 카테고리 규칙을 재적용했습니다."
