CREATE TABLE IF NOT EXISTS "account_balance_history" (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES "accounts"(id) ON DELETE CASCADE,
    change_date TIMESTAMPTZ NOT NULL,
    previous_balance BIGINT NOT NULL,
    change_amount BIGINT NOT NULL,
    new_balance BIGINT NOT NULL,
    reason TEXT
);
ALTER TABLE "transfer_rule"
ADD COLUMN IF NOT EXISTS linked_account_id INTEGER REFERENCES "accounts"(id);
ALTER TABLE "transaction"
ADD COLUMN IF NOT EXISTS is_manual_category BOOLEAN DEFAULT FALSE;
ALTER TABLE "accounts"
ADD COLUMN IF NOT EXISTS is_investment BOOLEAN DEFAULT FALSE;