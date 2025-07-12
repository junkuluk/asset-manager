import os
from datetime import datetime
import streamlit as st
import pandas as pd
import psycopg2
from sqlalchemy import text
from sqlalchemy.orm import Session

import config
from analysis import run_rule_engine, identify_transfers

# 데이터베이스의 최신 스키마 버전 정의
LATEST_DB_VERSION = 4
# 성공 메시지 상수
SUCCESS_MSG = "성공적으로 추가되었습니다."


def run_migrations(migrations_path=config.SCHEMA_PATH):
    """
    데이터베이스 스키마 마이그레이션을 실행.
    현재 데이터베이스 버전을 확인하고, 최신 버전까지 순차적으로 마이그레이션 스크립트를 적용.

    Args:
        migrations_path (str): 마이그레이션 SQL 스크립트 파일이 위치한 경로.
    """

    # Supabase 데이터베이스 연결
    conn = st.connection("supabase", type="sql")
    # 데이터베이스 세션 시작
    with conn.session as s:
        try:
            # schema_version 테이블이 없으면 생성
            s.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL PRIMARY KEY);"
                )
            )
            # 현재 데이터베이스 스키마 버전 조회
            current_version_result = s.execute(
                text("SELECT version FROM schema_version LIMIT 1;")
            ).scalar_one_or_none()

            # 버전 정보가 없는 경우 초기값(0) 삽입
            if current_version_result is None:
                s.execute(text("INSERT INTO schema_version (version) VALUES (0)"))
                current_version = 0
            else:
                current_version = current_version_result

            print(f"현재 DB 버전: {current_version}, 최신 버전: {LATEST_DB_VERSION}")

            # 현재 버전이 최신 버전보다 낮은 경우 마이그레이션 실행
            if current_version < LATEST_DB_VERSION:
                print("데이터베이스 마이그레이션을 시작합니다...")
                # 현재 버전 다음부터 최신 버전까지 순회하며 마이그레이션 스크립트 적용
                for v in range(current_version + 1, LATEST_DB_VERSION + 1):
                    # 중첩 트랜잭션 시작 (각 마이그레이션 스크립트는 별도의 트랜잭션으로 처리)
                    with s.begin_nested():
                        # 해당 버전의 마이그레이션 SQL 스크립트 파일 경로 생성
                        script_path = os.path.normpath(
                            os.path.join(migrations_path, f"v{v}.sql")
                        )
                        print(f"마이그레이션 파일 실행: {script_path}")
                        # SQL 스크립트 파일 읽기
                        with open(script_path, "r", encoding="utf-8") as f:
                            sql_script = f.read()

                        # 스크립트 내용이 비어있지 않은 경우 실행
                        if sql_script.strip():
                            s.execute(text(sql_script))

                        # 스키마 버전 업데이트
                        s.execute(
                            text("UPDATE schema_version SET version = :version"),
                            {"version": v},
                        )
                print(f"버전 {LATEST_DB_VERSION}까지 마이그레이션 완료.")
            else:
                print("데이터베이스가 이미 최신 버전입니다.")

            s.commit()  # 모든 마이그레이션 작업 커밋
        except Exception as e:
            print(f"마이그레이션 중 오류 발생: {e}")
            s.rollback()  # 오류 발생 시 모든 변경사항 롤백


def update_transaction_category(transaction_id: int, new_category_id: int):
    """
    특정 거래의 카테고리를 업데이트.

    Args:
        transaction_id (int): 업데이트할 거래의 ID.
        new_category_id (int): 새로 설정할 카테고리 ID.
    """

    # Supabase 데이터베이스 연결
    conn = st.connection("supabase", type="sql")
    # 데이터베이스 세션 시작
    with conn.session as s:
        # 'transaction' 테이블의 'category_id'와 'is_manual_category' 컬럼 업데이트
        s.execute(
            text(
                'UPDATE "transaction" SET category_id = :new_category_id, is_manual_category = true WHERE id = :transaction_id'
            ),
            {"new_category_id": new_category_id, "transaction_id": transaction_id},
        )
        s.commit()  # 변경사항 커밋


