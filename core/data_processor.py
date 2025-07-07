import hashlib
import os
import sqlite3

import numpy as np
import pandas as pd

import config
from analysis import run_rule_engine, identify_transfers
from core.db_manager import update_balance_and_log
from core.db_queries import get_account_id_by_name


def _parse_shinhan(filepath):
    df = pd.read_excel(filepath)
    columns_map = {'카드구분': 'card_type', '거래일': 'transaction_date', '가맹점명': 'content', '금액': 'transaction_amount', '이용카드': 'card_name', '승인번호': 'card_approval_number'}
    df.rename(columns=columns_map, inplace=True)
    df['transaction_provider'] = 'SHINHAN_CARD'
    return df

def _parse_kookmin(filepath):
    use_cols = [0, 3, 4, 5, 13]
    standard_names = ['transaction_date', 'card_name', 'content', 'transaction_amount', 'card_approval_number']
    df = pd.read_excel(filepath, skiprows=6, usecols=use_cols, names=standard_names)
    df['card_type'] = '신용'
    df['transaction_provider'] = 'KUKMIN_CARD'
    return df

CARD_PARSERS = {
    'shinhan': _parse_shinhan,
    'kookmin': _parse_kookmin
}

def insert_card_transactions_from_excel(filepath, db_path=config.DB_PATH):

    filename = os.path.basename(filepath.name if hasattr(filepath, 'name') else filepath)
    card_company = next((key for key in CARD_PARSERS if key in filename.lower()), 'kookmin')

    if not card_company:
        print(f"지원하지 않는 카드사 파일입니다: {filename}")
        return 0

    try:
        parser_func = CARD_PARSERS[card_company]
        df = parser_func(filepath)
    except Exception as e:
        print(f"파일 파싱 중 오류 발생: {filename}, {e}")
        return 0

    df.dropna(subset=['transaction_date', 'content', 'transaction_amount'], inplace=True)
    if df.empty: return 0
    df['transaction_date'] = pd.to_datetime(df['transaction_date']).dt.strftime('%Y-%m-%d %H:%M:%S')
    df['transaction_amount'] = pd.to_numeric(df['transaction_amount'].astype(str).str.replace(',', ''), errors='coerce')
    df.dropna(subset=['transaction_amount'], inplace=True)
    df['transaction_amount'] = df['transaction_amount'].astype(int)
    df['card_approval_number'] = df['card_approval_number'].astype(str)

    # transaction_party_id는 아직 규칙이 없으므로 기본값(1)으로 설정
    df['transaction_party_id'] = 1
    # 트랜잭션 타입 등 고정값 컬럼 추가
    df['type'] = 'EXPENSE'
    df['transaction_type'] = 'CARD'

    conn_temp = sqlite3.connect(db_path)
    try:
        cursor = conn_temp.cursor()
        cursor.execute("SELECT id FROM category WHERE category_code = 'UNCATEGORIZED' AND category_type = 'EXPENSE'")
        result = cursor.fetchone()
        # 미분류 카테고리가 있으면 해당 ID를, 없으면 1(지출)을 기본값으로 사용
        default_cat_id = result[0] if result else 1
    finally:
        conn_temp.close()

    df = run_rule_engine(df, default_category_id=default_cat_id, db_path=db_path)

    # 1. 카드사 이름에 맞는 계좌 ID를 DB에서 조회
    shinhan_card_account_id = get_account_id_by_name('신한카드')
    kukmin_card_account_id = get_account_id_by_name('국민카드')

    # 2. DataFrame에 account_id 컬럼 추가
    df['account_id'] = np.where(
        df['transaction_provider'] == 'SHINHAN_CARD',
        shinhan_card_account_id,
        kukmin_card_account_id
    )

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    inserted_rows, skipped_rows = 0, 0

    for _, row in df.iterrows():
        try:
            cursor.execute(
                "SELECT t.id FROM \"transaction\" t JOIN \"card_transaction\" ct ON t.id = ct.id WHERE t.transaction_provider = ? AND ct.card_approval_number = ?",
                (row['transaction_provider'], row['card_approval_number']))

            if cursor.fetchone():
                skipped_rows += 1
                continue

            cursor.execute(
                """INSERT INTO "transaction"
                   (type, transaction_type, transaction_provider, category_id, transaction_party_id, transaction_date,
                    transaction_amount, content, account_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row['type'], row['transaction_type'], row['transaction_provider'],  row['category_id'],
                    row['transaction_party_id'], row['transaction_date'], row['transaction_amount'], row['content'],
                    row['account_id']))
            transaction_id = cursor.lastrowid

            cursor.execute(
                """
                INSERT INTO "card_transaction" (id, card_approval_number, card_type, card_name) VALUES (?, ?, ?, ?)
                """,
                (transaction_id, row['card_approval_number'], row['card_type'], row['card_name']))
            inserted_rows += 1

        except Exception as e:
            print(f"데이터 삽입 중 오류 발생: {e}")
            conn.rollback()

    conn.commit()
    conn.close()

    print(f"총 {inserted_rows}건 삽입, {skipped_rows}건은 중복으로 건너뜀.")

    return inserted_rows, skipped_rows


def insert_bank_transactions_from_excel(filepath, db_path=config.DB_PATH):
    try:
        df = pd.read_excel(filepath, skiprows=6,sheet_name=0)
        df.columns = df.columns.str.replace(r'\(원\)', '', regex=True).str.strip()
    except Exception as e:
        print(f"엑셀 파일 읽기 오류: {e}")
        return 0, 0

        # 1. DB 연결을 한번만 하고, with 구문으로 자동 관리
    with sqlite3.connect(db_path) as conn:
        try:
            cursor = conn.cursor()
            # --- 필요한 ID와 기존 해시값 미리 로드 ---
            existing_hashes = {row[0] for row in cursor.execute("SELECT unique_hash FROM bank_transaction")}
            bank_account_id = get_account_id_by_name('신한은행-110-227-963599')

            # 2. 안전하게 ID 조회
            transfer_cat_id = \
            (cursor.execute("SELECT id FROM category WHERE category_code = 'TRANSFER'").fetchone() or [None])[0]
            default_expense_cat_id = (cursor.execute(
                "SELECT id FROM category WHERE category_code = 'UNCATEGORIZED' AND category_type ='EXPENSE'").fetchone() or [
                                          None])[0]
            default_income_cat_id = (cursor.execute(
                "SELECT id FROM category WHERE category_code = 'UNCATEGORIZED' AND category_type ='INCOME'").fetchone() or [
                                         None])[0]

            if not all([bank_account_id, transfer_cat_id, default_expense_cat_id, default_income_cat_id]):
                print("오류: 필수 계좌 또는 카테고리 ID를 DB에서 찾을 수 없습니다.")
                return 0, 0

            df.dropna(subset=['거래일자', '거래시간'], inplace=True)
            date_str = pd.to_datetime(df['거래일자']).dt.strftime('%Y-%m-%d')
            time_str = df['거래시간'].astype(str)
            out_amount_str = df['출금'].fillna(0).astype(int).astype(str)
            in_amount_str = df['입금'].fillna(0).astype(int).astype(str)
            df['unique_hash'] = (date_str + '-' + time_str + '-' + out_amount_str + '-' + in_amount_str).apply(
                lambda x: hashlib.sha256(x.encode()).hexdigest())

            # 중복 제거
            original_rows = len(df)
            df = df[~df['unique_hash'].isin(existing_hashes)]
            skipped_count = original_rows - len(df)
            if df.empty:
                print(f"새로운 데이터가 없습니다. {skipped_count}건은 중복으로 건너뜁니다.")
                return 0, skipped_count

            # 3. 명확한 순서로 타입 및 카테고리 ID 할당
            df['amount'] = df['입금'].fillna(0) - df['출금'].fillna(0)
            df['transaction_amount'] = df['amount'].abs().astype(int)
            df['content'] = df['내용'].astype(str)

            # 이체 판별 엔진 실행: linked_account_id의 Series를 반환
            linked_account_id_series = identify_transfers(df, db_path)
            is_transfer_mask = (linked_account_id_series != 0) & (linked_account_id_series.notna())

            # 타입 및 카테고리 ID 설정
            df['type'] = np.where(df['amount'] > 0, 'INCOME', 'EXPENSE')
            df.loc[is_transfer_mask, 'type'] = 'TRANSFER'

            df['category_id'] = np.where(df['type'] == 'INCOME', default_income_cat_id, default_expense_cat_id)
            df.loc[is_transfer_mask, 'category_id'] = transfer_cat_id

            df['linked_account_id'] = linked_account_id_series


            # 카테고리 분류 규칙 엔진 실행 (TRANSFER가 아닌 행에 대해서만)
            expense_income_mask = (df['type'] != 'TRANSFER')
            if expense_income_mask.any():
                df_to_categorize = df[expense_income_mask].copy()
                categorized_subset = run_rule_engine(df_to_categorize, default_expense_cat_id, db_path)
                df.update(categorized_subset)

            inserted_count = 0

            for _, row in df.iterrows():
                    cursor.execute("""
                                   INSERT INTO "transaction" (type, transaction_type, transaction_provider, category_id,
                                                              transaction_party_id, transaction_date, transaction_amount,
                                                              content, account_id, linked_account_id)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,?)
                                   """, (
                                       row['type'], 'BANK', 'SHINHAN_BANK', row['category_id'], 1,
                                       pd.to_datetime(f"{row['거래일자']} {row['거래시간']}").strftime('%Y-%m-%d %H:%M:%S'),
                                       row['transaction_amount'], str(row.get('적요', '')) + ' / ' + str(row.get('내용', '')),
                                       bank_account_id,
                                       None if pd.isna(row['linked_account_id']) or row[
                                           'linked_account_id'] == 0 else int(row['linked_account_id'])
                                   ))
                    transaction_id = cursor.lastrowid
                    cursor.execute(
                        "INSERT INTO \"bank_transaction\" (id, unique_hash, branch, balance_amount) VALUES (?, ?, ?, ?)",
                        (transaction_id, row['unique_hash'], row.get('거래점'), row.get('잔액')))

                    # 잔액 업데이트
                    amount = row['transaction_amount']
                    reason = f"거래 ID {transaction_id}: {row['content']}"
                    if row['type'] == 'INCOME':
                        update_balance_and_log(bank_account_id, amount, reason, conn)
                    elif row['type'] == 'EXPENSE':
                        update_balance_and_log(bank_account_id, -amount, reason, conn)
                    elif row['type'] == 'TRANSFER':
                        update_balance_and_log(bank_account_id, -amount, f"이체 출금: {reason}", conn)
                        update_balance_and_log(int(row['linked_account_id']), amount, f"이체 입금: {reason}", conn)

                    inserted_count += 1

            conn.commit()
            return inserted_count, skipped_count

        except Exception as e:
            print(f"데이터 처리 중 오류 발생: {e}")
            conn.rollback()
            return 0, 0