import json
import streamlit as st
from sqlalchemy import text

import config
from core.db_manager import rebuild_category_paths


def seed_initial_categories():
    """
    초기 카테고리 데이터를 데이터베이스에 삽입.
    이미 카테고리 데이터가 존재하는 경우 삽입을 건너뜀.
    카테고리 삽입 후 계층 경로를 재구축.
    """

    conn = st.connection("supabase", type="sql")  # Supabase 데이터베이스 연결 객체
    s = conn.session  # SQLAlchemy 세션 객체

    # 'category' 테이블에 데이터가 이미 존재하는지 확인
    count_result = s.execute(text("SELECT COUNT(*) as cnt FROM category")).scalar_one()
    if count_result > 0:
        st.info("카테고리 데이터가 이미 존재하여 초기 데이터 삽입을 건너뜁니다.")
        return

    st.info("초기 카테고리 데이터를 삽입합니다...")

    try:
        # INSERT 쿼리를 실행하고 삽입된 레코드의 ID를 반환하는 헬퍼 함수
        def insert_and_get_id(query_str, params):
            result = s.execute(text(query_str), params)
            return result.scalar_one()  # 삽입된 ID 반환

        # 최상위(depth 1) 카테고리 삽입
        insert_top_query = "INSERT INTO category (category_code, category_type, description, depth) VALUES (:code, :type, :desc, :depth) RETURNING id"
        expense_id = insert_and_get_id(  # 지출 최상위 카테고리
            insert_top_query,
            {"code": "EXPENSE", "type": "EXPENSE", "desc": "지출", "depth": 1},
        )
        investment_id = insert_and_get_id(  # 투자 최상위 카테고리
            insert_top_query,
            {"code": "INVEST", "type": "INVEST", "desc": "투자", "depth": 1},
        )
        income_id = insert_and_get_id(  # 수입 최상위 카테고리
            insert_top_query,
            {"code": "INCOME", "type": "INCOME", "desc": "수입", "depth": 1},
        )
        transfer_id = insert_and_get_id(  # 내부 이체 최상위 카테고리
            insert_top_query,
            {"code": "TRANSFER", "type": "TRANSFER", "desc": "내부 이체", "depth": 1},
        )

        # 2단계 카테고리 삽입
        insert_level_query = "INSERT INTO category (category_code, category_type, parent_id, description, depth) VALUES (:code, :type, :parent_id, :desc, :depth) RETURNING id"
        insert_and_get_id(  # 미분류 지출
            insert_level_query,
            {
                "code": "UNCATEGORIZED",
                "type": "EXPENSE",
                "parent_id": expense_id,
                "desc": "미분류 지출",
                "depth": 2,
            },
        )
        insert_and_get_id(  # 미분류 수입
            insert_level_query,
            {
                "code": "UNCATEGORIZED",
                "type": "INCOME",
                "parent_id": income_id,
                "desc": "미분류 수입",
                "depth": 2,
            },
        )
        fixed_income_id = insert_and_get_id(  # 고정 수입
            insert_level_query,
            {
                "code": "FIXED_INCOME",
                "type": "INCOME",
                "parent_id": income_id,
                "desc": "고정 수입",
                "depth": 2,
            },
        )
        variable_income_id = insert_and_get_id(  # 변동 수입
            insert_level_query,
            {
                "code": "VARIABLE_INCOME",
                "type": "INCOME",
                "parent_id": income_id,
                "desc": "변동 수입",
                "depth": 2,
            },
        )
        fixed_expense_id = insert_and_get_id(  # 고정 지출
            insert_level_query,
            {
                "code": "FIXED_EXPENSE",
                "type": "EXPENSE",
                "parent_id": expense_id,
                "desc": "고정 지출",
                "depth": 2,
            },
        )
        variable_expense_id = insert_and_get_id(  # 변동 지출
            insert_level_query,
            {
                "code": "VARIABLE_EXPENSE",
                "type": "EXPENSE",
                "parent_id": expense_id,
                "desc": "변동 지출",
                "depth": 2,
            },
        )
        investment_lvl2_id = insert_and_get_id(  # 투자 (2단계)
            insert_level_query,
            {
                "code": "INVESTMENT",
                "type": "INVEST",
                "parent_id": investment_id,
                "desc": "투자",
                "depth": 2,
            },
        )
        insert_and_get_id(  # 카드대금 이체
            insert_level_query,
            {
                "code": "CARD_PAYMENT",
                "type": "TRANSFER",
                "parent_id": transfer_id,
                "desc": "카드대금 이체",
                "depth": 2,
            },
        )

        # 3단계 카테고리 삽입 (투자 관련)
        insert_and_get_id(  # 저축
            insert_level_query,
            {
                "code": "SAVINGS",
                "type": "INVEST",
                "parent_id": investment_lvl2_id,
                "desc": "저축",
                "depth": 3,
            },
        )
        insert_and_get_id(  # 주식
            insert_level_query,
            {
                "code": "STOCKS",
                "type": "INVEST",
                "parent_id": investment_lvl2_id,
                "desc": "주식",
                "depth": 3,
            },
        )
        insert_and_get_id(  # 비트코인
            insert_level_query,
            {
                "code": "CRYPTOCURRENCY",
                "type": "INVEST",
                "parent_id": investment_lvl2_id,
                "desc": "비트코인",
                "depth": 3,
            },
        )
        insert_and_get_id(  # 부동산
            insert_level_query,
            {
                "code": "REAL_ESTATE",
                "type": "INVEST",
                "parent_id": investment_lvl2_id,
                "desc": "부동산",
                "depth": 3,
            },
        )

        # 3단계 카테고리 삽입 (수입 관련)
        insert_and_get_id(  # 급여
            insert_level_query,
            {
                "code": "SALARY",
                "type": "INCOME",
                "parent_id": fixed_income_id,
                "desc": "급여",
                "depth": 3,
            },
        )
        subsidy_id = insert_and_get_id(  # 지원금
            insert_level_query,
            {
                "code": "SUBSIDY",
                "type": "INCOME",
                "parent_id": fixed_income_id,
                "desc": "지원금",
                "depth": 3,
            },
        )
        insert_and_get_id(  # 인센티브
            insert_level_query,
            {
                "code": "INCENTIVE",
                "type": "INCOME",
                "parent_id": variable_income_id,
                "desc": "인센티브",
                "depth": 3,
            },
        )
        insert_and_get_id(  # 금융수입
            insert_level_query,
            {
                "code": "FINANCIAL_INCOME",
                "type": "INCOME",
                "parent_id": variable_income_id,
                "desc": "금융수입",
                "depth": 3,
            },
        )

        # 3단계 카테고리 삽입 (지출 - 고정 관련)
        housing_id = insert_and_get_id(  # 주거비
            insert_level_query,
            {
                "code": "HOUSING_EXPENSE",
                "type": "EXPENSE",
                "parent_id": fixed_expense_id,
                "desc": "주거비",
                "depth": 3,
            },
        )
        utility_id = insert_and_get_id(  # 공과금
            insert_level_query,
            {
                "code": "UTILITY_BILLS",
                "type": "EXPENSE",
                "parent_id": fixed_expense_id,
                "desc": "공과금",
                "depth": 3,
            },
        )
        comm_id = insert_and_get_id(  # 통신비
            insert_level_query,
            {
                "code": "COMMUNICATION_EXPENSE",
                "type": "EXPENSE",
                "parent_id": fixed_expense_id,
                "desc": "통신비",
                "depth": 3,
            },
        )
        insurance_id = insert_and_get_id(  # 보험료
            insert_level_query,
            {
                "code": "INSURANCE_EXPENSE",
                "type": "EXPENSE",
                "parent_id": fixed_expense_id,
                "desc": "보험료",
                "depth": 3,
            },
        )
        membership_id = insert_and_get_id(  # 회원료
            insert_level_query,
            {
                "code": "MEMBERSHIP",
                "type": "EXPENSE",
                "parent_id": fixed_expense_id,
                "desc": "회원료",
                "depth": 3,
            },
        )
        insert_and_get_id(  # 가족 모임비
            insert_level_query,
            {
                "code": "FAMILY_GATHERING",
                "type": "EXPENSE",
                "parent_id": fixed_expense_id,
                "desc": "가족 모임비",
                "depth": 3,
            },
        )

        # 3단계 카테고리 삽입 (지출 - 변동 관련)
        food_id = insert_and_get_id(  # 식비
            insert_level_query,
            {
                "code": "FOOD_EXPENSE",
                "type": "EXPENSE",
                "parent_id": variable_expense_id,
                "desc": "식비",
                "depth": 3,
            },
        )
        transport_id = insert_and_get_id(  # 교통비
            insert_level_query,
            {
                "code": "TRANSPORTATION_EXPENSE",
                "type": "EXPENSE",
                "parent_id": variable_expense_id,
                "desc": "교통비",
                "depth": 3,
            },
        )
        shopping_id = insert_and_get_id(  # 쇼핑
            insert_level_query,
            {
                "code": "SHOPPING",
                "type": "EXPENSE",
                "parent_id": variable_expense_id,
                "desc": "쇼핑",
                "depth": 3,
            },
        )
        medical_id = insert_and_get_id(  # 의료비
            insert_level_query,
            {
                "code": "MEDICAL_EXPENSE",
                "type": "EXPENSE",
                "parent_id": variable_expense_id,
                "desc": "의료비",
                "depth": 3,
            },
        )
        insert_and_get_id(  # 교육비
            insert_level_query,
            {
                "code": "EDUCATION_EXPENSE",
                "type": "EXPENSE",
                "parent_id": variable_expense_id,
                "desc": "교육비",
                "depth": 3,
            },
        )
        living_id = insert_and_get_id(  # 생활비
            insert_level_query,
            {
                "code": "LIVING_EXPENSE",
                "type": "EXPENSE",
                "parent_id": variable_expense_id,
                "desc": "생활비",
                "depth": 3,
            },
        )
        insert_and_get_id(  # 경조사비
            insert_level_query,
            {
                "code": "EVENT_EXPENSE",
                "type": "EXPENSE",
                "parent_id": variable_expense_id,
                "desc": "경조사비",
                "depth": 3,
            },
        )
        leisure_id = insert_and_get_id(  # 여가비
            insert_level_query,
            {
                "code": "LEISURE_EXPENSE",
                "type": "EXPENSE",
                "parent_id": variable_expense_id,
                "desc": "여가비",
                "depth": 3,
            },
        )

        # 4단계 카테고리 삽입 (주거비 하위)
        insert_and_get_id(  # 월세
            insert_level_query,
            {
                "code": "MONTHLY_RENT",
                "type": "EXPENSE",
                "parent_id": housing_id,
                "desc": "월세",
                "depth": 4,
            },
        )
        insert_and_get_id(  # 관리비
            insert_level_query,
            {
                "code": "MANAGEMENT_FEE",
                "type": "EXPENSE",
                "parent_id": housing_id,
                "desc": "관리비",
                "depth": 4,
            },
        )
        # 4단계 카테고리 삽입 (공과금 하위)
        insert_and_get_id(  # 전기세
            insert_level_query,
            {
                "code": "ELECTRICITY_BILL",
                "type": "EXPENSE",
                "parent_id": utility_id,
                "desc": "전기세",
                "depth": 4,
            },
        )
        insert_and_get_id(  # 수도세
            insert_level_query,
            {
                "code": "WATER_BILL",
                "type": "EXPENSE",
                "parent_id": utility_id,
                "desc": "수도세",
                "depth": 4,
            },
        )
        insert_and_get_id(  # 가스비
            insert_level_query,
            {
                "code": "GAS_BILL",
                "type": "EXPENSE",
                "parent_id": utility_id,
                "desc": "가스비",
                "depth": 4,
            },
        )
        # 4단계 카테고리 삽입 (통신비 하위)
        insert_and_get_id(  # 인터넷
            insert_level_query,
            {
                "code": "INTERNET_BILL",
                "type": "EXPENSE",
                "parent_id": comm_id,
                "desc": "인터넷",
                "depth": 4,
            },
        )
        insert_and_get_id(  # 티비수신비
            insert_level_query,
            {
                "code": "TV_BILL",
                "type": "EXPENSE",
                "parent_id": comm_id,
                "desc": "티비수신비",
                "depth": 4,
            },
        )
        insert_and_get_id(  # 핸드폰비
            insert_level_query,
            {
                "code": "MOBILE_BILL",
                "type": "EXPENSE",
                "parent_id": comm_id,
                "desc": "핸드폰비",
                "depth": 4,
            },
        )
        # 4단계 카테고리 삽입 (보험료 하위)
        insert_and_get_id(  # 영준 보험
            insert_level_query,
            {
                "code": "YOUNGJUN_INSURANCE",
                "type": "EXPENSE",
                "parent_id": insurance_id,
                "desc": "영준 보험",
                "depth": 4,
            },
        )
        insert_and_get_id(  # 혜인 보험
            insert_level_query,
            {
                "code": "HYEIN_INSURANCE",
                "type": "EXPENSE",
                "parent_id": insurance_id,
                "desc": "혜인 보험",
                "depth": 4,
            },
        )
        insert_and_get_id(  # 세아 보험
            insert_level_query,
            {
                "code": "SEA_INSURANCE",
                "type": "EXPENSE",
                "parent_id": insurance_id,
                "desc": "세아 보험",
                "depth": 4,
            },
        )
        # 4단계 카테고리 삽입 (회원료 하위)
        insert_and_get_id(  # 쿠팡 맴버쉽
            insert_level_query,
            {
                "code": "COUPANG_MEMBERSHIP",
                "type": "EXPENSE",
                "parent_id": membership_id,
                "desc": "쿠팡 맴버쉽",
                "depth": 4,
            },
        )
        # 4단계 카테고리 삽입 (식비 하위)
        insert_and_get_id(  # 외식
            insert_level_query,
            {
                "code": "DINING_OUT",
                "type": "EXPENSE",
                "parent_id": food_id,
                "desc": "외식",
                "depth": 4,
            },
        )
        insert_and_get_id(  # 배달
            insert_level_query,
            {
                "code": "DELIVERY_FOOD",
                "type": "EXPENSE",
                "parent_id": food_id,
                "desc": "배달",
                "depth": 4,
            },
        )
        insert_and_get_id(  # 주류
            insert_level_query,
            {
                "code": "ALCOHOL",
                "type": "EXPENSE",
                "parent_id": food_id,
                "desc": "주류",
                "depth": 4,
            },
        )
        insert_and_get_id(  # 편의점
            insert_level_query,
            {
                "code": "CONVENIENCE_STORE",
                "type": "EXPENSE",
                "parent_id": food_id,
                "desc": "편의점",
                "depth": 4,
            },
        )
        insert_and_get_id(  # 식료품
            insert_level_query,
            {
                "code": "GROCERIES",
                "type": "EXPENSE",
                "parent_id": food_id,
                "desc": "식료품",
                "depth": 4,
            },
        )
        # 4단계 카테고리 삽입 (교통비 하위)
        insert_and_get_id(  # 대중교통비
            insert_level_query,
            {
                "code": "PUBLIC_TRANSPORT",
                "type": "EXPENSE",
                "parent_id": transport_id,
                "desc": "대중교통비",
                "depth": 4,
            },
        )
        insert_and_get_id(  # 주유비
            insert_level_query,
            {
                "code": "FUEL_EXPENSE",
                "type": "EXPENSE",
                "parent_id": transport_id,
                "desc": "주유비",
                "depth": 4,
            },
        )
        # 4단계 카테고리 삽입 (쇼핑 하위)
        insert_and_get_id(  # 의류비
            insert_level_query,
            {
                "code": "CLOTHING",
                "type": "EXPENSE",
                "parent_id": shopping_id,
                "desc": "의류비",
                "depth": 4,
            },
        )
        insert_and_get_id(  # 가구
            insert_level_query,
            {
                "code": "FURNITURE",
                "type": "EXPENSE",
                "parent_id": shopping_id,
                "desc": "가구",
                "depth": 4,
            },
        )
        insert_and_get_id(  # 유아용품
            insert_level_query,
            {
                "code": "CHILDCARE_PRODUCTS",
                "type": "EXPENSE",
                "parent_id": shopping_id,
                "desc": "유아용품",
                "depth": 4,
            },
        )
        insert_and_get_id(  # 전자제품
            insert_level_query,
            {
                "code": "ELECTRONICS",
                "type": "EXPENSE",
                "parent_id": shopping_id,
                "desc": "전자제품",
                "depth": 4,
            },
        )
        # 4단계 카테고리 삽입 (의료비 하위)
        insert_and_get_id(  # 병원비
            insert_level_query,
            {
                "code": "HOSPITAL_EXPENSE",
                "type": "EXPENSE",
                "parent_id": medical_id,
                "desc": "병원비",
                "depth": 4,
            },
        )
        insert_and_get_id(  # 의약품
            insert_level_query,
            {
                "code": "PHARMACY",
                "type": "EXPENSE",
                "parent_id": medical_id,
                "desc": "의약품",
                "depth": 4,
            },
        )
        # 4단계 카테고리 삽입 (생활비 하위)
        insert_and_get_id(  # 용돈
            insert_level_query,
            {
                "code": "ALLOWANCE",
                "type": "EXPENSE",
                "parent_id": living_id,
                "desc": "용돈",
                "depth": 4,
            },
        )
        insert_and_get_id(  # 세탁비
            insert_level_query,
            {
                "code": "LAUNDRY_EXPENSE",
                "type": "EXPENSE",
                "parent_id": living_id,
                "desc": "세탁비",
                "depth": 4,
            },
        )
        insert_and_get_id(  # 유아비
            insert_level_query,
            {
                "code": "CHILDCARE_EXPENSE",
                "type": "EXPENSE",
                "parent_id": living_id,
                "desc": "유아비",
                "depth": 4,
            },
        )
        # 4단계 카테고리 삽입 (여가비 하위)
        insert_and_get_id(  # 여행
            insert_level_query,
            {
                "code": "TRAVEL",
                "type": "EXPENSE",
                "parent_id": leisure_id,
                "desc": "여행",
                "depth": 4,
            },
        )
        insert_and_get_id(  # 영화
            insert_level_query,
            {
                "code": "MOVIES",
                "type": "EXPENSE",
                "parent_id": leisure_id,
                "desc": "영화",
                "depth": 4,
            },
        )
        # 4단계 카테고리 삽입 (지원금 하위)
        insert_and_get_id(  # 아동수당
            insert_level_query,
            {
                "code": "CHILD_SUBSIDY",
                "type": "INCOME",
                "parent_id": subsidy_id,
                "desc": "아동수당",
                "depth": 4,
            },
        )
        insert_and_get_id(  # 부모수당
            insert_level_query,
            {
                "code": "PARENT_SUBSIDY",
                "type": "INCOME",
                "parent_id": subsidy_id,
                "desc": "부모수당",
                "depth": 4,
            },
        )
        insert_and_get_id(  # 핸드폰지원금
            insert_level_query,
            {
                "code": "MOBILE_SUBSIDY",
                "type": "INCOME",
                "parent_id": subsidy_id,
                "desc": "핸드폰지원금",
                "depth": 4,
            },
        )

        s.commit()  # 모든 삽입 작업 커밋
        st.success("초기 카테고리 데이터 삽입 완료.")

        rebuild_category_paths()  # 카테고리 경로 재구축 함수 호출
        st.success("초기 카테고리 경로 작업 완료.")

    except Exception as e:
        st.error(f"초기 데이터 삽입 중 오류 발생: {e}")
        s.rollback()  # 오류 발생 시 롤백


