import sqlite3
import json
def seed_initial_categories(db_path='asset_data.db'):

    conn = sqlite3.connect(db_path)
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

        cursor.execute(insert_level_top, ('INVESTMENT', 'INVESTMENT', '투자', '2', 1))
        investment_id = cursor.lastrowid

        cursor.execute(insert_level_top, ('INCOME', 'INCOME', '수입', '3', 1))
        income_id = cursor.lastrowid

        # --- Level 2: 지출 하위 ---
        cursor.execute(insert_level,
                       ('UNCATEGORIZED', 'EXPENSE', expense_id, '비분류 지출', '1-2', 2))

        cursor.execute(insert_level,
                       ('FIXED_EXPENSE', 'EXPENSE', expense_id, '고정 지출', '1-2', 2))
        fixed_expense_id = cursor.lastrowid

        cursor.execute(insert_level,
                       ('VARIABLE_EXPENSE', 'EXPENSE', expense_id, '변동 지출', '1-2', 2))
        variable_expense_id = cursor.lastrowid

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

        # --- Level 2: 투자 하위 ---
        cursor.execute(insert_level,
                       ('SAVINGS', 'INVESTMENT', investment_id, '저축', '2-2', 2))
        cursor.execute(insert_level,
                       ('STOCKS', 'INVESTMENT', investment_id, '주식', '2-2', 2))
        cursor.execute(insert_level,
                       ('CRYPTOCURRENCY', 'INVESTMENT', investment_id, '비트코인', '2-2', 2))

        # --- Level 2: 수입 하위 ---
        cursor.execute(insert_level,
                       ('SALARY', 'INCOME', income_id, '급여', '3-2', 2))
        cursor.execute(insert_level,
                       ('SUBSIDY', 'INCOME', income_id, '지원금', '3-2', 2))
        cursor.execute(insert_level,
                       ('INCENTIVE', 'INCOME', income_id, '인센티브', '3-2', 2))
        cursor.execute(insert_level,
                       ('FINANCIAL_INCOME', 'INCOME', income_id, '금융수입', '3-2', 2))
        subsidy_id = cursor.lastrowid

        # --- Level 3: 지원금 하위 ---
        cursor.execute(insert_level,
                       ('CHILD_SUBSIDY', 'INCOME', subsidy_id, '아동수당', '3-2-3', 3))
        cursor.execute(insert_level,
                       ('PARENT_SUBSIDY', 'INCOME', subsidy_id, '부모수당', '3-2-3', 3))
        cursor.execute(insert_level,
                       ('MOBILE_SUBSIDY', 'INCOME', subsidy_id, '핸드폰지원금', '3-2-3', 3))

        conn.commit()
        print("초기 카테고리 데이터 삽입 완료.")

    except Exception as e:
        print(f"초기 데이터 삽입 중 오류 발생: {e}")
        conn.rollback()
    finally:
        conn.close()


def seed_initial_parties(db_path='asset_data.db'):
    conn = sqlite3.connect(db_path)
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


def seed_initial_rules(db_path='asset_data.db', rules_path='initial_rules.json'):
    conn = sqlite3.connect(db_path)
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