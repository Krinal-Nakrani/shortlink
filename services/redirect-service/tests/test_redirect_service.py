import pytest
from fastapi.testclient import TestClient

import main


class FakeCache:
    """Stands in for Redis: a dictionary plus a list of stream events."""

    def __init__(self, data=None):
        self.data = data or {}
        self.events = []

    def get(self, key):
        return self.data.get(key)

    def xadd(self, stream, fields, **kwargs):
        self.events.append((stream, fields))


@pytest.fixture
def client():
    return TestClient(main.app)


def test_known_code_redirects_and_records_a_click(client, monkeypatch):
    cache = FakeCache({"url:abc123": "https://example.com/devops"})
    monkeypatch.setattr(main, "cache", cache)

    response = client.get("/abc123", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/devops"
    assert len(cache.events) == 1
    stream, fields = cache.events[0]
    assert stream == main.STREAM_NAME
    assert fields["code"] == "abc123"


def test_unknown_code_returns_404_and_records_nothing(client, monkeypatch):
    cache = FakeCache()
    monkeypatch.setattr(main, "cache", cache)

    response = client.get("/missing", follow_redirects=False)

    assert response.status_code == 404
    assert cache.events == []


def test_every_click_adds_an_event(client, monkeypatch):
    cache = FakeCache({"url:abc123": "https://example.com"})
    monkeypatch.setattr(main, "cache", cache)

    for _ in range(3):
        client.get("/abc123", follow_redirects=False)

    assert len(cache.events) == 3
