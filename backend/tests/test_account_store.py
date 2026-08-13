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


@pytest.fixture
def store():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(Path("migrations/0001_commercial_accounts.sql").read_text())
    connection.executescript(Path("migrations/0002_admin_quota_audit.sql").read_text())
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