def update_transaction_description(transaction_id: int, new_description: str):
    """
    특정 거래의 설명을 업데이트.

    Args:
        transaction_id (int): 업데이트할 거래의 ID.
        new_description (str): 새로 설정할 설명.
    """

    # Supabase 데이터베이스 연결
    conn = st.connection("supabase", type="sql")
    # 데이터베이스 세션 시작
    with conn.session as s:
        # 'transaction' 테이블의 'description' 컬럼 업데이트
        s.execute(
            text(
                'UPDATE "transaction" SET description = :new_description WHERE id = :transaction_id'
            ),
            {"new_description": new_description, "transaction_id": transaction_id},
        )
        s.commit()  # 변경사항 커밋


def update_transaction_party(transaction_id: int, new_party_id: int):
    """
    특정 거래의 거래처 ID를 업데이트.

    Args:
        transaction_id (int): 업데이트할 거래의 ID.
        new_party_id (int): 새로 설정할 거래처 ID.
    """

    # Supabase 데이터베이스 연결
    conn = st.connection("supabase", type="sql")
    # 데이터베이스 세션 시작
    with conn.session as s:
        # 'transaction' 테이블의 'transaction_party_id' 컬럼 업데이트
        s.execute(
            text(
                'UPDATE "transaction" SET transaction_party_id = :new_party_id WHERE id = :transaction_id'
            ),
            {"new_party_id": new_party_id, "transaction_id": transaction_id},
        )
        s.commit()  # 변경사항 커밋


def add_new_party(party_code: str, description: str):
    """
    새로운 거래처를 데이터베이스에 추가.

    Args:
        party_code (str): 새로운 거래처 코드 (고유해야 함).
        description (str): 새로운 거래처 설명.

    Returns:
        tuple: (성공 여부: bool, 메시지: str)
    """
    # Supabase 데이터베이스 연결
    conn = st.connection("supabase", type="sql")
    # 데이터베이스 세션 시작
    with conn.session as s:
        try:
            # 'transaction_party' 테이블에 새로운 거래처 삽입
            s.execute(
                text(
                    'INSERT INTO "transaction_party" (party_code, description) VALUES (:party_code, :description)'
                ),
                {"party_code": party_code, "description": description},
            )
            s.commit()  # 변경사항 커밋
            return True, SUCCESS_MSG
        except psycopg2.Error as e:
            s.rollback()  # 오류 발생 시 롤백
            # PostgreSQL 고유 제약 조건 위반 오류 (duplicate key)
            if e.pgcode == "23505":
                return False, f"오류: 거래처 코드 '{party_code}'가 이미 존재합니다."
            return False, f"데이터베이스 오류: {e}"
        except Exception as e:
            s.rollback()  # 오류 발생 시 롤백
            return False, f"알 수 없는 오류 발생: {e}"


def add_new_category(parent_id: int, new_code: str, new_desc: str, new_type: str):
    """
    새로운 카테고리를 데이터베이스에 추가.
    계층 구조를 위해 부모 카테고리 정보와 경로(materialized_path_desc)를 업데이트.

    Args:
        parent_id (int): 부모 카테고리 ID.
        new_code (str): 새로운 카테고리 코드 (고유해야 함).
        new_desc (str): 새로운 카테고리 설명.
        new_type (str): 새로운 카테고리 유형.

    Returns:
        tuple: (성공 여부: bool, 메시지: str)
    """

    # Supabase 데이터베이스 연결
    conn = st.connection("supabase", type="sql")
    # 데이터베이스 세션 시작
    with conn.session as s:
        try:
            # 부모 카테고리의 깊이와 경로 정보 조회
            parent_info = s.execute(
                text(
                    "SELECT depth, materialized_path_desc FROM category WHERE id = :parent_id"
                ),
                {"parent_id": parent_id},
            ).first()

            # 부모 카테고리가 존재하지 않는 경우 오류 반환
            if not parent_info:
                return False, "선택된 부모 카테고리가 존재하지 않습니다."

            parent_depth, parent_path = parent_info
            new_depth = parent_depth + 1  # 새로운 카테고리의 깊이 설정

            # 'category' 테이블에 새로운 카테고리 삽입 후 ID 반환
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

            # 새로운 카테고리의 materialized path 생성 및 업데이트
            new_path = f"{parent_path}-{new_id}"
            s.execute(
                text(
                    "UPDATE category SET materialized_path_desc = :new_path WHERE id = :new_id"
                ),
                {"new_path": new_path, "new_id": new_id},
            )
            s.commit()  # 변경사항 커밋
            return True, SUCCESS_MSG
        except psycopg2.Error as e:
            s.rollback()  # 오류 발생 시 롤백
            # PostgreSQL 고유 제약 조건 위반 오류 (duplicate key)
            if e.pgcode == "23505":
                return (
                    False,
                    f"오류: 카테고리 코드 '{new_code}'가 이미 존재할 수 있습니다.",
                )
            return False, f"데이터베이스 오류: {e}"
        except Exception as e:
            s.rollback()  # 오류 발생 시 롤백
            return False, f"알 수 없는 오류 발생: {e}"


