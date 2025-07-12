import json
import streamlit as st
import pandas as pd
from sqlalchemy import text

import config
from core.db_manager import rebuild_category_paths


def seed_initial_categories():

    conn = st.connection("supabase", type="sql")

    s = conn.session

    count_result = s.execute(text("SELECT COUNT(*) as cnt FROM category")).scalar_one()
    if count_result > 0:
        print("카테고리 데이터가 이미 존재하여 초기 데이터 삽입을 건너뜁니다.")
        return

    print("초기 카테고리 데이터를 삽입합니다...")

    try:

        def insert_and_get_id(query_str, params):
            result = s.execute(text(query_str), params)
            return result.scalar_one()

        insert_top_query = "INSERT INTO category (category_code, category_type, description, depth) VALUES (:code, :type, :desc, :depth) RETURNING id"
        expense_id = insert_and_get_id(
            insert_top_query,
            {"code": "EXPENSE", "type": "EXPENSE", "desc": "지출", "depth": 1},
        )
        investment_id = insert_and_get_id(
            insert_top_query,
            {"code": "INVEST", "type": "INVEST", "desc": "투자", "depth": 1},
        )
        income_id = insert_and_get_id(
            insert_top_query,
            {"code": "INCOME", "type": "INCOME", "desc": "수입", "depth": 1},
        )
        transfer_id = insert_and_get_id(
            insert_top_query,
            {"code": "TRANSFER", "type": "TRANSFER", "desc": "내부 이체", "depth": 1},
        )

        insert_level_query = "INSERT INTO category (category_code, category_type, parent_id, description, depth) VALUES (:code, :type, :parent_id, :desc, :depth) RETURNING id"
        insert_and_get_id(
            insert_level_query,
            {
                "code": "UNCATEGORIZED",
                "type": "EXPENSE",
                "parent_id": expense_id,
                "desc": "미분류 지출",
                "depth": 2,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "UNCATEGORIZED",
                "type": "INCOME",
                "parent_id": income_id,
                "desc": "미분류 수입",
                "depth": 2,
            },
        )
        fixed_income_id = insert_and_get_id(
            insert_level_query,
            {
                "code": "FIXED_INCOME",
                "type": "INCOME",
                "parent_id": income_id,
                "desc": "고정 수입",
                "depth": 2,
            },
        )
        variable_income_id = insert_and_get_id(
            insert_level_query,
            {
                "code": "VARIABLE_INCOME",
                "type": "INCOME",
                "parent_id": income_id,
                "desc": "변동 수입",
                "depth": 2,
            },
        )
        fixed_expense_id = insert_and_get_id(
            insert_level_query,
            {
                "code": "FIXED_EXPENSE",
                "type": "EXPENSE",
                "parent_id": expense_id,
                "desc": "고정 지출",
                "depth": 2,
            },
        )
        variable_expense_id = insert_and_get_id(
            insert_level_query,
            {
                "code": "VARIABLE_EXPENSE",
                "type": "EXPENSE",
                "parent_id": expense_id,
                "desc": "변동 지출",
                "depth": 2,
            },
        )
        investment_lvl2_id = insert_and_get_id(
            insert_level_query,
            {
                "code": "INVESTMENT",
                "type": "INVEST",
                "parent_id": investment_id,
                "desc": "투자",
                "depth": 2,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "CARD_PAYMENT",
                "type": "TRANSFER",
                "parent_id": transfer_id,
                "desc": "카드대금 이체",
                "depth": 2,
            },
        )

        insert_and_get_id(
            insert_level_query,
            {
                "code": "SAVINGS",
                "type": "INVEST",
                "parent_id": investment_lvl2_id,
                "desc": "저축",
                "depth": 3,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "STOCKS",
                "type": "INVEST",
                "parent_id": investment_lvl2_id,
                "desc": "주식",
                "depth": 3,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "CRYPTOCURRENCY",
                "type": "INVEST",
                "parent_id": investment_lvl2_id,
                "desc": "비트코인",
                "depth": 3,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "REAL_ESTATE",
                "type": "INVEST",
                "parent_id": investment_lvl2_id,
                "desc": "부동산",
                "depth": 3,
            },
        )

        insert_and_get_id(
            insert_level_query,
            {
                "code": "SALARY",
                "type": "INCOME",
                "parent_id": fixed_income_id,
                "desc": "급여",
                "depth": 3,
            },
        )
        subsidy_id = insert_and_get_id(
            insert_level_query,
            {
                "code": "SUBSIDY",
                "type": "INCOME",
                "parent_id": fixed_income_id,
                "desc": "지원금",
                "depth": 3,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "INCENTIVE",
                "type": "INCOME",
                "parent_id": variable_income_id,
                "desc": "인센티브",
                "depth": 3,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "FINANCIAL_INCOME",
                "type": "INCOME",
                "parent_id": variable_income_id,
                "desc": "금융수입",
                "depth": 3,
            },
        )

        housing_id = insert_and_get_id(
            insert_level_query,
            {
                "code": "HOUSING_EXPENSE",
                "type": "EXPENSE",
                "parent_id": fixed_expense_id,
                "desc": "주거비",
                "depth": 3,
            },
        )
        utility_id = insert_and_get_id(
            insert_level_query,
            {
                "code": "UTILITY_BILLS",
                "type": "EXPENSE",
                "parent_id": fixed_expense_id,
                "desc": "공과금",
                "depth": 3,
            },
        )
        comm_id = insert_and_get_id(
            insert_level_query,
            {
                "code": "COMMUNICATION_EXPENSE",
                "type": "EXPENSE",
                "parent_id": fixed_expense_id,
                "desc": "통신비",
                "depth": 3,
            },
        )
        insurance_id = insert_and_get_id(
            insert_level_query,
            {
                "code": "INSURANCE_EXPENSE",
                "type": "EXPENSE",
                "parent_id": fixed_expense_id,
                "desc": "보험료",
                "depth": 3,
            },
        )
        membership_id = insert_and_get_id(
            insert_level_query,
            {
                "code": "MEMBERSHIP",
                "type": "EXPENSE",
                "parent_id": fixed_expense_id,
                "desc": "회원료",
                "depth": 3,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "FAMILY_GATHERING",
                "type": "EXPENSE",
                "parent_id": fixed_expense_id,
                "desc": "가족 모임비",
                "depth": 3,
            },
        )

        food_id = insert_and_get_id(
            insert_level_query,
            {
                "code": "FOOD_EXPENSE",
                "type": "EXPENSE",
                "parent_id": variable_expense_id,
                "desc": "식비",
                "depth": 3,
            },
        )
        transport_id = insert_and_get_id(
            insert_level_query,
            {
                "code": "TRANSPORTATION_EXPENSE",
                "type": "EXPENSE",
                "parent_id": variable_expense_id,
                "desc": "교통비",
                "depth": 3,
            },
        )
        shopping_id = insert_and_get_id(
            insert_level_query,
            {
                "code": "SHOPPING",
                "type": "EXPENSE",
                "parent_id": variable_expense_id,
                "desc": "쇼핑",
                "depth": 3,
            },
        )
        medical_id = insert_and_get_id(
            insert_level_query,
            {
                "code": "MEDICAL_EXPENSE",
                "type": "EXPENSE",
                "parent_id": variable_expense_id,
                "desc": "의료비",
                "depth": 3,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "EDUCATION_EXPENSE",
                "type": "EXPENSE",
                "parent_id": variable_expense_id,
                "desc": "교육비",
                "depth": 3,
            },
        )
        living_id = insert_and_get_id(
            insert_level_query,
            {
                "code": "LIVING_EXPENSE",
                "type": "EXPENSE",
                "parent_id": variable_expense_id,
                "desc": "생활비",
                "depth": 3,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "EVENT_EXPENSE",
                "type": "EXPENSE",
                "parent_id": variable_expense_id,
                "desc": "경조사비",
                "depth": 3,
            },
        )
        leisure_id = insert_and_get_id(
            insert_level_query,
            {
                "code": "LEISURE_EXPENSE",
                "type": "EXPENSE",
                "parent_id": variable_expense_id,
                "desc": "여가비",
                "depth": 3,
            },
        )

        insert_and_get_id(
            insert_level_query,
            {
                "code": "MONTHLY_RENT",
                "type": "EXPENSE",
                "parent_id": housing_id,
                "desc": "월세",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "MANAGEMENT_FEE",
                "type": "EXPENSE",
                "parent_id": housing_id,
                "desc": "관리비",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "ELECTRICITY_BILL",
                "type": "EXPENSE",
                "parent_id": utility_id,
                "desc": "전기세",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "WATER_BILL",
                "type": "EXPENSE",
                "parent_id": utility_id,
                "desc": "수도세",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "GAS_BILL",
                "type": "EXPENSE",
                "parent_id": utility_id,
                "desc": "가스비",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "INTERNET_BILL",
                "type": "EXPENSE",
                "parent_id": comm_id,
                "desc": "인터넷",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "TV_BILL",
                "type": "EXPENSE",
                "parent_id": comm_id,
                "desc": "티비수신비",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "MOBILE_BILL",
                "type": "EXPENSE",
                "parent_id": comm_id,
                "desc": "핸드폰비",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "YOUNGJUN_INSURANCE",
                "type": "EXPENSE",
                "parent_id": insurance_id,
                "desc": "영준 보험",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "HYEIN_INSURANCE",
                "type": "EXPENSE",
                "parent_id": insurance_id,
                "desc": "혜인 보험",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "SEA_INSURANCE",
                "type": "EXPENSE",
                "parent_id": insurance_id,
                "desc": "세아 보험",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "COUPANG_MEMBERSHIP",
                "type": "EXPENSE",
                "parent_id": membership_id,
                "desc": "쿠팡 맴버쉽",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "DINING_OUT",
                "type": "EXPENSE",
                "parent_id": food_id,
                "desc": "외식",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "DELIVERY_FOOD",
                "type": "EXPENSE",
                "parent_id": food_id,
                "desc": "배달",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "ALCOHOL",
                "type": "EXPENSE",
                "parent_id": food_id,
                "desc": "주류",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "CONVENIENCE_STORE",
                "type": "EXPENSE",
                "parent_id": food_id,
                "desc": "편의점",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "GROCERIES",
                "type": "EXPENSE",
                "parent_id": food_id,
                "desc": "식료품",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "PUBLIC_TRANSPORT",
                "type": "EXPENSE",
                "parent_id": transport_id,
                "desc": "대중교통비",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "FUEL_EXPENSE",
                "type": "EXPENSE",
                "parent_id": transport_id,
                "desc": "주유비",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "CLOTHING",
                "type": "EXPENSE",
                "parent_id": shopping_id,
                "desc": "의류비",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "FURNITURE",
                "type": "EXPENSE",
                "parent_id": shopping_id,
                "desc": "가구",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "CHILDCARE_PRODUCTS",
                "type": "EXPENSE",
                "parent_id": shopping_id,
                "desc": "유아용품",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "ELECTRONICS",
                "type": "EXPENSE",
                "parent_id": shopping_id,
                "desc": "전자제품",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "HOSPITAL_EXPENSE",
                "type": "EXPENSE",
                "parent_id": medical_id,
                "desc": "병원비",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "PHARMACY",
                "type": "EXPENSE",
                "parent_id": medical_id,
                "desc": "의약품",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "ALLOWANCE",
                "type": "EXPENSE",
                "parent_id": living_id,
                "desc": "용돈",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "LAUNDRY_EXPENSE",
                "type": "EXPENSE",
                "parent_id": living_id,
                "desc": "세탁비",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "CHILDCARE_EXPENSE",
                "type": "EXPENSE",
                "parent_id": living_id,
                "desc": "유아비",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "TRAVEL",
                "type": "EXPENSE",
                "parent_id": leisure_id,
                "desc": "여행",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "MOVIES",
                "type": "EXPENSE",
                "parent_id": leisure_id,
                "desc": "영화",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "CHILD_SUBSIDY",
                "type": "INCOME",
                "parent_id": subsidy_id,
                "desc": "아동수당",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "PARENT_SUBSIDY",
                "type": "INCOME",
                "parent_id": subsidy_id,
                "desc": "부모수당",
                "depth": 4,
            },
        )
        insert_and_get_id(
            insert_level_query,
            {
                "code": "MOBILE_SUBSIDY",
                "type": "INCOME",
                "parent_id": subsidy_id,
                "desc": "핸드폰지원금",
                "depth": 4,
            },
        )

        s.commit()
        print("초기 카테고리 데이터 삽입 완료.")

        rebuild_category_paths()
        print("초기 카테고리 경로 작업 완료.")

    except Exception as e:
        print(f"초기 데이터 삽입 중 오류 발생: {e}")
        s.rollback()


