"""Fail-closed payment provider boundary for mainland China channels."""

import json
from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class PaymentNotification:
    event_key: str
    event_type: str
    provider_order_id: str
    provider_trade_id: str
    amount_fen: int
    payload_digest: str


@dataclass(frozen=True)
class PaymentQuery:
    provider_order_id: str
    provider_trade_id: str
    status: str
    amount_fen: int


@dataclass(frozen=True)
class PaymentRefund:
    provider_order_id: str
    provider_trade_id: str
    refund_request_id: str
    amount_fen: int


class PaymentProvider:
    channel = ""

    async def create_checkout(self, order: Dict[str, Any], origin: str, scene: str) -> Dict[str, str]:
        raise NotImplementedError

    async def verify_notification(self, headers: Dict[str, str], body: bytes) -> PaymentNotification:
        raise NotImplementedError


class AlipayProvider(PaymentProvider):
    """Delegates RSA2 operations to a private JavaScript Worker via Service Binding."""

    channel = "alipay"

    def __init__(self, binding, gateway_token: str):
        if binding is None or not gateway_token:
            raise ValueError("Alipay gateway binding and token are required")
        self.binding = binding
        self.gateway_token = gateway_token

    async def _call(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = await self.binding.fetch(
            f"https://idea-spark-payment.internal{path}",
            method="POST",
            headers={
                "Authorization": f"Bearer {self.gateway_token}",
                "Content-Type": "application/json",
            },
            body=json.dumps(payload, ensure_ascii=False),
        )
        text = await response.text()
        if response.status != 200:
            raise RuntimeError("支付宝支付网关拒绝了请求")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("支付宝支付网关返回无效响应") from exc

    async def create_checkout(self, order: Dict[str, Any], origin: str, scene: str) -> Dict[str, str]:
        result = await self._call("/checkout", {
            "order_id": order["id"],
            "amount_fen": order["amount_fen"],
            "subject": f"Idea Spark {order['package_name']} 创作额度",
            "notify_url": f"{origin}/api/billing/webhooks/alipay",
            "return_url": f"{origin}/account?payment=return&order_id={order['id']}",
            "scene": scene,
        })
        return {
            "provider_order_id": result["provider_order_id"],
            "pay_url": result["pay_url"],
        }

    async def verify_notification(self, headers: Dict[str, str], body: bytes) -> PaymentNotification:
        result = await self._call("/verify", {"body": body.decode("utf-8")})
        return PaymentNotification(
            event_key=result["event_key"],
            event_type=result["event_type"],
            provider_order_id=result["provider_order_id"],
            provider_trade_id=result["provider_trade_id"],
            amount_fen=int(result["amount_fen"]),
            payload_digest=result["payload_digest"],
        )

    async def query_order(self, order: Dict[str, Any]) -> PaymentQuery:
        result = await self._call("/query", {"provider_order_id": order["provider_order_id"]})
        return PaymentQuery(
            provider_order_id=result["provider_order_id"],
            provider_trade_id=result.get("provider_trade_id", ""),
            status=result["status"],
            amount_fen=int(result["amount_fen"]),
        )

    async def refund_order(self, order: Dict[str, Any], refund_request_id: str) -> PaymentRefund:
        result = await self._call("/refund", {
            "provider_order_id": order["provider_order_id"],
            "amount_fen": int(order["amount_fen"]),
            "refund_request_id": refund_request_id,
        })
        return PaymentRefund(
            provider_order_id=result["provider_order_id"],
            provider_trade_id=result.get("provider_trade_id", ""),
            refund_request_id=result["refund_request_id"],
            amount_fen=int(result["amount_fen"]),
        )


class PaymentRegistry:
    """Only fully configured, signature-verifying providers may be registered."""

    def __init__(self, providers=None, requirements=None):
        self.providers = dict(providers or {})
        self.requirements = requirements or {
            "alipay": ["应用 AppID", "应用私钥", "支付宝公钥", "Seller ID"],
        }

    def get(self, channel: str) -> PaymentProvider | None:
        return self.providers.get(channel)

    def public_status(self) -> Dict[str, Dict[str, Any]]:
        labels = {"alipay": "支付宝"}
        return {
            channel: {
                "name": labels[channel],
                "configured": channel in self.providers,
                "missing": [] if channel in self.providers else fields,
            }
            for channel, fields in self.requirements.items()
        }
