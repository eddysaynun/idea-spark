import asyncio

from routers.stream_router import with_heartbeat


async def delayed_events():
    yield {"type": "progress", "data": {"progress": 10}}
    await asyncio.sleep(0.03)
    yield {"type": "complete", "data": {"total": 3}}


async def test_with_heartbeat_keeps_long_pipeline_waits_alive():
    received = [event async for event in with_heartbeat(delayed_events(), 0.005)]

    assert received[0]["type"] == "progress"
    assert received[-1]["type"] == "complete"
    assert received.count(None) >= 2
