import streamlit as st
import numpy as np
import pandas as pd
from typing import Optional
from sqlalchemy import (
    text,
)


def load_data_from_db(
    start_date,
    end_date,
    transaction_types: list | None = None,
    cat_types: list | None = None,
):
    """
    지정된 기간 동안의 거래 데이터를 데이터베이스에서 로드.
    선택적으로 거래 유형 및 카테고리 유형으로 필터링.

    Args:
        start_date (str): 조회 시작일 (YYYY-MM-DD 형식).
        end_date (str): 조회 종료일 (YYYY-MM-DD 형식).
        transaction_types (list | None): 필터링할 거래 유형 리스트 (예: ['INCOME', 'EXPENSE']).
        cat_types (list | None): 필터링할 카테고리 유형 리스트 (예: ['BANK', 'CARD']).

    Returns:
        pd.DataFrame: 조회된 거래 데이터. 오류 발생 시 빈 데이터프레임.
    """

    conn = st.connection("supabase", type="sql")  # Streamlit Supabase 연결 객체

    # 기본 SQL 쿼리 시작 부분
    query_parts = [
        """
        SELECT 
            t.id, t.transaction_type, t.transaction_date, t.content, t.transaction_amount, t.description, t.type, 
            c.description as category_name,
            p.description as party_description
        FROM "transaction" t
        LEFT JOIN "category" c ON t.category_id = c.id
        LEFT JOIN "transaction_party" p ON t.transaction_party_id = p.id
        WHERE t.transaction_date::date BETWEEN :start_date AND :end_date
    """
    ]
    # 쿼리 파라미터 초기화
    params = {"start_date": start_date, "end_date": end_date}

    # 거래 유형 필터링 조건 추가
    if transaction_types:
        query_parts.append("AND t.type IN :transaction_types")
        params["transaction_types"] = tuple(
            transaction_types
        )  # SQL IN 절에 사용하기 위해 튜플로 변환

    # 카테고리 유형 필터링 조건 추가 (참고: 컬럼명이 t.transaction_type으로 되어 있으나, cat_types는 category_type을 의도한 것일 수 있음)
    if cat_types:
        query_parts.append("AND t.transaction_type IN :cat_types")
        params["cat_types"] = tuple(cat_types)  # SQL IN 절에 사용하기 위해 튜플로 변환

    # 결과 정렬 조건 추가
    query_parts.append("ORDER BY t.transaction_date DESC")

    # 최종 SQL 쿼리 문자열 생성
    final_query = " ".join(query_parts)

    try:
        # 데이터베이스 쿼리 실행 및 결과 데이터프레임으로 반환
        df = conn.query(final_query, params=params, ttl=0)
    except Exception as e:
        # 오류 발생 시 오류 메시지 출력 및 빈 데이터프레임 반환
        st.error(f"데이터 로드 오류: {e}")
        df = pd.DataFrame()

    return df


def get_all_categories(
    category_type: Optional[str] = None, include_top_level: bool = False
):
    """
    모든 카테고리 정보를 데이터베이스에서 로드.
    선택적으로 카테고리 유형 및 최상위 카테고리 포함 여부로 필터링.

    Args:
        category_type (Optional[str]): 필터링할 카테고리 유형 (예: 'EXPENSE', 'INCOME').
        include_top_level (bool): 최상위 카테고리(depth=1)를 포함할지 여부.

    Returns:
        dict: 카테고리 ID를 키로, 설명을 값으로 하는 딕셔너리. 오류 발생 시 빈 딕셔너리.
    """

    conn = st.connection("supabase", type="sql")
    # 기본 SQL 쿼리 시작
    query_parts = ["SELECT id, description FROM category"]
    conditions = []
    params = {}

    # 최상위 카테고리 제외 조건 추가
    if not include_top_level:
        conditions.append("depth > 1")
    # 카테고리 유형 필터링 조건 추가
    if category_type:
        conditions.append("category_type = :category_type")
        params["category_type"] = category_type

    # 조건이 있는 경우 WHERE 절 추가
    if conditions:
        query_parts.append("WHERE " + " AND ".join(conditions))

    # 결과 정렬 조건 추가
    query_parts.append("ORDER BY description")
    # 최종 SQL 쿼리 문자열 생성
    final_query = " ".join(query_parts)

    try:
        # 데이터베이스 쿼리 실행 및 결과 데이터프레임으로 반환
        df = conn.query(final_query, params=params, ttl=0)
        # ID를 키로, 설명을 값으로 하는 딕셔너리로 변환하여 반환
        return pd.Series(df.description.values, index=df.id).to_dict()
    except Exception as e:
        # 오류 발생 시 오류 메시지 출력 및 빈 딕셔너리 반환
        st.error(f"카테고리 로드 오류: {e}")
        return {}


