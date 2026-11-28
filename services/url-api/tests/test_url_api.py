from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import main


class FakeCursor:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    """Stands in for a PostgreSQL connection, so no database is needed."""

    def __init__(self, row=None):
        self.row = row
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        return FakeCursor(self.row)

    def rollback(self):
        pass


class FakeCache:
    """Stands in for Redis."""

    def __init__(self):
        self.data = {}

    def set(self, key, value):
        self.data[key] = value


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def fake_cache(monkeypatch):
    cache = FakeCache()
    monkeypatch.setattr(main, "cache", cache)
    return cache


def test_new_code_has_six_letters_and_digits():
    code = main.new_code()
    assert len(code) == 6
    assert all(ch in main.ALPHABET for ch in code)


def test_shorten_creates_a_short_link(client, fake_cache, monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(main, "get_conn", lambda: conn)

    response = client.post("/shorten", json={"url": "https://example.com/devops"})

    assert response.status_code == 200
    body = response.json()
    assert len(body["code"]) == 6
    assert body["short_url"].endswith("/" + body["code"])
    assert body["original_url"] == "https://example.com/devops"
    assert fake_cache.data["url:" + body["code"]] == "https://example.com/devops"
    assert len(conn.executed) == 1


def test_shorten_rejects_an_invalid_url(client, fake_cache, monkeypatch):
    monkeypatch.setattr(main, "get_conn", lambda: FakeConnection())

    response = client.post("/shorten", json={"url": "not-a-url"})

    assert response.status_code == 422


def test_stats_returns_the_click_count(client, monkeypatch):
    created = datetime(2026, 11, 27, tzinfo=timezone.utc)
    row = ("abc123", "https://example.com", created, 5)
    monkeypatch.setattr(main, "get_conn", lambda: FakeConnection(row))

    response = client.get("/stats/abc123")

    assert response.status_code == 200
    assert response.json()["clicks"] == 5
    assert response.json()["original_url"] == "https://example.com"


def test_stats_unknown_code_returns_404(client, monkeypatch):
    monkeypatch.setattr(main, "get_conn", lambda: FakeConnection(None))

    response = client.get("/stats/nope")

    assert response.status_code == 404
