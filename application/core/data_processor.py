import hashlib
import os
import streamlit as st
import numpy as np
import pandas as pd
from sqlalchemy import text

# 다른 모듈들은 이미 올바르게 수정되었다고 가정합니다.
import config
from analysis import run_rule_engine, identify_transfers
from core.db_manager import update_balance_and_log
from core.db_queries import get_account_id_by_name


# --- 엑셀 파서 정의 (변경 없음) ---
def _parse_shinhan(filepath):
    """신한카드 엑셀 파일을 파싱합니다."""
    df = pd.read_excel(filepath)
    columns_map = {
        "카드구분": "card_type",
        "거래일": "transaction_date",
        "가맹점명": "content",
        "금액": "transaction_amount",
        "이용카드": "card_name",
        "승인번호": "card_approval_number",
    }
    df.rename(columns=columns_map, inplace=True)
    df["transaction_provider"] = "SHINHAN_CARD"
    return df


def _parse_kookmin(filepath):
    """국민카드 엑셀 파일을 파싱합니다."""
    use_cols = [0, 3, 4, 5, 13]
    standard_names = [
        "transaction_date",
        "card_name",
        "content",
        "transaction_amount",
        "card_approval_number",
    ]
    df = pd.read_excel(filepath, skiprows=6, usecols=use_cols, names=standard_names)
    df["card_type"] = "신용"
    df["transaction_provider"] = "KUKMIN_CARD"
    return df


CARD_PARSERS = {"shinhan": _parse_shinhan, "kookmin": _parse_kookmin}


def insert_card_transactions_from_excel(filepath):

    filename = os.path.basename(
        filepath.name if hasattr(filepath, "name") else filepath
    )

    # card_company = next((key for key in CARD_PARSERS if key in filename.lower()), None)
    card_company = next(
        (key for key in CARD_PARSERS if key in filename.lower()), "kookmin"
    )

    if not card_company:
        st.error(f"지원하지 않는 카드사 파일입니다: {filename}")
        return 0, 0

    try:
        df = CARD_PARSERS[card_company](filepath)
    except Exception as e:
        st.error(f"파일 파싱 중 오류 발생: {filename}, {e}")
        return 0, 0

    # --- 데이터 전처리 ---
    df.dropna(
        subset=["transaction_date", "content", "transaction_amount"], inplace=True
    )
    if df.empty:
        return 0, 0
    df["transaction_date"] = pd.to_datetime(df["transaction_date"]).dt.strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    df["transaction_amount"] = pd.to_numeric(
        df["transaction_amount"].astype(str).str.replace(",", ""), errors="coerce"
    )
    df.dropna(subset=["transaction_amount"], inplace=True)
    df["transaction_amount"] = df["transaction_amount"].astype(int)
    df["card_approval_number"] = df["card_approval_number"].astype(str)
    df["type"] = "EXPENSE"
    df["transaction_type"] = "CARD"
    df["transaction_party_id"] = 1  # 기본값

    # --- 규칙 엔진 실행 ---
    conn = st.connection("supabase", type="sql")
    cat_df = conn.query(
        "SELECT id FROM category WHERE category_code = 'UNCATEGORIZED' AND category_type = 'EXPENSE' LIMIT 1",
        ttl=0,
    )
    default_cat_id = cat_df["id"].iloc[0] if not cat_df.empty else 1

    df = run_rule_engine(df, default_category_id=default_cat_id)

    # --- 계좌 ID 매핑 ---
    shinhan_card_account_id = get_account_id_by_name("신한카드")
    kukmin_card_account_id = get_account_id_by_name("국민카드")
    assert shinhan_card_account_id is not None
    assert kukmin_card_account_id is not None
    df["account_id"] = np.where(
        df["transaction_provider"] == "SHINHAN_CARD",
        shinhan_card_account_id,
        kukmin_card_account_id,
    )

    # --- DB 삽입 (수정된 트랜잭션 블록) ---
    inserted_rows = 0
    skipped_rows = 0
    try:
        # with 블록이 끝나면 자동 commit, 오류 시 자동 rollback
        with conn.session as s:
            for _, row in df.iterrows():
                # 중복 확인
                check_query = text(
                    """
                    SELECT 1 FROM "transaction" t
                    JOIN "card_transaction" ct ON t.id = ct.id
                    WHERE t.transaction_provider = :provider AND ct.card_approval_number = :approval
                """
                )
                existing = s.execute(
                    check_query,
                    {
                        "provider": row["transaction_provider"],
                        "approval": row["card_approval_number"],
                    },
                ).first()

                if existing:
                    skipped_rows += 1
                    continue

                # transaction 삽입
                insert_trans_query = text(
                    """
                    INSERT INTO "transaction" (type, transaction_type, transaction_provider, category_id,
                                               transaction_party_id, transaction_date, transaction_amount, content, account_id)
                    VALUES (:type, :ttype, :provider, :cat_id, :party_id, :tdate, :amount, :content, :acc_id)
                    RETURNING id
                """
                )
                result = s.execute(
                    insert_trans_query,
                    {
                        "type": row["type"],
                        "ttype": row["transaction_type"],
                        "provider": row["transaction_provider"],
                        "cat_id": int(row["category_id"]),
                        "party_id": int(row["transaction_party_id"]),
                        "tdate": row["transaction_date"],
                        "amount": int(row["transaction_amount"]),
                        "content": row["content"],
                        "acc_id": int(row["account_id"]),
                    },
                )
                transaction_id = result.scalar_one()

                # card_transaction 삽입
                insert_card_query = text(
                    """
                    INSERT INTO "card_transaction" (id, card_approval_number, card_type, card_name)
                    VALUES (:id, :approval, :ctype, :cname)
                """
                )
                s.execute(
                    insert_card_query,
                    {
                        "id": transaction_id,
                        "approval": row["card_approval_number"],
                        "ctype": row["card_type"],
                        "cname": row["card_name"],
                    },
                )
                inserted_rows += 1

            # ✅ [수정] 모든 루프가 성공적으로 끝나면 최종 커밋
            s.commit()
            print("커밋 성공!")
    except Exception as e:
        st.error(f"데이터 삽입 중 오류 발생: {e}")
        return 0, 0

    return inserted_rows, skipped_rows


