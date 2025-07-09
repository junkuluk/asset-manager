import sqlite3
import json
import config
from core.db_manager import rebuild_category_paths
import streamlit as st

def seed_initial_categories(db_path=config.DB_PATH):

    #conn = sqlite3.connect(db_path)
    conn = st.connection("supabase", type="sql")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM category")
    if cursor.fetchone()[0] > 0:
        print("카테고리 데이터가 이미 존재하여 초기 데이터 삽입을 건너뜁니다.")
        conn.close()
        return

    print("초기 카테고리 데이터를 삽입합니다...")

    try:

        insert_level_top = """
                    INSERT INTO "category" (category_code, category_type, description, materialized_path_desc, depth)
                    VALUES (?, ?, ?, ?, ?) \
                    """

        insert_level = """
                         INSERT INTO "category" (category_code, category_type, parent_id, description, \
                                                 materialized_path_desc, depth)
                         VALUES (?, ?, ?, ?, ?, ?) \
                         """

        # --- Level 1 삽입 ---
        cursor.execute(insert_level_top, ('EXPENSE', 'EXPENSE', '지출', '1', 1))
        expense_id = cursor.lastrowid

        cursor.execute(insert_level_top, ('INVEST', 'INVEST', '투자', '2', 1))
        investment_id = cursor.lastrowid

        cursor.execute(insert_level_top, ('INCOME', 'INCOME', '수입', '3', 1))
        income_id = cursor.lastrowid

        cursor.execute(insert_level_top, ('TRANSFER', 'TRANSFER', '내부 이체', '4', 1))
        transfer_id = cursor.lastrowid

        # --- Level 2: 지출 하위 ---
        cursor.execute(insert_level,
                       ('UNCATEGORIZED', 'EXPENSE', expense_id, '미분류 지출', '1-2', 2))

        cursor.execute(insert_level,
                       ('UNCATEGORIZED', 'INCOME', income_id, '미분류 수입', '1-2', 2))

        cursor.execute(insert_level,
                       ('FIXED_INCOME', 'INCOME', income_id, '고정 수입', '1-2', 2))
        fixed_income_id = cursor.lastrowid
        cursor.execute(insert_level,
                       ('VARIABLE_INCOME', 'INCOME', income_id, '변동 수입', '1-2', 2))
        variable_income_id = cursor.lastrowid
        cursor.execute(insert_level,
                       ('FIXED_EXPENSE', 'EXPENSE', expense_id, '고정 지출', '1-2', 2))
        fixed_expense_id = cursor.lastrowid

        cursor.execute(insert_level,
                       ('VARIABLE_EXPENSE', 'EXPENSE', expense_id, '변동 지출', '1-2', 2))
        variable_expense_id = cursor.lastrowid

        cursor.execute(insert_level, ('INVESTMENT', 'INVEST', investment_id, '투자', '2-temp', 2))
        investment_lvl2_id = cursor.lastrowid
        cursor.execute(insert_level, ('CARD_PAYMENT', 'TRANSFER', transfer_id, '카드대금 이체', '4-temp', 2))

        # --- Level 3: 투자 하위 ---
        cursor.execute(insert_level,
                       ('SAVINGS', 'INVEST', investment_lvl2_id, '저축', '2-2', 3))
        cursor.execute(insert_level,
                       ('STOCKS', 'INVEST', investment_lvl2_id, '주식', '2-2', 3))
        cursor.execute(insert_level,
                       ('CRYPTOCURRENCY', 'INVEST', investment_lvl2_id, '비트코인', '2-2', 3))
        cursor.execute(insert_level,
                       ('REAL_ESTATE', 'INVEST', investment_lvl2_id, '부동산', '2-2', 3))


        # --- Level 3: 수입 하위 ---
        cursor.execute(insert_level,
                       ('SALARY', 'INCOME', fixed_income_id, '급여', '3-2-1', 3))
        cursor.execute(insert_level,
                       ('SUBSIDY', 'INCOME', fixed_income_id, '지원금', '3-2-1', 3))
        cursor.execute(insert_level,
                       ('INCENTIVE', 'INCOME', variable_income_id, '인센티브', '3-2-1', 3))
        cursor.execute(insert_level,
                       ('FINANCIAL_INCOME', 'INCOME', variable_income_id, '금융수입', '3-2-1', 3))
        subsidy_id = cursor.lastrowid

        # --- Level 3: 고정 지출 하위 ---
        level3_fixed_parents = {
            'HOUSING_EXPENSE': ('주거비', fixed_expense_id), 'UTILITY_BILLS': ('공과금', fixed_expense_id),
            'COMMUNICATION_EXPENSE': ('통신비', fixed_expense_id), 'INSURANCE_EXPENSE': ('보험료', fixed_expense_id),
            'MEMBERSHIP': ('회원료', fixed_expense_id), 'FAMILY_GATHERING': ('가족 모임비', fixed_expense_id)
        }
        level3_fixed_ids = {}
        for code, (desc, parent) in level3_fixed_parents.items():
            cursor.execute(insert_level,
                           (code, 'EXPENSE', parent, desc, '1-2-3', 3))
            level3_fixed_ids[code] = cursor.lastrowid

        # --- Level 3: 변동 지출 하위 ---
        level3_variable_parents = {
            'FOOD_EXPENSE': ('식비', variable_expense_id), 'TRANSPORTATION_EXPENSE': ('교통비', variable_expense_id),
            'SHOPPING': ('쇼핑', variable_expense_id), 'MEDICAL_EXPENSE': ('의료비', variable_expense_id),
            'EDUCATION_EXPENSE': ('교육비', variable_expense_id), 'LIVING_EXPENSE': ('생활비', variable_expense_id),
            'EVENT_EXPENSE': ('경조사비', variable_expense_id), 'LEISURE_EXPENSE': ('여가비', variable_expense_id)
        }
        level3_variable_ids = {}
        for code, (desc, parent) in level3_variable_parents.items():
            cursor.execute(insert_level,
                           (code, 'EXPENSE', parent, desc, '1-2-3', 3))
            level3_variable_ids[code] = cursor.lastrowid

        # --- Level 4: 세부 항목들 ---
        # 주거비 하위
        cursor.execute(insert_level,
                       ('MONTHLY_RENT', 'EXPENSE', level3_fixed_ids['HOUSING_EXPENSE'], '월세', '1-2-3-4', 4))
        cursor.execute(insert_level,
                       ('MANAGEMENT_FEE', 'EXPENSE', level3_fixed_ids['HOUSING_EXPENSE'], '관리비', '1-2-3-4', 4))

        # 공과금 하위
        cursor.execute(insert_level,
                       ('ELECTRICITY_BILL', 'EXPENSE', level3_fixed_ids['UTILITY_BILLS'], '전기세', '1-2-3-4', 4))
        cursor.execute(insert_level,
                       ('WATER_BILL', 'EXPENSE', level3_fixed_ids['UTILITY_BILLS'], '수도세', '1-2-3-4', 4))
        cursor.execute(insert_level,
                       ('GAS_BILL', 'EXPENSE', level3_fixed_ids['UTILITY_BILLS'], '가스비', '1-2-3-4', 4))

        # 통신비 하위
        cursor.execute(insert_level,
                       ('INTERNET_BILL', 'EXPENSE', level3_fixed_ids['COMMUNICATION_EXPENSE'], '인터넷', '1-2-3-4', 4))
        cursor.execute(insert_level,
                       ('TV_BILL', 'EXPENSE', level3_fixed_ids['COMMUNICATION_EXPENSE'], '티비수신비', '1-2-3-4', 4))
        cursor.execute(insert_level,
                       ('MOBILE_BILL', 'EXPENSE', level3_fixed_ids['COMMUNICATION_EXPENSE'], '핸드폰비', '1-2-3-4', 4))

        # 보험료 하위
        cursor.execute(insert_level,
                       ('YOUNGJUN_INSURANCE', 'EXPENSE', level3_fixed_ids['INSURANCE_EXPENSE'], '영준 보험', '1-2-3-4',
                        4))
        cursor.execute(insert_level,
                       ('HYEIN_INSURANCE', 'EXPENSE', level3_fixed_ids['INSURANCE_EXPENSE'], '혜인 보험', '1-2-3-4', 4))
        cursor.execute(insert_level,
                       ('SEA_INSURANCE', 'EXPENSE', level3_fixed_ids['INSURANCE_EXPENSE'], '세아 보험', '1-2-3-4', 4))

        # 회원료 하위
        cursor.execute(insert_level,
                       ('COUPANG_MEMBERSHIP', 'EXPENSE', level3_fixed_ids['MEMBERSHIP'], '쿠팡 맴버쉽', '1-2-3-4', 4))

        # 식비 하위
        cursor.execute(insert_level,
                       ('DINING_OUT', 'EXPENSE', level3_variable_ids['FOOD_EXPENSE'], '외식', '1-2-3-4', 4))
        cursor.execute(insert_level,
                       ('DELIVERY_FOOD', 'EXPENSE', level3_variable_ids['FOOD_EXPENSE'], '배달', '1-2-3-4', 4))
        cursor.execute(insert_level,
                       ('ALCOHOL', 'EXPENSE', level3_variable_ids['FOOD_EXPENSE'], '주류', '1-2-3-4', 4))
        cursor.execute(insert_level,
                       ('CONVENIENCE_STORE', 'EXPENSE', level3_variable_ids['FOOD_EXPENSE'], '편의점', '1-2-3-4', 4))
        cursor.execute(insert_level,
                       ('GROCERIES', 'EXPENSE', level3_variable_ids['FOOD_EXPENSE'], '식료품', '1-2-3-4', 4))

        # 교통비 하위
        cursor.execute(insert_level,
                       ('PUBLIC_TRANSPORT', 'EXPENSE', level3_variable_ids['TRANSPORTATION_EXPENSE'], '대중교통비', '1-2-3-4', 4))
        cursor.execute(insert_level,
                       ('FUEL_EXPENSE', 'EXPENSE', level3_variable_ids['TRANSPORTATION_EXPENSE'], '주유비', '1-2-3-4', 4))

        # 쇼핑 하위
        cursor.execute(insert_level,
                       ('CLOTHING', 'EXPENSE', level3_variable_ids['SHOPPING'], '의류비', '1-2-3-4', 4))
        cursor.execute(insert_level,
                       ('FURNITURE', 'EXPENSE', level3_variable_ids['SHOPPING'], '가구', '1-2-3-4', 4))
        cursor.execute(insert_level,
                       ('CHILDCARE_PRODUCTS', 'EXPENSE', level3_variable_ids['SHOPPING'], '유아용품', '1-2-3-4', 4))
        cursor.execute(insert_level,
                       ('ELECTRONICS', 'EXPENSE', level3_variable_ids['SHOPPING'], '전자제품', '1-2-3-4', 4))

        # 의료비 하위
        cursor.execute(insert_level,
                       ('HOSPITAL_EXPENSE', 'EXPENSE', level3_variable_ids['MEDICAL_EXPENSE'], '병원비', '1-2-3-4', 4))
        cursor.execute(insert_level,
                       ('PHARMACY', 'EXPENSE', level3_variable_ids['MEDICAL_EXPENSE'], '의약품', '1-2-3-4', 4))

        # 생활비 하위
        cursor.execute(insert_level,
                       ('ALLOWANCE', 'EXPENSE', level3_variable_ids['LIVING_EXPENSE'], '용돈', '1-2-3-4', 4))
        cursor.execute(insert_level,
                       ('LAUNDRY_EXPENSE', 'EXPENSE', level3_variable_ids['LIVING_EXPENSE'], '세탁비', '1-2-3-4', 4))
        cursor.execute(insert_level,
                       ('CHILDCARE_EXPENSE', 'EXPENSE', level3_variable_ids['LIVING_EXPENSE'], '유아비', '1-2-3-4', 4))

        # 여가비 하위
        cursor.execute(insert_level,
                       ('TRAVEL', 'EXPENSE', level3_variable_ids['LEISURE_EXPENSE'], '여행', '1-2-3-4', 4))
        cursor.execute(insert_level,
                       ('MOVIES', 'EXPENSE', level3_variable_ids['LEISURE_EXPENSE'], '영화', '1-2-3-4', 4))


        # --- Level 3: 지원금 하위 ---
        cursor.execute(insert_level,
                       ('CHILD_SUBSIDY', 'INCOME', subsidy_id, '아동수당', '3-2-3', 3))
        cursor.execute(insert_level,
                       ('PARENT_SUBSIDY', 'INCOME', subsidy_id, '부모수당', '3-2-3', 3))
        cursor.execute(insert_level,
                       ('MOBILE_SUBSIDY', 'INCOME', subsidy_id, '핸드폰지원금', '3-2-3', 3))

        conn.commit()
        print("초기 카테고리 데이터 삽입 완료.")
        rebuild_category_paths()
        print("초기 카테고리 경로 작업 완료.")

    except Exception as e:
        print(f"초기 데이터 삽입 중 오류 발생: {e}")
        conn.rollback()
    finally:
        conn.close()