def load_data_for_sunburst(start_date, end_date, transaction_type="EXPENSE"):
    """
    선버스트 차트 생성을 위한 데이터를 로드.
    지정된 기간과 거래 유형에 따라 카테고리별 직접 지출 금액과 총 금액을 계산.

    Args:
        start_date (str): 조회 시작일.
        end_date (str): 조회 종료일.
        transaction_type (str): 필터링할 거래 유형 (기본값: 'EXPENSE').

    Returns:
        pd.DataFrame: 선버스트 차트에 필요한 카테고리 계층 및 금액 데이터. 오류 발생 시 빈 데이터프레임.
    """

    conn = st.connection("supabase", type="sql")
    try:
        # 모든 카테고리 정보 로드
        categories_df = conn.query("SELECT * FROM category", ttl=0)

        # 지정된 기간 및 거래 유형에 따른 카테고리별 직접 지출(direct_amount) 합계 조회
        query = """
            SELECT category_id, SUM(transaction_amount) as direct_amount 
            FROM "transaction" 
            WHERE type = :transaction_type AND transaction_date::date BETWEEN :start_date AND :end_date 
            GROUP BY category_id
        """
        direct_spending = conn.query(
            query,
            params={
                "transaction_type": transaction_type,
                "start_date": start_date,
                "end_date": end_date,
            },
            ttl=0,
        )

        # 카테고리 데이터와 직접 지출 데이터를 category_id를 기준으로 병합
        df = pd.merge(
            categories_df,
            direct_spending,
            left_on="id",
            right_on="category_id",
            how="left",  # 왼쪽 조인: 모든 카테고리를 포함하고 매칭되는 직접 지출 추가
        )
        # 직접 지출이 없는 카테고리의 경우 0으로 채움
        df["direct_amount"] = df["direct_amount"].fillna(0)
        # parent_id를 숫자형으로 변환하고 NaN은 0으로 채운 후 정수형으로 변환
        df["parent_id"] = (
            pd.to_numeric(df["parent_id"], errors="coerce").fillna(0).astype(int)
        )

        # 각 카테고리의 총 금액을 계산하기 위한 딕셔너리 생성 (초기값은 direct_amount)
        total_amounts = df.set_index("id")["direct_amount"].to_dict()
        # 깊이(depth)를 기준으로 내림차순 정렬하여 하위 카테고리부터 처리
        sorted_df = df.sort_values(by="depth", ascending=False)
        # 정렬된 데이터프레임을 순회하며 부모 카테고리에 하위 카테고리의 금액을 합산
        for _, row in sorted_df.iterrows():
            cat_id, parent_id = row["id"], row["parent_id"]
            # 부모 ID가 0이 아니고, total_amounts에 존재하며, 자기 자신이 아닌 경우에만 합산
            if parent_id != 0 and parent_id in total_amounts and parent_id != cat_id:
                total_amounts[parent_id] += total_amounts.get(cat_id, 0)

        # 계산된 총 금액(total_amount)을 데이터프레임에 매핑
        df["total_amount"] = df["id"].map(total_amounts)
        # 총 금액이 0보다 큰 카테고리만 필터링하여 반환
        return df[df["total_amount"] > 0].copy()
    except Exception as e:
        # 오류 발생 시 오류 메시지 출력 및 빈 데이터프레임 반환
        st.error(f"Sunburst 데이터 로드 오류: {e}")
        return pd.DataFrame()


