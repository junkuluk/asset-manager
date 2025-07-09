import os
from datetime import datetime
import streamlit as st
import pandas as pd
import psycopg2  # PostgreSQL 예외 처리를 위해 import
from sqlalchemy import text # 필요한 경우를 대비해 import, 현재 코드에서는 필수는 아님

import config
from analysis import run_rule_engine, identify_transfers

LATEST_DB_VERSION = 4
SUCCESS_MSG = "성공적으로 추가되었습니다."


def run_migrations(migrations_path=config.SCHEMA_PATH):
    """
    PostgreSQL 데이터베이스 마이그레이션을 실행합니다.
    세션(session)을 통해 execute를 호출하도록 수정되었습니다.
    """
    conn = st.connection("supabase", type="sql")
    
    # conn.session을 사용하여 세션 객체를 가져옵니다.
    s = conn.session

    try:
        # 1. 스키마 버전 관리 테이블 생성 (세션을 통해 실행)
        s.execute(text('''
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER NOT NULL PRIMARY KEY
            );
        '''))
        
        # CREATE TABLE 후 즉시 커밋하여 테이블이 인식되도록 합니다.
        s.commit() 
        print("schema_version 테이블 생성 또는 확인 및 커밋 완료.")
        
        # 2. 현재 버전 확인 (conn.query는 그대로 사용 가능)
        result = conn.query("SELECT version FROM schema_version LIMIT 1;", ttl=0)
        current_version = result['version'].iloc[0] if not result.empty else 0
        
        print(f"현재 DB 버전: {current_version}, 최신 버전: {LATEST_DB_VERSION}")

        if current_version < LATEST_DB_VERSION:
            print("데이터베이스 마이그레이션을 시작합니다...")

            for v in range(current_version + 1, LATEST_DB_VERSION + 1):
                # <<< 핵심 수정 사항: os.path.normpath 적용 >>>
                # os.path.join으로 생성된 경로를 정규화하여 올바른 구분자를 사용하도록 합니다.
                script_path = os.path.normpath(os.path.join(migrations_path, f"v{v}.sql"))
                
                print(f"마이그레이션 파일 로드 시도: {script_path}") # 디버깅을 위해 경로 출력

                with open(script_path, 'r', encoding='utf-8') as f:
                    sql_script = f.read()
                    sql_commands = [cmd.strip() for cmd in sql_script.split(';') if cmd.strip()]
                    
                    for command in sql_commands:
                        s.execute(text(command))

                # 버전 정보 업데이트 또는 삽입 (세션을 통해 실행)
                if current_version == 0 and result.empty: 
                    s.execute(text("INSERT INTO schema_version (version) VALUES (:version)"), {"version": v})
                else:
                    s.execute(text("UPDATE schema_version SET version = :version"), {"version": v})
                
                s.commit() # 각 버전의 마이그레이션이 성공하면 커밋
                print(f"버전 {v} 마이그레이션 성공.")
                current_version = v 
        
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
    # PostgreSQL 파라미터 바인딩은 %s를 사용하며, conn.execute는 자동으로 트랜잭션을 처리
    conn.execute(
        text('UPDATE "transaction" SET category_id = :new_category_id, is_manual_category = 1 WHERE id = :transaction_id'),
        {'new_category_id': new_category_id, 'transaction_id': transaction_id}
    )


def update_transaction_description(transaction_id, new_description):
    """거래 내역의 설명을 업데이트합니다."""
    conn = st.connection("supabase", type="sql")
    conn.execute(
        text('UPDATE "transaction" SET description = :new_description WHERE id = :transaction_id'),
        {'new_description': new_description, 'transaction_id': transaction_id}
    )


def update_transaction_party(transaction_id, new_party_id):
    """거래 내역의 거래처를 업데이트합니다."""
    conn = st.connection("supabase", type="sql")
    conn.execute(
        text('UPDATE "transaction" SET transaction_party_id = :new_party_id WHERE id = :transaction_id'),
        {'new_party_id': new_party_id, 'transaction_id': transaction_id}
    )


def add_new_party(party_code, description):
    """새로운 거래처를 추가합니다."""
    conn = st.connection("supabase", type="sql")
    try:
        conn.execute(
            text('INSERT INTO "transaction_party" (party_code, description) VALUES (:party_code, :description)'),
            {'party_code': party_code, 'description': description}
        )
        return True, SUCCESS_MSG
    except psycopg2.Error as e: # PostgreSQL의 IntegrityError는 psycopg2.Error의 하위 클래스
        conn.session.rollback() # conn.execute는 자동으로 커밋되므로, 오류 시 롤백을 위해 session 사용
        if e.pgcode == '23505': # Unique violation
             return False, f"오류: 거래처 코드 '{party_code}'가 이미 존재합니다."
        return False, f"오류 발생: {e}"
    except Exception as e:
        conn.session.rollback()
        return False, f"오류 발생: {e}"


