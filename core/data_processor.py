import pandas as pd
import os
import sqlite3
from analysis import run_rule_engine

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

def insert_card_transactions_from_excel(filepath, db_path='asset_data.db'):

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

    # --- DB 저장을 위한 최종 준비 ---
    # transaction_party_id는 아직 규칙이 없으므로 기본값(1)으로 설정
    df['transaction_party_id'] = 1
    # 트랜잭션 타입 등 고정값 컬럼 추가
    df['type'] = 'EXPENSE'
    df['transaction_type'] = 'CARD'

    conn_temp = sqlite3.connect(db_path)
    try:
        cursor = conn_temp.cursor()
        cursor.execute("SELECT id FROM category WHERE category_code = 'UNCATEGORIZED'")
        result = cursor.fetchone()
        # 미분류 카테고리가 있으면 해당 ID를, 없으면 1(지출)을 기본값으로 사용
        default_cat_id = result[0] if result else 1
    finally:
        conn_temp.close()

    df = run_rule_engine(df, default_category_id=default_cat_id, db_path=db_path)

    print(df)

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
                "INSERT INTO \"transaction\" (type, transaction_type, transaction_provider, category_id, transaction_party_id, transaction_date, transaction_amount, content) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row['type'], row['transaction_type'], row['transaction_provider'],  row['category_id'],
                    row['transaction_party_id'], row['transaction_date'], row['transaction_amount'], row['content']))
            transaction_id = cursor.lastrowid

            cursor.execute(
                "INSERT INTO \"card_transaction\" (id, card_approval_number, card_type, card_name) VALUES (?, ?, ?, ?)",
                (transaction_id, row['card_approval_number'], row['card_type'], row['card_name']))
            inserted_rows += 1

        except Exception as e:
            print(f"데이터 삽입 중 오류 발생: {e}")
            conn.rollback()

    conn.commit()
    conn.close()

    print(f"총 {inserted_rows}건 삽입, {skipped_rows}건은 중복으로 건너뜀.")

    return inserted_rows, skipped_rows