def load_data_for_pivot_grid(start_date, end_date, transaction_type="EXPENSE"):
    """
    피벗 그리드 생성을 위한 데이터를 로드.
    거래 내역과 카테고리 계층 정보를 결합하여 월별/카테고리별 분석에 적합한 형태로 변환.

    Args:
        start_date (str): 조회 시작일.
        end_date (str): 조회 종료일.
        transaction_type (str): 필터링할 거래 유형 (기본값: 'EXPENSE').

    Returns:
        pd.DataFrame: 피벗 그리드에 필요한 거래 및 카테고리 계층 데이터. 오류 발생 시 빈 데이터프레임.
    """
    conn = st.connection("supabase", type="sql")
    try:
        # 카테고리 ID, 부모 ID, 설명 정보 로드
        categories_df = conn.query(
            "SELECT id, parent_id, description FROM category", ttl=0
        )
        # parent_id를 숫자형으로 변환하고 NaN은 0으로 채운 후 정수형으로 변환
        categories_df["parent_id"] = (
            pd.to_numeric(categories_df["parent_id"], errors="coerce")
            .fillna(0)
            .astype(int)
        )
        # ID를 키로, 설명을 값으로 하는 맵 생성
        id_to_desc_map = categories_df.set_index("id")["description"].to_dict()
        # ID를 키로, 부모 ID를 값으로 하는 맵 생성
        id_to_parent_map = categories_df.set_index("id")["parent_id"].to_dict()

        # 거래 내역과 카테고리 정보를 조인하여 조회
        query = """
            SELECT 
                to_char(transaction_date, 'YYYY/MM') as "연월",
                t.transaction_amount as "금액",
                c.id, c.depth
            FROM "transaction" t
            JOIN "category" c ON t.category_id = c.id
            WHERE t.type = :transaction_type AND t.transaction_date::date BETWEEN :start_date AND :end_date
        """

        df = conn.query(
            query,
            params={
                "transaction_type": transaction_type,
                "start_date": start_date,
                "end_date": end_date,
            },
            ttl=0,
        )
        if df.empty:
            return pd.DataFrame()

        paths = []
        # 각 거래의 카테고리 ID를 기반으로 상위 카테고리 경로(이름)를 생성
        for cat_id in df["id"]:
            path_names = []
            current_id = cat_id
            # 부모 ID를 따라 최상위까지 이동하며 경로 구성
            while current_id != 0 and current_id in id_to_parent_map:
                if current_id in id_to_desc_map:
                    path_names.insert(
                        0, id_to_desc_map[current_id]
                    )  # 경로를 역순으로 삽입
                current_id = id_to_parent_map.get(current_id, 0)
                # 순환 참조 방지 (매우 중요)
                if current_id == cat_id:
                    break
            paths.append(path_names)

        # 카테고리 깊이만큼 'L1', 'L2' 등의 컬럼을 생성하여 경로명 할당
        max_depth = df["depth"].max()
        for i in range(1, int(max_depth) + 1):
            df[f"L{i}"] = [p[i - 1] if len(p) >= i else None for p in paths]

        return df
    except Exception as e:
        # 오류 발생 시 오류 메시지 출력 및 빈 데이터프레임 반환
        st.error(f"피벗 그리드 데이터 로드 오류: {e}")
        return pd.DataFrame()


def get_all_parties():
    """
    모든 거래처 정보를 데이터베이스에서 로드.

    Returns:
        dict: 거래처 ID를 키로, 설명을 값으로 하는 딕셔너리. 오류 발생 시 빈 딕셔너리.
    """

    conn = st.connection("supabase", type="sql")
    try:
        # 'transaction_party' 테이블에서 ID와 설명 조회 및 설명 기준으로 정렬
        df = conn.query(
            "SELECT id, description FROM transaction_party ORDER BY description", ttl=0
        )
        # ID를 키로, 설명을 값으로 하는 딕셔너리로 변환하여 반환
        return pd.Series(df.description.values, index=df.id).to_dict()
    except Exception as e:
        # 오류 발생 시 오류 메시지 출력 및 빈 딕셔너리 반환
        st.error(f"거래처 로드 오류: {e}")
        return {}


def load_monthly_total_spending(start_date, end_date, transaction_type="EXPENSE"):
    """
    지정된 기간 동안 월별 총 지출(또는 수입/투자) 금액을 로드.

    Args:
        start_date (str): 조회 시작일.
        end_date (str): 조회 종료일.
        transaction_type (str): 필터링할 거래 유형 (기본값: 'EXPENSE').

    Returns:
        pd.DataFrame: '연월'과 'total_spending' 컬럼을 포함하는 데이터프레임.
    """

    conn = st.connection("supabase", type="sql")
    # 월별 총 거래 금액을 집계하는 SQL 쿼리
    query = """
        SELECT 
            to_char(transaction_date, 'YYYY/MM') AS year_month,
            SUM(transaction_amount) AS total_spending
        FROM "transaction"
        WHERE type = :transaction_type AND transaction_date::date BETWEEN :start_date AND :end_date
        GROUP BY year_month
        ORDER BY year_month;
    """

    # 쿼리 실행 및 결과 반환
    return conn.query(
        query,
        params={
            "transaction_type": transaction_type,
            "start_date": start_date,
            "end_date": end_date,
        },
        ttl=0,
    )