def seed_initial_parties():
    conn = st.connection("supabase", type="sql")
    s = conn.session

    try:
        with s.begin():
            count_result = s.execute(
                text('SELECT COUNT(*) as cnt FROM "transaction_party"')
            ).scalar_one()
            if count_result > 0:
                print("거래처 데이터가 이미 존재하여 초기 데이터 삽입을 건너뜁니다.")
                return

            print("초기 거래처 데이터를 삽입합니다...")
            parties_to_seed = [
                ("UNREGISTERED", "미등록"),
                ("쿠팡", "쿠팡"),
                ("GS25", "GS25 편의점"),
                ("스타필드", "스타필드"),
                ("쿠팡이츠", "쿠팡이츠"),
            ]

            for code, desc in parties_to_seed:
                s.execute(
                    text(
                        'INSERT INTO "transaction_party" (party_code, description) VALUES (:code, :desc)'
                    ),
                    {"code": code, "desc": desc},
                )
            print("초기 거래처 데이터 삽입 완료.")

    except Exception as e:
        print(f"초기 거래처 데이터 삽입 중 오류 발생: {e}")


def seed_initial_rules(rules_path=config.RULES_PATH):

    conn = st.connection("supabase", type="sql")
    s = conn.session

    try:
        with s.begin():
            count_result = s.execute(
                text('SELECT COUNT(*) as cnt FROM "rule"')
            ).scalar_one()
            if count_result > 0:
                print("분류 규칙 데이터가 이미 존재하여 초기 데이터 삽입을 건너뜜.")
                return

            print("초기 분류 규칙 데이터를 삽입합니다...")

            category_map_result = s.execute(
                text("SELECT category_code, id FROM category")
            ).fetchall()
            category_map = {row.category_code: row.id for row in category_map_result}

            with open(rules_path, "r", encoding="utf-8") as f:
                rules_from_json = json.load(f)

            for rule_data in rules_from_json:
                category_code = rule_data.get("category_code")
                if category_code not in category_map:
                    continue

                rule_id_result = s.execute(
                    text(
                        'INSERT INTO "rule" (category_id, description, priority) VALUES (:category_id, :description, :priority) RETURNING id'
                    ),
                    {
                        "category_id": category_map[category_code],
                        "description": rule_data.get("description"),
                        "priority": rule_data.get("priority", 0),
                    },
                )
                rule_id = rule_id_result.scalar_one()

                for cond in rule_data.get("conditions", []):
                    s.execute(
                        text(
                            'INSERT INTO "rule_condition" (rule_id, column_to_check, match_type, value) VALUES (:rule_id, :column, :match_type, :value)'
                        ),
                        {
                            "rule_id": rule_id,
                            "column": cond.get("column"),
                            "match_type": cond.get("match_type"),
                            "value": cond.get("value"),
                        },
                    )
            print("초기 분류 규칙 데이터 삽입 완료.")

    except Exception as e:
        print(f"초기 규칙 데이터 삽입 중 오류 발생: {e}")


