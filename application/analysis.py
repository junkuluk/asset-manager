import streamlit as st
import pandas as pd
import re
from sqlalchemy import text  # SQL 쿼리 문자열을 안전하게 처리하기 위함


def _evaluate_contains(series, value):
    """
    Pandas Series의 문자열 값이 특정 문자열을 포함하는지 확인.
    대소문자를 구분하며 정규식 특수 문자는 처리하지 않음.
    """
    return series.astype(str).str.contains(value, na=False, regex=False)


def _evaluate_exact(series, value):
    """
    Pandas Series의 문자열 값이 특정 문자열과 정확히 일치하는지 확인.
    선행/후행 공백을 제거한 후 비교.
    """
    return series.astype(str).str.strip() == value


def _evaluate_regex(series, value):
    """
    Pandas Series의 문자열 값이 주어진 정규식 패턴과 일치하는지 확인.
    대소문자를 구분하지 않음 (re.IGNORECASE).
    """
    return series.astype(str).str.contains(
        value, na=False, regex=True, flags=re.IGNORECASE
    )


def _evaluate_greater_than(series, value):
    """
    Pandas Series의 숫자 값이 특정 값보다 큰지 확인.
    비숫자 값은 NaN으로 변환 후 비교.
    """
    return pd.to_numeric(series, errors="coerce") > int(value)


def _evaluate_less_than(series, value):
    """
    Pandas Series의 숫자 값이 특정 값보다 작은지 확인.
    비숫자 값은 NaN으로 변환 후 비교.
    """
    return pd.to_numeric(series, errors="coerce") < int(value)


def _evaluate_equals(series, value):
    """
    Pandas Series의 숫자 값이 특정 값과 같은지 확인.
    비숫자 값은 NaN으로 변환 후 비교.
    """
    return pd.to_numeric(series, errors="coerce").eq(int(value))


# 조건 평가 함수들을 딕셔너리로 매핑. match_type에 따라 적절한 함수를 선택하여 사용.
CONDITION_EVALUATORS = {
    "CONTAINS": _evaluate_contains,
    "EXACT": _evaluate_exact,
    "REGEX": _evaluate_regex,
    "GREATER_THAN": _evaluate_greater_than,
    "LESS_THAN": _evaluate_less_than,
    "EQUALS": _evaluate_equals,
}


def run_rule_engine(df: pd.DataFrame, default_category_id: int) -> pd.DataFrame:
    """
    주어진 거래 데이터프레임에 분류 규칙을 적용하여 카테고리를 자동 할당.
    규칙은 데이터베이스에서 우선순위(priority)에 따라 로드되어 적용됨.

    Args:
        df (pd.DataFrame): 분류할 거래 데이터프레임.
        default_category_id (int): 미분류 거래에 할당할 기본 카테고리 ID.

    Returns:
        pd.DataFrame: 카테고리가 할당된 거래 데이터프레임.
    """

    if df.empty:
        return df  # 데이터프레임이 비어있으면 그대로 반환

    conn = st.connection("supabase", type="sql")  # Supabase 데이터베이스 연결 객체

    # 데이터베이스에서 분류 규칙과 규칙 조건 로드 (우선순위 순으로 정렬)
    rules_df = conn.query("SELECT * FROM rule ORDER BY priority", ttl=0)
    conditions_df = conn.query("SELECT * FROM rule_condition", ttl=0)

    # 'category_id' 컬럼이 없으면 기본값을 가진 컬럼을 추가
    if "category_id" not in df.columns:
        df["category_id"] = default_category_id
    # 'category_id' 컬럼의 NaN 값을 기본 카테고리 ID로 채움
    df["category_id"].fillna(default_category_id, inplace=True)

    # 아직 분류되지 않은 거래를 식별하는 마스크. 처음에는 모든 거래가 미분류 상태.
    unclassified_mask = df["category_id"] == default_category_id

    # 각 규칙을 우선순위 순으로 순회하며 적용
    for _, rule in rules_df.iterrows():
        # 더 이상 미분류된 거래가 없으면 루프 중단
        if not unclassified_mask.any():
            break

        # 현재 규칙에 해당하는 조건들을 필터링
        rule_conditions = conditions_df[conditions_df["rule_id"] == rule["id"]]
        if rule_conditions.empty:
            continue  # 규칙에 조건이 없으면 건너뛰기

        # 현재 규칙의 모든 조건을 만족하는 거래를 식별하기 위한 마스크 (초기값 True)
        combined_conditions_mask = pd.Series(True, index=df.index)

        # 현재 규칙의 각 조건을 순회하며 평가
        for _, cond in rule_conditions.iterrows():
            column = cond["column_to_check"]
            value = cond["value"]
            match_type = cond["match_type"].strip()

            # 조건 유형에 맞는 평가 함수 가져오기
            eval_func = CONDITION_EVALUATORS.get(match_type)
            # 평가 함수가 없거나 대상 컬럼이 데이터프레임에 없으면, 이 규칙은 어떤 행에도 적용되지 않도록 마스크를 False로 설정 후 중단
            if not eval_func or column not in df.columns:
                combined_conditions_mask = pd.Series(False, index=df.index)
                break

            # 현재 조건 평가 결과를 combined_conditions_mask에 AND 연산으로 적용
            combined_conditions_mask &= eval_func(df[column], value)

        # 아직 미분류 상태이면서 현재 규칙의 모든 조건을 만족하는 거래를 최종적으로 식별
        final_mask_to_apply = unclassified_mask & combined_conditions_mask
        # 해당 거래들의 'category_id'를 규칙에 지정된 카테고리 ID로 업데이트
        df.loc[final_mask_to_apply, "category_id"] = rule["category_id"]

        # 성공적으로 분류된 거래들을 미분류 마스크에서 제거
        unclassified_mask &= ~final_mask_to_apply

    return df