def get_all_parties_df():
    """
    모든 거래처 정보를 데이터프레임 형태로 로드.

    Returns:
        pd.DataFrame: 거래처 정보 데이터프레임.
    """

    conn = st.connection("supabase", type="sql")

    # 'transaction_party' 테이블의 모든 컬럼 조회 및 ID 기준으로 정렬
    return conn.query("SELECT * FROM transaction_party ORDER BY id", ttl=0)


def get_all_categories_with_hierarchy():
    """
    계층 구조를 포함한 모든 카테고리 정보를 데이터프레임 형태로 반환.
    materialized_path_desc를 기반으로 'name_path' 컬럼을 생성하여 계층 경로를 문자열로 표현.

    Returns:
        pd.DataFrame: 카테고리 정보와 'name_path' 컬럼을 포함하는 데이터프레임. 빈 경우 빈 데이터프레임.
    """
    conn = st.connection("supabase", type="sql")

    # 모든 카테고리 정보 조회 및 materialized_path_desc 기준으로 정렬
    df = conn.query("SELECT * FROM category ORDER BY materialized_path_desc", ttl=0)
    if df.empty:
        return pd.DataFrame()

    # ID를 키로, 설명을 값으로 하는 맵 생성
    id_to_desc_map = df.set_index("id")["description"].to_dict()
    # ID를 키로, 부모 ID를 값으로 하는 맵 생성 (숫자형 변환 및 NaN 처리)
    id_to_parent_map = (
        pd.to_numeric(df.set_index("id")["parent_id"], errors="coerce")
        .fillna(0)
        .astype(int)
        .to_dict()
    )

    path_names_list = []
    # 각 카테고리에 대해 전체 계층 경로(이름)를 생성
    for cat_id in df["id"]:
        path_names = []
        current_id = cat_id
        # 부모 ID를 따라 최상위까지 이동하며 경로 구성
        while current_id != 0 and current_id in id_to_parent_map:
            if current_id in id_to_desc_map:
                path_names.insert(0, id_to_desc_map[current_id])  # 경로를 역순으로 삽입
            current_id = id_to_parent_map.get(current_id, 0)
            # 순환 참조 방지
            if current_id == cat_id:
                break
        path_names_list.append("/".join(path_names))  # '/'로 구분된 경로 문자열 생성

    df["name_path"] = path_names_list  # 'name_path' 컬럼 추가
    return df


def load_income_expense_summary(start_date, end_date):
    """
    지정된 기간 동안 월별 수입 및 지출 요약을 로드.

    Args:
        start_date (str): 조회 시작일.
        end_date (str): 조회 종료일.

    Returns:
        pd.DataFrame: '연월', '수입', '지출' 컬럼을 포함하는 데이터프레임.
    """

    conn = st.connection("supabase", type="sql")
    # 월별 수입 및 지출을 집계하는 SQL 쿼리
    query = """
        SELECT 
            to_char(transaction_date, 'YYYY/MM') as "연월",
            SUM(CASE WHEN type = 'INCOME' THEN transaction_amount ELSE 0 END) as "수입",
            SUM(CASE WHEN type = 'EXPENSE' THEN transaction_amount ELSE 0 END) as "지출"
        FROM "transaction"
        WHERE transaction_date::date BETWEEN :start_date AND :end_date AND type IN ('INCOME', 'EXPENSE')
        GROUP BY "연월"
        ORDER BY "연월"
    """

    # 쿼리 실행 및 결과 반환
    return conn.query(
        query, params={"start_date": start_date, "end_date": end_date}, ttl=0
    )