def seed_initial_accounts():

    conn = st.connection("supabase", type="sql")
    s = conn.session

    print("기본 계좌 데이터 삽입을 확인합니다...")

    default_accounts = [
        ("신한은행-110-227-963599", "BANK_ACCOUNT", True, False),
        ("신한카드", "CREDIT_CARD", False, False),
        ("국민카드", "CREDIT_CARD", False, False),
        ("현대카드", "CREDIT_CARD", False, False),
        ("현금", "CASH", True, False),
        ("미지정_거래처", "UNCATEGORIZED", True, False),
        ("세아적금", "SAVINGS", True, True),
        ("혜인적금", "SAVINGS", True, True),
        ("영준해외주식", "STOCKS", True, True),
        ("영준국내주식", "STOCKS", True, True),
        ("혜인국내주식", "STOCKS", True, True),
        ("코인원", "CRYPTOCURRENCY", True, True),
        ("일산집", "REAL_ESTATE", True, True),
        ("전세금", "REAL_ESTATE", True, False),
    ]

    try:

        with s.begin():

            existing_accounts_result = s.execute(
                text("SELECT name FROM accounts")
            ).fetchall()
            existing_account_names = {row.name for row in existing_accounts_result}

            for name, acc_type, is_asset, is_invest in default_accounts:
                if name not in existing_account_names:
                    s.execute(
                        text(
                            "INSERT INTO accounts (name, account_type, is_asset, balance, is_investment) VALUES (:name, :acc_type, :is_asset, :balance, :is_invest)"
                        ),
                        {
                            "name": name,
                            "acc_type": acc_type,
                            "is_asset": is_asset,
                            "balance": 0,
                            "is_invest": is_invest,
                        },
                    )
                    print(f"기본 계좌 '{name}'이(가) 추가되었습니다.")
                else:
                    print(f"기본 계좌 '{name}'은(는) 이미 존재합니다. 건너뜜.")

            print("초기 계좌 데이터 확인 및 삽입 완료.")

    except Exception as e:
        print(f"초기 계좌 데이터 삽입 중 오류 발생: {e}")


