import hashlib
import os
import streamlit as st
import numpy as np
import pandas as pd
from sqlalchemy import text

from analysis import run_rule_engine, identify_transfers
from core.db_manager import update_balance_and_log
from core.db_queries import get_account_id_by_name


def _parse_shinhan(filepath):
    """
    신한카드 엑셀 파일을 파싱하여 표준 데이터프레임으로 변환.

    Args:
        filepath (str 또는 file-like object): 신한카드 엑셀 파일 경로 또는 객체.

    Returns:
        pd.DataFrame: 표준화된 카드 거래 내역 데이터프레임.
    """
    df = pd.read_excel(filepath)
    # 원본 컬럼명과 표준화된 컬럼명 매핑
    columns_map = {
        "카드구분": "card_type",
        "거래일": "transaction_date",
        "가맹점명": "content",
        "금액": "transaction_amount",
        "이용카드": "card_name",
        "승인번호": "card_approval_number",
    }
    # 데이터프레임 컬럼명 변경
    df.rename(columns=columns_map, inplace=True)
    # 거래 제공자 정보 추가
    df["transaction_provider"] = "SHINHAN_CARD"
    return df


def _parse_kookmin(filepath):
    """
    국민카드 엑셀 파일을 파싱하여 표준 데이터프레임으로 변환.

    Args:
        filepath (str 또는 file-like object): 국민카드 엑셀 파일 경로 또는 객체.

    Returns:
        pd.DataFrame: 표준화된 카드 거래 내역 데이터프레임.
    """
    # 엑셀 파일에서 읽어올 컬럼 인덱스
    use_cols = [0, 3, 4, 5, 13]
    # 표준화될 컬럼명 정의
    standard_names = [
        "transaction_date",
        "card_name",
        "content",
        "transaction_amount",
        "card_approval_number",
    ]
    # 엑셀 파일 읽기: 6행 건너뛰고, 지정된 컬럼만 읽으며, 표준 컬럼명 사용
    df = pd.read_excel(filepath, skiprows=6, usecols=use_cols, names=standard_names)
    # 카드 유형 고정
    df["card_type"] = "신용"
    # 거래 제공자 정보 추가
    df["transaction_provider"] = "KUKMIN_CARD"
    return df


# 카드사별 파서 함수 딕셔너리
CARD_PARSERS = {"shinhan": _parse_shinhan, "kookmin": _parse_kookmin}


