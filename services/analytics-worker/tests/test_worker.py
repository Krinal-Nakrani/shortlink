import pytest
import redis

import worker


class FakeConnection:
    """Stands in for a PostgreSQL connection."""

    def __init__(self):
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))


class FakeRedis:
    """Stands in for Redis; can be told to fail when the group is created."""

    def __init__(self, error=None):
        self.error = error
        self.created = []

    def xgroup_create(self, stream, group, id="0", mkstream=False):
        if self.error:
            raise self.error
        self.created.append((stream, group))


def test_count_click_adds_one_for_the_code():
    conn = FakeConnection()

    worker.count_click(conn, "abc123")

    sql, params = conn.executed[0]
    assert "INSERT INTO click_counts" in sql
    assert params == ("abc123",)


def test_ensure_group_creates_the_group():
    client = FakeRedis()

    worker.ensure_group(client)

    assert client.created == [(worker.STREAM_NAME, worker.GROUP_NAME)]


def test_ensure_group_ignores_an_existing_group():
    error = redis.exceptions.ResponseError("BUSYGROUP Consumer Group name already exists")

    worker.ensure_group(FakeRedis(error))


def test_ensure_group_raises_other_errors():
    error = redis.exceptions.ResponseError("WRONGTYPE something else")

    with pytest.raises(redis.exceptions.ResponseError):
        worker.ensure_group(FakeRedis(error))
