import json
import streamlit as st
import config
from core.db_manager import rebuild_category_paths
import pandas as pd

def seed_initial_categories():
    """초기 카테고리 데이터를 모두 삽입하고, 계층 경로를 재구성합니다."""
    conn = st.connection("supabase", type="sql")
    
    count_df = conn.query("SELECT COUNT(*) as cnt FROM category", ttl=0)
    if not count_df.empty and count_df['cnt'].iloc[0] > 0:
        print("카테고리 데이터가 이미 존재하여 초기 데이터 삽입을 건너뜁니다.")
        return

    print("초기 카테고리 데이터를 삽입합니다...")
    
    # conn.session을 직접 사용하여 복잡한 트랜잭션 관리
    s = conn.session
    try:
        # 헬퍼 함수 정의: INSERT 후 ID 반환
        def insert_and_get_id(query, params):
            result = s.execute(query, params)
            return result.scalar_one()

        # --- Level 1 삽입 ---
        insert_top_query = "INSERT INTO category (category_code, category_type, description, depth) VALUES (%s, %s, %s, %s) RETURNING id"
        expense_id = insert_and_get_id(insert_top_query, ('EXPENSE', 'EXPENSE', '지출', 1))
        investment_id = insert_and_get_id(insert_top_query, ('INVEST', 'INVEST', '투자', 1))
        income_id = insert_and_get_id(insert_top_query, ('INCOME', 'INCOME', '수입', 1))
        transfer_id = insert_and_get_id(insert_top_query, ('TRANSFER', 'TRANSFER', '내부 이체', 1))

        # --- Level 2 삽입 ---
        insert_level_query = "INSERT INTO category (category_code, category_type, parent_id, description, depth) VALUES (%s, %s, %s, %s, %s) RETURNING id"
        insert_and_get_id(insert_level_query, ('UNCATEGORIZED', 'EXPENSE', expense_id, '미분류 지출', 2))
        insert_and_get_id(insert_level_query, ('UNCATEGORIZED', 'INCOME', income_id, '미분류 수입', 2))
        fixed_income_id = insert_and_get_id(insert_level_query, ('FIXED_INCOME', 'INCOME', income_id, '고정 수입', 2))
        variable_income_id = insert_and_get_id(insert_level_query, ('VARIABLE_INCOME', 'INCOME', income_id, '변동 수입', 2))
        fixed_expense_id = insert_and_get_id(insert_level_query, ('FIXED_EXPENSE', 'EXPENSE', expense_id, '고정 지출', 2))
        variable_expense_id = insert_and_get_id(insert_level_query, ('VARIABLE_EXPENSE', 'EXPENSE', expense_id, '변동 지출', 2))
        investment_lvl2_id = insert_and_get_id(insert_level_query, ('INVESTMENT', 'INVEST', investment_id, '투자', 2))
        insert_and_get_id(insert_level_query, ('CARD_PAYMENT', 'TRANSFER', transfer_id, '카드대금 이체', 2))

        # --- Level 3: 투자 하위 ---
        insert_and_get_id(insert_level_query, ('SAVINGS', 'INVEST', investment_lvl2_id, '저축', 3))
        insert_and_get_id(insert_level_query, ('STOCKS', 'INVEST', investment_lvl2_id, '주식', 3))
        insert_and_get_id(insert_level_query, ('CRYPTOCURRENCY', 'INVEST', investment_lvl2_id, '비트코인', 3))
        insert_and_get_id(insert_level_query, ('REAL_ESTATE', 'INVEST', investment_lvl2_id, '부동산', 3))

        # --- Level 3: 수입 하위 ---
        insert_and_get_id(insert_level_query, ('SALARY', 'INCOME', fixed_income_id, '급여', 3))
        subsidy_id = insert_and_get_id(insert_level_query, ('SUBSIDY', 'INCOME', fixed_income_id, '지원금', 3))
        insert_and_get_id(insert_level_query, ('INCENTIVE', 'INCOME', variable_income_id, '인센티브', 3))
        insert_and_get_id(insert_level_query, ('FINANCIAL_INCOME', 'INCOME', variable_income_id, '금융수입', 3))

        # --- Level 3: 고정 지출 하위 ---
        housing_id = insert_and_get_id(insert_level_query, ('HOUSING_EXPENSE', 'EXPENSE', fixed_expense_id, '주거비', 3))
        utility_id = insert_and_get_id(insert_level_query, ('UTILITY_BILLS', 'EXPENSE', fixed_expense_id, '공과금', 3))
        comm_id = insert_and_get_id(insert_level_query, ('COMMUNICATION_EXPENSE', 'EXPENSE', fixed_expense_id, '통신비', 3))
        insurance_id = insert_and_get_id(insert_level_query, ('INSURANCE_EXPENSE', 'EXPENSE', fixed_expense_id, '보험료', 3))
        membership_id = insert_and_get_id(insert_level_query, ('MEMBERSHIP', 'EXPENSE', fixed_expense_id, '회원료', 3))
        insert_and_get_id(insert_level_query, ('FAMILY_GATHERING', 'EXPENSE', fixed_expense_id, '가족 모임비', 3))

        # --- Level 3: 변동 지출 하위 ---
        food_id = insert_and_get_id(insert_level_query, ('FOOD_EXPENSE', 'EXPENSE', variable_expense_id, '식비', 3))
        transport_id = insert_and_get_id(insert_level_query, ('TRANSPORTATION_EXPENSE', 'EXPENSE', variable_expense_id, '교통비', 3))
        shopping_id = insert_and_get_id(insert_level_query, ('SHOPPING', 'EXPENSE', variable_expense_id, '쇼핑', 3))
        medical_id = insert_and_get_id(insert_level_query, ('MEDICAL_EXPENSE', 'EXPENSE', variable_expense_id, '의료비', 3))
        insert_and_get_id(insert_level_query, ('EDUCATION_EXPENSE', 'EXPENSE', variable_expense_id, '교육비', 3))
        living_id = insert_and_get_id(insert_level_query, ('LIVING_EXPENSE', 'EXPENSE', variable_expense_id, '생활비', 3))
        insert_and_get_id(insert_level_query, ('EVENT_EXPENSE', 'EXPENSE', variable_expense_id, '경조사비', 3))
        leisure_id = insert_and_get_id(insert_level_query, ('LEISURE_EXPENSE', 'EXPENSE', variable_expense_id, '여가비', 3))

        # --- Level 4: 세부 항목들 ---
        # 주거비 하위
        insert_and_get_id(insert_level_query, ('MONTHLY_RENT', 'EXPENSE', housing_id, '월세', 4))
        insert_and_get_id(insert_level_query, ('MANAGEMENT_FEE', 'EXPENSE', housing_id, '관리비', 4))
        # 공과금 하위
        insert_and_get_id(insert_level_query, ('ELECTRICITY_BILL', 'EXPENSE', utility_id, '전기세', 4))
        insert_and_get_id(insert_level_query, ('WATER_BILL', 'EXPENSE', utility_id, '수도세', 4))
        insert_and_get_id(insert_level_query, ('GAS_BILL', 'EXPENSE', utility_id, '가스비', 4))
        # 통신비 하위
        insert_and_get_id(insert_level_query, ('INTERNET_BILL', 'EXPENSE', comm_id, '인터넷', 4))
        insert_and_get_id(insert_level_query, ('TV_BILL', 'EXPENSE', comm_id, '티비수신비', 4))
        insert_and_get_id(insert_level_query, ('MOBILE_BILL', 'EXPENSE', comm_id, '핸드폰비', 4))
        # 보험료 하위
        insert_and_get_id(insert_level_query, ('YOUNGJUN_INSURANCE', 'EXPENSE', insurance_id, '영준 보험', 4))
        insert_and_get_id(insert_level_query, ('HYEIN_INSURANCE', 'EXPENSE', insurance_id, '혜인 보험', 4))
        insert_and_get_id(insert_level_query, ('SEA_INSURANCE', 'EXPENSE', insurance_id, '세아 보험', 4))
        # 회원료 하위
        insert_and_get_id(insert_level_query, ('COUPANG_MEMBERSHIP', 'EXPENSE', membership_id, '쿠팡 맴버쉽', 4))
        # 식비 하위
        insert_and_get_id(insert_level_query, ('DINING_OUT', 'EXPENSE', food_id, '외식', 4))
        insert_and_get_id(insert_level_query, ('DELIVERY_FOOD', 'EXPENSE', food_id, '배달', 4))
        insert_and_get_id(insert_level_query, ('ALCOHOL', 'EXPENSE', food_id, '주류', 4))
        insert_and_get_id(insert_level_query, ('CONVENIENCE_STORE', 'EXPENSE', food_id, '편의점', 4))
        insert_and_get_id(insert_level_query, ('GROCERIES', 'EXPENSE', food_id, '식료품', 4))
        # 교통비 하위
        insert_and_get_id(insert_level_query, ('PUBLIC_TRANSPORT', 'EXPENSE', transport_id, '대중교통비', 4))
        insert_and_get_id(insert_level_query, ('FUEL_EXPENSE', 'EXPENSE', transport_id, '주유비', 4))
        # 쇼핑 하위
        insert_and_get_id(insert_level_query, ('CLOTHING', 'EXPENSE', shopping_id, '의류비', 4))
        insert_and_get_id(insert_level_query, ('FURNITURE', 'EXPENSE', shopping_id, '가구', 4))
        insert_and_get_id(insert_level_query, ('CHILDCARE_PRODUCTS', 'EXPENSE', shopping_id, '유아용품', 4))
        insert_and_get_id(insert_level_query, ('ELECTRONICS', 'EXPENSE', shopping_id, '전자제품', 4))
        # 의료비 하위
        insert_and_get_id(insert_level_query, ('HOSPITAL_EXPENSE', 'EXPENSE', medical_id, '병원비', 4))
        insert_and_get_id(insert_level_query, ('PHARMACY', 'EXPENSE', medical_id, '의약품', 4))
        # 생활비 하위
        insert_and_get_id(insert_level_query, ('ALLOWANCE', 'EXPENSE', living_id, '용돈', 4))
        insert_and_get_id(insert_level_query, ('LAUNDRY_EXPENSE', 'EXPENSE', living_id, '세탁비', 4))
        insert_and_get_id(insert_level_query, ('CHILDCARE_EXPENSE', 'EXPENSE', living_id, '유아비', 4))
        # 여가비 하위
        insert_and_get_id(insert_level_query, ('TRAVEL', 'EXPENSE', leisure_id, '여행', 4))
        insert_and_get_id(insert_level_query, ('MOVIES', 'EXPENSE', leisure_id, '영화', 4))
        # 지원금 하위
        insert_and_get_id(insert_level_query, ('CHILD_SUBSIDY', 'INCOME', subsidy_id, '아동수당', 4))
        insert_and_get_id(insert_level_query, ('PARENT_SUBSIDY', 'INCOME', subsidy_id, '부모수당', 4))
        insert_and_get_id(insert_level_query, ('MOBILE_SUBSIDY', 'INCOME', subsidy_id, '핸드폰지원금', 4))
        
        s.commit()
        print("초기 카테고리 데이터 삽입 완료.")
        
        # 경로 재계산
        rebuild_category_paths()
        print("초기 카테고리 경로 작업 완료.")

    except Exception as e:
        print(f"초기 데이터 삽입 중 오류 발생: {e}")
        s.rollback()