def seed_initial_parties(db_path=config.DB_PATH):
    conn = st.connection("supabase", type="sql")
    #conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM \"transaction_party\"")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    print("초기 거래처 데이터를 삽입합니다...")

    try:
        parties_to_seed = [
            ('UNREGISTERED', '미등록'), ('쿠팡', '쿠팡'), ('GS25', 'GS25 편의점'),
            ('스타필드', '스타필드'), ('쿠팡이츠', '쿠팡이츠')
        ]
        cursor.executemany("INSERT INTO \"transaction_party\" (party_code, description) VALUES (?, ?)", parties_to_seed)
        conn.commit()
        print("초기 거래처 데이터 삽입 완료.")
    except Exception as e:
        print(f"초기 거래처 데이터 삽입 중 오류 발생: {e}")
        conn.rollback()
    finally:
        conn.close()


def seed_initial_rules(db_path=config.DB_PATH, rules_path=config.RULES_PATH):
    #conn = sqlite3.connect(db_path)
    conn = st.connection("supabase", type="sql")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM \"rule\"")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    print("JSON 파일에서 초기 분류 규칙을 로드하여 삽입합니다...")
    try:
        cursor.execute("SELECT category_code, id FROM category")
        category_map = dict(cursor.fetchall())
        with open(rules_path, 'r', encoding='utf-8') as f:
            rules_from_json = json.load(f)

        for rule_data in rules_from_json:
            category_code = rule_data.get('category_code')
            if category_code not in category_map: continue

            cursor.execute("INSERT INTO \"rule\" (category_id, description, priority) VALUES (?, ?, ?)",
                         (category_map[category_code], rule_data.get('description'), rule_data.get('priority', 0)))
            rule_id = cursor.lastrowid

            for cond in rule_data.get('conditions', []):
                cursor.execute("INSERT INTO \"rule_condition\" (rule_id, column_to_check, match_type, value) VALUES (?, ?, ?, ?)",
                             (rule_id, cond.get('column'), cond.get('match_type'), cond.get('value')))
        conn.commit()
        print("초기 분류 규칙 데이터 삽입 완료.")
    except Exception as e:
        print(f"초기 규칙 데이터 삽입 중 오류 발생: {e}")
        conn.rollback()
    finally:
        conn.close()

