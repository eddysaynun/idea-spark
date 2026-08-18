ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'active'
    CHECK(status IN ('active', 'deletion_pending', 'deletion_finalizing', 'deleted'));
ALTER TABLE users ADD COLUMN deletion_requested_at TEXT;
ALTER TABLE users ADD COLUMN deletion_due_at TEXT;
ALTER TABLE users ADD COLUMN deleted_at TEXT;

CREATE INDEX IF NOT EXISTS idx_users_deletion_due
ON users(status, deletion_due_at);

CREATE TABLE IF NOT EXISTS account_deletion_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    action TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_account_deletion_events_user_created
ON account_deletion_events(user_id, created_at DESC);

ALTER TABLE payment_orders ADD COLUMN refund_state TEXT NOT NULL DEFAULT 'none'
    CHECK(refund_state IN ('none', 'pending', 'refunded'));
ALTER TABLE payment_orders ADD COLUMN refund_request_id TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS product_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    project_id TEXT NOT NULL,
    idea_index INTEGER,
    action TEXT NOT NULL CHECK(action IN ('expand', 'detail', 'export', 'delete', 'no_value')),
    idempotency_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_product_events_user_created
ON product_events(user_id, created_at DESC);