def insert_bank_transactions_from_excel(filepath):
    """
    은행 엑셀 파일을 읽어 거래 내역을 DB에 삽입합니다.
    효율적인 트랜잭션 처리를 위해 수정되었습니다.
    """
    try:
        df = pd.read_excel(filepath, skiprows=6, sheet_name=0)
        df.columns = df.columns.str.replace(r"\(원\)", "", regex=True).str.strip()
    except Exception as e:
        st.error(f"엑셀 파일 읽기 오류: {e}")
        return 0, 0

    conn = st.connection("supabase", type="sql")
    inserted_count = 0
    skipped_count = 0

    try:
        # --- 필요한 ID와 기존 해시값 미리 로드 ---
        existing_hashes_df = conn.query(
            "SELECT unique_hash FROM bank_transaction", ttl=0
        )
        existing_hashes = set(existing_hashes_df["unique_hash"])

        bank_account_id = get_account_id_by_name("신한은행-110-227-963599")
        transfer_cat_id = conn.query(
            "SELECT id FROM category WHERE category_code = 'TRANSFER'", ttl=0
        )["id"].iloc[0]
        default_expense_cat_id = conn.query(
            "SELECT id FROM category WHERE category_code = 'UNCATEGORIZED' AND category_type ='EXPENSE'",
            ttl=0,
        )["id"].iloc[0]
        default_income_cat_id = conn.query(
            "SELECT id FROM category WHERE category_code = 'UNCATEGORIZED' AND category_type ='INCOME'",
            ttl=0,
        )["id"].iloc[0]

        if not all(
            [
                bank_account_id,
                transfer_cat_id,
                default_expense_cat_id,
                default_income_cat_id,
            ]
        ):
            st.error("오류: 필수 계좌 또는 카테고리 ID를 DB에서 찾을 수 없습니다.")
            return 0, 0

        # --- 데이터 전처리 및 중복 제거 ---
        df.dropna(subset=["거래일자", "거래시간"], inplace=True)
        date_str = pd.to_datetime(df["거래일자"]).dt.strftime("%Y-%m-%d")
        time_str = df["거래시간"].astype(str)
        out_amount_str = df["출금"].fillna(0).astype(int).astype(str)
        in_amount_str = df["입금"].fillna(0).astype(int).astype(str)
        df["unique_hash"] = (
            date_str + "-" + time_str + "-" + out_amount_str + "-" + in_amount_str
        ).apply(lambda x: hashlib.sha256(x.encode()).hexdigest())

        original_rows = len(df)
        df = df[~df["unique_hash"].isin(existing_hashes)]
        skipped_count = original_rows - len(df)
        if df.empty:
            st.info(
                f"새로운 데이터가 없습니다. {skipped_count}건은 중복으로 건너뜁니다."
            )
            return 0, skipped_count

        # --- 타입 및 카테고리 분류 ---
        df["amount"] = df["입금"].fillna(0) - df["출금"].fillna(0)
        df["transaction_amount"] = df["amount"].abs().astype(int)

        linked_account_id_series = identify_transfers(df)
        is_transfer_mask = (linked_account_id_series != 0) & (
            linked_account_id_series.notna()
        )

        df["type"] = np.where(df["amount"] > 0, "INCOME", "EXPENSE")
        df.loc[is_transfer_mask, "type"] = "TRANSFER"
        df["category_id"] = np.where(
            df["type"] == "INCOME", default_income_cat_id, default_expense_cat_id
        )
        df.loc[is_transfer_mask, "category_id"] = transfer_cat_id
        df["linked_account_id"] = linked_account_id_series

        expense_income_mask = df["type"] != "TRANSFER"
        if expense_income_mask.any():
            df_to_categorize = df[expense_income_mask].copy()
            categorized_subset = run_rule_engine(
                df_to_categorize, default_expense_cat_id
            )
            df.update(categorized_subset)

        assert bank_account_id is not None
        # --- DB 삽입 및 잔액 업데이트 (수정된 트랜잭션 블록) ---
        with conn.session as s:
            for _, row in df.iterrows():
                insert_trans_query = text(
                    """
                    INSERT INTO "transaction" (type, transaction_type, transaction_provider, category_id, transaction_party_id,
                                               transaction_date, transaction_amount, content, account_id, linked_account_id)
                    VALUES (:type, 'BANK', 'SHINHAN_BANK', :cat_id, 1, :t_date, :t_amount, :content, :acc_id, :linked_id)
                    RETURNING id
                """
                )
                t_date = pd.to_datetime(
                    f"{row['거래일자']} {row['거래시간']}"
                ).strftime("%Y-%m-%d %H:%M:%S")
                content = f"{row.get('적요', '')} / {row.get('내용', '')}"
                linked_id = (
                    None
                    if pd.isna(row["linked_account_id"])
                    or row["linked_account_id"] == 0
                    else int(row["linked_account_id"])
                )

                result = s.execute(
                    insert_trans_query,
                    {
                        "type": row["type"],
                        "cat_id": int(row["category_id"]),
                        "t_date": t_date,
                        "t_amount": int(row["transaction_amount"]),
                        "content": content,
                        "acc_id": int(bank_account_id),
                        "linked_id": linked_id,
                    },
                )
                transaction_id = result.scalar_one()

                s.execute(
                    text(
                        'INSERT INTO "bank_transaction" (id, unique_hash, branch, balance_amount) VALUES (:id, :hash, :branch, :balance)'
                    ),
                    {
                        "id": transaction_id,
                        "hash": row["unique_hash"],
                        "branch": row.get("거래점"),
                        "balance": row.get("잔액"),
                    },
                )

                # 잔액 업데이트 (s.connection을 전달하여 동일한 트랜잭션에 참여)
                change_amount = int(row["transaction_amount"])
                reason = f"거래 ID {transaction_id}: {content}"
                if row["type"] == "INCOME":
                    update_balance_and_log(
                        int(bank_account_id), change_amount, reason, session=s
                    )
                elif row["type"] == "EXPENSE":
                    update_balance_and_log(
                        int(bank_account_id), -change_amount, reason, session=s
                    )
                elif row["type"] == "TRANSFER":
                    update_balance_and_log(
                        int(bank_account_id),
                        -change_amount,
                        f"이체 출금: {reason}",
                        session=s,
                    )
                    if linked_id:
                        update_balance_and_log(
                            int(linked_id),
                            change_amount,
                            f"이체 입금: {reason}",
                            session=s,
                        )

                inserted_count += 1

            # ✅ [수정] 모든 루프가 성공적으로 끝나면 최종 커밋
            print(f"{inserted_count}건의 데이터 처리 완료. 커밋을 시도합니다...")
            s.commit()
            print("커밋 성공!")

        return inserted_count, skipped_count

    except Exception as e:
        st.error(f"데이터 처리 중 오류 발생: {e}")
        return 0, 0
