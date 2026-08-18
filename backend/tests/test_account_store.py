import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import services.account_store as account_store_module
from services.account_store import AccountStore


class Result:
    def __init__(self, rows=None, changes=0):
        self.results = rows or []
        self.meta = {"changes": changes}


class Statement:
    def __init__(self, database, query):
        self.database = database
        self.query = query
        self.params = ()

    def bind(self, *params):
        self.params = params
        return self

    async def all(self):
        cursor = self.database.connection.execute(self.query, self.params)
        return Result([dict(row) for row in cursor.fetchall()])

    async def run(self):
        cursor = self.database.connection.execute(self.query, self.params)
        self.database.connection.commit()
        return Result(changes=cursor.rowcount if cursor.rowcount > 0 else 0)


class Database:
    def __init__(self, connection):
        self.connection = connection

    def prepare(self, query):
        return Statement(self, query)

    async def batch(self, statements):
        try:
            self.connection.execute("BEGIN")
            results = []
            for statement in statements:
                cursor = self.connection.execute(statement.query, statement.params)
                results.append(Result(changes=cursor.rowcount if cursor.rowcount > 0 else 0))
            self.connection.commit()
            return results
        except Exception:
            self.connection.rollback()
            raise


@pytest.fixture
def store():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(Path("migrations/0001_commercial_accounts.sql").read_text())
    connection.executescript(Path("migrations/0002_admin_quota_audit.sql").read_text())
    connection.executescript(Path("migrations/0003_purchase_requests.sql").read_text())
    connection.executescript(Path("migrations/0004_payment_orders.sql").read_text())
    connection.executescript(Path("migrations/0005_atomic_quota_reservations.sql").read_text())
    connection.executescript(Path("migrations/0006_commercial_hardening.sql").read_text())
    yield AccountStore(Database(connection))
    connection.close()


async def create_user(store, subject):
    return await store.upsert_identity_user("supabase", subject, f"user-{subject}", f"User {subject}", "")


def test_quota_migration_preserves_prior_admin_reservation_repairs():
    connection = sqlite3.connect(":memory:")
    connection.executescript(Path("migrations/0001_commercial_accounts.sql").read_text())
    connection.executescript(Path("migrations/0002_admin_quota_audit.sql").read_text())
    connection.execute(
        "INSERT INTO users(id, provider, provider_subject, login, display_name, created_at, updated_at) "
        "VALUES('user-1', 'github', 'subject', 'user', 'User', '2026-01-01Z', '2026-01-01Z')"
    )
    connection.execute(
        "INSERT INTO usage_events(id, user_id, reservation_key, resource, amount, outcome, created_at) "
        "VALUES('event-1', 'user-1', 'request-1', 'idea', 2, 'reserved', '2026-01-02Z')"
    )
    connection.execute(
        "INSERT INTO admin_quota_events(id, user_id, resource, action, delta, limit_before, limit_after, "
        "reserved_before, reserved_after, reason, created_at) "
        "VALUES('audit-1', 'user-1', 'idea', 'clear_reserved', 0, 5, 5, 2, 0, 'manual repair', '2026-01-03Z')"
    )

    connection.executescript(Path("migrations/0005_atomic_quota_reservations.sql").read_text())

    reservation = connection.execute(
        "SELECT outcome FROM quota_reservations WHERE user_id = 'user-1'"
    ).fetchone()
    user = connection.execute("SELECT idea_reserved FROM users WHERE id = 'user-1'").fetchone()
    assert reservation[0] == "refunded"
    assert user[0] == 0
    connection.close()


async def test_projects_are_strictly_scoped_by_user(store):
    alice = await create_user(store, "alice")
    bob = await create_user(store, "bob")
    project = await store.create_project(alice["id"], "私有方向", 5, "general", "model")

    with pytest.raises(ValueError, match="Project not found"):
        await store.get_project(bob["id"], project["id"])
    assert await store.delete_project(bob["id"], project["id"]) is False
    assert (await store.get_project(alice["id"], project["id"]))["direction"] == "私有方向"