def insert_card_transactions_from_excel(filepath):
    """
    엑셀 파일에서 카드 거래 내역을 읽어와 데이터베이스에 삽입.

    Args:
        filepath (str 또는 file-like object): 카드 거래 내역 엑셀 파일 경로 또는 객체.

    Returns:
        tuple: (삽입된 행 수, 건너뛴 행 수)
    """

    # 파일 경로에서 파일 이름 추출 (Streamlit UploadedFile 객체 포함)
    filename = os.path.basename(
        filepath.name if hasattr(filepath, "name") else filepath
    )

    # 파일 이름 키워드를 기반으로 카드사 파서 선택. 일치하는 파서가 없으면 "kookmin" 기본값 사용.
    card_company = next(
        (key for key in CARD_PARSERS if key in filename.lower()), "kookmin"
    )

    # 지원하지 않는 카드사 파일인 경우 오류 메시지 출력 및 종료
    if not card_company:
        st.error(f"지원하지 않는 카드사 파일: {filename}")
        return 0, 0

    try:
        # 선택된 카드사 파서를 사용하여 엑셀 파일 파싱
        df = CARD_PARSERS[card_company](filepath)
    except Exception as e:
        # 파일 파싱 중 오류 발생 시 오류 메시지 출력 및 종료
        st.error(f"파일 파싱 중 오류 발생: {filename}, {e}")
        return 0, 0

    # 필수 컬럼(거래일, 내용, 금액)에 NaN 값이 있는 행 제거
    df.dropna(
        subset=["transaction_date", "content", "transaction_amount"], inplace=True
    )
    # 데이터프레임이 비어있는 경우 0, 0 반환
    if df.empty:
        return 0, 0
    # 'transaction_date' 컬럼을 datetime 형식으로 변환 후 지정된 문자열 형식으로 포맷
    df["transaction_date"] = pd.to_datetime(df["transaction_date"]).dt.strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    # 'transaction_amount' 컬럼에서 쉼표(,) 제거 후 숫자로 변환 (변환 오류 시 NaN 처리)
    df["transaction_amount"] = pd.to_numeric(
        df["transaction_amount"].astype(str).str.replace(",", ""), errors="coerce"
    )
    # 'transaction_amount' 컬럼에 NaN 값이 있는 행 제거
    df.dropna(subset=["transaction_amount"], inplace=True)
    # 'transaction_amount' 컬럼을 정수형으로 변환
    df["transaction_amount"] = df["transaction_amount"].astype(int)
    # 'card_approval_number' 컬럼을 문자열로 변환
    df["card_approval_number"] = df["card_approval_number"].astype(str)
    # 거래 유형을 'EXPENSE'(지출)로 고정
    df["type"] = "EXPENSE"
    # 거래 종류를 'CARD'로 고정
    df["transaction_type"] = "CARD"
    df["income_content"] = "NA"
    # 거래 당사자 ID를 기본값 1로 설정
    df["transaction_party_id"] = 1  # 기본값

    # Supabase 데이터베이스 연결
    conn = st.connection("supabase", type="sql")
    # 'UNCATEGORIZED' 및 'EXPENSE' 유형의 기본 카테고리 ID 조회
    cat_df = conn.query(
        "SELECT id FROM category WHERE category_code = 'UNCATEGORIZED' AND category_type = 'EXPENSE' LIMIT 1",
        ttl=0,
    )
    # 기본 카테고리 ID 설정 (조회 결과가 없으면 1)
    default_cat_id = cat_df["id"].iloc[0] if not cat_df.empty else 1

    # 정의된 규칙 엔진을 실행하여 카테고리 등 할당
    df = run_rule_engine(df, default_category_id=default_cat_id)

    # 신한카드 및 국민카드 계좌 ID를 데이터베이스에서 조회
    shinhan_card_account_id = get_account_id_by_name("신한카드")
    kookmin_card_account_id = get_account_id_by_name("국민카드")

    # 계좌 ID가 성공적으로 조회되었는지 확인
    assert shinhan_card_account_id is not None
    assert kookmin_card_account_id is not None

    # 'transaction_provider'에 따라 'account_id' 설정
    df["account_id"] = np.where(
        df["transaction_provider"] == "SHINHAN_CARD",
        shinhan_card_account_id,
        kookmin_card_account_id,
    )

    inserted_rows = 0  # 삽입된 행 수
    skipped_rows = 0  # 건너뛴 행 수

    # 데이터베이스 세션 시작
    with conn.session as s:
        try:
            # 데이터프레임의 각 행을 반복하며 데이터베이스에 삽입
            for _, row in df.iterrows():
                # 기존 거래인지 확인하는 SQL 쿼리
                check_query = text(
                    """
                    SELECT 1 FROM "transaction" t
                    JOIN "card_transaction" ct ON t.id = ct.id
                    WHERE t.transaction_provider = :provider AND ct.card_approval_number = :approval
                """
                )
                # 쿼리 실행하여 기존 거래 여부 확인
                existing = s.execute(
                    check_query,
                    {
                        "provider": row["transaction_provider"],
                        "approval": row["card_approval_number"],
                    },
                ).first()

                # 이미 존재하는 거래인 경우 건너뛰고 다음 행으로 이동
                if existing:
                    skipped_rows += 1
                    continue

                if row["card_type"] == "체크":
                    skipped_rows += 1
                    continue

                # 'transaction' 테이블에 데이터 삽입 SQL 쿼리
                insert_trans_query = text(
                    """
                    INSERT INTO "transaction" (type, transaction_type, transaction_provider, category_id,
                                            transaction_party_id, transaction_date, transaction_amount, content, account_id)
                    VALUES (:type, :ttype, :provider, :cat_id, :party_id, :tdate, :amount, :content, :acc_id)
                    RETURNING id
                """
                )
                # 쿼리 실행 및 삽입된 거래의 ID 반환
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
                transaction_id = result.scalar_one()  # 삽입된 ID 가져오기

                # 'card_transaction' 테이블에 카드 관련 데이터 삽입 SQL 쿼리
                insert_card_query = text(
                    """
                    INSERT INTO "card_transaction" (id, card_approval_number, card_type, card_name)
                    VALUES (:id, :approval, :ctype, :cname)
                """
                )
                # 쿼리 실행
                s.execute(
                    insert_card_query,
                    {
                        "id": transaction_id,
                        "approval": row["card_approval_number"],
                        "ctype": row["card_type"],
                        "cname": row["card_name"],
                    },
                )
                inserted_rows += 1  # 삽입된 행 수 증가

            s.commit()  # 모든 변경사항 데이터베이스에 커밋
            print("커밋 성공!")
        except Exception as e:
            # 데이터 삽입 중 오류 발생 시 오류 메시지 출력 및 롤백
            st.error(f"데이터 삽입 중 오류 발생: {e}")
            s.rollback()  # 오류 발생 시 모든 변경사항 롤백
            return 0, 0

    return inserted_rows, skipped_rows