def seed_initial_transfer_rules(rules_path=config.TRANSFER_RULES_PATH):
    conn = st.connection("supabase", type="sql")
    s = conn.session

    try:
        with s.begin():
            count_result = s.execute(
                text('SELECT COUNT(*) as cnt FROM "transfer_rule"')
            ).scalar_one()
            if count_result > 0:
                print("이체 규칙 데이터가 이미 존재하여 초기 데이터 삽입을 건너뜜.")
                return

            print("초기 이체 규칙 데이터를 삽입합니다...")

            accounts_map_result = s.execute(
                text("SELECT id, name FROM accounts")
            ).fetchall()
            accounts_map = {row.name: row.id for row in accounts_map_result}

            with open(rules_path, "r", encoding="utf-8") as f:
                rules_from_json = json.load(f)

            for rule_data in rules_from_json:
                linked_account_name = rule_data.get("linked_account_name")
                linked_account_id = accounts_map.get(linked_account_name)
                if not linked_account_id:
                    print(
                        f"경고: 연결된 계좌 '{linked_account_name}'을(를) 찾을 수 없어 이체 규칙을 건너뜁니다."
                    )
                    continue

                rule_id_result = s.execute(
                    text(
                        'INSERT INTO "transfer_rule" (description, priority, linked_account_id) VALUES (:description, :priority, :linked_account_id) RETURNING id'
                    ),
                    {
                        "description": rule_data.get("description"),
                        "priority": rule_data.get("priority", 0),
                        "linked_account_id": linked_account_id,
                    },
                )
                rule_id = rule_id_result.scalar_one()

                for cond in rule_data.get("conditions", []):
                    s.execute(
                        text(
                            'INSERT INTO "transfer_rule_condition" (rule_id, column_to_check, match_type, value) VALUES (:rule_id, :column, :match_type, :value)'
                        ),
                        {
                            "rule_id": rule_id,
                            "column": cond.get("column"),
                            "match_type": cond.get("match_type"),
                            "value": cond.get("value"),
                        },
                    )
            print("초기 이체 규칙 데이터 삽입 완료.")

    except Exception as e:
        print(f"초기 이체 규칙 데이터 삽입 중 오류: {e}")
