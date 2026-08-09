import pytest

from app.intelligence.context import DeviceContextStore


def test_context_is_isolated_by_device_and_survives_a_reconnect_lookup():
    store = DeviceContextStore()
    store.update("device-a", platform="YOUTUBE", query="HUMBLE", action="SEARCH_MEDIA")
    store.update("device-b", platform="SPOTIFY", query="Runaway", action="SEARCH_MEDIA")

    assert store.get("device-a").query == "HUMBLE"
    assert store.get("device-b").query == "Runaway"
    assert store.get("device-a") is store.get("device-a")


def test_context_expires_predictably_without_disk_persistence():
    now = [10.0]
    store = DeviceContextStore(ttl_seconds=5, time_fn=lambda: now[0])
    store.update("device-a", platform="YOUTUBE")

    now[0] = 14.9
    assert store.get("device-a") is not None
    now[0] = 15.0
    assert store.get("device-a") is None


def test_context_evicts_the_least_recently_used_device_at_the_bound():
    store = DeviceContextStore(max_devices=2)
    store.update("device-a", platform="YOUTUBE")
    store.update("device-b", platform="SPOTIFY")
    assert store.get("device-a") is not None
    store.update("device-c", platform="NETFLIX")

    assert store.get("device-a") is not None
    assert store.get("device-b") is None
    assert store.get("device-c") is not None


def test_context_fields_are_bounded_and_clear_is_explicit():
    store = DeviceContextStore()
    with pytest.raises(ValueError):
        store.update("d" * 129, platform="YOUTUBE")
    with pytest.raises(ValueError):
        store.update("device-a", query="q" * 201)
    with pytest.raises(ValueError):
        store.update("device-a", action="a" * 65)

    store.update("device-a", query="safe")
    store.clear("device-a")
    assert store.get("device-a") is None
