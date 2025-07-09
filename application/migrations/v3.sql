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

ALTER TABLE "transfer_rule" ADD COLUMN linked_account_id INTEGER;

ALTER TABLE "transaction" ADD COLUMN is_manual_category BOOLEAN DEFAULT FALSE;

ALTER TABLE "accounts" ADD COLUMN is_investment BOOLEAN DEFAULT FALSE;