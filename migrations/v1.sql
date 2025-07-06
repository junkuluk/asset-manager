PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS "category" (
    id INTEGER PRIMARY KEY,
    category_code TEXT NOT NULL,
    category_type TEXT NOT NULL,
    description TEXT,
    parent_id INTEGER,
    materialized_path_desc TEXT NOT NULL,
    depth INTEGER NOT NULL,
    FOREIGN KEY (parent_id) REFERENCES "category" (id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_category_code_type ON "category" (category_code, category_type);

CREATE TABLE IF NOT EXISTS "transaction_party" (
    id INTEGER PRIMARY KEY,
    party_code TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS "rule" (
    id INTEGER PRIMARY KEY,
    category_id INTEGER NOT NULL,
    description TEXT,
    priority INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (category_id) REFERENCES "category" (id)
);

CREATE TABLE IF NOT EXISTS "rule_condition" (
    id INTEGER PRIMARY KEY,
    rule_id INTEGER NOT NULL,              -- 어떤 규칙에 속한 조건인지
    column_to_check TEXT NOT NULL,         -- 검사할 컬럼 이름 ('content', 'transaction_amount' 등)
    match_type TEXT NOT NULL CHECK(match_type IN ('EXACT', 'CONTAINS', 'REGEX', 'GREATER_THAN', 'LESS_THAN', 'EQUALS')),
    value TEXT NOT NULL,                   -- 비교할 값
    FOREIGN KEY (rule_id) REFERENCES "rule" (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "accounts" (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,          -- 계좌 이름 (예: 하나은행 입출금, 신한카드)
    account_type TEXT NOT NULL,         -- 타입 (예: BANK_ACCOUNT, CREDIT_CARD, CASH, STOCK_ASSET)
    balance INTEGER NOT NULL DEFAULT 0, -- 현재 잔액 (부채는 음수로 저장 가능)
    is_asset BOOLEAN NOT NULL           -- 자산(True)인지 부채(False)인지 구분
);



CREATE TABLE IF NOT EXISTS "transaction" (
    id INTEGER PRIMARY KEY,
    "type" TEXT NOT NULL,
    account_id INTEGER NOT NULL,
    transaction_type TEXT NOT NULL,
    transaction_provider TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    transaction_party_id INTEGER NOT NULL,
    transaction_date TEXT NOT NULL,
    transaction_amount INTEGER,
    description TEXT,
    content TEXT,
    FOREIGN KEY (category_id) REFERENCES "category" (id),
    FOREIGN KEY (account_id) REFERENCES "accounts" (id),
    FOREIGN KEY (transaction_party_id) REFERENCES "transaction_party" (id)
);

CREATE TABLE IF NOT EXISTS "card_transaction" (
    id INTEGER PRIMARY KEY,
    card_approval_number TEXT NOT NULL,
    card_type TEXT NOT NULL,
    card_name TEXT NOT NULL,
    FOREIGN KEY (id) REFERENCES "transaction" (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_card_approval_number ON "card_transaction" (card_approval_number);


CREATE TABLE IF NOT EXISTS "bank_transaction" (
    id INTEGER PRIMARY KEY,
    unique_hash TEXT NOT NULL UNIQUE, -- 중복 입력을 막기 위한 고유 해시값
    branch TEXT,                      -- '거래점' 컬럼
    balance_amount INTEGER,
    FOREIGN KEY (id) REFERENCES "transaction" (id) ON DELETE CASCADE
);

