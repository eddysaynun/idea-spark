import sqlite3
from pathlib import Path

import pytest

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
    yield AccountStore(Database(connection))
    connection.close()


async def create_user(store, subject):
    return await store.upsert_github_user(subject, f"user-{subject}", f"User {subject}", "")


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


async def test_admin_can_clear_stuck_reservation_with_audit(store):
    user = await create_user(store, "repair")
    assert await store.reserve_quota(user["id"], "stuck-request", "detail", 1) == "reserved"

    repaired = await store.clear_reserved_quota(user["id"], "detail", "任务中断，确认模型未调用")
    assert repaired["detail_reserved"] == 0
    event = (await store.quota_audit(user["id"]))[0]
    assert event["action"] == "clear_reserved"
    assert event["reserved_before"] == 1


async def test_purchase_request_is_user_scoped_and_pending_idempotent(store):
    alice = await create_user(store, "purchase-alice")
    bob = await create_user(store, "purchase-bob")

    first = await store.create_purchase_request(alice["id"], "starter", 20, 5)
    duplicate = await store.create_purchase_request(alice["id"], "starter", 20, 5)
    await store.create_purchase_request(bob["id"], "builder", 60, 20)

    assert first["id"] == duplicate["id"]
    assert [item["id"] for item in await store.list_purchase_requests(alice["id"])] == [first["id"]]
    pending = await store.admin_purchase_requests("pending")
    assert {item["user_id"] for item in pending} == {alice["id"], bob["id"]}


async def test_only_pending_purchase_request_can_change_status(store):
    user = await create_user(store, "purchase-status")
    purchase = await store.create_purchase_request(user["id"], "starter", 20, 5)

    fulfilled = await store.update_purchase_request(purchase["id"], "fulfilled")
    assert fulfilled["status"] == "fulfilled"
    with pytest.raises(ValueError, match="Pending purchase request not found"):
        await store.update_purchase_request(purchase["id"], "cancelled")


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


@pytest.mark.parametrize("return_to", ["//evil.example", "/\\evil.example", "https://evil.example"])
async def test_oauth_state_rejects_open_redirect_targets(store, return_to):
    state = await store.create_oauth_state(return_to)

    assert await store.consume_oauth_state(state) == "/"
    assert await store.consume_oauth_state(state) is None


async def test_user_cannot_save_plan_to_another_users_project(store):
    alice = await create_user(store, "plan-alice")
    bob = await create_user(store, "plan-bob")
    project = await store.create_project(alice["id"], "私有项目", 1, "general", "model")

    with pytest.raises(ValueError, match="Project not found"):
        await store.save_plan(bob["id"], project["id"], 0, "stolen")


async def test_legacy_imports_are_idempotent_and_bounded(store):
    user = await create_user(store, "imports")
    payload = {
        "direction": "旧记录",
        "count": 1,
        "category": "general",
        "model": "model",
        "ideas": [{"name": "Idea"}],
        "detailed_plans": {},
    }
    first = None
    for index in range(5):
        payload["idempotency_key"] = f"legacy-import-key-{index:04d}"
        project = await store.import_project(user["id"], payload)
        first = first or project

    payload["idempotency_key"] = "legacy-import-key-0000"
    assert (await store.import_project(user["id"], payload))["id"] == first["id"]
    payload["idempotency_key"] = "legacy-import-key-overflow"
    with pytest.raises(ValueError, match="最多可导入 5 条"):
        await store.import_project(user["id"], payload)