def load_monthly_category_summary(start_date, end_date, transaction_type):
    """
    지정된 기간 동안 월별 카테고리별 요약을 로드.
    최하위 카테고리(부모가 없는 카테고리) 기준으로 집계.

    Args:
        start_date (str): 조회 시작일.
        end_date (str): 조회 종료일.
        transaction_type (str): 필터링할 거래 유형.

    Returns:
        pd.DataFrame: '연월', '카테고리', '금액' 컬럼을 포함하는 데이터프레임.
    """

    conn = st.connection("supabase", type="sql")
    # 월별 카테고리별 금액을 집계하는 SQL 쿼리 (최하위 카테고리 제외)
    query = """
        SELECT 
            to_char(t.transaction_date, 'YYYY/MM') as "연월",
            c.description as "카테고리",
            SUM(t.transaction_amount) as "금액"
        FROM "transaction" t
        JOIN "category" c ON t.category_id = c.id
        WHERE t.type = :transaction_type AND t.transaction_date::date BETWEEN :start_date AND :end_date
          AND c.id NOT IN (SELECT DISTINCT parent_id FROM category WHERE parent_id IS NOT NULL) -- 부모 카테고리가 아닌 (최하위) 카테고리만 포함
        GROUP BY "연월", "카테고리"
        ORDER BY "연월", "금액" DESC
    """

    # 쿼리 실행 및 결과 반환
    return conn.query(
        query,
        params={
            "transaction_type": transaction_type,
            "start_date": start_date,
            "end_date": end_date,
        },
        ttl=0,
    )


def get_account_id_by_name(account_name):
    """
    계좌 이름으로 계좌 ID를 조회.

    Args:
        account_name (str): 조회할 계좌 이름.

    Returns:
        Optional[int]: 계좌 ID (존재하지 않으면 None).
    """

    conn = st.connection("supabase", type="sql")

    # 계좌 이름으로 ID 조회
    df = conn.query(
        "SELECT id FROM accounts WHERE name = :account_name",
        params={"account_name": account_name},
        ttl=0,
    )
    # 결과가 있으면 첫 번째 ID 반환, 없으면 None 반환
    return df["id"].iloc[0] if not df.empty else None


def get_all_accounts(account_type: Optional[str] = None):
    """
    모든 계좌 정보를 로드.
    선택적으로 계좌 유형으로 필터링.

    Args:
        account_type (Optional[str]): 필터링할 계좌 유형 (예: 'BANK', 'CARD').

    Returns:
        dict: 계좌 이름을 키로, ID를 값으로 하는 딕셔너리. 오류 발생 시 빈 딕셔너리.
    """

    conn = st.connection("supabase", type="sql")
    # 기본 SQL 쿼리
    query = "SELECT id, name FROM accounts"
    params = {}
    # 계좌 유형 필터링 조건 추가
    if account_type:
        query += " WHERE account_type = :account_type"
        params["account_type"] = account_type
    # 결과 정렬 조건 추가
    query += " ORDER BY name"

    try:
        # 쿼리 실행 및 결과 데이터프레임 반환
        df = conn.query(query, params=params, ttl=0)
        # 이름을 키로, ID를 값으로 하는 딕셔너리로 변환하여 반환
        return pd.Series(df.id.values, index=df.name).to_dict()
    except Exception as e:
        # 오류 발생 시 오류 메시지 출력 및 빈 딕셔너리 반환
        st.error(f"계좌 목록 로드 오류: {e}")
        return {}


def get_bank_expense_transactions(start_date, end_date):
    """
    지정된 기간 동안의 은행 지출 거래 내역을 로드.

    Args:
        start_date (str): 조회 시작일.
        end_date (str): 조회 종료일.

    Returns:
        pd.DataFrame: 은행 지출 거래 데이터프레임.
    """

    conn = st.connection("supabase", type="sql")
    # 은행 지출 거래를 조회하는 SQL 쿼리
    query = """
        SELECT id, transaction_date, content, transaction_amount
        FROM "transaction"
        WHERE type = 'EXPENSE' AND transaction_type = 'BANK'
          AND transaction_date::date BETWEEN :start_date AND :end_date
        ORDER BY transaction_date DESC
    """

    # 쿼리 실행 및 결과 반환
    return conn.query(
        query, params={"start_date": start_date, "end_date": end_date}, ttl=0
    )


def get_balance_history(account_id):
    """
    특정 계좌의 잔액 변경 이력을 로드.

    Args:
        account_id (int): 조회할 계좌 ID.

    Returns:
        pd.DataFrame: 잔액 변경 이력 데이터프레임.
    """

    conn = st.connection("supabase", type="sql")
    # 계좌 잔액 이력을 조회하는 SQL 쿼리
    query = """
        SELECT change_date, reason, previous_balance, change_amount, new_balance 
        FROM account_balance_history 
        WHERE account_id = :account_id ORDER BY change_date DESC
    """

    # 쿼리 실행 및 결과 반환
    return conn.query(query, params={"account_id": account_id}, ttl=0)


