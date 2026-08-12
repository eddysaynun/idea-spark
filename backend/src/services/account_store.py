"""D1-backed accounts, sessions, projects and usage audit storage."""

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _rows(result: Any) -> List[Dict[str, Any]]:
    rows = getattr(result, "results", None)
    if rows is None and isinstance(result, dict):
        rows = result.get("results")
    return [dict(row) for row in (rows or [])]


class AccountStore:
    """All private object access is scoped by the authenticated user id."""

    def __init__(self, database, idea_limit: int = 5, detail_limit: int = 2):
        if database is None:
            raise RuntimeError("D1 binding is required for commercial mode")
        self.db = database
        self.idea_limit = idea_limit
        self.detail_limit = detail_limit

    async def _all(self, query: str, *params) -> List[Dict[str, Any]]:
        result = await self.db.prepare(query).bind(*params).all()
        return _rows(result)

    async def _first(self, query: str, *params) -> Optional[Dict[str, Any]]:
        rows = await self._all(query, *params)
        return rows[0] if rows else None

    async def _run(self, query: str, *params):
        return await self.db.prepare(query).bind(*params).run()

    async def create_oauth_state(self, return_to: str = "/") -> str:
        state = secrets.token_urlsafe(32)
        now = utc_now()
        safe_return_to = (
            return_to
            if return_to.startswith("/") and not return_to.startswith("//") and "\\" not in return_to
            else "/"
        )
        await self._run(
            "INSERT INTO oauth_states(state_hash, return_to, expires_at, created_at) VALUES(?, ?, ?, ?)",
            token_hash(state), safe_return_to, iso(now + timedelta(minutes=10)), iso(now),
        )
        return state

    async def consume_oauth_state(self, state: str) -> Optional[str]:
        hashed = token_hash(state)
        now = iso(utc_now())
        row = await self._first(
            "SELECT return_to FROM oauth_states WHERE state_hash = ? AND expires_at > ?",
            hashed, now,
        )
        await self._run("DELETE FROM oauth_states WHERE state_hash = ?", hashed)
        return row["return_to"] if row else None

    async def upsert_github_user(self, subject: str, login: str, display_name: str, avatar_url: str) -> Dict[str, Any]:
        existing = await self._first(
            "SELECT * FROM users WHERE provider = 'github' AND provider_subject = ?", subject
        )
        now = iso(utc_now())
        if existing:
            await self._run(
                "UPDATE users SET login = ?, display_name = ?, avatar_url = ?, updated_at = ? WHERE id = ?",
                login, display_name, avatar_url, now, existing["id"],
            )
            existing.update(login=login, display_name=display_name, avatar_url=avatar_url, updated_at=now)
            return existing
        user_id = str(uuid.uuid4())
        await self._run(
            "INSERT INTO users(id, provider, provider_subject, login, display_name, avatar_url, idea_limit, detail_limit, created_at, updated_at) VALUES(?, 'github', ?, ?, ?, ?, ?, ?, ?, ?)",
            user_id, subject, login, display_name, avatar_url, self.idea_limit, self.detail_limit, now, now,
        )
        return {"id": user_id, "provider": "github", "login": login, "display_name": display_name, "avatar_url": avatar_url}

    async def create_session(self, user_id: str, days: int = 30) -> str:
        token = secrets.token_urlsafe(48)
        now = utc_now()
        await self._run(
            "INSERT INTO user_sessions(token_hash, user_id, expires_at, created_at) VALUES(?, ?, ?, ?)",
            token_hash(token), user_id, iso(now + timedelta(days=days)), iso(now),
        )
        return token

    async def get_user_by_session(self, token: str) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        return await self._first(
            "SELECT u.id, u.login, u.display_name, u.avatar_url, u.idea_limit, u.idea_used, u.idea_reserved, u.detail_limit, u.detail_used, u.detail_reserved FROM user_sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.expires_at > ?",
            token_hash(token), iso(utc_now()),
        )

    async def delete_expired_auth_records(self) -> None:
        """Bound authentication-table growth during normal login traffic."""
        now = iso(utc_now())
        await self._run("DELETE FROM oauth_states WHERE expires_at <= ?", now)
        await self._run("DELETE FROM user_sessions WHERE expires_at <= ?", now)

    async def delete_session(self, token: str) -> None:
        if token:
            await self._run("DELETE FROM user_sessions WHERE token_hash = ?", token_hash(token))

    async def create_project(self, user_id: str, direction: str, count: int, category: str, model: str) -> Dict[str, Any]:
        project_id = str(uuid.uuid4())
        now = iso(utc_now())
        await self._run(
            "INSERT INTO projects(id, user_id, direction, category, requested_count, model, status, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, 'running', ?, ?)",
            project_id, user_id, direction, category, count, model, now, now,
        )
        return {"id": project_id, "direction": direction, "count": count, "category": category, "model": model, "status": "running", "ideas": [], "detailed_plans": {}, "created_at": now, "updated_at": now}

    async def complete_project(self, user_id: str, project_id: str, ideas: List[Dict[str, Any]]) -> None:
        result = await self._run(
            "UPDATE projects SET ideas_json = ?, status = 'complete', updated_at = ? WHERE id = ? AND user_id = ?",
            json.dumps(ideas, ensure_ascii=False), iso(utc_now()), project_id, user_id,
        )
        if not self._changed(result):
            raise ValueError("Project not found")

    async def fail_project(self, user_id: str, project_id: str) -> None:
        await self._run(
            "UPDATE projects SET status = 'failed', updated_at = ? WHERE id = ? AND user_id = ?",
            iso(utc_now()), project_id, user_id,
        )

    async def list_projects(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        rows = await self._all(
            "SELECT id, direction, category, requested_count AS count, model, status, created_at, updated_at FROM projects WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
            user_id, min(max(limit, 1), 100),
        )
        return rows

    async def get_project(self, user_id: str, project_id: str) -> Dict[str, Any]:
        project = await self._first(
            "SELECT id, direction, category, requested_count AS count, model, status, ideas_json, created_at, updated_at FROM projects WHERE id = ? AND user_id = ?",
            project_id, user_id,
        )
        if not project:
            raise ValueError("Project not found")
        plans = await self._all(
            "SELECT idea_index, content_markdown FROM detailed_plans WHERE project_id = ? AND user_id = ?",
            project_id, user_id,
        )
        project["ideas"] = json.loads(project.pop("ideas_json") or "[]")
        project["detailed_plans"] = {str(row["idea_index"]): row["content_markdown"] for row in plans}
        return project

    async def delete_project(self, user_id: str, project_id: str) -> bool:
        result = await self._run("DELETE FROM projects WHERE id = ? AND user_id = ?", project_id, user_id)
        return self._changed(result)

    async def save_plan(self, user_id: str, project_id: str, idea_index: int, content: str) -> None:
        owned = await self._first("SELECT id FROM projects WHERE id = ? AND user_id = ?", project_id, user_id)
        if not owned:
            raise ValueError("Project not found")
        now = iso(utc_now())
        await self._run(
            "INSERT INTO detailed_plans(id, user_id, project_id, idea_index, content_markdown, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?) ON CONFLICT(project_id, idea_index) DO UPDATE SET content_markdown = excluded.content_markdown, updated_at = excluded.updated_at WHERE user_id = excluded.user_id",
            str(uuid.uuid4()), user_id, project_id, idea_index, content, now, now,
        )

    async def import_project(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        prior = await self._first(
            "SELECT project_id FROM imports WHERE user_id = ? AND idempotency_key = ?",
            user_id, payload["idempotency_key"],
        )
        if prior:
            return await self.get_project(user_id, prior["project_id"])
        imported = await self._first(
            "SELECT COUNT(*) AS count FROM imports WHERE user_id = ?", user_id
        )
        if imported and imported["count"] >= 5:
            raise ValueError("最多可导入 5 条旧版本地记录")
        project = await self.create_project(
            user_id, payload["direction"], payload["count"], payload["category"], payload["model"]
        )
        await self.complete_project(user_id, project["id"], payload["ideas"])
        for key, content in payload.get("detailed_plans", {}).items():
            try:
                index = int(key)
            except ValueError:
                continue
            if 0 <= index < len(payload["ideas"]) and isinstance(content, str) and content.strip():
                await self.save_plan(user_id, project["id"], index, content[:100000])
        await self._run(
            "INSERT INTO imports(user_id, idempotency_key, project_id, created_at) VALUES(?, ?, ?, ?)",
            user_id, payload["idempotency_key"], project["id"], iso(utc_now()),
        )
        return await self.get_project(user_id, project["id"])

    async def record_usage(self, user_id: str, project_id: str, reservation_key: str, resource: str, amount: int, outcome: str) -> None:
        await self._run(
            "INSERT OR IGNORE INTO usage_events(id, user_id, project_id, reservation_key, resource, amount, outcome, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
            str(uuid.uuid4()), user_id, project_id, reservation_key, resource, amount, outcome, iso(utc_now()),
        )

    async def reserve_quota(self, user_id: str, reservation_key: str, resource: str, amount: int) -> str:
        if resource not in {"idea", "detail"} or amount < 1:
            raise ValueError("Invalid quota reservation")
        prior = await self._first(
            "SELECT outcome FROM usage_events WHERE user_id = ? AND reservation_key = ? AND resource = ? ORDER BY created_at DESC LIMIT 1",
            user_id, reservation_key, resource,
        )
        if prior:
            return "duplicate"
        inserted = await self._run(
            "INSERT OR IGNORE INTO usage_events(id, user_id, project_id, reservation_key, resource, amount, outcome, created_at) VALUES(?, ?, '', ?, ?, ?, 'reserved', ?)",
            str(uuid.uuid4()), user_id, reservation_key, resource, amount, iso(utc_now()),
        )
        if not self._changed(inserted):
            prior = await self._first(
                "SELECT outcome FROM usage_events WHERE user_id = ? AND reservation_key = ? AND resource = ? ORDER BY created_at DESC LIMIT 1",
                user_id, reservation_key, resource,
            )
            return "duplicate" if prior else "denied"
        result = await self._run(
            f"UPDATE users SET {resource}_reserved = {resource}_reserved + ? WHERE id = ? AND {resource}_used + {resource}_reserved + ? <= {resource}_limit",
            amount, user_id, amount,
        )
        if not self._changed(result):
            await self.record_usage(user_id, "", reservation_key, resource, amount, "refunded")
            return "denied"
        return "reserved"

    async def settle_quota(self, user_id: str, project_id: str, reservation_key: str, resource: str, amount: int, success: bool) -> None:
        outcome = "committed" if success else "refunded"
        inserted = await self._run(
            "INSERT OR IGNORE INTO usage_events(id, user_id, project_id, reservation_key, resource, amount, outcome, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
            str(uuid.uuid4()), user_id, project_id, reservation_key, resource, amount, outcome, iso(utc_now()),
        )
        if not self._changed(inserted):
            return
        used_delta = amount if success else 0
        await self._run(
            f"UPDATE users SET {resource}_reserved = MAX(0, {resource}_reserved - ?), {resource}_used = {resource}_used + ? WHERE id = ?",
            amount, used_delta, user_id,
        )

    @staticmethod
    def public_user(user: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": user["id"],
            "login": user["login"],
            "display_name": user["display_name"],
            "avatar_url": user.get("avatar_url", ""),
            "quota": {
                "idea": {
                    "limit": user.get("idea_limit", 5),
                    "used": user.get("idea_used", 0),
                    "reserved": user.get("idea_reserved", 0),
                },
                "detail": {
                    "limit": user.get("detail_limit", 2),
                    "used": user.get("detail_used", 0),
                    "reserved": user.get("detail_reserved", 0),
                },
            },
        }

    @staticmethod
    def _changed(result: Any) -> bool:
        meta = getattr(result, "meta", None)
        if meta is None and isinstance(result, dict):
            meta = result.get("meta", {})
        changes = getattr(meta, "changes", None) if meta is not None else None
        if changes is None and isinstance(meta, dict):
            changes = meta.get("changes")
        return bool(changes)