def identify_transfers(df: pd.DataFrame) -> pd.Series:
    """
    주어진 거래 데이터프레임에서 이체 거래를 식별하고 연결된 계좌 ID를 반환.
    이체 규칙은 데이터베이스에서 우선순위(priority)에 따라 로드되어 적용됨.

    Args:
        df (pd.DataFrame): 이체 여부를 식별할 거래 데이터프레임.

    Returns:
        pd.Series: 각 거래에 대한 연결된 계좌 ID (이체가 아니면 0).
    """

    if df.empty:
        return pd.Series(dtype="int")  # 데이터프레임이 비어있으면 빈 Series 반환

    conn = st.connection("supabase", type="sql")  # Supabase 데이터베이스 연결 객체

    # 데이터베이스에서 이체 규칙과 규칙 조건 로드 (우선순위 순으로 정렬)
    rules_df = conn.query("SELECT * FROM transfer_rule ORDER BY priority", ttl=0)
    conditions_df = conn.query("SELECT * FROM transfer_rule_condition", ttl=0)

    # 각 거래에 대해 최종적으로 식별된 연결 계좌 ID를 저장할 Series (초기값 0)
    final_linked_ids = pd.Series(0, index=df.index, dtype="int")
    # 아직 이체로 식별되지 않은 거래를 식별하는 마스크 (처음에는 모든 거래)
    unidentified_mask = pd.Series(True, index=df.index)

    # 각 이체 규칙을 우선순위 순으로 순회하며 적용
    for _, rule in rules_df.iterrows():
        # 더 이상 이체로 식별되지 않은 거래가 없으면 루프 중단
        if not unidentified_mask.any():
            break

        # 현재 규칙에 해당하는 조건들을 필터링
        rule_conditions = conditions_df[conditions_df["rule_id"] == rule["id"]]
        if rule_conditions.empty:
            continue  # 규칙에 조건이 없으면 건너뛰기

        # 현재 규칙의 모든 조건을 만족하는 거래를 식별하기 위한 마스크 (초기값 True)
        combined_conditions_mask = pd.Series(True, index=df.index)
        # 현재 규칙의 각 조건을 순회하며 평가
        for _, cond in rule_conditions.iterrows():
            column, match_type, value = (
                cond["column_to_check"],
                cond["match_type"],
                cond["value"],
            )

            # 조건 유형에 맞는 평가 함수 가져오기
            eval_func = CONDITION_EVALUATORS.get(match_type)
            # 평가 함수가 없거나 대상 컬럼이 데이터프레임에 없으면, 이 규칙은 어떤 행에도 적용되지 않도록 마스크를 False로 설정 후 중단
            if not eval_func or column not in df.columns:
                combined_conditions_mask = pd.Series(False, index=df.index)
                break

            # 현재 조건 평가 결과를 combined_conditions_mask에 AND 연산으로 적용
            combined_conditions_mask &= eval_func(df[column], value)

        # 아직 이체로 식별되지 않았고 현재 규칙의 모든 조건을 만족하는 거래를 최종적으로 식별
        mask_to_apply = unidentified_mask & combined_conditions_mask
        if mask_to_apply.any():
            # 해당 거래들의 'linked_account_id'를 규칙에 지정된 연결 계좌 ID로 업데이트
            final_linked_ids.loc[mask_to_apply] = rule["linked_account_id"]
            # 성공적으로 식별된 거래들을 미식별 마스크에서 제거
            unidentified_mask &= ~mask_to_apply

    return final_linked_ids


