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

    async def _batch(self, statements):
        batch = getattr(self.db, "batch", None)
        if batch is None:
            raise RuntimeError("Atomic D1 batch support is required")
        return await batch(statements)

    async def upsert_identity_user(
        self, provider: str, subject: str, login: str, display_name: str, avatar_url: str
    ) -> Dict[str, Any]:
        """Map one verified identity-provider user to one commercial account."""
        if not provider or not subject:
            raise ValueError("Identity provider and subject are required")
        existing = await self._first(
            "SELECT * FROM users WHERE provider = ? AND provider_subject = ?", provider, subject
        )
        now = iso(utc_now())
        if existing:
            if existing.get("status", "active") != "active":
                return existing
            await self._run(
                "UPDATE users SET login = ?, display_name = ?, avatar_url = ?, updated_at = ? WHERE id = ?",
                login, display_name, avatar_url, now, existing["id"],
            )
            existing.update(login=login, display_name=display_name, avatar_url=avatar_url, updated_at=now)
            return existing
        user_id = str(uuid.uuid4())
        await self._run(
            "INSERT INTO users(id, provider, provider_subject, login, display_name, avatar_url, idea_limit, detail_limit, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            user_id, provider, subject, login, display_name, avatar_url, self.idea_limit, self.detail_limit, now, now,
        )
        return {"id": user_id, "provider": provider, "login": login, "display_name": display_name, "avatar_url": avatar_url}

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
            "SELECT u.id, u.login, u.display_name, u.avatar_url, u.idea_limit, u.idea_used, u.idea_reserved, "
            "u.detail_limit, u.detail_used, u.detail_reserved, u.status, u.deletion_due_at "
            "FROM user_sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = ? AND s.expires_at > ? AND u.status = 'active'",
            token_hash(token), iso(utc_now()),
        )

    async def delete_session(self, token: str) -> None:
        if token:
            await self._run("DELETE FROM user_sessions WHERE token_hash = ?", token_hash(token))

    async def request_account_deletion(self, user_id: str) -> Dict[str, Any]:
        user = await self._first("SELECT * FROM users WHERE id = ?", user_id)
        if not user:
            raise ValueError("User not found")
        if user.get("status") == "deletion_pending":
            return user
        if user.get("status", "active") != "active":
            raise ValueError("Account cannot be deleted from its current state")
        now = utc_now()
        requested_at = iso(now)
        due_at = iso(now + timedelta(days=7))
        await self._batch([
            self.db.prepare(
                "UPDATE users SET status = 'deletion_pending', deletion_requested_at = ?, "
                "deletion_due_at = ?, updated_at = ? WHERE id = ? AND status = 'active'"
            ).bind(requested_at, due_at, requested_at, user_id),
            self.db.prepare("DELETE FROM user_sessions WHERE user_id = ?").bind(user_id),
            self.db.prepare(
                "INSERT INTO account_deletion_events(id, user_id, action, created_at) VALUES(?, ?, 'requested', ?)"
            ).bind(str(uuid.uuid4()), user_id, requested_at),
        ])
        return await self._first("SELECT * FROM users WHERE id = ?", user_id)

    async def restore_account(self, provider: str, subject: str) -> Dict[str, Any]:
        user = await self._first(
            "SELECT * FROM users WHERE provider = ? AND provider_subject = ?", provider, subject
        )
        if not user:
            raise ValueError("User not found")
        if user.get("status") == "active":
            return user
        now = iso(utc_now())
        if user.get("status") != "deletion_pending" or not user.get("deletion_due_at") or user["deletion_due_at"] <= now:
            raise ValueError("Account can no longer be restored")
        await self._batch([
            self.db.prepare(
                "UPDATE users SET status = 'active', deletion_requested_at = NULL, deletion_due_at = NULL, "
                "updated_at = ? WHERE id = ? AND status = 'deletion_pending'"
            ).bind(now, user["id"]),
            self.db.prepare(
                "INSERT INTO account_deletion_events(id, user_id, action, created_at) VALUES(?, ?, 'restored', ?)"
            ).bind(str(uuid.uuid4()), user["id"], now),
        ])
        return await self._first("SELECT * FROM users WHERE id = ?", user["id"])

    async def export_account(self, user_id: str) -> Dict[str, Any]:
        user = await self._first("SELECT * FROM users WHERE id = ? AND status = 'active'", user_id)
        if not user:
            raise ValueError("User not found")
        project_ids = await self._all(
            "SELECT id FROM projects WHERE user_id = ? ORDER BY updated_at DESC", user_id
        )
        projects = [await self.get_project(user_id, item["id"]) for item in project_ids]
        profile = self.public_user(user)
        profile.update({"provider": user["provider"], "created_at": user["created_at"]})
        return {
            "exported_at": iso(utc_now()),
            "profile": profile,
            "projects": projects,
            "payment_orders": await self._all(
                "SELECT id, package_id, package_name, idea_amount, detail_amount, amount_fen, currency, "
                "channel, status, expires_at, paid_at, fulfilled_at, refunded_at, created_at, updated_at "
                "FROM payment_orders WHERE user_id = ? ORDER BY created_at DESC", user_id,
            ),
            "quota_audit": await self._all(
                "SELECT resource, action, delta, limit_before, limit_after, reserved_before, reserved_after, "
                "reason, created_at FROM admin_quota_events WHERE user_id = ? ORDER BY created_at DESC", user_id,
            ),
        }

    async def process_due_deletions(self, delete_identity, limit: int = 20) -> Dict[str, int]:
        now = iso(utc_now())
        users = await self._all(
            "SELECT * FROM users WHERE (status = 'deletion_pending' AND deletion_due_at <= ?) "
            "OR status = 'deletion_finalizing' ORDER BY deletion_due_at LIMIT ?",
            now, min(max(limit, 1), 100),
        )
        processed = 0
        failed = 0
        for user in users:
            if user["status"] == "deletion_pending":
                await self._batch([
                    self.db.prepare(
                        "UPDATE users SET status = 'deletion_finalizing', updated_at = ? "
                        "WHERE id = ? AND status = 'deletion_pending'"
                    ).bind(now, user["id"]),
                    self.db.prepare(
                        "INSERT INTO account_deletion_events(id, user_id, action, created_at) "
                        "VALUES(?, ?, 'finalizing', ?)"
                    ).bind(str(uuid.uuid4()), user["id"], now),
                ])
            try:
                await delete_identity(user["provider_subject"])
            except Exception as exc:
                failed += 1
                await self._run(
                    "INSERT INTO account_deletion_events(id, user_id, action, detail, created_at) "
                    "VALUES(?, ?, 'identity_delete_failed', ?, ?)",
                    str(uuid.uuid4()), user["id"], str(exc)[:300], now,
                )
                continue
            anonymous_login = f"deleted-{user['id']}@deleted.invalid"
            await self._batch([
                self.db.prepare("DELETE FROM user_sessions WHERE user_id = ?").bind(user["id"]),
                self.db.prepare("DELETE FROM projects WHERE user_id = ?").bind(user["id"]),
                self.db.prepare("DELETE FROM usage_events WHERE user_id = ?").bind(user["id"]),
                self.db.prepare("DELETE FROM quota_reservations WHERE user_id = ?").bind(user["id"]),
                self.db.prepare("DELETE FROM quota_purchase_requests WHERE user_id = ?").bind(user["id"]),
                self.db.prepare("DELETE FROM product_events WHERE user_id = ?").bind(user["id"]),
                self.db.prepare(
                    "UPDATE users SET provider = 'deleted', provider_subject = ?, login = ?, "
                    "display_name = '已注销用户', avatar_url = '', idea_limit = 0, idea_used = 0, "
                    "idea_reserved = 0, detail_limit = 0, detail_used = 0, detail_reserved = 0, "
                    "status = 'deleted', deleted_at = ?, updated_at = ? WHERE id = ?"
                ).bind(f"deleted:{user['id']}", anonymous_login, now, now, user["id"]),
                self.db.prepare(
                    "INSERT INTO account_deletion_events(id, user_id, action, created_at) "
                    "VALUES(?, ?, 'completed', ?)"
                ).bind(str(uuid.uuid4()), user["id"], now),
            ])
            processed += 1
        return {"processed": processed, "failed": failed}

    async def create_payment_order(
        self, user_id: str, package: Dict[str, Any], channel: str, expires_minutes: int = 15
    ) -> Dict[str, Any]:
        if channel not in {"wechat", "alipay"}:
            raise ValueError("Invalid payment channel")
        order_id = str(uuid.uuid4())
        now = utc_now()
        await self._run(
            "INSERT INTO payment_orders(id, user_id, package_id, package_name, idea_amount, detail_amount, "
            "amount_fen, currency, channel, status, expires_at, created_at, updated_at) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, 'CNY', ?, 'pending', ?, ?, ?)",
            order_id, user_id, package["id"], package["name"], package["idea_amount"],
            package["detail_amount"], package["amount_fen"], channel,
            iso(now + timedelta(minutes=expires_minutes)), iso(now), iso(now),
        )
        return await self.get_payment_order(user_id, order_id)

    async def attach_payment_checkout(
        self, user_id: str, order_id: str, provider_order_id: str, pay_url: str
    ) -> Dict[str, Any]:
        result = await self._run(
            "UPDATE payment_orders SET provider_order_id = ?, pay_url = ?, updated_at = ? "
            "WHERE id = ? AND user_id = ? AND status = 'pending'",
            provider_order_id[:200], pay_url[:2000], iso(utc_now()), order_id, user_id,
        )
        if not self._changed(result):
            raise ValueError("Pending payment order not found")
        return await self.get_payment_order(user_id, order_id)

    async def fail_payment_order(self, user_id: str, order_id: str, reason: str) -> None:
        await self._run(
            "UPDATE payment_orders SET status = 'failed', failure_reason = ?, updated_at = ? "
            "WHERE id = ? AND user_id = ? AND status = 'pending'",
            reason[:300], iso(utc_now()), order_id, user_id,
        )

    async def get_payment_order(self, user_id: str, order_id: str) -> Dict[str, Any]:
        order = await self._first(
            "SELECT id, package_id, package_name, idea_amount, detail_amount, amount_fen, currency, "
            "channel, status, pay_url, expires_at, paid_at, fulfilled_at, refunded_at, created_at, updated_at "
            "FROM payment_orders WHERE id = ? AND user_id = ?",
            order_id, user_id,
        )
        if not order:
            raise ValueError("Payment order not found")
        if order["status"] == "pending" and order["expires_at"] <= iso(utc_now()):
            await self._run(
                "UPDATE payment_orders SET status = 'expired', updated_at = ? WHERE id = ? AND status = 'pending'",
                iso(utc_now()), order_id,
            )
            order["status"] = "expired"
        return order

    async def list_payment_orders(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        return await self._all(
            "SELECT id, package_id, package_name, idea_amount, detail_amount, amount_fen, currency, "
            "channel, CASE WHEN status = 'pending' AND expires_at <= ? THEN 'expired' ELSE status END AS status, "
            "pay_url, expires_at, paid_at, fulfilled_at, refunded_at, created_at, updated_at "
            "FROM payment_orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            iso(utc_now()), user_id, min(max(limit, 1), 100),
        )

    async def payment_order_id_for_provider(self, channel: str, provider_order_id: str) -> str:
        order = await self._first(
            "SELECT id FROM payment_orders WHERE channel = ? AND provider_order_id = ?",
            channel, provider_order_id,
        )
        if not order:
            raise ValueError("Payment order not found")
        return order["id"]

    async def admin_payment_orders(self, status: str = "") -> List[Dict[str, Any]]:
        return await self._all(
            "SELECT o.id, o.user_id, u.login, u.display_name, o.package_id, o.package_name, o.idea_amount, "
            "o.detail_amount, o.amount_fen, o.currency, o.channel, o.status, o.provider_order_id, "
            "o.provider_trade_id, o.failure_reason, o.refund_state, o.refund_request_id, "
            "o.expires_at, o.paid_at, o.fulfilled_at, o.refunded_at, "
            "o.created_at, o.updated_at FROM payment_orders o JOIN users u ON u.id = o.user_id "
            "WHERE ? = '' OR o.status = ? ORDER BY o.created_at DESC LIMIT 100",
            status, status,
        )

    async def admin_payment_order(self, order_id: str) -> Dict[str, Any]:
        order = await self._first(
            "SELECT o.*, u.login, u.display_name, u.idea_limit, u.idea_used, u.idea_reserved, "
            "u.detail_limit, u.detail_used, u.detail_reserved FROM payment_orders o "
            "JOIN users u ON u.id = o.user_id WHERE o.id = ?",
            order_id,
        )
        if not order:
            raise ValueError("Payment order not found")
        return order

    async def expire_payment_order(self, order_id: str) -> Dict[str, Any]:
        await self._run(
            "UPDATE payment_orders SET status = 'expired', updated_at = ? "
            "WHERE id = ? AND status = 'pending'",
            iso(utc_now()), order_id,
        )
        return await self.admin_payment_order(order_id)

    async def payment_reconciliation_candidates(self, limit: int = 20) -> List[Dict[str, Any]]:
        return await self._all(
            "SELECT * FROM payment_orders WHERE provider_order_id <> '' AND "
            "(refund_state = 'pending' OR (status = 'pending' AND expires_at <= ?)) "
            "ORDER BY updated_at LIMIT ?",
            iso(utc_now()), min(max(limit, 1), 100),
        )

    async def prepare_payment_refund(self, order_id: str) -> Dict[str, Any]:
        order = await self.admin_payment_order(order_id)
        if order["status"] == "refunded" and order["refund_state"] == "refunded":
            return order
        if order["status"] != "paid" or not order.get("fulfilled_at"):
            raise ValueError("Only fulfilled payments can be refunded")
        if order["refund_state"] == "pending":
            return order
        if (
            int(order["idea_limit"]) - int(order["idea_amount"]) < int(order["idea_used"]) + int(order["idea_reserved"])
            or int(order["detail_limit"]) - int(order["detail_amount"]) < int(order["detail_used"]) + int(order["detail_reserved"])
        ):
            raise ValueError("Purchased quota has already been used")
        refund_request_id = f"RF{order_id.replace('-', '')}"
        await self._run(
            "UPDATE payment_orders SET refund_state = 'pending', refund_request_id = ?, updated_at = ? "
            "WHERE id = ? AND status = 'paid' AND refund_state = 'none'",
            refund_request_id, iso(utc_now()), order_id,
        )
        return await self.admin_payment_order(order_id)

    async def complete_payment_refund(
        self, order_id: str, refund_request_id: str, provider_trade_id: str
    ) -> Dict[str, Any]:
        order = await self.admin_payment_order(order_id)
        if order["status"] == "refunded" and order["refund_state"] == "refunded":
            return {"status": "duplicate", "order": order}
        if order["status"] != "paid" or order["refund_state"] != "pending" or order["refund_request_id"] != refund_request_id:
            raise ValueError("Payment refund is not prepared")
        now = iso(utc_now())
        idea_after = int(order["idea_limit"]) - int(order["idea_amount"])
        detail_after = int(order["detail_limit"]) - int(order["detail_amount"])
        await self._batch([
            self.db.prepare(
                "UPDATE users SET idea_limit = ?, detail_limit = ?, updated_at = ? WHERE id = ?"
            ).bind(idea_after, detail_after, now, order["user_id"]),
            self.db.prepare(
                "UPDATE payment_orders SET status = 'refunded', refund_state = 'refunded', "
                "provider_trade_id = ?, refunded_at = ?, updated_at = ? "
                "WHERE id = ? AND status = 'paid' AND refund_state = 'pending'"
            ).bind(provider_trade_id, now, now, order_id),
            self.db.prepare(
                "INSERT INTO payment_events(id, event_key, order_id, channel, event_type, provider_trade_id, "
                "amount_fen, verified, payload_digest, processing_status, created_at) "
                "VALUES(?, ?, ?, ?, 'REFUND', ?, ?, 1, ?, 'processed', ?)"
            ).bind(
                str(uuid.uuid4()), f"refund:{refund_request_id}", order_id, order["channel"],
                provider_trade_id, order["amount_fen"], refund_request_id, now,
            ),
            self.db.prepare(
                "INSERT INTO admin_quota_events(id, user_id, resource, action, delta, limit_before, limit_after, "
                "reserved_before, reserved_after, reason, created_at) "
                "VALUES(?, ?, 'idea', 'adjust_limit', ?, ?, ?, ?, ?, ?, ?)"
            ).bind(
                str(uuid.uuid4()), order["user_id"], -int(order["idea_amount"]), order["idea_limit"], idea_after,
                order["idea_reserved"], order["idea_reserved"], f"支付宝订单 {order_id} 全额退款", now,
            ),
            self.db.prepare(
                "INSERT INTO admin_quota_events(id, user_id, resource, action, delta, limit_before, limit_after, "
                "reserved_before, reserved_after, reason, created_at) "
                "VALUES(?, ?, 'detail', 'adjust_limit', ?, ?, ?, ?, ?, ?, ?)"
            ).bind(
                str(uuid.uuid4()), order["user_id"], -int(order["detail_amount"]), order["detail_limit"], detail_after,
                order["detail_reserved"], order["detail_reserved"], f"支付宝订单 {order_id} 全额退款", now,
            ),
        ])
        return {"status": "refunded", "order": await self.admin_payment_order(order_id)}

    async def fulfill_payment(
        self, order_id: str, channel: str, event_key: str, event_type: str,
        provider_trade_id: str, amount_fen: int, payload_digest: str, verified: bool,
    ) -> Dict[str, Any]:
        order = await self._first("SELECT * FROM payment_orders WHERE id = ?", order_id)
        if not order:
            raise ValueError("Payment order not found")
        if not verified:
            await self._run(
                "INSERT OR IGNORE INTO payment_events(id, event_key, order_id, channel, event_type, provider_trade_id, "
                "amount_fen, verified, payload_digest, processing_status, rejection_reason, created_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, 0, ?, 'rejected', 'signature verification failed', ?)",
                str(uuid.uuid4()), event_key, order_id, channel, event_type, provider_trade_id,
                amount_fen, payload_digest, iso(utc_now()),
            )
            raise ValueError("Payment signature verification failed")
        if channel != order["channel"] or amount_fen != int(order["amount_fen"]):
            raise ValueError("Payment channel or amount mismatch")
        if order["status"] == "paid" and order.get("fulfilled_at"):
            return {"status": "duplicate", "order": order}
        if order["status"] not in {"pending", "expired"}:
            raise ValueError("Payment order is not payable")

        now = iso(utc_now())
        statements = [
            self.db.prepare(
                "INSERT INTO payment_events(id, event_key, order_id, channel, event_type, provider_trade_id, "
                "amount_fen, verified, payload_digest, processing_status, created_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, 1, ?, 'processed', ?)"
            ).bind(str(uuid.uuid4()), event_key, order_id, channel, event_type, provider_trade_id, amount_fen, payload_digest, now),
            self.db.prepare(
                "UPDATE payment_orders SET status = 'paid', provider_trade_id = ?, paid_at = ?, updated_at = ? "
                "WHERE id = ? AND status IN ('pending', 'expired') AND fulfilled_at IS NULL"
            ).bind(provider_trade_id[:200], now, now, order_id),
            self.db.prepare(
                "UPDATE users SET idea_limit = idea_limit + ?, detail_limit = detail_limit + ?, updated_at = ? "
                "WHERE id = ? AND EXISTS(SELECT 1 FROM payment_orders WHERE id = ? AND status = 'paid' AND fulfilled_at IS NULL)"
            ).bind(order["idea_amount"], order["detail_amount"], now, order["user_id"], order_id),
            self.db.prepare(
                "UPDATE payment_orders SET fulfilled_at = ?, updated_at = ? "
                "WHERE id = ? AND status = 'paid' AND fulfilled_at IS NULL"
            ).bind(now, now, order_id),
        ]
        try:
            await self._batch(statements)
        except Exception as exc:
            duplicate = await self._first("SELECT id FROM payment_events WHERE event_key = ?", event_key)
            if duplicate:
                return {"status": "duplicate", "order": await self._first("SELECT * FROM payment_orders WHERE id = ?", order_id)}
            raise exc
        return {"status": "fulfilled", "order": await self._first("SELECT * FROM payment_orders WHERE id = ?", order_id)}

    async def find_users(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        needle = query.strip()
        pattern = f"%{needle}%"
        return await self._all(
            "SELECT id, provider, login, display_name, idea_limit, idea_used, idea_reserved, "
            "detail_limit, detail_used, detail_reserved, created_at, updated_at "
            "FROM users WHERE ? = '' OR id = ? OR login LIKE ? OR display_name LIKE ? "
            "ORDER BY updated_at DESC LIMIT ?",
            needle, needle, pattern, pattern, min(max(limit, 1), 100),
        )

    async def adjust_quota(self, user_id: str, resource: str, delta: int, reason: str) -> Dict[str, Any]:
        if resource not in {"idea", "detail"} or delta == 0 or abs(delta) > 1_000_000:
            raise ValueError("Invalid quota adjustment")
        user = await self._first("SELECT * FROM users WHERE id = ?", user_id)
        if not user:
            raise ValueError("User not found")
        before = int(user[f"{resource}_limit"])
        after = before + delta
        minimum = int(user[f"{resource}_used"]) + int(user[f"{resource}_reserved"])
        if after < minimum:
            raise ValueError("Quota limit cannot be lower than used plus reserved")
        now = iso(utc_now())
        await self._batch([
            self.db.prepare(
                f"UPDATE users SET {resource}_limit = ?, updated_at = ? WHERE id = ?"
            ).bind(after, now, user_id),
            self.db.prepare(
                "INSERT INTO admin_quota_events(id, user_id, resource, action, delta, limit_before, limit_after, reserved_before, reserved_after, reason, created_at) "
                "VALUES(?, ?, ?, 'adjust_limit', ?, ?, ?, ?, ?, ?, ?)"
            ).bind(
                str(uuid.uuid4()), user_id, resource, delta, before, after,
                user[f"{resource}_reserved"], user[f"{resource}_reserved"], reason, now,
            ),
        ])
        return (await self.find_users(user_id, 1))[0]

    async def clear_reserved_quota(self, user_id: str, resource: str, reason: str) -> Dict[str, Any]:
        if resource not in {"idea", "detail"}:
            raise ValueError("Invalid quota resource")
        user = await self._first("SELECT * FROM users WHERE id = ?", user_id)
        if not user:
            raise ValueError("User not found")
        before = int(user[f"{resource}_reserved"])
        now = iso(utc_now())
        await self._batch([
            self.db.prepare(
                "UPDATE quota_reservations SET outcome = 'refunded', updated_at = ? "
                "WHERE user_id = ? AND resource = ? AND outcome = 'reserved'"
            ).bind(now, user_id, resource),
            self.db.prepare(
                "INSERT INTO admin_quota_events(id, user_id, resource, action, delta, limit_before, limit_after, reserved_before, reserved_after, reason, created_at) "
                "VALUES(?, ?, ?, 'clear_reserved', 0, ?, ?, ?, 0, ?, ?)"
            ).bind(
                str(uuid.uuid4()), user_id, resource, user[f"{resource}_limit"],
                user[f"{resource}_limit"], before, reason, now,
            ),
        ])
        return (await self.find_users(user_id, 1))[0]

    async def quota_audit(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        return await self._all(
            "SELECT resource, action, delta, limit_before, limit_after, reserved_before, reserved_after, reason, created_at "
            "FROM admin_quota_events WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            user_id, min(max(limit, 1), 100),
        )

    async def recharge_history(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取用户的充值记录（支付订单）"""
        return await self._all(
            "SELECT id, package_id, package_name, idea_amount, detail_amount, amount_fen, currency, "
            "channel, status, paid_at, fulfilled_at, created_at "
            "FROM payment_orders WHERE user_id = ? AND status IN ('paid', 'fulfilled') "
            "ORDER BY created_at DESC LIMIT ?",
            user_id, min(max(limit, 1), 100),
        )

    async def admin_metrics(self, days: int = 30) -> Dict[str, Any]:
        days = min(max(int(days), 1), 90)
        cutoff = iso(utc_now() - timedelta(days=days))
        users = await self._first(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN created_at >= ? THEN 1 ELSE 0 END) AS new, "
            "SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active FROM users",
            cutoff,
        )
        generation = await self._first(
            "SELECT SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END) AS complete, "
            "SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed "
            "FROM projects WHERE created_at >= ?",
            cutoff,
        )
        details = await self._first(
            "SELECT COUNT(*) AS total FROM detailed_plans WHERE created_at >= ?", cutoff
        )
        feedback = await self._first(
            "SELECT SUM(CASE WHEN action = 'no_value' THEN 1 ELSE 0 END) AS no_value "
            "FROM product_events WHERE created_at >= ?",
            cutoff,
        )
        payments = await self._first(
            "SELECT SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) AS paid, "
            "SUM(CASE WHEN status = 'refunded' THEN 1 ELSE 0 END) AS refunded, "
            "SUM(CASE WHEN status = 'paid' THEN amount_fen ELSE 0 END) AS revenue_fen "
            "FROM payment_orders WHERE created_at >= ?",
            cutoff,
        )
        quota = await self._first(
            "SELECT COUNT(*) AS stuck_reservations FROM quota_reservations "
            "WHERE outcome = 'reserved' AND created_at < ?",
            iso(utc_now() - timedelta(minutes=30)),
        )
        integer = lambda value: int(value or 0)
        return {
            "window_days": days,
            "users": {key: integer(users.get(key)) for key in ("total", "new", "active")},
            "generation": {
                "complete": integer(generation.get("complete")),
                "failed": integer(generation.get("failed")),
                "details": integer(details.get("total")),
                "no_value": integer(feedback.get("no_value")),
            },
            "payments": {key: integer(payments.get(key)) for key in ("paid", "refunded", "revenue_fen")},
            "quota": {"stuck_reservations": integer(quota.get("stuck_reservations"))},
        }

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

    async def record_product_event(
        self, user_id: str, project_id: str, idea_index: Optional[int], action: str, idempotency_key: str
    ) -> str:
        if action not in {"expand", "detail", "export", "delete", "no_value"}:
            raise ValueError("Invalid product event")
        project = await self.get_project(user_id, project_id)
        if idea_index is not None and not 0 <= idea_index < len(project["ideas"]):
            raise ValueError("Idea not found")
        try:
            await self._run(
                "INSERT INTO product_events(id, user_id, project_id, idea_index, action, idempotency_key, created_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?)",
                str(uuid.uuid4()), user_id, project_id, idea_index, action, idempotency_key, iso(utc_now()),
            )
        except Exception:
            prior = await self._first(
                "SELECT id FROM product_events WHERE user_id = ? AND idempotency_key = ?",
                user_id, idempotency_key,
            )
            if prior:
                return "duplicate"
            raise
        return "recorded"

    async def save_plan(self, user_id: str, project_id: str, idea_index: int, content: str) -> None:
        owned = await self._first("SELECT id FROM projects WHERE id = ? AND user_id = ?", project_id, user_id)
        if not owned:
            raise ValueError("Project not found")
        now = iso(utc_now())
        await self._run(
            "INSERT INTO detailed_plans(id, user_id, project_id, idea_index, content_markdown, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?) ON CONFLICT(project_id, idea_index) DO UPDATE SET content_markdown = excluded.content_markdown, updated_at = excluded.updated_at WHERE user_id = excluded.user_id",
            str(uuid.uuid4()), user_id, project_id, idea_index, content, now, now,
        )

    async def reserve_quota(self, user_id: str, reservation_key: str, resource: str, amount: int) -> str:
        if resource not in {"idea", "detail"} or amount < 1:
            raise ValueError("Invalid quota reservation")
        now = iso(utc_now())
        try:
            await self._run(
                "INSERT INTO quota_reservations(user_id, reservation_key, resource, project_id, amount, outcome, created_at, updated_at) "
                "VALUES(?, ?, ?, '', ?, 'reserved', ?, ?)",
                user_id, reservation_key, resource, amount, now, now,
            )
        except Exception:
            prior = await self._first(
                "SELECT outcome FROM quota_reservations WHERE user_id = ? AND reservation_key = ? AND resource = ?",
                user_id, reservation_key, resource,
            )
            if prior:
                return "duplicate"
            user = await self._first(
                f"SELECT {resource}_limit AS quota_limit, {resource}_used AS used, "
                f"{resource}_reserved AS reserved FROM users WHERE id = ?",
                user_id,
            )
            if user and user["used"] + user["reserved"] + amount > user["quota_limit"]:
                return "denied"
            raise
        return "reserved"

    async def settle_quota(self, user_id: str, project_id: str, reservation_key: str, resource: str, amount: int, success: bool) -> None:
        outcome = "committed" if success else "refunded"
        result = await self._run(
            "UPDATE quota_reservations SET project_id = ?, outcome = ?, updated_at = ? "
            "WHERE user_id = ? AND reservation_key = ? AND resource = ? AND amount = ? AND outcome = 'reserved'",
            project_id, outcome, iso(utc_now()), user_id, reservation_key, resource, amount,
        )
        if self._changed(result):
            return
        reservation = await self._first(
            "SELECT amount, outcome FROM quota_reservations "
            "WHERE user_id = ? AND reservation_key = ? AND resource = ?",
            user_id, reservation_key, resource,
        )
        if reservation and reservation["amount"] == amount and reservation["outcome"] == outcome:
            return
        raise ValueError("Quota reservation not found or already settled differently")

    @staticmethod
    def public_user(user: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": user["id"],
            "login": user["login"],
            "display_name": user["display_name"],
            "avatar_url": user.get("avatar_url", ""),
            "status": user.get("status", "active"),
            "deletion_due_at": user.get("deletion_due_at"),
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