def get_init_balance(account_id):
    """
    특정 계좌의 현재 잔액과 초기 잔액을 조회.

    Args:
        account_id (int): 조회할 계좌 ID.

    Returns:
        pd.Series: 'balance'와 'initial_balance'를 포함하는 Series. 계좌가 없으면 None.
    """

    conn = st.connection("supabase", type="sql")

    # 계좌의 잔액 및 초기 잔액 조회
    df = conn.query(
        "SELECT balance, initial_balance FROM accounts WHERE id = :account_id",
        params={"account_id": account_id},
        ttl=0,
    )
    # 결과가 있으면 첫 번째 행 반환, 없으면 None 반환
    return df.iloc[0] if not df.empty else None


def get_investment_accounts():
    """
    모든 투자 계좌 정보를 로드.

    Returns:
        pd.DataFrame: 투자 계좌 정보 데이터프레임.
    """

    conn = st.connection("supabase", type="sql")

    # is_investment가 true인 계좌 조회
    return conn.query("SELECT * FROM accounts WHERE is_investment = true", ttl=0)


def get_all_accounts_df():
    """
    모든 계좌 정보를 데이터프레임 형태로 로드하고, 자산/부채 및 투자/비투자 여부를 추가.

    Returns:
        pd.DataFrame: 모든 계좌 정보 데이터프레임.
    """

    conn = st.connection("supabase", type="sql")
    # 계좌 정보를 조회하고 'type'(자산/부채) 및 'investment'(투자/비투자) 컬럼 추가
    query = """
        SELECT 
            id, name, account_type, initial_balance, balance,
            CASE WHEN is_asset = true THEN '자산' ELSE '부채' END as type, 
            CASE WHEN is_investment = true THEN '투자' ELSE '비투자' END as investment
        FROM accounts 
        ORDER BY type, name
    """

    # 쿼리 실행 및 결과 반환
    return conn.query(query, ttl=0)


def get_monthly_summary_for_dashboard():
    """
    대시보드에 표시할 월별 수입, 지출, 투자 금액 및 총 자산 요약 데이터를 로드.

    Returns:
        pd.DataFrame: 월별 요약 데이터프레임.
    """

    conn = st.connection("supabase", type="sql")

    # 월별 수입, 지출, 투자 흐름 집계 쿼리
    flow_query = """
        SELECT
            to_char(transaction_date, 'YYYY/MM') as "연월",
            SUM(CASE WHEN type = 'INCOME' THEN transaction_amount ELSE 0 END) as "수입", 
            SUM(CASE WHEN type = 'EXPENSE' THEN transaction_amount ELSE 0 END) as "지출", 
            SUM(CASE WHEN type = 'INVEST' THEN transaction_amount ELSE 0 END) as "투자"
        FROM "transaction"
        GROUP BY "연월"
    """

    flow_df = conn.query(flow_query, ttl=0)  # 월별 수입/지출/투자 데이터

    # 총 자산의 초기 잔액 합계 조회
    initial_total_asset_df = conn.query(
        "SELECT SUM(initial_balance) as total FROM accounts WHERE is_asset = true",
        ttl=0,
    )
    initial_total_asset = (
        initial_total_asset_df["total"].iloc[0]
        if not initial_total_asset_df.empty
        else 0
    )

    # 월별 자산 계좌의 잔액 변경 이력 조회
    history_query = """
        SELECT 
            to_char(change_date, 'YYYY/MM') as "연월",
            SUM(change_amount) as change_amount
        FROM account_balance_history abh
        JOIN accounts a ON a.id = abh.account_id
        WHERE a.is_asset = true
        GROUP BY "연월"
    """

    history_df = conn.query(history_query, ttl=0)

    asset_balance_df: pd.DataFrame
    if not history_df.empty:
        # 이력 데이터를 연월 기준으로 정렬하고 인덱스를 설정
        history_df = history_df.sort_values("연월").set_index("연월")
        # 누적 변경 금액을 초기 총 자산에 더하여 월별 총 자산 계산
        asset_balance_df = (
            history_df["change_amount"].cumsum() + initial_total_asset
        ).reset_index(name="총자산")
    else:
        # 이력 데이터가 없는 경우 빈 데이터프레임 생성
        asset_balance_df = pd.DataFrame(columns=["연월", "총자산"])

    # 수입/지출/투자 흐름 데이터와 총 자산 데이터를 연월 기준으로 병합
    if not flow_df.empty and not asset_balance_df.empty:
        summary_df = pd.merge(flow_df, asset_balance_df, on="연월", how="outer")
    elif not flow_df.empty:
        summary_df = flow_df
    else:
        summary_df = asset_balance_df

    # '연월' 기준으로 정렬하고, 결측값을 이전 값으로 채운 후 0으로 대체
    summary_df = summary_df.sort_values("연월").ffill().fillna(0)
    return summary_df