def seed_initial_parties():
    """초기 거래처 데이터를 삽입합니다."""
    conn = st.connection("supabase", type="sql")

    count_df = conn.query('SELECT COUNT(*) as cnt FROM "transaction_party"', ttl=0)
    if not count_df.empty and count_df['cnt'].iloc[0] > 0:
        return

    print("초기 거래처 데이터를 삽입합니다...")
    parties_to_seed = [
        ('UNREGISTERED', '미등록'), ('쿠팡', '쿠팡'), ('GS25', 'GS25 편의점'),
        ('스타필드', '스타필드'), ('쿠팡이츠', '쿠팡이츠')
    ]
    
    try:
        with conn.session.begin() as s:
            for code, desc in parties_to_seed:
                s.execute('INSERT INTO "transaction_party" (party_code, description) VALUES (%s, %s)', (code, desc))
        print("초기 거래처 데이터 삽입 완료.")
    except Exception as e:
        print(f"초기 거래처 데이터 삽입 중 오류 발생: {e}")


def seed_initial_rules(rules_path=config.RULES_PATH):
    """JSON 파일에서 초기 분류 규칙을 로드하여 삽입합니다."""
    conn = st.connection("supabase", type="sql")
    
    count_df = conn.query('SELECT COUNT(*) as cnt FROM "rule"', ttl=0)
    if not count_df.empty and count_df['cnt'].iloc[0] > 0:
        return

    print("초기 분류 규칙 데이터를 삽입합니다...")
    try:
        category_map_df = conn.query("SELECT category_code, id FROM category", ttl=0)
        category_map = pd.Series(category_map_df.id.values, index=category_map_df.category_code).to_dict()

        with open(rules_path, 'r', encoding='utf-8') as f:
            rules_from_json = json.load(f)

        with conn.session.begin() as s:
            for rule_data in rules_from_json:
                category_code = rule_data.get('category_code')
                if category_code not in category_map: continue

                rule_id_result = s.execute(
                    'INSERT INTO "rule" (category_id, description, priority) VALUES (%s, %s, %s) RETURNING id',
                    (category_map[category_code], rule_data.get('description'), rule_data.get('priority', 0))
                )
                rule_id = rule_id_result.scalar_one()

                for cond in rule_data.get('conditions', []):
                    s.execute(
                        'INSERT INTO "rule_condition" (rule_id, column_to_check, match_type, value) VALUES (%s, %s, %s, %s)',
                        (rule_id, cond.get('column'), cond.get('match_type'), cond.get('value'))
                    )
        print("초기 분류 규칙 데이터 삽입 완료.")
    except Exception as e:
        print(f"초기 규칙 데이터 삽입 중 오류 발생: {e}")


