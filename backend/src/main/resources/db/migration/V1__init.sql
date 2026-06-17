-- 자산관리 앱 통합 스키마 (간소화 버전)

CREATE TABLE account (
    id              BIGSERIAL PRIMARY KEY,
    name            TEXT      NOT NULL UNIQUE,
    type            TEXT      NOT NULL,              -- BANK | CARD | INVEST | CASH
    is_asset        BOOLEAN   NOT NULL DEFAULT TRUE,
    initial_balance BIGINT    NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE category (
    id         BIGSERIAL PRIMARY KEY,
    name       TEXT   NOT NULL,
    type       TEXT   NOT NULL,                      -- INCOME | EXPENSE
    parent_id  BIGINT REFERENCES category(id),
    sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX ux_category_name_type ON category(name, type);

CREATE TABLE rule (
    id                BIGSERIAL PRIMARY KEY,
    name              TEXT    NOT NULL,
    priority          INTEGER NOT NULL DEFAULT 0,
    action            TEXT    NOT NULL,              -- CATEGORIZE | TRANSFER
    category_id       BIGINT  REFERENCES category(id),
    linked_account_id BIGINT  REFERENCES account(id)
);

CREATE TABLE rule_condition (
    id         BIGSERIAL PRIMARY KEY,
    rule_id    BIGINT NOT NULL REFERENCES rule(id) ON DELETE CASCADE,
    field      TEXT   NOT NULL,                      -- content | amount | merchant ...
    match_type TEXT   NOT NULL,                      -- CONTAINS | EXACT | REGEX | GT | LT | EQ
    value      TEXT   NOT NULL
);

CREATE TABLE transaction (
    id                  BIGSERIAL PRIMARY KEY,
    account_id          BIGINT NOT NULL REFERENCES account(id),
    type                TEXT   NOT NULL,             -- INCOME | EXPENSE | TRANSFER | INVEST
    source              TEXT   NOT NULL,             -- CARD | BANK | MANUAL
    category_id         BIGINT REFERENCES category(id),
    linked_account_id   BIGINT REFERENCES account(id),
    txn_date            TIMESTAMPTZ NOT NULL,
    amount              BIGINT NOT NULL,             -- 항상 양수, 방향은 type으로 판단
    content             TEXT,
    memo                TEXT,
    merchant            TEXT,
    is_manual_category  BOOLEAN NOT NULL DEFAULT FALSE,
    dedup_hash          TEXT NOT NULL UNIQUE,
    -- 카드 전용 (nullable)
    card_approval_no    TEXT,
    card_name           TEXT,
    card_kind           TEXT,                        -- 신용 | 체크
    -- 은행 전용 (nullable)
    bank_branch         TEXT
);
CREATE INDEX ix_transaction_date ON transaction(txn_date);
CREATE INDEX ix_transaction_type ON transaction(type);
CREATE INDEX ix_transaction_category ON transaction(category_id);