def get_annual_summary_data(year: int):
    """
    특정 연도의 월별 카테고리 요약 데이터를 로드.
    카테고리 계층을 '구분'(L1)과 '항목'(L2)으로 분리하여 반환.

    Args:
        year (int): 조회할 연도.

    Returns:
        pd.DataFrame: 연월, 구분, 항목, 금액을 포함하는 데이터프레임. 오류 발생 시 빈 데이터프레임.
    """

    conn = st.connection("supabase", type="sql")
    try:
        # 카테고리 ID, 부모 ID, 설명 정보 로드
        categories_df = conn.query(
            "SELECT id, parent_id, description FROM category", ttl=0
        )
        # parent_id를 숫자형으로 변환하고 NaN은 0으로 채운 후 정수형으로 변환
        categories_df["parent_id"] = (
            pd.to_numeric(categories_df["parent_id"], errors="coerce")
            .fillna(0)
            .astype(int)
        )
        # ID를 키로, 설명을 값으로 하는 맵 생성
        id_to_desc_map = categories_df.set_index("id")["description"].to_dict()
        # ID를 키로, 부모 ID를 값으로 하는 맵 생성
        id_to_parent_map = categories_df.set_index("id")["parent_id"].to_dict()

        # 특정 연도의 수입, 지출, 투자 거래 내역 조회
        query = """
            SELECT 
                to_char(transaction_date, 'YYYY/MM') as "연월",
                transaction_amount as "금액",
                category_id
            FROM "transaction"
            WHERE type IN ('INCOME', 'EXPENSE', 'INVEST')
              AND to_char(transaction_date, 'YYYY') = :year_str
        """

        df = conn.query(query, params={"year_str": str(year)}, ttl=0)
        if df.empty:
            return pd.DataFrame()

        l1_list, l2_list = [], []
        # 각 거래의 카테고리 ID를 기반으로 L1(구분) 및 L2(항목) 경로명 생성
        for cat_id in df["category_id"]:
            path_names = []
            current_id = cat_id
            # 부모 ID를 따라 최상위까지 이동하며 경로 구성
            while current_id != 0 and current_id in id_to_parent_map:
                if current_id in id_to_desc_map:
                    path_names.insert(
                        0, id_to_desc_map[current_id]
                    )  # 경로를 역순으로 삽입
                current_id = id_to_parent_map.get(current_id, 0)
                # 순환 참조 방지
                if current_id == cat_id:
                    break

            # L1은 최상위 카테고리, L2는 그 다음 카테고리 (없으면 L1과 동일)
            l1 = path_names[0] if len(path_names) > 0 else "미분류"
            l2 = path_names[1] if len(path_names) > 1 else l1
            l1_list.append(l1)
            l2_list.append(l2)

        df["구분"] = l1_list  # L1 카테고리 컬럼 추가
        df["항목"] = l2_list  # L2 카테고리 컬럼 추가
        return df[["구분", "항목", "연월", "금액"]]  # 필요한 컬럼만 선택하여 반환
    except Exception as e:
        # 오류 발생 시 오류 메시지 출력 및 빈 데이터프레임 반환
        st.error(f"연간 요약 데이터 로드 오류: {e}")
        return pd.DataFrame()