def rebuild_category_paths():
    """
    모든 카테고리의 계층 경로(materialized_path_desc)를 재계산하여 업데이트.
    데이터베이스에 저장된 카테고리 관계를 기반으로 올바른 경로를 구축.

    Returns:
        tuple: (업데이트된 행 수: int, 메시지: str)
    """
    # Supabase 데이터베이스 연결
    conn = st.connection("supabase", type="sql")
    # 데이터베이스 세션 시작
    with conn.session as s:
        try:
            # 모든 카테고리 ID와 부모 ID 조회
            all_categories = (
                s.execute(text("SELECT id, parent_id FROM category")).mappings().all()
            )
            if not all_categories:
                return 0, "처리할 카테고리가 없습니다."

            # 데이터프레임으로 변환하여 부모 ID를 맵핑 딕셔너리 생성
            df = pd.DataFrame(all_categories)
            parent_map = pd.Series(df.parent_id.values, index=df.id).to_dict()

            update_data = []
            # 각 카테고리에 대해 경로를 역추적하여 재구축
            for cat_id in df["id"]:
                path_segments, current_id, visited = [], cat_id, set()
                while (
                    pd.notna(current_id)  # 현재 ID가 NaN이 아니고
                    and current_id in parent_map  # 부모 맵에 존재하며
                    and current_id not in visited  # 방문하지 않은 경우
                ):
                    visited.add(current_id)  # 방문한 ID 추가
                    path_segments.insert(
                        0, str(int(current_id))
                    )  # 경로 세그먼트의 시작에 추가
                    current_id = parent_map.get(current_id)  # 다음 부모 ID로 이동

                new_path = "-".join(path_segments)  # 재구축된 경로 생성
                update_data.append({"new_path": new_path, "cat_id": cat_id})

            if update_data:
                # 모든 업데이트 데이터를 일괄적으로 실행
                s.execute(
                    text(
                        "UPDATE category SET materialized_path_desc = :new_path WHERE id = :cat_id"
                    ),
                    update_data,
                )
            s.commit()  # 변경사항 커밋
            return len(update_data), "모든 카테고리 경로를 성공적으로 재계산했습니다."
        except Exception as e:
            s.rollback()  # 오류 발생 시 롤백
            return 0, f"오류 발생: {e}"


def update_init_balance_and_log(account_id: int, change_amount: int):
    """
    계좌의 초기 잔액을 업데이트.

    Args:
        account_id (int): 업데이트할 계좌 ID.
        change_amount (int): 새로운 초기 잔액.
    """
    # Supabase 데이터베이스 연결
    conn = st.connection("supabase", type="sql")
    # 데이터베이스 세션 시작
    with conn.session as s:
        try:
            # 계좌 존재 여부 확인 및 락 (FOR UPDATE)
            account_exists = s.execute(
                text("SELECT 1 FROM accounts WHERE id = :account_id FOR UPDATE"),
                {"account_id": account_id},
            ).scalar_one_or_none()

            # 계좌가 존재하지 않는 경우 ValueError 발생
            if not account_exists:
                raise ValueError(f"Account with ID {account_id} not found.")

            # 계좌의 초기 잔액 업데이트
            s.execute(
                text(
                    "UPDATE accounts SET initial_balance = :change_amount WHERE id = :account_id"
                ),
                {"change_amount": change_amount, "account_id": account_id},
            )
            s.commit()  # 변경사항 커밋
        except Exception as e:
            s.rollback()  # 오류 발생 시 롤백
            raise e  # 예외 다시 발생