def insert_bank_transactions_from_excel(filepath):
    """
    엑셀 파일에서 은행 거래 내역을 읽어와 데이터베이스에 삽입.

    Args:
        filepath (str 또는 file-like object): 은행 거래 내역 엑셀 파일 경로 또는 객체.

    Returns:
        tuple: (삽입된 행 수, 건너뛴 행 수)
    """
    try:
        # 엑셀 파일 읽기: 6행 건너뛰고 첫 번째 시트 사용
        df = pd.read_excel(filepath, skiprows=6, sheet_name=0)
        # 컬럼명에서 '(원)' 제거 및 공백 제거
        df.columns = df.columns.str.replace(r"\(원\)", "", regex=True).str.strip()
    except Exception as e:
        # 엑셀 파일 읽기 중 오류 발생 시 오류 메시지 출력 및 종료
        st.error(f"엑셀 파일 읽기 오류: {e}")
        return 0, 0

    # Supabase 데이터베이스 연결
    conn = st.connection("supabase", type="sql")
    inserted_count = 0  # 삽입된 행 수
    skipped_count = 0  # 건너뛴 행 수

    # 기존 은행 거래의 고유 해시값 조회 (중복 확인용)
    existing_hashes_df = conn.query("SELECT unique_hash FROM bank_transaction", ttl=0)
    existing_hashes = set(existing_hashes_df["unique_hash"])

    # 신한은행 계좌 ID, 이체 카테고리 ID, 기본 지출/수입 카테고리 ID 조회
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

    # 필수 ID들이 모두 조회되었는지 확인
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

    # '거래일자'와 '거래시간' 컬럼에 NaN 값이 있는 행 제거
    df.dropna(subset=["거래일자", "거래시간"], inplace=True)
    # 거래일자를 YYYY-MM-DD 형식의 문자열로 변환
    date_str = pd.to_datetime(df["거래일자"]).dt.strftime("%Y-%m-%d")
    # 거래시간을 문자열로 변환
    time_str = df["거래시간"].astype(str)
    # 출금 금액을 정수형으로 변환 후 문자열로 변환 (NaN은 0으로 처리)
    out_amount_str = df["출금"].fillna(0).astype(int).astype(str)
    # 입금 금액을 정수형으로 변환 후 문자열로 변환 (NaN은 0으로 처리)
    in_amount_str = df["입금"].fillna(0).astype(int).astype(str)
    # 위 네 가지 정보를 조합하여 고유 해시값 생성
    df["unique_hash"] = (
        date_str + "-" + time_str + "-" + out_amount_str + "-" + in_amount_str
    ).apply(lambda x: hashlib.sha256(x.encode()).hexdigest())

    # 원본 데이터프레임의 행 수 저장
    original_rows = len(df)
    # 이미 데이터베이스에 존재하는 해시값을 가진 행들을 제거하여 중복 데이터 필터링
    df = df[~df["unique_hash"].isin(existing_hashes)]
    # 건너뛴 행 수 계산
    skipped_count = original_rows - len(df)
    # 필터링 후 데이터프레임이 비어있으면 정보 메시지 출력 및 종료
    if df.empty:
        st.info(f"새로운 데이터가 없습니다. {skipped_count}건은 중복으로 건너뜁니다.")
        return 0, skipped_count

    # '입금'과 '출금'을 이용하여 순 거래 금액('amount') 계산
    df["amount"] = df["입금"].fillna(0) - df["출금"].fillna(0)
    # 거래 금액의 절댓값을 'transaction_amount'로 저장 (정수형)
    df["transaction_amount"] = df["amount"].abs().astype(int)
    df["income_content"] = df["내용"].astype(str)

    # 이체 거래를 식별하고 연결된 계좌 ID 반환
    linked_account_id_series = identify_transfers(df)
    # linked_account_id_series가 0이 아니고 NaN이 아닌 경우를 이체 거래로 마스킹
    is_transfer_mask = (linked_account_id_series != 0) & (
        linked_account_id_series.notna()
    )

    # 'amount'에 따라 거래 유형('type')을 'INCOME' 또는 'EXPENSE'로 설정
    df["type"] = np.where(df["amount"] > 0, "INCOME", "EXPENSE")
    # 이체 거래인 경우 'type'을 'TRANSFER'로 업데이트
    df.loc[is_transfer_mask, "type"] = "TRANSFER"
    # 거래 유형에 따라 기본 카테고리 ID 할당
    df["category_id"] = np.where(
        df["type"] == "INCOME", default_income_cat_id, default_expense_cat_id
    )
    # 이체 거래인 경우 'category_id'를 이체 카테고리 ID로 업데이트
    df.loc[is_transfer_mask, "category_id"] = transfer_cat_id
    # 연결된 계좌 ID 컬럼 추가
    df["linked_account_id"] = linked_account_id_series

    # 이체 거래가 아닌(지출/수입) 행들만 필터링
    expense_income_mask = df["type"] != "TRANSFER"
    # 이체 거래가 아닌 행이 하나라도 있다면 규칙 엔진 실행
    if expense_income_mask.any():
        df_to_categorize = df[expense_income_mask].copy()
        # 규칙 엔진을 사용하여 카테고리 분류 (기본 지출 카테고리 ID 사용)
        categorized_subset = run_rule_engine(df_to_categorize, default_expense_cat_id)
        # 원본 데이터프레임에 분류된 결과 업데이트

        df.update(categorized_subset)
        categorized_subset = run_rule_engine(df_to_categorize, default_income_cat_id)
        # 원본 데이터프레임에 분류된 결과 업데이트
        print(categorized_subset)
        df.update(categorized_subset)

    # 은행 계좌 ID가 성공적으로 조회되었는지 확인
    assert bank_account_id is not None

    # 데이터베이스 세션 시작
    with conn.session as s:
        try:
            # 데이터프레임의 각 행을 반복하며 데이터베이스에 삽입
            for _, row in df.iterrows():
                # 'transaction' 테이블에 데이터 삽입 SQL 쿼리
                insert_trans_query = text(
                    """
                    INSERT INTO "transaction" (type, transaction_type, transaction_provider, category_id, transaction_party_id,
                                            transaction_date, transaction_amount, content, account_id, linked_account_id)
                    VALUES (:type, 'BANK', 'SHINHAN_BANK', :cat_id, 1, :t_date, :t_amount, :content, :acc_id, :linked_id)
                    RETURNING id
                """
                )
                # '거래일자'와 '거래시간'을 조합하여 datetime 형식의 문자열로 포맷
                t_date = pd.to_datetime(
                    f"{row['거래일자']} {row['거래시간']}"
                ).strftime("%Y-%m-%d %H:%M:%S")
                content = f"{row.get('내용', '')}"
                # 'linked_account_id'가 NaN이거나 0이면 None, 아니면 정수형으로 변환
                linked_id = (
                    None
                    if pd.isna(row["linked_account_id"])
                    or row["linked_account_id"] == 0
                    else int(row["linked_account_id"])
                )

                # 쿼리 실행 및 삽입된 거래의 ID 반환
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
                transaction_id = result.scalar_one()  # 삽입된 ID 가져오기

                # 'bank_transaction' 테이블에 은행 거래 관련 데이터 삽입
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

                # 계좌 잔액 업데이트
                change_amount = int(row["transaction_amount"])
                reason = f"거래 ID {transaction_id}: {content}"
                if row["type"] == "INCOME":
                    # 수입인 경우 계좌 잔액 증가
                    update_balance_and_log(
                        int(bank_account_id), change_amount, reason, session=s
                    )
                elif row["type"] == "EXPENSE":
                    # 지출인 경우 계좌 잔액 감소
                    update_balance_and_log(
                        int(bank_account_id), -change_amount, reason, session=s
                    )
                elif row["type"] == "TRANSFER":
                    # 이체인 경우 본 계좌에서 출금 처리
                    update_balance_and_log(
                        int(bank_account_id),
                        -change_amount,
                        f"이체 출금: {reason}",
                        session=s,
                    )
                    if linked_id:
                        # 연결된 계좌가 있다면 해당 계좌로 입금 처리
                        update_balance_and_log(
                            int(linked_id),
                            change_amount,
                            f"이체 입금: {reason}",
                            session=s,
                        )

                inserted_count += 1  # 삽입된 행 수 증가

            print(f"{inserted_count}건의 데이터 처리 완료. 커밋을 시도합니다...")
            s.commit()  # 모든 변경사항 데이터베이스에 커밋
            print("커밋 성공!")
        except Exception as e:
            # 데이터 처리 중 오류 발생 시 오류 메시지 출력 및 롤백
            st.error(f"데이터 처리 중 오류 발생: {e}")
            s.rollback()  # 오류 발생 시 모든 변경사항 롤백
            return 0, 0

    return inserted_count, skipped_count