def get_annual_asset_summary(year: int):
    """
    특정 연도의 월별 자산 잔액 요약을 로드.
    계좌의 초기 잔액과 해당 연도 내의 모든 거래를 합산하여 월말 잔액 계산.

    Args:
        year (int): 조회할 연도.

    Returns:
        pd.DataFrame: 계좌별 월말 잔액을 포함하는 피벗 테이블 형식의 데이터프레임. 오류 발생 시 빈 데이터프레임.
    """

    conn = st.connection("supabase", type="sql")

    try:
        # 모든 계좌의 ID, 이름, 초기 잔액 조회 (초기 잔액 날짜는 임의의 과거 날짜로 설정)
        accounts_df = conn.query(
            """
            SELECT id, name, initial_balance, '1777-01-01 00:00:00'::timestamp as initial_balance_date 
            FROM accounts
            """,
            parse_dates=["initial_balance_date"],  # 날짜 컬럼 파싱
            ttl=0,
        )
        if accounts_df.empty:
            return pd.DataFrame()

        # initial_balance_date를 UTC 타임존으로 로컬라이즈
        accounts_df["initial_balance_date"] = accounts_df[
            "initial_balance_date"
        ].dt.tz_localize("UTC")

        # 해당 연도의 모든 거래 내역과 관련된 잔액 변경(수입/지출 및 이체/투자) 조회
        query = """
            SELECT account_id, transaction_date,
                        CASE WHEN type IN ('INCOME') THEN transaction_amount ELSE -transaction_amount END as change
            FROM "transaction"
            WHERE account_id IS NOT NULL AND to_char(transaction_date, 'YYYY') = :year_str
            UNION ALL -- 두 쿼리 결과를 합침
            SELECT linked_account_id, transaction_date,
                        CASE WHEN type = 'INVEST' THEN transaction_amount ELSE -transaction_amount END as change
            FROM "transaction"
            WHERE linked_account_id IS NOT NULL AND type IN ('INVEST', 'TRANSFER') AND to_char(transaction_date, 'YYYY') = :year_str
        """
        all_changes_df = conn.query(
            query,
            params={"year_str": str(year)},
            parse_dates=["transaction_date"],  # 날짜 컬럼 파싱
            ttl=0,
        )

        # 초기 잔액 데이터를 거래 내역 형식으로 변환하여 합칠 준비
        initial_balances_df = accounts_df.rename(
            columns={
                "id": "account_id",
                "initial_balance_date": "transaction_date",
                "initial_balance": "change",
            }
        )[["account_id", "transaction_date", "change"]]

        # 모든 변경 내역 (초기 잔액 포함)을 합치고 날짜 기준으로 정렬
        full_history = pd.concat([all_changes_df, initial_balances_df]).sort_values(
            "transaction_date"
        )
        # 변경 금액이 없는 경우 0으로 채움
        full_history["change"] = full_history["change"].fillna(0)

        # 각 계좌별로 변경 금액의 누적 합계를 계산하여 잔액 필드 생성
        full_history["balance"] = full_history.groupby("account_id")["change"].cumsum()

        # transaction_date를 인덱스로 설정
        full_history.set_index("transaction_date", inplace=True)
        # 각 계좌별로 월별 마지막 잔액을 샘플링
        monthly_balances = (
            full_history.groupby("account_id")["balance"].resample("M").last()
        )

        report_df_source = monthly_balances.reset_index()  # 인덱스 리셋

        # 'transaction_date'를 'YYYY/MM' 형식의 'year_month' 컬럼으로 변환
        report_df_source["year_month"] = report_df_source[
            "transaction_date"
        ].dt.strftime("%Y/%m")

        # 'account_id'를 인덱스, 'year_month'를 컬럼으로 하는 피벗 테이블 생성
        report_df = report_df_source.pivot_table(
            index="account_id", columns="year_month", values="balance"
        )

        # 계좌 ID를 이름으로 매핑하여 인덱스 이름 변경
        id_to_name_map = accounts_df.set_index("id")["name"].to_dict()
        report_df.rename(index=id_to_name_map, inplace=True)

        # 행 방향(axis=1)으로 결측값을 이전 값으로 채움
        report_df.ffill(axis=1, inplace=True)

        # 해당 연도의 모든 월에 대한 컬럼 리스트 생성 (예: '2023/01', '2023/02'...)
        all_months_of_year = [f"{year}/{str(m).zfill(2)}" for m in range(1, 13)]
        # 모든 월 컬럼이 포함되도록 데이터프레임을 재인덱싱하고, 없는 월은 0으로 채움
        report_df = report_df.reindex(columns=all_months_of_year).fillna(0)

        # 최종 데이터프레임의 모든 값을 64비트 정수형으로 변환
        return report_df.astype(np.int64)

    except Exception as e:
        # 오류 발생 시 오류 메시지 출력 및 빈 데이터프레임 반환
        st.error(f"연간 자산 요약 데이터 로드 오류: {e}")
        return pd.DataFrame()
