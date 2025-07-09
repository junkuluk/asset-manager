-- PostgreSQL에서는 테이블과 컬럼 이름에 큰따옴표(")를 사용하는 것이 표준입니다.

CREATE TABLE IF NOT EXISTS "category" (
    id SERIAL PRIMARY KEY,                      -- SQLite의 INTEGER PRIMARY KEY -> SERIAL PRIMARY KEY
    category_code TEXT NOT NULL,
    category_type TEXT NOT NULL,
    description TEXT,
    parent_id INTEGER REFERENCES "category"(id), -- 외래 키를 컬럼 정의에 직접 포함
    materialized_path_desc TEXT,
    depth INTEGER NOT NULL
);

-- 인덱스 생성은 별도로 유지
CREATE UNIQUE INDEX IF NOT EXISTS idx_category_code_type ON "category" (category_code, category_type);

CREATE TABLE IF NOT EXISTS "transaction_party" (
    id SERIAL PRIMARY KEY,
    party_code TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS "rule" (
    id SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES "category"(id),
    description TEXT,
    priority INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS "rule_condition" (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER NOT NULL REFERENCES "rule"(id) ON DELETE CASCADE,
    column_to_check TEXT NOT NULL,
    match_type TEXT NOT NULL CHECK(match_type IN ('EXACT', 'CONTAINS', 'REGEX', 'GREATER_THAN', 'LESS_THAN', 'EQUALS')),
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS "accounts" (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    account_type TEXT NOT NULL,
    balance BIGINT NOT NULL DEFAULT 0, -- 큰 금액을 위해 BIGINT 사용
    is_asset BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS "transaction" (
    id BIGSERIAL PRIMARY KEY, -- 거래량이 많을 것을 대비해 BIGSERIAL 사용
    "type" TEXT NOT NULL,
    account_id INTEGER NOT NULL REFERENCES "accounts"(id),
    linked_account_id INTEGER REFERENCES "accounts"(id),
    transaction_type TEXT,
    transaction_provider TEXT,
    category_id INTEGER NOT NULL REFERENCES "category"(id),
    transaction_party_id INTEGER NOT NULL REFERENCES "transaction_party"(id),
    transaction_date TIMESTAMPTZ NOT NULL, -- 시간대 정보를 포함하는 TIMESTAMPTZ 추천
    transaction_amount BIGINT,
    description TEXT,
    content TEXT
);

CREATE TABLE IF NOT EXISTS "card_transaction" (
    -- transaction 테이블의 id를 그대로 사용하므로 BIGINT로 타입을 맞춤
    id BIGINT PRIMARY KEY REFERENCES "transaction"(id) ON DELETE CASCADE,
    card_approval_number TEXT NOT NULL,
    card_type TEXT NOT NULL,
    card_name TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_card_approval_number ON "card_transaction" (card_approval_number);

CREATE TABLE IF NOT EXISTS "bank_transaction" (
    -- transaction 테이블의 id를 그대로 사용하므로 BIGINT로 타입을 맞춤
    id BIGINT PRIMARY KEY REFERENCES "transaction"(id) ON DELETE CASCADE,
    unique_hash TEXT NOT NULL UNIQUE,
    branch TEXT,
    balance_amount BIGINT
);