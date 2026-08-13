CREATE TABLE IF NOT EXISTS payment_orders (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    package_id TEXT NOT NULL,
    package_name TEXT NOT NULL,
    idea_amount INTEGER NOT NULL CHECK(idea_amount > 0),
    detail_amount INTEGER NOT NULL CHECK(detail_amount >= 0),
    amount_fen INTEGER NOT NULL CHECK(amount_fen > 0),
    currency TEXT NOT NULL DEFAULT 'CNY' CHECK(currency = 'CNY'),
    channel TEXT NOT NULL CHECK(channel IN ('wechat', 'alipay')),
    status TEXT NOT NULL CHECK(status IN ('pending', 'paid', 'expired', 'cancelled', 'refunded', 'failed')),
    provider_order_id TEXT NOT NULL DEFAULT '',
    provider_trade_id TEXT NOT NULL DEFAULT '',
    pay_url TEXT NOT NULL DEFAULT '',
    failure_reason TEXT NOT NULL DEFAULT '',
    expires_at TEXT NOT NULL,
    paid_at TEXT,
    fulfilled_at TEXT,
    refunded_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_payment_orders_user_created
ON payment_orders(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_payment_orders_status_created
ON payment_orders(status, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_payment_orders_provider_order
ON payment_orders(channel, provider_order_id) WHERE provider_order_id <> '';

CREATE TABLE IF NOT EXISTS payment_events (
    id TEXT PRIMARY KEY,
    event_key TEXT NOT NULL UNIQUE,
    order_id TEXT NOT NULL REFERENCES payment_orders(id) ON DELETE CASCADE,
    channel TEXT NOT NULL CHECK(channel IN ('wechat', 'alipay')),
    event_type TEXT NOT NULL,
    provider_trade_id TEXT NOT NULL DEFAULT '',
    amount_fen INTEGER NOT NULL,
    verified INTEGER NOT NULL CHECK(verified IN (0, 1)),
    payload_digest TEXT NOT NULL,
    processing_status TEXT NOT NULL CHECK(processing_status IN ('processed', 'rejected')),
    rejection_reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_payment_events_order_created
ON payment_events(order_id, created_at DESC);
