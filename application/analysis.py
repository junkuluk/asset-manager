import streamlit as st
import pandas as pd
import re
import config
from sqlalchemy import text


def _evaluate_contains(series, value):
    """시리즈에 특정 문자열이 포함되는지 확인."""
    return series.astype(str).str.contains(value, na=False, regex=False)


def _evaluate_exact(series, value):
    """시리즈의 값이 특정 문자열과 정확히 일치하는지 확인."""
    return series.astype(str).str.strip() == value


def _evaluate_regex(series, value):
    """시리즈가 정규식 패턴과 일치하는지 확인."""
    return series.astype(str).str.contains(
        value, na=False, regex=True, flags=re.IGNORECASE
    )


def _evaluate_greater_than(series, value):
    """시리즈의 숫자 값이 특정 값보다 큰지 확인."""
    return pd.to_numeric(series, errors="coerce") > int(value)


def _evaluate_less_than(series, value):
    """시리즈의 숫자 값이 특정 값보다 작은지 확인."""
    return pd.to_numeric(series, errors="coerce") < int(value)


def _evaluate_equals(series, value):
    """시리즈의 숫자 값이 특정 값과 같은지 확인."""
    return pd.to_numeric(series, errors="coerce").eq(int(value))


CONDITION_EVALUATORS = {
    "CONTAINS": _evaluate_contains,
    "EXACT": _evaluate_exact,
    "REGEX": _evaluate_regex,
    "GREATER_THAN": _evaluate_greater_than,
    "LESS_THAN": _evaluate_less_than,
    "EQUALS": _evaluate_equals,
}


def run_rule_engine(df: pd.DataFrame, default_category_id: int) -> pd.DataFrame:

    if df.empty:
        return df

    conn = st.connection("supabase", type="sql")

    rules_df = conn.query("SELECT * FROM rule ORDER BY priority", ttl=0)
    conditions_df = conn.query("SELECT * FROM rule_condition", ttl=0)

    if "category_id" not in df.columns:
        df["category_id"] = default_category_id
    df["category_id"].fillna(default_category_id, inplace=True)

    unclassified_mask = df["category_id"] == default_category_id

    for _, rule in rules_df.iterrows():
        if not unclassified_mask.any():
            break

        rule_conditions = conditions_df[conditions_df["rule_id"] == rule["id"]]
        if rule_conditions.empty:
            continue

        combined_conditions_mask = pd.Series(True, index=df.index)

        for _, cond in rule_conditions.iterrows():
            column = cond["column_to_check"]
            value = cond["value"]
            match_type = cond["match_type"].strip()

            eval_func = CONDITION_EVALUATORS.get(match_type)
            if not eval_func or column not in df.columns:

                combined_conditions_mask = pd.Series(False, index=df.index)
                break

            combined_conditions_mask &= eval_func(df[column], value)

        final_mask_to_apply = unclassified_mask & combined_conditions_mask
        df.loc[final_mask_to_apply, "category_id"] = rule["category_id"]

        unclassified_mask &= ~final_mask_to_apply

    return df


def identify_transfers(df: pd.DataFrame) -> pd.Series:

    if df.empty:
        return pd.Series(dtype="int")

    conn = st.connection("supabase", type="sql")

    rules_df = conn.query("SELECT * FROM transfer_rule ORDER BY priority", ttl=0)
    conditions_df = conn.query("SELECT * FROM transfer_rule_condition", ttl=0)

    final_linked_ids = pd.Series(0, index=df.index, dtype="int")
    unidentified_mask = pd.Series(True, index=df.index)

    for _, rule in rules_df.iterrows():
        if not unidentified_mask.any():
            break

        rule_conditions = conditions_df[conditions_df["rule_id"] == rule["id"]]
        if rule_conditions.empty:
            continue

        combined_conditions_mask = pd.Series(True, index=df.index)
        for _, cond in rule_conditions.iterrows():
            column, match_type, value = (
                cond["column_to_check"],
                cond["match_type"],
                cond["value"],
            )

            eval_func = CONDITION_EVALUATORS.get(match_type)
            if not eval_func or column not in df.columns:
                combined_conditions_mask = pd.Series(False, index=df.index)
                break

            combined_conditions_mask &= eval_func(df[column], value)

        mask_to_apply = unidentified_mask & combined_conditions_mask
        if mask_to_apply.any():
            final_linked_ids.loc[mask_to_apply] = rule["linked_account_id"]
            unidentified_mask &= ~mask_to_apply

    return final_linked_ids


def run_engine_and_update_db_final():
    print("DB 전체 재분류를 시작합니다...")
    conn = st.connection("supabase", type="sql")
    message = ""
    with conn.session as s:
        query = text(
            """
            SELECT t.* FROM "transaction" t
            JOIN category c ON t.category_id = c.id
            WHERE c.category_code = 'UNCATEGORIZED' AND t.is_manual_category = false AND category_type in ('EXPENSE')
        """
        )

        df_expense = pd.DataFrame(s.execute(query).mappings().all())

        if df_expense.empty:
            message += "지출 카테고리를 재분류할 대상이 없습니다.\n"
        else:

            default_expense_cat_id = df_expense["category_id"].iloc[0]
            categorized_expense_df = run_rule_engine(df_expense, default_expense_cat_id)
            updates_expense_df = categorized_expense_df[
                categorized_expense_df["category_id"] != default_expense_cat_id
            ]

            if updates_expense_df.empty:
                message += "새롭게 분류된 지출 거래가 없습니다.\n"
            else:
                update__expense_params = [
                    {
                        "category_id": int(row["category_id"]),
                        "transaction_id": int(row["id"]),
                    }
                    for _, row in updates_expense_df.iterrows()
                ]

                if update__expense_params:
                    s.execute(
                        text(
                            'UPDATE "transaction" SET category_id = :category_id WHERE id = :transaction_id'
                        ),
                        update__expense_params,
                    )
                s.commit()
                message += f"총 {len(update__expense_params)}건의 지출 거래에 카테고리 규칙을 재적용했습니다.\n"

        query = text(
            """
            SELECT t.* FROM "transaction" t
            JOIN category c ON t.category_id = c.id
            WHERE c.category_code = 'UNCATEGORIZED' AND t.is_manual_category = false AND category_type in ('INCOME')
        """
        )

        df_income = pd.DataFrame(s.execute(query).mappings().all())

        if df_income.empty:
            message += "수입 카테고리를 재분류할 대상이 없습니다.\n"
            return message
        else:
            default_income_cat_id = df_income["category_id"].iloc[0]
            categorized_income_df = run_rule_engine(df_income, default_income_cat_id)
            updates_income_df = categorized_income_df[
                categorized_income_df["category_id"] != default_income_cat_id
            ]

            if updates_income_df.empty:
                message += "새롭게 분류된 수입 거래가 없습니다.\n"
                return message
            else:
                update__income_params = [
                    {
                        "category_id": int(row["category_id"]),
                        "transaction_id": int(row["id"]),
                    }
                    for _, row in updates_income_df.iterrows()
                ]

                if update__income_params:
                    s.execute(
                        text(
                            'UPDATE "transaction" SET category_id = :category_id WHERE id = :transaction_id'
                        ),
                        update__income_params,
                    )
                s.commit()
                message += f"총 {len(update__income_params)}건의 수입 거래에 카테고리 규칙을 재적용했습니다.\n"
                return message
