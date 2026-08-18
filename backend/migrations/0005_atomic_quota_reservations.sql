CREATE TABLE IF NOT EXISTS quota_reservations (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reservation_key TEXT NOT NULL,
    resource TEXT NOT NULL CHECK(resource IN ('idea', 'detail')),
    project_id TEXT NOT NULL DEFAULT '',
    amount INTEGER NOT NULL CHECK(amount > 0),
    outcome TEXT NOT NULL CHECK(outcome IN ('reserved', 'committed', 'refunded')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(user_id, reservation_key, resource)
);

INSERT OR IGNORE INTO quota_reservations(
    user_id, reservation_key, resource, project_id, amount, outcome, created_at, updated_at
)
SELECT
    reserved.user_id,
    reserved.reservation_key,
    reserved.resource,
    COALESCE((
        SELECT final.project_id FROM usage_events final
        WHERE final.user_id = reserved.user_id
          AND final.reservation_key = reserved.reservation_key
          AND final.resource = reserved.resource
          AND final.outcome IN ('committed', 'refunded')
        ORDER BY final.created_at DESC LIMIT 1
    ), reserved.project_id, ''),
    reserved.amount,
    COALESCE((
        SELECT final.outcome FROM usage_events final
        WHERE final.user_id = reserved.user_id
          AND final.reservation_key = reserved.reservation_key
          AND final.resource = reserved.resource
          AND final.outcome IN ('committed', 'refunded')
        ORDER BY final.created_at DESC LIMIT 1
    ), CASE WHEN EXISTS (
        SELECT 1 FROM admin_quota_events repair
        WHERE repair.user_id = reserved.user_id
          AND repair.resource = reserved.resource
          AND repair.action = 'clear_reserved'
          AND repair.created_at >= reserved.created_at
    ) THEN 'refunded' ELSE 'reserved' END),
    reserved.created_at,
    COALESCE((
        SELECT final.created_at FROM usage_events final
        WHERE final.user_id = reserved.user_id
          AND final.reservation_key = reserved.reservation_key
          AND final.resource = reserved.resource
          AND final.outcome IN ('committed', 'refunded')
        ORDER BY final.created_at DESC LIMIT 1
    ), reserved.created_at)
FROM usage_events reserved
WHERE reserved.outcome = 'reserved';

-- Existing counters may have been left between the old two-statement writes.
-- Rebuild them once from the migrated reservation ledger before enabling triggers.
UPDATE users SET
    idea_reserved = COALESCE((
        SELECT SUM(amount) FROM quota_reservations
        WHERE user_id = users.id AND resource = 'idea' AND outcome = 'reserved'
    ), 0),
    detail_reserved = COALESCE((
        SELECT SUM(amount) FROM quota_reservations
        WHERE user_id = users.id AND resource = 'detail' AND outcome = 'reserved'
    ), 0),
    idea_used = COALESCE((
        SELECT SUM(amount) FROM quota_reservations
        WHERE user_id = users.id AND resource = 'idea' AND outcome = 'committed'
    ), 0),
    detail_used = COALESCE((
        SELECT SUM(amount) FROM quota_reservations
        WHERE user_id = users.id AND resource = 'detail' AND outcome = 'committed'
    ), 0);

CREATE TRIGGER IF NOT EXISTS quota_reservations_guard_insert
BEFORE INSERT ON quota_reservations
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM users
        WHERE id = NEW.user_id
          AND CASE NEW.resource
              WHEN 'idea' THEN idea_used + idea_reserved + NEW.amount <= idea_limit
              WHEN 'detail' THEN detail_used + detail_reserved + NEW.amount <= detail_limit
              ELSE 0
          END
    ) THEN RAISE(ABORT, 'quota exceeded') END;
END;

CREATE TRIGGER IF NOT EXISTS quota_reservations_apply_insert
AFTER INSERT ON quota_reservations
BEGIN
    UPDATE users SET
        idea_reserved = idea_reserved + CASE WHEN NEW.resource = 'idea' THEN NEW.amount ELSE 0 END,
        detail_reserved = detail_reserved + CASE WHEN NEW.resource = 'detail' THEN NEW.amount ELSE 0 END,
        updated_at = NEW.updated_at
    WHERE id = NEW.user_id;
END;

CREATE TRIGGER IF NOT EXISTS quota_reservations_guard_settlement
BEFORE UPDATE ON quota_reservations
WHEN OLD.outcome <> NEW.outcome
BEGIN
    SELECT CASE WHEN
        OLD.outcome <> 'reserved'
        OR NEW.outcome NOT IN ('committed', 'refunded')
        OR OLD.user_id <> NEW.user_id
        OR OLD.reservation_key <> NEW.reservation_key
        OR OLD.resource <> NEW.resource
        OR OLD.amount <> NEW.amount
        OR OLD.created_at <> NEW.created_at
    THEN RAISE(ABORT, 'invalid quota transition') END;
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM users
        WHERE id = OLD.user_id
          AND CASE OLD.resource
              WHEN 'idea' THEN idea_reserved >= OLD.amount
              WHEN 'detail' THEN detail_reserved >= OLD.amount
              ELSE 0
          END
    ) THEN RAISE(ABORT, 'quota reservation underflow') END;
END;

CREATE TRIGGER IF NOT EXISTS quota_reservations_apply_settlement
AFTER UPDATE ON quota_reservations
WHEN OLD.outcome = 'reserved' AND NEW.outcome IN ('committed', 'refunded')
BEGIN
    UPDATE users SET
        idea_reserved = idea_reserved - CASE WHEN OLD.resource = 'idea' THEN OLD.amount ELSE 0 END,
        detail_reserved = detail_reserved - CASE WHEN OLD.resource = 'detail' THEN OLD.amount ELSE 0 END,
        idea_used = idea_used + CASE WHEN OLD.resource = 'idea' AND NEW.outcome = 'committed' THEN OLD.amount ELSE 0 END,
        detail_used = detail_used + CASE WHEN OLD.resource = 'detail' AND NEW.outcome = 'committed' THEN OLD.amount ELSE 0 END,
        updated_at = NEW.updated_at
    WHERE id = OLD.user_id;
END;

CREATE INDEX IF NOT EXISTS idx_quota_reservations_user_outcome
ON quota_reservations(user_id, outcome, updated_at DESC);