# should not be used until this is get fixed.
def run_engine_and_update_db_final():
    """
    데이터베이스에 저장된 미분류 거래(수입/지출)에 대해 규칙 엔진을 실행하고,
    새롭게 분류된 거래를 데이터베이스에 반영.
    수동으로 카테고리가 지정된 거래는 제외.
    """
    print("DB 전체 재분류를 시작합니다...")
    conn = st.connection("supabase", type="sql")  # Supabase 데이터베이스 연결 객체
    message = ""  # 반환할 메시지 문자열 초기화

    # 데이터베이스 세션 시작 (트랜잭션 관리)
    with conn.session as s:
        # 미분류된 지출 거래 중 수동으로 분류되지 않은 거래를 조회
        query = text(
            """
            SELECT t.* FROM "transaction" t
            JOIN category c ON t.category_id = c.id
            WHERE c.category_code = 'UNCATEGORIZED' AND t.is_manual_category = false AND c.category_type = 'EXPENSE'
        """
        )

        df_expense = pd.DataFrame(s.execute(query).mappings().all())

        if df_expense.empty:
            message += "지출 카테고리를 재분류할 대상이 없습니다.\n"
        else:
            # 기본 지출 카테고리 ID (조회된 데이터프레임에서 가져옴)
            default_expense_cat_id = df_expense["category_id"].iloc[0]
            # 지출 거래에 대해 규칙 엔진 실행
            categorized_expense_df = run_rule_engine(df_expense, default_expense_cat_id)
            # 규칙 엔진에 의해 카테고리가 변경된(새롭게 분류된) 지출 거래만 필터링
            updates_expense_df = categorized_expense_df[
                categorized_expense_df["category_id"] != default_expense_cat_id
            ]

            if updates_expense_df.empty:
                message += "새롭게 분류된 지출 거래가 없습니다.\n"
            else:
                # 업데이트할 지출 거래의 파라미터 리스트 생성
                update__expense_params = [
                    {
                        "category_id": int(row["category_id"]),
                        "transaction_id": int(row["id"]),
                    }
                    for _, row in updates_expense_df.iterrows()
                ]

                if update__expense_params:
                    # 데이터베이스의 'transaction' 테이블 업데이트 (카테고리 ID 변경)
                    s.execute(
                        text(
                            'UPDATE "transaction" SET category_id = :category_id WHERE id = :transaction_id'
                        ),
                        update__expense_params,  # 여러 행을 한 번에 업데이트
                    )
                    s.commit()  # 변경사항 커밋
                message += f"총 {len(update__expense_params)}건의 지출 거래에 카테고리 규칙을 재적용했습니다.\n"

        # 미분류된 수입 거래 중 수동으로 분류되지 않은 거래를 조회
        query = text(
            """
            SELECT t.* FROM "transaction" t
            JOIN category c ON t.category_id = c.id
            WHERE c.category_code = 'UNCATEGORIZED' AND t.is_manual_category = false AND c.category_type = 'INCOME'
        """
        )

        df_income = pd.DataFrame(s.execute(query).mappings().all())

        if df_income.empty:
            message += "수입 카테고리를 재분류할 대상이 없습니다.\n"
            return message  # 수입 거래가 없으면 현재까지의 메시지 반환
        else:
            # 기본 수입 카테고리 ID (조회된 데이터프레임에서 가져옴)
            default_income_cat_id = df_income["category_id"].iloc[0]
            # 수입 거래에 대해 규칙 엔진 실행
            categorized_income_df = run_rule_engine(df_income, default_income_cat_id)
            # 규칙 엔진에 의해 카테고리가 변경된(새롭게 분류된) 수입 거래만 필터링
            updates_income_df = categorized_income_df[
                categorized_income_df["category_id"] != default_income_cat_id
            ]

            if updates_income_df.empty:
                message += "새롭게 분류된 수입 거래가 없습니다.\n"
                return message  # 업데이트할 수입 거래가 없으면 현재까지의 메시지 반환
            else:
                # 업데이트할 수입 거래의 파라미터 리스트 생성
                update__income_params = [
                    {
                        "category_id": int(row["category_id"]),
                        "transaction_id": int(row["id"]),
                    }
                    for _, row in updates_income_df.iterrows()
                ]

                if update__income_params:
                    # 데이터베이스의 'transaction' 테이블 업데이트 (카테고리 ID 변경)
                    s.execute(
                        text(
                            'UPDATE "transaction" SET category_id = :category_id WHERE id = :transaction_id'
                        ),
                        update__income_params,  # 여러 행을 한 번에 업데이트
                    )
                    s.commit()  # 변경사항 커밋
                message += f"총 {len(update__income_params)}건의 수입 거래에 카테고리 규칙을 재적용했습니다.\n"
                return message  # 최종 메시지 반환