async def test_quota_reservation_is_bounded_and_idempotent(store):
    user = await create_user(store, "quota")

    assert await store.reserve_quota(user["id"], "request-key-0001", "idea", 5) == "reserved"
    assert await store.reserve_quota(user["id"], "request-key-0001", "idea", 5) == "duplicate"
    assert await store.reserve_quota(user["id"], "request-key-0002", "idea", 1) == "denied"
    await store.settle_quota(user["id"], "project", "request-key-0001", "idea", 5, True)

    refreshed = await store._first("SELECT * FROM users WHERE id = ?", user["id"])
    assert refreshed["idea_used"] == 5
    assert refreshed["idea_reserved"] == 0


async def test_quota_reservation_uses_one_atomic_state_row(store):
    user = await create_user(store, "quota-state")

    assert await store.reserve_quota(user["id"], "atomic-request-0001", "idea", 2) == "reserved"
    reservation = await store._first(
        "SELECT outcome, amount FROM quota_reservations WHERE user_id = ? AND reservation_key = ?",
        user["id"], "atomic-request-0001",
    )
    assert reservation == {"outcome": "reserved", "amount": 2}

    await store.settle_quota(user["id"], "project", "atomic-request-0001", "idea", 2, True)
    reservation = await store._first(
        "SELECT outcome, project_id FROM quota_reservations WHERE user_id = ? AND reservation_key = ?",
        user["id"], "atomic-request-0001",
    )
    counters = await store._first(
        "SELECT idea_used, idea_reserved FROM users WHERE id = ?", user["id"]
    )
    assert reservation == {"outcome": "committed", "project_id": "project"}
    assert counters == {"idea_used": 2, "idea_reserved": 0}


async def test_failed_detail_reservation_is_refunded(store):
    user = await create_user(store, "refund")

    assert await store.reserve_quota(user["id"], "detail-key-0001", "detail", 1) == "reserved"
    await store.settle_quota(user["id"], "project", "detail-key-0001", "detail", 1, False)

    refreshed = await store._first("SELECT * FROM users WHERE id = ?", user["id"])
    assert refreshed["detail_used"] == 0
    assert refreshed["detail_reserved"] == 0


async def test_session_tokens_are_stored_as_hashes(store):
    user = await create_user(store, "session")
    token = await store.create_session(user["id"])

    row = await store._first("SELECT token_hash FROM user_sessions WHERE user_id = ?", user["id"])
    assert token not in row["token_hash"]
    assert await store.get_user_by_session(token)
    assert await store.get_user_by_session("wrong-token") is None


