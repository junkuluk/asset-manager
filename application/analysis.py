import streamlit as st
import pandas as pd
import re
import config

# -------------------------------------------------------------------
# 1. 개별 조건 평가 함수들 (변경 없음)
# -------------------------------------------------------------------

def _evaluate_contains(series, value):
    """시리즈에 특정 문자열이 포함되는지 확인합니다."""
    return series.astype(str).str.contains(value, na=False, regex=False)

def _evaluate_exact(series, value):
    """시리즈의 값이 특정 문자열과 정확히 일치하는지 확인합니다."""
    return series.astype(str).str.strip() == value

def _evaluate_regex(series, value):
    """시리즈가 정규식 패턴과 일치하는지 확인합니다."""
    return series.astype(str).str.contains(value, na=False, regex=True, flags=re.IGNORECASE)

def _evaluate_greater_than(series, value):
    """시리즈의 숫자 값이 특정 값보다 큰지 확인합니다."""
    return pd.to_numeric(series, errors='coerce') > int(value)

def _evaluate_less_than(series, value):
    """시리즈의 숫자 값이 특정 값보다 작은지 확인합니다."""
    return pd.to_numeric(series, errors='coerce') < int(value)

def _evaluate_equals(series, value):
    """시리즈의 숫자 값이 특정 값과 같은지 확인합니다."""
    return pd.to_numeric(series, errors='coerce').eq(int(value))

# -------------------------------------------------------------------
# 2. 매칭 타입과 평가 함수 매핑 (변경 없음)
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
# 3. 메인 엔진 함수들 (PostgreSQL 및 성능 최적화)
# -------------------------------------------------------------------

def run_rule_engine(df: pd.DataFrame, default_category_id: int) -> pd.DataFrame:
    """
    규칙 엔진을 실행하여 DataFrame의 'category_id'를 분류합니다.
    N+1 쿼리 문제를 해결하여 성능을 최적화했습니다.
    """
    if df.empty:
        return df

    conn = st.connection("supabase", type="sql")
    # 1. 모든 규칙과 조건을 한 번에 가져오기
    rules_df = conn.query("SELECT * FROM rule ORDER BY priority", ttl=0)
    conditions_df = conn.query("SELECT * FROM rule_condition", ttl=0)

    if 'category_id' not in df.columns:
        df['category_id'] = default_category_id
    df['category_id'].fillna(default_category_id, inplace=True)

    unclassified_mask = (df['category_id'] == default_category_id)

    for _, rule in rules_df.iterrows():
        if not unclassified_mask.any():
            break

        # 2. DB 대신 Pandas DataFrame에서 조건 필터링
        rule_conditions = conditions_df[conditions_df['rule_id'] == rule['id']]
        if rule_conditions.empty:
            continue

        # 모든 조건이 True로 시작하는 마스크
        combined_conditions_mask = pd.Series(True, index=df.index)

        for _, cond in rule_conditions.iterrows():
            column = cond['column_to_check']
            value = cond['value']
            match_type = cond['match_type'].strip()
            
            eval_func = CONDITION_EVALUATORS.get(match_type)
            if not eval_func or column not in df.columns:
                # 지원하지 않는 함수나 존재하지 않는 컬럼이면, 이 규칙은 적용 불가
                combined_conditions_mask = pd.Series(False, index=df.index)
                break
            
            # 각 조건의 결과를 AND 연산으로 누적
            combined_conditions_mask &= eval_func(df[column], value)
        
        # 최종적으로 분류할 행 = 아직 분류되지 않았고(unclassified) && 모든 조건을 만족하는(combined) 행
        final_mask_to_apply = unclassified_mask & combined_conditions_mask
        df.loc[final_mask_to_apply, 'category_id'] = rule['category_id']
        
        # 분류된 행은 다음 규칙의 대상에서 제외
        unclassified_mask &= ~final_mask_to_apply

    return df


def run_engine_and_update_db():
    """DB의 모든 거래내역을 재분류하고 결과를 다시 DB에 업데이트합니다."""
    print("DB 전체 재분류를 시작합니다...")
    conn = st.connection("supabase", type="sql")

    df = conn.query('SELECT * FROM "transaction"', ttl=0)
    if df.empty:
        print("재분류할 데이터가 없습니다.")
        return 0

    # 미분류 카테고리 ID를 DB에서 조회
    uncategorized_df = conn.query("SELECT id FROM category WHERE category_code = 'UNCATEGORIZED' AND category_type = 'EXPENSE' LIMIT 1", ttl=0)
    default_cat_id = uncategorized_df['id'].iloc[0] if not uncategorized_df.empty else -1 # 기본값 설정

    # 규칙 엔진 실행
    categorized_df = run_rule_engine(df.copy(), default_category_id=default_cat_id)

    # 변경된 내용만 필터링
    update_data = categorized_df[df['category_id'] != categorized_df['category_id']][['id', 'category_id']]
    if update_data.empty:
        print("업데이트할 내용이 없습니다.")
        return 0

    print(f"업데이트 대상 {len(update_data)}건 발견...")
    
    # DB 업데이트 (트랜잭션 사용)
    updated_rows = 0
    try:
        with conn.session.begin() as s:
            for _, row in update_data.iterrows():
                result = s.execute(
                    'UPDATE "transaction" SET category_id = %s WHERE id = %s',
                    (int(row['category_id']), int(row['id']))
                )
                updated_rows += result.rowcount
        print(f"총 {updated_rows}건의 카테고리가 업데이트되었습니다.")
        return updated_rows
    except Exception as e:
        print(f"DB 업데이트 중 오류 발생: {e}")
        return 0


def identify_transfers(df: pd.DataFrame) -> pd.Series:
    """
    이체 규칙을 적용하여 DataFrame의 각 행에 해당하는 연결 계좌 ID를 반환합니다.
    N+1 쿼리 문제를 해결하여 성능을 최적화했습니다.
    """
    if df.empty:
        return pd.Series(dtype='int')

    conn = st.connection("supabase", type="sql")
    # 1. 모든 이체 규칙과 조건을 한 번에 로드
    rules_df = conn.query("SELECT * FROM transfer_rule ORDER BY priority", ttl=0)
    conditions_df = conn.query("SELECT * FROM transfer_rule_condition", ttl=0)

    final_linked_ids = pd.Series(0, index=df.index, dtype='int')
    unidentified_mask = pd.Series(True, index=df.index)

    for _, rule in rules_df.iterrows():
        if not unidentified_mask.any():
            break

        # 2. DB 대신 Pandas DataFrame에서 조건 필터링
        rule_conditions = conditions_df[conditions_df['rule_id'] == rule['id']]
        if rule_conditions.empty:
            continue

        combined_conditions_mask = pd.Series(True, index=df.index)
        for _, cond in rule_conditions.iterrows():
            column, match_type, value = cond['column_to_check'], cond['match_type'], cond['value']
            
            eval_func = CONDITION_EVALUATORS.get(match_type)
            if not eval_func or column not in df.columns:
                combined_conditions_mask = pd.Series(False, index=df.index)
                break
                
            combined_conditions_mask &= eval_func(df[column], value)
        
        mask_to_apply = unidentified_mask & combined_conditions_mask
        if mask_to_apply.any():
            final_linked_ids.loc[mask_to_apply] = rule['linked_account_id']
            unidentified_mask &= ~mask_to_apply

    return final_linked_ids