def update_balance_and_log(
    account_id: int, change_amount: int, reason: str, session: Session
):
    """
    계좌의 현재 잔액을 업데이트하고 잔액 변경 내역을 로그에 기록.
    이 함수는 외부 트랜잭션 세션 내에서 호출되어야 함.

    Args:
        account_id (int): 업데이트할 계좌 ID.
        change_amount (int): 잔액 변경 금액.
        reason (str): 잔액 변경 사유.
        session (Session): SQLAlchemy 세션 객체 (외부에서 전달).
    """

    # 계좌의 현재 잔액 조회 (락 설정)
    select_query = text(
        "SELECT balance FROM accounts WHERE id = :account_id FOR UPDATE"
    )
    previous_balance = session.execute(
        select_query, {"account_id": account_id}
    ).scalar_one_or_none()

    # 계좌가 존재하지 않는 경우 ValueError 발생
    if previous_balance is None:
        raise ValueError(f"Account with ID {account_id} not found.")

    new_balance = previous_balance + change_amount  # 새로운 잔액 계산

    # 계좌의 현재 잔액 업데이트
    update_query = text(
        "UPDATE accounts SET balance = :new_balance WHERE id = :account_id"
    )
    session.execute(
        update_query, {"new_balance": new_balance, "account_id": account_id}
    )

    # 계좌 잔액 변경 이력 테이블에 기록
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
            "change_date": datetime.now(),  # 현재 시간 기록
            "previous_balance": previous_balance,
            "change_amount": change_amount,
            "new_balance": new_balance,
            "reason": reason,
        },
    )


def reclassify_expense(transaction_id: int, linked_account_id: int):
    """
    특정 지출 거래를 이체(TRANSFER) 또는 투자(INVEST) 거래로 재분류.
    관련 계좌의 잔액도 업데이트.

    Args:
        transaction_id (int): 재분류할 거래의 ID.
        linked_account_id (int): 연결될 계좌의 ID.

    Returns:
        tuple: (성공 여부: bool, 메시지: str)
    """
    # Supabase 데이터베이스 연결
    conn = st.connection("supabase", type="sql")
    # 데이터베이스 세션 시작
    with conn.session as s:
        try:
            # 거래 금액 및 현재 거래 유형 조회
            trans_info = s.execute(
                text(
                    'SELECT transaction_amount, type FROM "transaction" WHERE id = :tid'
                ),
                {"tid": transaction_id},
            ).first()
            # 연결될 계좌의 유형 및 투자 계좌 여부 조회
            linked_account_info = s.execute(
                text(
                    "SELECT account_type, is_investment FROM accounts WHERE id = :lid"
                ),
                {"lid": linked_account_id},
            ).first()

            # 거래 또는 대상 계좌 정보가 없는 경우 오류 반환
            if not trans_info or not linked_account_info:
                return False, "거래 또는 대상 계좌 정보를 찾을 수 없습니다."

            amount, current_type = trans_info
            _, is_investment = linked_account_info

            # 현재 거래 유형이 'EXPENSE'가 아니면 재분류 불가
            if current_type != "EXPENSE":
                return (
                    False,
                    f"'{current_type}' 타입의 거래는 '이체'로 변경할 수 없습니다.",
                )

            # 연결될 계좌가 투자 계좌인지에 따라 새로운 유형 및 카테고리 코드 결정
            new_type = "INVEST" if is_investment else "TRANSFER"
            category_code = "INVESTMENT" if is_investment else "CARD_PAYMENT"

            # 새로운 카테고리 ID 조회
            new_category_id = s.execute(
                text("SELECT id FROM category WHERE category_code = :code"),
                {"code": category_code},
            ).scalar_one_or_none()

            # 필요한 카테고리를 찾을 수 없는 경우 오류 반환
            if not new_category_id:
                return (
                    False,
                    f"재분류에 필요한 '{category_code}' 카테고리를 찾을 수 없습니다.",
                )

            # 'transaction' 테이블의 유형, 카테고리, 연결 계좌 ID 업데이트
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

            # 연결된 계좌의 잔액 업데이트 및 로그 기록
            reason = f"거래 ID {transaction_id}: '{new_type}'(으)로 재분류"
            update_balance_and_log(linked_account_id, amount, reason, session=s)

            s.commit()  # 변경사항 커밋
            return (
                True,
                f"ID {transaction_id}가 '{new_type}'(으)로 성공적으로 재분류되었습니다.",
            )
        except Exception as e:
            s.rollback()  # 오류 발생 시 롤백
            return False, f"작업 중 오류 발생: {e}"


