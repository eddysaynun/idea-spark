from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from routers.billing_router import PaymentOrderRequest, create_order, packages
from services.payments import PaymentRegistry


@pytest.mark.asyncio
async def test_packages_expose_fail_closed_channel_status():
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(payment_registry=PaymentRegistry())))
    result = await packages(request, {"id": "user"})

    assert result["payment_mode"] == "manual_review"
    assert result["channels"]["wechat"]["configured"] is False
    assert "商户号" in result["channels"]["wechat"]["missing"]


@pytest.mark.asyncio
async def test_unconfigured_channel_cannot_create_fake_checkout():
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(payment_registry=PaymentRegistry())))
    with pytest.raises(HTTPException) as error:
        await create_order(PaymentOrderRequest(package_id="starter", channel="wechat"), request, {"id": "user"})
    assert error.value.status_code == 503
    assert "暂未开放" in error.value.detail