async def test_account_deletion_invalidates_sessions_and_can_be_restored_within_seven_days(store, monkeypatch):
    now = datetime(2026, 8, 18, 8, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(account_store_module, "utc_now", lambda: now)
    user = await create_user(store, "deletion-restore")
    token = await store.create_session(user["id"])

    pending = await store.request_account_deletion(user["id"])

    assert pending["status"] == "deletion_pending"
    assert pending["deletion_due_at"] == "2026-08-25T08:00:00Z"
    assert await store.get_user_by_session(token) is None
    restored = await store.restore_account("supabase", "deletion-restore")
    assert restored["status"] == "active"
    assert restored["deletion_due_at"] is None


async def test_due_account_deletion_retries_identity_failure_then_anonymizes_business_data(store, monkeypatch):
    now = datetime(2026, 8, 18, 8, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(account_store_module, "utc_now", lambda: now)
    user = await create_user(store, "deletion-due")
    project = await store.create_project(user["id"], "待删除方向", 1, "general", "model")
    await store.complete_project(user["id"], project["id"], [{"name": "private idea"}])
    package = {"id": "starter", "name": "Starter", "idea_amount": 20, "detail_amount": 5, "amount_fen": 2900}
    order = await store.create_payment_order(user["id"], package, "alipay")
    await store.request_account_deletion(user["id"])
    monkeypatch.setattr(account_store_module, "utc_now", lambda: now + timedelta(days=8))

    async def unavailable(_subject):
        raise RuntimeError("supabase unavailable")

    first = await store.process_due_deletions(unavailable)
    assert first == {"processed": 0, "failed": 1}
    assert (await store._first("SELECT status FROM users WHERE id = ?", user["id"]))["status"] == "deletion_finalizing"

    subjects = []
    async def available(subject):
        subjects.append(subject)

    second = await store.process_due_deletions(available)
    assert second == {"processed": 1, "failed": 0}
    assert subjects == ["deletion-due"]
    deleted = await store._first("SELECT * FROM users WHERE id = ?", user["id"])
    assert deleted["status"] == "deleted"
    assert deleted["login"].endswith("@deleted.invalid")
    assert await store._first("SELECT id FROM projects WHERE id = ?", project["id"]) is None
    assert await store._first("SELECT id FROM payment_orders WHERE id = ?", order["id"])


async def test_account_export_contains_only_owned_projects_and_safe_payment_fields(store):
    alice = await create_user(store, "export-alice")
    bob = await create_user(store, "export-bob")
    alice_project = await store.create_project(alice["id"], "Alice 私有方向", 1, "general", "model")
    bob_project = await store.create_project(bob["id"], "Bob 私有方向", 1, "general", "model")
    await store.complete_project(alice["id"], alice_project["id"], [{"name": "Alice Idea"}])
    await store.complete_project(bob["id"], bob_project["id"], [{"name": "Bob Idea"}])

    exported = await store.export_account(alice["id"])

    assert exported["profile"]["login"] == "user-export-alice"
    assert [project["direction"] for project in exported["projects"]] == ["Alice 私有方向"]
    assert "provider_subject" not in exported["profile"]


async def test_account_export_is_not_truncated_by_history_page_limit(store):
    user = await create_user(store, "export-all")
    for index in range(101):
        await store.create_project(user["id"], f"方向 {index}", 1, "general", "model")

    exported = await store.export_account(user["id"])

    assert len(exported["projects"]) == 101


async def test_admin_quota_adjustment_is_bounded_and_audited(store):
    user = await create_user(store, "admin-quota")

    updated = await store.adjust_quota(user["id"], "idea", 95, "管理员测试账号扩容")
    assert updated["idea_limit"] == 100
    event = (await store.quota_audit(user["id"]))[0]
    assert event["limit_before"] == 5
    assert event["limit_after"] == 100
    assert event["reason"] == "管理员测试账号扩容"

    await store.reserve_quota(user["id"], "admin-reservation", "idea", 10)
    with pytest.raises(ValueError, match="used plus reserved"):
        await store.adjust_quota(user["id"], "idea", -100, "不可低于已消费和预占")


async def test_admin_quota_adjustment_rolls_back_when_audit_fails(store):
    user = await create_user(store, "admin-atomic")
    store.db.connection.execute(
        "CREATE TRIGGER reject_admin_audit BEFORE INSERT ON admin_quota_events "
        "BEGIN SELECT RAISE(ABORT, 'audit failed'); END"
    )

    with pytest.raises(sqlite3.IntegrityError, match="audit failed"):
        await store.adjust_quota(user["id"], "idea", 10, "验证管理员操作原子性")

    refreshed = await store._first("SELECT idea_limit FROM users WHERE id = ?", user["id"])
    assert refreshed["idea_limit"] == 5


async def test_admin_can_clear_stuck_reservation_with_audit(store):
    user = await create_user(store, "repair")
    assert await store.reserve_quota(user["id"], "stuck-request", "detail", 1) == "reserved"

    repaired = await store.clear_reserved_quota(user["id"], "detail", "任务中断，确认模型未调用")
    assert repaired["detail_reserved"] == 0
    event = (await store.quota_audit(user["id"]))[0]
    assert event["action"] == "clear_reserved"
    assert event["reserved_before"] == 1


async def test_payment_order_is_owned_and_snapshots_server_package(store):
    alice = await create_user(store, "payment-alice")
    bob = await create_user(store, "payment-bob")
    package = {"id": "starter", "name": "Starter", "idea_amount": 20, "detail_amount": 5, "amount_fen": 2900}

    order = await store.create_payment_order(alice["id"], package, "wechat")
    assert order["amount_fen"] == 2900
    assert order["idea_amount"] == 20
    with pytest.raises(ValueError, match="Payment order not found"):
        await store.get_payment_order(bob["id"], order["id"])


async def test_verified_payment_fulfills_quota_once(store):
    user = await create_user(store, "payment-paid")
    package = {"id": "builder", "name": "Builder", "idea_amount": 60, "detail_amount": 20, "amount_fen": 7900}
    order = await store.create_payment_order(user["id"], package, "alipay")
    await store.attach_payment_checkout(user["id"], order["id"], "provider-order-1", "https://pay.example.test/1")

    first = await store.fulfill_payment(
        order["id"], "alipay", "event-1", "TRADE_SUCCESS", "trade-1", 7900, "digest", True
    )
    duplicate = await store.fulfill_payment(
        order["id"], "alipay", "event-1", "TRADE_SUCCESS", "trade-1", 7900, "digest", True
    )
    refreshed = await store._first("SELECT idea_limit, detail_limit FROM users WHERE id = ?", user["id"])
    assert first["status"] == "fulfilled"
    assert duplicate["status"] == "duplicate"
    assert refreshed == {"idea_limit": 65, "detail_limit": 22}


async def test_verified_delayed_notification_fulfills_expired_order(store):
    user = await create_user(store, "payment-delayed")
    package = {"id": "starter", "name": "Starter", "idea_amount": 20, "detail_amount": 5, "amount_fen": 2900}
    order = await store.create_payment_order(user["id"], package, "alipay", expires_minutes=-1)
    assert (await store.get_payment_order(user["id"], order["id"]))["status"] == "expired"

    result = await store.fulfill_payment(
        order["id"], "alipay", "event-delayed", "TRADE_SUCCESS", "trade-delayed", 2900, "digest", True
    )

    assert result["status"] == "fulfilled"
    refreshed = await store._first("SELECT idea_limit, detail_limit FROM users WHERE id = ?", user["id"])
    assert refreshed == {"idea_limit": 25, "detail_limit": 7}


async def test_full_refund_rejects_consumed_quota_and_reuses_one_request_id(store):
    user = await create_user(store, "refund-guard")
    package = {"id": "starter", "name": "Starter", "idea_amount": 20, "detail_amount": 5, "amount_fen": 2900}
    order = await store.create_payment_order(user["id"], package, "alipay")
    await store.attach_payment_checkout(user["id"], order["id"], "ISrefundguard", "https://pay.example.test")
    await store.fulfill_payment(order["id"], "alipay", "paid-refund-guard", "TRADE_SUCCESS", "trade", 2900, "digest", True)
    await store._run("UPDATE users SET idea_used = 6 WHERE id = ?", user["id"])

    with pytest.raises(ValueError, match="Purchased quota has already been used"):
        await store.prepare_payment_refund(order["id"])


async def test_refund_local_reconciliation_is_retryable_and_deducts_quota_once(store):
    user = await create_user(store, "refund-reconcile")
    package = {"id": "starter", "name": "Starter", "idea_amount": 20, "detail_amount": 5, "amount_fen": 2900}
    order = await store.create_payment_order(user["id"], package, "alipay")
    await store.attach_payment_checkout(user["id"], order["id"], "ISrefundretry", "https://pay.example.test")
    await store.fulfill_payment(order["id"], "alipay", "paid-refund-retry", "TRADE_SUCCESS", "trade", 2900, "digest", True)

    prepared = await store.prepare_payment_refund(order["id"])
    assert prepared["refund_request_id"].startswith("RF")
    assert (await store.prepare_payment_refund(order["id"]))["refund_request_id"] == prepared["refund_request_id"]
    store.db.connection.execute(
        "CREATE TRIGGER reject_refund_event BEFORE INSERT ON payment_events "
        "WHEN NEW.event_type = 'REFUND' BEGIN SELECT RAISE(ABORT, 'refund audit failed'); END"
    )
    with pytest.raises(sqlite3.IntegrityError, match="refund audit failed"):
        await store.complete_payment_refund(order["id"], prepared["refund_request_id"], "trade")
    unchanged = await store._first("SELECT idea_limit, refund_state FROM users JOIN payment_orders ON payment_orders.user_id = users.id WHERE payment_orders.id = ?", order["id"])
    assert unchanged == {"idea_limit": 25, "refund_state": "pending"}

    store.db.connection.execute("DROP TRIGGER reject_refund_event")
    first = await store.complete_payment_refund(order["id"], prepared["refund_request_id"], "trade")
    duplicate = await store.complete_payment_refund(order["id"], prepared["refund_request_id"], "trade")
    assert first["status"] == "refunded"
    assert duplicate["status"] == "duplicate"
    limits = await store._first("SELECT idea_limit, detail_limit FROM users WHERE id = ?", user["id"])
    assert limits == {"idea_limit": 5, "detail_limit": 2}


async def test_payment_order_list_marks_abandoned_orders_expired(store):
    user = await create_user(store, "payment-list-expired")
    package = {"id": "starter", "name": "Starter", "idea_amount": 20, "detail_amount": 5, "amount_fen": 2900}
    order = await store.create_payment_order(user["id"], package, "alipay")
    await store._run(
        "UPDATE payment_orders SET expires_at = '2000-01-01T00:00:00Z' WHERE id = ?",
        order["id"],
    )

    orders = await store.list_payment_orders(user["id"])

    assert orders[0]["status"] == "expired"


async def test_provider_order_resolves_internal_order_without_user_input(store):
    user = await create_user(store, "provider-order")
    package = {"id": "starter", "name": "Starter", "idea_amount": 20, "detail_amount": 5, "amount_fen": 2900}
    order = await store.create_payment_order(user["id"], package, "alipay")
    await store.attach_payment_checkout(user["id"], order["id"], "IS-provider-order", "https://qr.alipay.com/order")

    assert await store.payment_order_id_for_provider("alipay", "IS-provider-order") == order["id"]
    with pytest.raises(ValueError, match="Payment order not found"):
        await store.payment_order_id_for_provider("wechat", "IS-provider-order")


@pytest.mark.parametrize("channel,amount", [("wechat", 7900), ("alipay", 7800)])
async def test_payment_rejects_wrong_channel_or_amount(store, channel, amount):
    user = await create_user(store, f"mismatch-{channel}-{amount}")
    package = {"id": "builder", "name": "Builder", "idea_amount": 60, "detail_amount": 20, "amount_fen": 7900}
    order = await store.create_payment_order(user["id"], package, "alipay")
    with pytest.raises(ValueError, match="channel or amount mismatch"):
        await store.fulfill_payment(order["id"], channel, f"event-{channel}-{amount}", "paid", "trade", amount, "digest", True)
    refreshed = await store._first("SELECT idea_limit FROM users WHERE id = ?", user["id"])
    assert refreshed["idea_limit"] == 5


async def test_user_cannot_save_plan_to_another_users_project(store):
    alice = await create_user(store, "plan-alice")
    bob = await create_user(store, "plan-bob")
    project = await store.create_project(alice["id"], "私有项目", 1, "general", "model")

    with pytest.raises(ValueError, match="Project not found"):
        await store.save_plan(bob["id"], project["id"], 0, "stolen")


async def test_product_events_are_whitelisted_owned_and_idempotent(store):
    alice = await create_user(store, "event-alice")
    bob = await create_user(store, "event-bob")
    project = await store.create_project(alice["id"], "反馈项目", 1, "general", "model")
    await store.complete_project(alice["id"], project["id"], [{"name": "Idea"}])

    first = await store.record_product_event(alice["id"], project["id"], 0, "no_value", "event-key-0000001")
    duplicate = await store.record_product_event(alice["id"], project["id"], 0, "no_value", "event-key-0000001")

    assert first == "recorded"
    assert duplicate == "duplicate"
    with pytest.raises(ValueError, match="Project not found"):
        await store.record_product_event(bob["id"], project["id"], 0, "expand", "event-key-0000002")
    with pytest.raises(ValueError, match="Invalid product event"):
        await store.record_product_event(alice["id"], project["id"], 0, "free_text", "event-key-0000003")


async def test_admin_metrics_aggregate_only_business_counts(store, monkeypatch):
    now = datetime(2026, 8, 18, 8, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(account_store_module, "utc_now", lambda: now)
    user = await create_user(store, "metrics")
    project = await store.create_project(user["id"], "指标项目", 2, "general", "model")
    await store.complete_project(user["id"], project["id"], [{"name": "A"}, {"name": "B"}])
    await store.save_plan(user["id"], project["id"], 0, "plan")
    await store.record_product_event(user["id"], project["id"], 0, "detail", "metrics-detail-0001")
    await store.record_product_event(user["id"], project["id"], 1, "no_value", "metrics-no-value-01")
    package = {"id": "starter", "name": "Starter", "idea_amount": 20, "detail_amount": 5, "amount_fen": 2900}
    order = await store.create_payment_order(user["id"], package, "alipay")
    await store.attach_payment_checkout(user["id"], order["id"], "ISmetrics", "https://pay.example.test")
    await store.fulfill_payment(order["id"], "alipay", "metrics-paid", "TRADE_SUCCESS", "trade", 2900, "digest", True)

    metrics = await store.admin_metrics(30)

    assert metrics["users"] == {"total": 1, "new": 1, "active": 1}
    assert metrics["generation"] == {"complete": 1, "failed": 0, "details": 1, "no_value": 1}
    assert metrics["payments"] == {"paid": 1, "refunded": 0, "revenue_fen": 2900}
    assert metrics["quota"]["stuck_reservations"] == 0


async def test_reconciliation_candidates_are_bounded_to_expired_payments_and_pending_refunds(store):
    user = await create_user(store, "reconciliation")
    package = {"id": "starter", "name": "Starter", "idea_amount": 20, "detail_amount": 5, "amount_fen": 2900}
    active = await store.create_payment_order(user["id"], package, "alipay")
    expired = await store.create_payment_order(user["id"], package, "alipay")
    refunded = await store.create_payment_order(user["id"], package, "alipay")
    await store.attach_payment_checkout(user["id"], active["id"], "ISactive", "https://pay.example.test")
    await store.attach_payment_checkout(user["id"], expired["id"], "ISexpired", "https://pay.example.test")
    await store.attach_payment_checkout(user["id"], refunded["id"], "ISrefund", "https://pay.example.test")
    await store._run("UPDATE payment_orders SET expires_at = '2000-01-01T00:00:00Z' WHERE id = ?", expired["id"])
    await store.fulfill_payment(refunded["id"], "alipay", "paid-for-refund", "TRADE_SUCCESS", "trade", 2900, "digest", True)
    await store.prepare_payment_refund(refunded["id"])

    candidates = await store.payment_reconciliation_candidates(20)

    assert {item["id"] for item in candidates} == {expired["id"], refunded["id"]}
    assert active["id"] not in {item["id"] for item in candidates}
