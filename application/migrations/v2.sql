CREATE TABLE IF NOT EXISTS "transfer_rule" (
    id SERIAL PRIMARY KEY, -- Auto-increment ID
    description TEXT,
    priority INTEGER NOT NULL DEFAULT 0,
    linked_account_id INTEGER REFERENCES "accounts"(id) -- 이전에 논의된 연결 계좌 ID 컬럼
);

CREATE TABLE IF NOT EXISTS "transfer_rule_condition" (
    id SERIAL PRIMARY KEY, -- Auto-increment ID
    rule_id INTEGER NOT NULL REFERENCES "transfer_rule"(id) ON DELETE CASCADE,
    column_to_check TEXT NOT NULL,
    match_type TEXT NOT NULL,
    value TEXT NOT NULL
);