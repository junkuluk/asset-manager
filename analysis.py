import sqlite3
import pandas as pd
import re
import config

# -------------------------------------------------------------------
# 1. 개별 조건 평가 함수들 (작고, 독립적이며, 테스트하기 쉬움)
# -------------------------------------------------------------------

def _evaluate_contains(series, value):
    return series.astype(str).str.contains(value, na=False, regex=False)


def _evaluate_exact(series, value):
    return series.astype(str).str.strip() == value


def _evaluate_regex(series, value):
    return series.astype(str).str.contains(value, na=False, regex=True, flags=re.IGNORECASE)


def _evaluate_greater_than(series, value):
    return pd.to_numeric(series, errors='coerce') > int(value)


def _evaluate_less_than(series, value):
    return pd.to_numeric(series, errors='coerce') < int(value)


def _evaluate_equals(series, value):
    # .eq()는 pandas의 동등 비교 함수로, 타입에 강건함
    return pd.to_numeric(series, errors='coerce').eq(int(value))


# -------------------------------------------------------------------
# 2. 매칭 타입과 평가 함수를 잇는 '전략' 딕셔너리
# -------------------------------------------------------------------
CONDITION_EVALUATORS = {
    'CONTAINS': _evaluate_contains,
    'EXACT': _evaluate_exact,
    'REGEX': _evaluate_regex,
    'GREATER_THAN': _evaluate_greater_than,
    'LESS_THAN': _evaluate_less_than,
    'EQUALS': _evaluate_equals
}


# -------------------------------------------------------------------
# 3. 간소화된 메인 규칙 엔진 함수
# -------------------------------------------------------------------
def run_rule_engine(df, default_category_id, db_path=config.DB_PATH):
    if df.empty:
        return df

    conn = sqlite3.connect(db_path)
    rules = pd.read_sql_query("SELECT * FROM rule ORDER BY priority ", conn)

    conditions_map = {}
    for rule_id in rules['id']:
        conditions_map[rule_id] = pd.read_sql_query(f"SELECT * FROM rule_condition WHERE rule_id = {rule_id}", conn)
    conn.close()

    if 'category_id' not in df.columns:
        df['category_id'] = default_category_id
    df['category_id'].fillna(default_category_id, inplace=True)

    unclassified_mask = (df['category_id'] == default_category_id)

    for _, rule in rules.iterrows():
        if not unclassified_mask.any():
            break

        target_category_id = rule['category_id']
        conditions = conditions_map[rule['id']]

        rule_applies_mask = pd.Series(True, index=df.index)

        for _, cond in conditions.iterrows():
            column = cond['column_to_check']
            value = cond['value']
            # --- 여기가 수정되었습니다! ---
            match_type = cond['match_type'].strip()  # 양 끝 공백을 제거하여 비교 안정성 확보

            eval_func = CONDITION_EVALUATORS.get(match_type)

            if eval_func:
                current_mask = eval_func(df[column], value)
            else:
                current_mask = pd.Series(False, index=df.index)

            rule_applies_mask &= current_mask

        final_mask = unclassified_mask & rule_applies_mask
        df.loc[final_mask, 'category_id'] = target_category_id
        unclassified_mask &= ~final_mask

    return df


def run_engine_and_update_db(db_path=config.DB_PATH):
    """
    DB의 모든 거래내역을 불러와 규칙 엔진을 실행하고, 결과를 다시 DB에 업데이트합니다.
    """
    print("DB 전체 재분류를 시작합니다...")
    conn = sqlite3.connect(db_path)

    # 업데이트할 대상은 '미분류'이거나, 사용자가 수동으로 바꾸지 않은 거래들
    # 여기서는 모든 거래를 대상으로 하겠습니다.
    df = pd.read_sql_query("SELECT * FROM \"transaction\"", conn)

    if df.empty:
        print("재분류할 데이터가 없습니다.")
        conn.close()
        return 0

    # 규칙 엔진 실행 (기존 함수 재사용)
    categorized_df = run_rule_engine(df, default_category_id=4, db_path=db_path)

    # 업데이트할 내용만 추림 (id, category_id)
    update_data = categorized_df[['id', 'category_id']]

    print(update_data)

    # DB 업데이트
    cursor = conn.cursor()
    try:
        # executemany를 사용하여 여러 업데이트를 효율적으로 실행
        cursor.executemany("""
                           UPDATE "transaction"
                           SET category_id = ?
                           WHERE id = ?
                           """, [(row['category_id'], row['id']) for _, row in update_data.iterrows()])

        conn.commit()
        updated_rows = cursor.rowcount
        print(f"총 {updated_rows}건의 카테고리가 업데이트되었습니다.")
        return updated_rows
    except Exception as e:
        print(f"DB 업데이트 중 오류 발생: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()


def identify_transfers(df, db_path=config.DB_PATH):

    conn = sqlite3.connect(db_path)
    rules = pd.read_sql_query("SELECT * FROM transfer_rule ORDER BY priority ASC", conn)

    final_mask = pd.Series(False, index=df.index)

    for _, rule in rules.iterrows():
        conditions = pd.read_sql_query(f"SELECT * FROM transfer_rule_condition WHERE rule_id = {rule['id']}", conn)

        rule_applies_mask = pd.Series(True, index=df.index)
        for _, cond in conditions.iterrows():
            column, match_type, value = cond['column_to_check'], cond['match_type'], cond['value']

            eval_func = CONDITION_EVALUATORS.get(match_type)
            if eval_func:
                current_mask = eval_func(df[column], value)
                rule_applies_mask &= current_mask
            else:
                rule_applies_mask = pd.Series(False, index=df.index)
                break

        # 여러 규칙 중 하나라도 만족하면 True (OR 연산)
        final_mask |= rule_applies_mask

    conn.close()
    return final_mask