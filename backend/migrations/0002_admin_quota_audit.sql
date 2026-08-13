CREATE TABLE IF NOT EXISTS admin_quota_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resource TEXT NOT NULL CHECK(resource IN ('idea', 'detail')),
    action TEXT NOT NULL CHECK(action IN ('adjust_limit', 'clear_reserved')),
    delta INTEGER NOT NULL DEFAULT 0,
    limit_before INTEGER NOT NULL,
    limit_after INTEGER NOT NULL,
    reserved_before INTEGER NOT NULL,
    reserved_after INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_admin_quota_user_created
ON admin_quota_events(user_id, created_at DESC);