def seed_initial_parties():
    """
    초기 거래처(transaction_party) 데이터를 데이터베이스에 삽입.
    이미 거래처 데이터가 존재하는 경우 삽입을 건너뜀.
    """
    conn = st.connection("supabase", type="sql")  # Supabase 데이터베이스 연결 객체
    s = conn.session  # SQLAlchemy 세션 객체

    try:
        # with s.begin() 블록을 사용하여 트랜잭션 관리
        with s.begin():
            # 'transaction_party' 테이블에 데이터가 이미 존재하는지 확인
            count_result = s.execute(
                text('SELECT COUNT(*) as cnt FROM "transaction_party"')
            ).scalar_one()
            if count_result > 0:
                st.info("거래처 데이터가 이미 존재하여 초기 데이터 삽입을 건너뜁니다.")
                return

            st.info("초기 거래처 데이터를 삽입합니다...")
            # 삽입할 기본 거래처 목록
            parties_to_seed = [
                ("UNREGISTERED", "미등록"),
                ("쿠팡", "쿠팡"),
                ("GS25", "GS25 편의점"),
                ("스타필드", "스타필드"),
                ("쿠팡이츠", "쿠팡이츠"),
            ]

            # 각 거래처 데이터를 테이블에 삽입
            for code, desc in parties_to_seed:
                s.execute(
                    text(
                        'INSERT INTO "transaction_party" (party_code, description) VALUES (:code, :desc)'
                    ),
                    {"code": code, "desc": desc},
                )
            # 트랜잭션이 with s.begin() 블록을 벗어나면 자동으로 커밋됨
            st.success("초기 거래처 데이터 삽입 완료.")

    except Exception as e:
        st.error(f"초기 거래처 데이터 삽입 중 오류 발생: {e}")
        # with s.begin() 사용 시 오류 발생 시 자동으로 롤백됨 (명시적 s.rollback() 불필요)


