"""Unit tests for TTLCache — no network, no mocking needed."""
import time

import pytest

from utils.cache import TTLCache


@pytest.fixture
def c():
    return TTLCache()


def test_get_miss_returns_none(c):
    assert c.get("missing") is None


def test_set_and_get(c):
    c.set("key", "value", ttl=60)
    assert c.get("key") == "value"


def test_set_overwrites(c):
    c.set("key", "first", ttl=60)
    c.set("key", "second", ttl=60)
    assert c.get("key") == "second"


def test_ttl_expiry(c):
    c.set("key", "value", ttl=1)
    time.sleep(1.05)
    assert c.get("key") is None


def test_expired_entry_is_deleted(c):
    c.set("key", "value", ttl=1)
    time.sleep(1.05)
    c.get("key")  # triggers deletion
    assert "key" not in c._store


def test_delete_existing(c):
    c.set("key", "value", ttl=60)
    c.delete("key")
    assert c.get("key") is None


def test_delete_nonexistent_is_noop(c):
    c.delete("nonexistent")  # must not raise


def test_different_keys_are_independent(c):
    c.set("a", 1, ttl=60)
    c.set("b", 2, ttl=60)
    assert c.get("a") == 1
    assert c.get("b") == 2
    c.delete("a")
    assert c.get("a") is None
    assert c.get("b") == 2


def test_stores_arbitrary_types(c):
    c.set("list", [1, 2, 3], ttl=60)
    c.set("dict", {"x": 1}, ttl=60)
    assert c.get("list") == [1, 2, 3]
    assert c.get("dict") == {"x": 1}