def add_new_category(parent_id, new_code, new_desc, new_type):
    """새로운 카테고리를 추가하고 materialized_path를 업데이트합니다."""
    conn = st.connection("supabase", type="sql")
    s = conn.session # 여러 단계의 작업을 트랜잭션으로 묶기 위해 세션 사용
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
            VALUES (:new_code, :new_type, :new_desc, :new_depth, :parent_id, :temp_path)
            RETURNING id;
        """
        # s.execute를 사용하여 쿼리 실행 및 결과 가져오기
        # SQLAlchemy 2.0 스타일로 execute 결과를 사용
        result = s.execute(
            text(insert_query), 
            {
                'new_code': new_code, 'new_type': new_type, 'new_desc': new_desc, 
                'new_depth': new_depth, 'parent_id': parent_id, 'temp_path': 'TEMP'
            }
        )
        new_id = result.scalar_one() # RETURNING id의 결과는 scalar_one()으로 가져올 수 있음

        # 3. materialized_path 업데이트
        new_path = f"{parent_path}-{new_id}"
        s.execute(text("UPDATE category SET materialized_path_desc = :new_path WHERE id = :new_id"), 
                  {'new_path': new_path, 'new_id': new_id})
        
        s.commit()
        return True, SUCCESS_MSG
    except psycopg2.Error as e:
        s.rollback()
        if e.pgcode == '23505':
            return False, f"오류: 카테고리 코드 '{new_code}'가 이미 존재할 수 있습니다."
        return False, f"데이터베이스 오류: {e}"
    except Exception as e:
        s.rollback()
        return False, f"알 수 없는 오류 발생: {e}"


def rebuild_category_paths():
    """모든 카테고리의 materialized_path를 다시 계산하여 업데이트합니다."""
    conn = st.connection("supabase", type="sql")
    s = conn.session # 일괄 업데이트를 위해 세션 사용
    try:
        df = conn.query("SELECT id, parent_id FROM category", ttl=0)
        if df.empty:
            return 0, "처리할 카테고리가 없습니다."

        parent_map = pd.Series(df.parent_id.values, index=df.id).to_dict()
        
        update_data = []
        for cat_id in df['id']:
            path_segments = []
            current_id = cat_id
            
            # 부모 ID가 유효하고, parent_map에 있을 때까지 경로를 추적
            while pd.notna(current_id) and current_id in parent_map and parent_map.get(current_id) != current_id: # 순환 참조 방지
                path_segments.insert(0, str(int(current_id)))
                current_id = parent_map.get(current_id)
                if pd.isna(current_id): # 최상위 노드에 도달하면 중단
                    break
            
            # 최상위 노드(parent_id가 없는)의 경우, 자기 자신만 포함
            if pd.isna(parent_map.get(cat_id)) and not path_segments:
                path_segments.append(str(int(cat_id)))
            
            new_path = "-".join(path_segments)
            update_data.append({'new_path': new_path, 'cat_id': cat_id})
            
        updated_count = 0
        # executemany 대신 for loop와 session.execute 사용
        for data in update_data:
            result = s.execute(
                text("UPDATE category SET materialized_path_desc = :new_path WHERE id = :cat_id"), 
                data
            )
            updated_count += result.rowcount # rowcount로 업데이트된 행 수 확인

        s.commit()
        return updated_count, "모든 카테고리 경로를 성공적으로 재계산했습니다."
    except Exception as e:
        s.rollback()
        return 0, f"오류 발생: {e}"

def update_init_balance_and_log(account_id, change_amount, conn):
    """계좌의 초기 잔액을 업데이트합니다. (conn 객체를 인자로 받음)"""
    # conn.query는 DataFrame을 반환하므로 .iloc[0]을 통해 값 접근
    result = conn.query("SELECT initial_balance FROM accounts WHERE id = %s", params=(account_id,), ttl=0)
    if result.empty:
        raise ValueError(f"Account with ID {account_id} not found.")
    
    # conn.execute는 직접 딕셔너리 형태의 파라미터를 받을 수 있습니다.
    conn.execute(text("UPDATE accounts SET initial_balance = :change_amount WHERE id = :account_id"), 
                 {'change_amount': change_amount, 'account_id': account_id})


def update_balance_and_log(account_id, change_amount, reason, conn):
    """계좌 잔액을 업데이트하고 히스토리를 기록합니다. (conn 객체를 인자로 받음)"""
    # 1. 현재 잔액 가져오기
    result = conn.query("SELECT balance FROM accounts WHERE id = %s", params=(account_id,), ttl=0)
    if result.empty:
        raise ValueError(f"Account with ID {account_id} not found.")

    previous_balance = result['balance'].iloc[0]
    new_balance = previous_balance + change_amount

    # 2. 잔액 업데이트
    conn.execute(text("UPDATE accounts SET balance = :new_balance WHERE id = :account_id"), 
                 {'new_balance': new_balance, 'account_id': account_id})

    # 3. 변경 이력 기록
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    history_query = """
        INSERT INTO account_balance_history 
            (account_id, change_date, previous_balance, change_amount, new_balance, reason)
        VALUES (:account_id, :now_str, :previous_balance, :change_amount, :new_balance, :reason)
    """
    conn.execute(text(history_query), {
        'account_id': account_id, 
        'now_str': now_str, 
        'previous_balance': previous_balance, 
        'change_amount': change_amount, 
        'new_balance': new_balance, 
        'reason': reason
    })


def reclassify_expense(transaction_id, linked_account_id):
    """'지출' 거래를 '이체' 또는 '투자'로 재분류합니다."""
    conn = st.connection("supabase", type="sql")
    s = conn.session # 여러 단계의 작업을 트랜잭션으로 묶기 위해 세션 사용
    try:
        # 1. 거래 정보 조회
        trans_df = conn.query('SELECT transaction_amount, type FROM "transaction" WHERE id = %s', params=(int(transaction_id),), ttl=0)
        linked_account_df = conn.query("SELECT account_type, is_investment FROM accounts WHERE id = %s", params=(int(linked_account_id),), ttl=0)

        if trans_df.empty or linked_account_df.empty:
            s.rollback()
            return False, "거래 또는 대상 계좌 정보를 찾을 수 없습니다."

        amount, current_type = trans_df.iloc[0]
        linked_account_type, is_investment = linked_account_df.iloc[0]

        if current_type != 'EXPENSE':
            s.rollback()
            return False, f"'{current_type}' 타입의 거래는 '이체'로 변경할 수 없습니다."

        # 2. 새로운 타입과 카테고리 결정
        if is_investment:
            new_type = 'INVEST'
            cat_df = conn.query("SELECT id FROM category WHERE category_code = %s", params=(linked_account_type,), ttl=0)
        else:
            new_type = 'TRANSFER'
            cat_df = conn.query("SELECT id FROM category WHERE category_code = 'CARD_PAYMENT'", ttl=0)
        
        if cat_df.empty:
            s.rollback()
            return False, "재분류에 필요한 카테고리를 찾을 수 없습니다."
        new_category_id = cat_df['id'].iloc[0]

        # 3. 거래 내역 업데이트
        update_query = text('UPDATE "transaction" SET type = :new_type, category_id = :new_category_id, linked_account_id = :linked_account_id WHERE id = :transaction_id')
        s.execute(update_query, {
            'new_type': new_type, 
            'new_category_id': new_category_id, 
            'linked_account_id': int(linked_account_id), 
            'transaction_id': int(transaction_id)
        })

        # 4. 잔액 업데이트 및 로그 기록 (이 함수는 내부적으로 conn.execute 사용)
        reason = f"거래 ID {transaction_id}: '{new_type}'(으)로 재분류"
        # update_balance_and_log 함수가 자체적으로 conn.execute를 사용하므로, 
        # 여기서는 별도로 session을 전달할 필요 없이 conn 객체만 넘겨주면 됩니다.
        update_balance_and_log(int(linked_account_id), amount, reason, conn)

        s.commit() # 모든 작업이 성공하면 커밋
        return True, f"ID {transaction_id}가 '{new_type}'(으)로 성공적으로 재분류되었습니다."
    except Exception as e:
        s.rollback() # 오류 발생 시 롤백
        return False, f"작업 중 오류 발생: {e}"


def add_new_account(name, account_type, is_asset, initial_balance):
    """새로운 계좌를 추가합니다."""
    conn = st.connection("supabase", type="sql")
    try:
        conn.execute(
            text("INSERT INTO accounts (name, account_type, is_asset, initial_balance, balance) VALUES (:name, :account_type, :is_asset, :initial_balance, :balance)"),
            {'name': name, 'account_type': account_type, 'is_asset': is_asset, 'initial_balance': initial_balance, 'balance': initial_balance} # 초기 잔액을 현재 잔액에도 설정
        )
        # 초기 잔액 설정에 대한 히스토리 로그는 필요 시 추가 구현
        return True, SUCCESS_MSG
    except psycopg2.Error as e:
        conn.session.rollback() # conn.execute는 자동으로 커밋되므로, 오류 시 롤백을 위해 session 사용
        if e.pgcode == '23505':
            return False, f"오류: 계좌 이름 '{name}'이(가) 이미 존재합니다."
        return False, f"데이터베이스 오류: {e}"
    except Exception as e:
        conn.session.rollback()
        return False, f"오류 발생: {e}"


def reclassify_all_transfers():
    """모든 은행 지출 내역을 검사하여 이체 거래를 자동으로 재분류합니다."""
    conn = st.connection("supabase", type="sql")
    s = conn.session # 일괄 업데이트를 위해 세션 사용
    
    # PostgreSQL에서 테이블 이름에 대소문자가 있거나 키워드와 겹칠 수 있는 경우 큰따옴표로 묶습니다.
    df = conn.query("SELECT * FROM \"transaction\" WHERE transaction_type = 'BANK' AND type = 'EXPENSE'", ttl=0)
    if df.empty:
        return "재분류할 은행 지출 내역이 없습니다."

    # identify_transfers 함수가 db_path 인자를 받지 않으므로 제거
    linked_account_id_series = identify_transfers(df) 
    is_transfer_mask = (linked_account_id_series != 0) & (linked_account_id_series.notna())

    df_to_update = df[is_transfer_mask].copy()
    if df_to_update.empty:
        return "이체로 재분류할 거래를 찾지 못했습니다."
        
    df_to_update['linked_account_id'] = linked_account_id_series[is_transfer_mask]

    card_payment_cat_df = conn.query("SELECT id FROM category WHERE category_code = 'CARD_PAYMENT'", ttl=0)
    if card_payment_cat_df.empty:
        s.rollback()
        return "카드 대금 카테고리를 찾을 수 없습니다."
    card_payment_cat_id = card_payment_cat_df['id'].iloc[0]

    # DB 업데이트 (for loop와 session.execute 사용)
    update_count = 0
    for _, row in df_to_update.iterrows():
        result = s.execute(
            text("UPDATE \"transaction\" SET type = 'TRANSFER', category_id = :category_id, linked_account_id = :linked_account_id WHERE id = :transaction_id"),
            {
                'category_id': int(card_payment_cat_id), 
                'linked_account_id': int(row['linked_account_id']), 
                'transaction_id': int(row['id'])
            }
        )
        update_count += result.rowcount
    
    s.commit()
    return f"총 {update_count}건의 거래를 '이체'로 재분류했습니다."


def recategorize_uncategorized():
    """미분류된 거래 내역에 대해 규칙 엔진을 다시 실행하여 카테고리를 재분류합니다."""
    conn = st.connection("supabase", type="sql")
    s = conn.session # 일괄 업데이트를 위해 세션 사용

    uncategorized_df = conn.query(text("""
        SELECT t.*
        FROM "transaction" t
        JOIN category c ON t.category_id = c.id
        WHERE c.category_code = 'UNCATEGORIZED' AND t.is_manual_category = false
    """), ttl=0)

    if uncategorized_df.empty:
        return "카테고리를 재분류할 대상이 없습니다."

    # 규칙 엔진 실행
    default_cat_id = uncategorized_df['category_id'].iloc[0]
    # run_rule_engine 함수가 db_path 인자를 받지 않으므로 제거
    categorized_df = run_rule_engine(uncategorized_df, default_cat_id) 

    # 변경된 부분만 업데이트 (for loop와 session.execute 사용)
    update_count = 0
    for _, row in categorized_df.iterrows():
        # 기존 코드에서 category_id를 int로 변환하고 있었으므로 유지
        if int(row['category_id']) != default_cat_id: # 실제로 카테고리가 변경된 경우에만 업데이트
            result = s.execute(
                text("UPDATE \"transaction\" SET category_id = :category_id WHERE id = :transaction_id"),
                {
                    'category_id': int(row['category_id']), 
                    'transaction_id': int(row['id'])
                }
            )
            update_count += result.rowcount
    
    s.commit()
    return f"총 {update_count}건의 거래에 카테고리 규칙을 재적용했습니다."