def seed_initial_rules(rules_path=config.RULES_PATH):
    """
    초기 분류 규칙(rule) 데이터를 JSON 파일로부터 데이터베이스에 삽입.
    이미 규칙 데이터가 존재하는 경우 삽입을 건너뜀.
    JSON 파일 내의 'category_code'를 'category' 테이블의 ID로 매핑하여 삽입.

    Args:
        rules_path (str): 분류 규칙 JSON 파일 경로.
    """

    conn = st.connection("supabase", type="sql")  # Supabase 데이터베이스 연결 객체
    s = conn.session  # SQLAlchemy 세션 객체

    try:
        # with s.begin() 블록을 사용하여 트랜잭션 관리
        with s.begin():
            # 'rule' 테이블에 데이터가 이미 존재하는지 확인
            count_result = s.execute(
                text('SELECT COUNT(*) as cnt FROM "rule"')
            ).scalar_one()
            if count_result > 0:
                st.info("분류 규칙 데이터가 이미 존재하여 초기 데이터 삽입을 건너뜀.")
                return

            st.info("초기 분류 규칙 데이터를 삽입합니다...")

            # 'category' 테이블에서 category_code와 ID를 조회하여 매핑 딕셔너리 생성
            category_map_result = s.execute(
                text("SELECT category_code, id FROM category")
            ).fetchall()
            category_map = {row.category_code: row.id for row in category_map_result}

            # JSON 파일에서 규칙 데이터 로드
            with open(rules_path, "r", encoding="utf-8") as f:
                rules_from_json = json.load(f)

            # 각 규칙 데이터를 순회하며 데이터베이스에 삽입
            for rule_data in rules_from_json:
                category_code = rule_data.get("category_code")
                # 규칙에 명시된 카테고리 코드가 DB에 존재하지 않으면 건너김
                if category_code not in category_map:
                    continue

                # 'rule' 테이블에 규칙 삽입 및 삽입된 규칙 ID 반환
                rule_id_result = s.execute(
                    text(
                        'INSERT INTO "rule" (category_id, description, priority) VALUES (:category_id, :description, :priority) RETURNING id'
                    ),
                    {
                        "category_id": category_map[category_code],
                        "description": rule_data.get("description"),
                        "priority": rule_data.get("priority", 0),  # priority 기본값 0
                    },
                )
                rule_id = rule_id_result.scalar_one()  # 삽입된 규칙 ID

                # 각 규칙의 조건을 'rule_condition' 테이블에 삽입
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
            # 트랜잭션이 with s.begin() 블록을 벗어나면 자동으로 커밋됨
            st.success("초기 분류 규칙 데이터 삽입 완료.")

    except Exception as e:
        st.error(f"초기 규칙 데이터 삽입 중 오류 발생: {e}")
        # with s.begin() 사용 시 오류 발생 시 자동으로 롤백됨