def seed_initial_accounts(db_path=config.DB_PATH):

    #conn = sqlite3.connect(db_path)
    conn = st.connection("supabase", type="sql")
    cursor = conn.cursor()

    # 등록할 기본 계좌 목록
    # (계좌 이름, 계좌 타입, 자산 여부(True/False))
    default_accounts = [
        ('신한은행-110-227-963599', 'BANK_ACCOUNT', True, False),
        ('신한카드', 'CREDIT_CARD', False, False),
        ('국민카드', 'CREDIT_CARD', False, False),
        ('현대카드', 'CREDIT_CARD', False, False),
        ('현금', 'CASH', True, False),
        ('미지정_거래처', 'UNCATEGORIZED', True, False),
        ('세아적금', 'SAVINGS', True, True),
        ('혜인적금', 'SAVINGS', True, True),
        ('영준해외주식', 'STOCKS', True, True),
        ('영준국내주식', 'STOCKS', True, True),
        ('혜인국내주식', 'STOCKS', True, True),
        ('코인원', 'CRYPTOCURRENCY', True, True),
        ('일산집', 'REAL_ESTATE', True, True),
        ('전세금', 'REAL_ESTATE', True, False),
    ]

    for name, acc_type, is_asset, is_invest in default_accounts:
        # 이미 같은 이름의 계좌가 있는지 확인
        cursor.execute("SELECT id FROM accounts WHERE name = ?", (name,))
        if cursor.fetchone() is None:
            # 없으면 추가
            cursor.execute(
                "INSERT INTO accounts (name, account_type, is_asset, balance, is_investment) VALUES (?, ?, ?, ?, ?)",
                (name, acc_type, is_asset, 0, is_invest) # 초기 잔액은 0으로 설정
            )
            print(f"기본 계좌 '{name}'이(가) 추가되었습니다.")

    conn.commit()
    conn.close()