def seed_initial_accounts():
    """기본 계좌 목록을 확인하고 없으면 삽입합니다."""
    conn = st.connection("supabase", type="sql")
    
    default_accounts = [
        ('신한은행-110-227-963599', 'BANK_ACCOUNT', True, False), ('신한카드', 'CREDIT_CARD', False, False),
        ('국민카드', 'CREDIT_CARD', False, False), ('현대카드', 'CREDIT_CARD', False, False),
        ('현금', 'CASH', True, False), ('미지정_거래처', 'UNCATEGORIZED', True, False),
        ('세아적금', 'SAVINGS', True, True), ('혜인적금', 'SAVINGS', True, True),
        ('영준해외주식', 'STOCKS', True, True), ('영준국내주식', 'STOCKS', True, True),
        ('혜인국내주식', 'STOCKS', True, True), ('코인원', 'CRYPTOCURRENCY', True, True),
        ('일산집', 'REAL_ESTATE', True, True), ('전세금', 'REAL_ESTATE', True, False),
    ]

    try:
        with conn.session.begin() as s:
            for name, acc_type, is_asset, is_invest in default_accounts:
                existing_account = s.execute("SELECT id FROM accounts WHERE name = %s", (name,)).first()
                if existing_account is None:
                    s.execute(
                        "INSERT INTO accounts (name, account_type, is_asset, balance, is_investment) VALUES (%s, %s, %s, %s, %s)",
                        (name, acc_type, is_asset, 0, is_invest)
                    )
                    print(f"기본 계좌 '{name}'이(가) 추가되었습니다.")
    except Exception as e:
        print(f"초기 계좌 데이터 삽입 중 오류 발생: {e}")