def seed_initial_accounts():
    """
    초기 계좌(accounts) 데이터를 데이터베이스에 삽입.
    이미 계좌 데이터가 존재하는 경우 해당 계좌는 건너뛰고, 없는 계좌만 삽입.
    """

    conn = st.connection("supabase", type="sql")  # Supabase 데이터베이스 연결 객체
    s = conn.session  # SQLAlchemy 세션 객체

    st.info("기본 계좌 데이터 삽입을 확인합니다...")

    # 삽입할 기본 계좌 목록 (이름, 유형, 자산 여부, 투자 계좌 여부)
    default_accounts = [
        ("신한은행-110-227-963599", "BANK_ACCOUNT", True, False),
        ("신한카드", "CREDIT_CARD", False, False),
        ("국민카드", "CREDIT_CARD", False, False),
        ("현대카드", "CREDIT_CARD", False, False),
        ("현금", "CASH", True, False),
        (
            "미지정_거래처",
            "UNCATEGORIZED",
            True,
            False,
        ),  # 이 계좌는 transaction_party와 관련된 것으로 보이나 accounts 테이블에 삽입되는 점 확인 필요
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
        # with s.begin() 블록을 사용하여 트랜잭션 관리
        with s.begin():
            # 현재 데이터베이스에 존재하는 계좌 이름 목록 조회
            existing_accounts_result = s.execute(
                text("SELECT name FROM accounts")
            ).fetchall()
            existing_account_names = {row.name for row in existing_accounts_result}

            # 기본 계좌 목록을 순회하며 존재하지 않는 계좌만 삽입
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
                            "balance": 0,  # 초기 잔액은 0으로 설정
                            "is_invest": is_invest,
                        },
                    )
                    print(f"기본 계좌 '{name}'이(가) 추가되었습니다.")
                else:
                    print(f"기본 계좌 '{name}'은(는) 이미 존재합니다. 건너뜀.")
            # 트랜잭션이 with s.begin() 블록을 벗어나면 자동으로 커밋됨
            st.success("초기 계좌 데이터 확인 및 삽입 완료.")

    except Exception as e:
        st.error(f"초기 계좌 데이터 삽입 중 오류 발생: {e}")
        # with s.begin() 사용 시 오류 발생 시 자동으로 롤백됨


