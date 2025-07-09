CREATE TABLE IF NOT EXISTS "transfer_rule" (
    id INTEGER PRIMARY KEY,
    description TEXT,                      -- 규칙 설명 (예: "신한카드 자동이체")
    priority INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS "transfer_rule_condition" (
    id INTEGER PRIMARY KEY,
    rule_id INTEGER NOT NULL,
    column_to_check TEXT NOT NULL,
    match_type TEXT NOT NULL,
    value TEXT NOT NULL,
    FOREIGN KEY (rule_id) REFERENCES "transfer_rule" (id) ON DELETE CASCADE
);