def seed_initial_transfer_rules(rules_path=config.TRANSFER_RULES_PATH):
    """JSON 파일에서 초기 이체 규칙을 로드하여 삽입합니다."""
    conn = st.connection("supabase", type="sql")
    
    count_df = conn.query('SELECT COUNT(*) as cnt FROM "transfer_rule"', ttl=0)
    if not count_df.empty and count_df['cnt'].iloc[0] > 0:
        return

    print("초기 이체 규칙 데이터를 삽입합니다...")
    try:
        accounts_map_df = conn.query("SELECT id, name FROM accounts", ttl=0)
        accounts_map = pd.Series(accounts_map_df.id.values, index=accounts_map_df.name).to_dict()

        with open(rules_path, 'r', encoding='utf-8') as f:
            rules_from_json = json.load(f)

        with conn.session.begin() as s:
            for rule_data in rules_from_json:
                linked_account_name = rule_data.get('linked_account_name')
                linked_account_id = accounts_map.get(linked_account_name)
                if not linked_account_id: continue

                rule_id_result = s.execute(
                    'INSERT INTO "transfer_rule" (description, priority, linked_account_id) VALUES (%s, %s, %s) RETURNING id',
                    (rule_data.get('description'), rule_data.get('priority', 0), linked_account_id)
                )
                rule_id = rule_id_result.scalar_one()

                for cond in rule_data.get('conditions', []):
                    s.execute(
                        'INSERT INTO "transfer_rule_condition" (rule_id, column_to_check, match_type, value) VALUES (%s, %s, %s, %s)',
                        (rule_id, cond.get('column'), cond.get('match_type'), cond.get('value'))
                    )
        print("초기 이체 규칙 데이터 삽입 완료.")
    except Exception as e:
        print(f"초기 이체 규칙 데이터 삽입 중 오류 발생: {e}")