def seed_initial_transfer_rules(rules_path=config.TRANSFER_RULES_PATH):
    """
    초기 이체 규칙(transfer_rule) 데이터를 JSON 파일로부터 데이터베이스에 삽입.
    이미 규칙 데이터가 존재하는 경우 삽입을 건너뜀.
    JSON 파일 내의 'linked_account_name'을 'accounts' 테이블의 ID로 매핑하여 삽입.

    Args:
        rules_path (str): 이체 규칙 JSON 파일 경로.
    """

    conn = st.connection("supabase", type="sql")  # Supabase 데이터베이스 연결 객체
    s = conn.session  # SQLAlchemy 세션 객체

    try:
        # with s.begin() 블록을 사용하여 트랜잭션 관리
        with s.begin():
            # 'transfer_rule' 테이블에 데이터가 이미 존재하는지 확인
            count_result = s.execute(
                text('SELECT COUNT(*) as cnt FROM "transfer_rule"')
            ).scalar_one()
            if count_result > 0:
                st.info("이체 규칙 데이터가 이미 존재하여 초기 데이터 삽입을 건너뜀.")
                return

            st.info("초기 이체 규칙 데이터를 삽입합니다...")

            # 'accounts' 테이블에서 ID와 이름을 조회하여 매핑 딕셔너리 생성
            accounts_map_result = s.execute(
                text("SELECT id, name FROM accounts")
            ).fetchall()
            accounts_map = {row.name: row.id for row in accounts_map_result}

            # JSON 파일에서 이체 규칙 데이터 로드
            with open(rules_path, "r", encoding="utf-8") as f:
                rules_from_json = json.load(f)

            # 각 규칙 데이터를 순회하며 데이터베이스에 삽입
            for rule_data in rules_from_json:
                linked_account_name = rule_data.get("linked_account_name")
                linked_account_id = accounts_map.get(linked_account_name)
                # 연결된 계좌 이름을 찾을 수 없는 경우 경고 출력 및 규칙 건너뛰기
                if not linked_account_id:
                    print(
                        f"경고: 연결된 계좌 '{linked_account_name}'을(를) 찾을 수 없어 이체 규칙을 건너뜁니다."
                    )
                    continue

                # 'transfer_rule' 테이블에 규칙 삽입 및 삽입된 규칙 ID 반환
                rule_id_result = s.execute(
                    text(
                        'INSERT INTO "transfer_rule" (description, priority, linked_account_id) VALUES (:description, :priority, :linked_account_id) RETURNING id'
                    ),
                    {
                        "description": rule_data.get("description"),
                        "priority": rule_data.get("priority", 0),  # priority 기본값 0
                        "linked_account_id": linked_account_id,
                    },
                )
                rule_id = rule_id_result.scalar_one()  # 삽입된 규칙 ID

                # 각 규칙의 조건을 'transfer_rule_condition' 테이블에 삽입
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
            # 트랜잭션이 with s.begin() 블록을 벗어나면 자동으로 커밋됨
            st.success("초기 이체 규칙 데이터 삽입 완료.")

    except Exception as e:
        st.error(f"초기 이체 규칙 데이터 삽입 중 오류: {e}")
        # with s.begin() 사용 시 오류 발생 시 자동으로 롤백됨