def add_new_account(name: str, account_type: str, is_asset: bool, initial_balance: int):
    """
    새로운 계좌를 데이터베이스에 추가.

    Args:
        name (str): 새로운 계좌 이름 (고유해야 함).
        account_type (str): 계좌 유형.
        is_asset (bool): 자산 계좌 여부.
        initial_balance (int): 초기 잔액.

    Returns:
        tuple: (성공 여부: bool, 메시지: str)
    """
    # Supabase 데이터베이스 연결
    conn = st.connection("supabase", type="sql")
    # 데이터베이스 세션 시작
    with conn.session as s:
        try:
            # 'accounts' 테이블에 새로운 계좌 삽입
            s.execute(
                text(
                    "INSERT INTO accounts (name, account_type, is_asset, initial_balance, balance) VALUES (:name, :type, :is_asset, :init, :balance)"
                ),
                {
                    "name": name,
                    "type": account_type,
                    "is_asset": is_asset,
                    "init": initial_balance,
                    "balance": initial_balance,  # 초기 잔액과 현재 잔액을 동일하게 설정
                },
            )
            s.commit()  # 변경사항 커밋
            return True, SUCCESS_MSG
        except psycopg2.Error as e:
            s.rollback()  # 오류 발생 시 롤백
            # PostgreSQL 고유 제약 조건 위반 오류 (duplicate key)
            if e.pgcode == "23505":
                return False, f"오류: 계좌 이름 '{name}'이(가) 이미 존재합니다."
            return False, f"데이터베이스 오류: {e}"
        except Exception as e:
            s.rollback()  # 오류 발생 시 롤백
            return False, f"오류 발생: {e}"


def reclassify_all_transfers():
    """
    모든 은행 지출 거래 중 이체로 식별될 수 있는 거래를 찾아 '이체'로 재분류.
    주로 카드 대금 결제와 같은 자동 이체 내역을 처리.

    Returns:
        str: 재분류 결과 메시지.
    """
    # Supabase 데이터베이스 연결
    conn = st.connection("supabase", type="sql")
    # 데이터베이스 세션 시작
    with conn.session as s:
        # 은행 거래 중 'EXPENSE' 유형의 모든 거래 조회
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

        # 이체 거래 식별 (analysis 모듈의 identify_transfers 함수 사용)
        linked_account_id_series = identify_transfers(df)
        # 이체로 식별된 거래만 마스킹
        is_transfer_mask = (linked_account_id_series != 0) & (
            linked_account_id_series.notna()
        )
        df_to_update = df[is_transfer_mask].copy()

        if df_to_update.empty:
            return "이체로 재분류할 거래를 찾지 못했습니다."

        # 재분류할 데이터프레임에 연결된 계좌 ID 추가
        df_to_update["linked_account_id"] = linked_account_id_series[is_transfer_mask]

        # 'CARD_PAYMENT' 카테고리 ID 조회
        card_payment_cat_id = s.execute(
            text("SELECT id FROM category WHERE category_code = 'CARD_PAYMENT'")
        ).scalar_one()

        # 업데이트에 필요한 파라미터 리스트 생성
        update_params = [
            {
                "category_id": int(card_payment_cat_id),
                "linked_account_id": int(row["linked_account_id"]),
                "transaction_id": int(row["id"]),
            }
            for _, row in df_to_update.iterrows()
        ]

        if update_params:
            # 'transaction' 테이블의 유형, 카테고리, 연결 계좌 ID를 일괄 업데이트
            s.execute(
                text(
                    "UPDATE \"transaction\" SET type = 'TRANSFER', category_id = :category_id, linked_account_id = :linked_account_id WHERE id = :transaction_id"
                ),
                update_params,  # 여러 행을 한 번에 업데이트 (executemany 최적화 가능성)
            )
        s.commit()  # 변경사항 커밋
        return f"총 {len(update_params)}건의 거래를 '이체'로 재분류했습니다."
