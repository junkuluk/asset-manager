CREATE TABLE IF NOT EXISTS "account_balance_history" (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL,
    change_date TEXT NOT NULL,
    previous_balance INTEGER NOT NULL,
    change_amount INTEGER NOT NULL,
    new_balance INTEGER NOT NULL,
    reason TEXT, -- 조정 사유 (예: 초기 잔액 설정)
    FOREIGN KEY (account_id) REFERENCES "accounts" (id) ON DELETE CASCADE
);