def seed_initial_transfer_rules(db_path=config.DB_PATH, rules_path=config.TRANSFER_RULES_PATH):

    #conn = sqlite3.connect(db_path)
    conn = st.connection("supabase", type="sql")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM \"transfer_rule\"")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    print("JSON 파일에서 초기 이체 규칙을 로드하여 삽입합니다...")
    try:
        cursor.execute("SELECT id, name FROM accounts")
        accounts_map = {name: id for id, name in cursor.fetchall()}

        with open(rules_path, 'r', encoding='utf-8') as f:
            rules_from_json = json.load(f)

        for rule_data in rules_from_json:
            linked_account_name = rule_data.get('linked_account_name')
            linked_account_id = accounts_map.get(linked_account_name)
            if not linked_account_id: continue  # 연결 계좌가 없으면 건너뜀

            cursor.execute("INSERT INTO \"transfer_rule\" (description, priority, linked_account_id) VALUES (?, ?, ?)",
                           (rule_data.get('description'), rule_data.get('priority', 0), linked_account_id))
            rule_id = cursor.lastrowid
            for cond in rule_data.get('conditions', []):
                cursor.execute("INSERT INTO \"transfer_rule_condition\" (rule_id, column_to_check, match_type, value) VALUES (?, ?, ?, ?)",
                             (rule_id, cond.get('column'), cond.get('match_type'), cond.get('value')))
        conn.commit()
    finally:
        conn.close()

