import json
import streamlit as st
from sqlalchemy import text

import config
from core.db_manager import rebuild_category_paths


def seed_initial_categories():
    """
    categories.json 파일을 읽어 초기 카테고리 데이터를 재귀적으로 삽입합니다.
    이미 카테고리 데이터가 존재하는 경우 삽입을 건너뜁니다.
    """
    conn = st.connection("supabase", type="sql")
    s = conn.session

    # 데이터 존재 여부 확인
    count_result = s.execute(text("SELECT COUNT(*) as cnt FROM category")).scalar_one()
    if count_result > 0:
        st.info("카테고리 데이터가 이미 존재하여 초기 데이터 삽입을 건너뜁니다.")
        return

    st.info("초기 카테고리 데이터를 삽입합니다...")

    # 재귀적으로 카테고리를 삽입하는 헬퍼 함수
    def insert_recursive(category_list, parent_id, depth, category_type):
        insert_query = text(
            "INSERT INTO category (category_code, category_type, parent_id, description, depth) "
            "VALUES (:code, :type, :parent_id, :desc, :depth) RETURNING id"
        )

        for category in category_list:
            # 현재 카테고리 삽입
            new_id = s.execute(
                insert_query,
                {
                    "code": category["code"],
                    "type": category_type,
                    "parent_id": parent_id,
                    "desc": category["desc"],
                    "depth": depth,
                },
            ).scalar_one()

            # 자식 카테고리가 있으면 재귀 호출
            if "children" in category and category["children"]:
                insert_recursive(category["children"], new_id, depth + 1, category_type)

    try:
        # JSON 파일 로드
        with open(config.CATEGORIES_PATH, "r", encoding="utf-8") as f:
            all_categories = json.load(f)

        # 최상위 카테고리부터 삽입 시작
        for top_category in all_categories:
            # 최상위 카테고리는 parent_id가 없으므로 None, depth는 1
            insert_recursive([top_category], None, 1, top_category["code"])

        s.commit()
        st.success("초기 카테고리 데이터 삽입 완료.")

        rebuild_category_paths()
        st.success("초기 카테고리 경로 작업 완료.")

    except Exception as e:
        st.error(f"초기 데이터 삽입 중 오류 발생: {e}")
        s.rollback()


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
