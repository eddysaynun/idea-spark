"""Fail-closed payment provider boundary for mainland China channels."""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class PaymentNotification:
    event_key: str
    event_type: str
    order_id: str
    provider_trade_id: str
    amount_fen: int
    payload_digest: str


class PaymentProvider:
    channel = ""

    async def create_checkout(self, order: Dict[str, Any], origin: str) -> Dict[str, str]:
        raise NotImplementedError

    async def verify_notification(self, headers: Dict[str, str], body: bytes) -> PaymentNotification:
        raise NotImplementedError


class PaymentRegistry:
    """Only fully configured, signature-verifying providers may be registered."""

    def __init__(self, providers=None, requirements=None):
        self.providers = dict(providers or {})
        self.requirements = requirements or {
            "wechat": ["商户号", "API v3 密钥", "商户私钥", "微信支付公钥", "AppID"],
            "alipay": ["应用 AppID", "应用私钥", "支付宝公钥"],
        }

    def get(self, channel: str) -> PaymentProvider | None:
        return self.providers.get(channel)

    def public_status(self) -> Dict[str, Dict[str, Any]]:
        labels = {"wechat": "微信支付", "alipay": "支付宝"}
        return {
            channel: {
                "name": labels[channel],
                "configured": channel in self.providers,
                "missing": [] if channel in self.providers else fields,
            }
            for channel, fields in self.requirements.items()
        }
