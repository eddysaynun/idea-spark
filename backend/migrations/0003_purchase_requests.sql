CREATE TABLE IF NOT EXISTS quota_purchase_requests (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    package_id TEXT NOT NULL,
    idea_amount INTEGER NOT NULL,
    detail_amount INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending', 'fulfilled', 'cancelled')),
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_purchase_requests_user_created
ON quota_purchase_requests(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_purchase_requests_status_created
ON quota_purchase_requests(status, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_purchase_requests_one_pending_package
ON quota_purchase_requests(user_id, package_id) WHERE status = 'pending';
