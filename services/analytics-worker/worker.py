import logging
import os
import socket
import time

import psycopg
import redis

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://shortlink:shortlink@localhost:5432/shortlink")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
STREAM_NAME = os.getenv("STREAM_NAME", "clicks")
GROUP_NAME = os.getenv("GROUP_NAME", "analytics")
CONSUMER_NAME = os.getenv("CONSUMER_NAME", socket.gethostname())

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("analytics-worker")


def connect_db(retries=30, delay=2):
    """Connect to PostgreSQL (waiting until it is ready) and make sure the table exists."""
    for attempt in range(1, retries + 1):
        try:
            conn = psycopg.connect(DATABASE_URL, autocommit=True)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS click_counts (
                    code   TEXT PRIMARY KEY,
                    clicks BIGINT NOT NULL DEFAULT 0
                )
                """
            )
            return conn
        except psycopg.OperationalError:
            log.warning("database not ready (attempt %d/%d), retrying...", attempt, retries)
            time.sleep(delay)
    raise RuntimeError("could not connect to the database")


def ensure_group(client):
    try:
        client.xgroup_create(STREAM_NAME, GROUP_NAME, id="0", mkstream=True)
        log.info("created consumer group %s on stream %s", GROUP_NAME, STREAM_NAME)
    except redis.exceptions.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def count_click(conn, code):
    conn.execute(
        """
        INSERT INTO click_counts (code, clicks) VALUES (%s, 1)
        ON CONFLICT (code) DO UPDATE SET clicks = click_counts.clicks + 1
        """,
        (code,),
    )


def main():
    client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=30)
    conn = connect_db()
    ensure_group(client)
    log.info("worker %s started, waiting for click events", CONSUMER_NAME)

    while True:
        response = client.xreadgroup(
            GROUP_NAME, CONSUMER_NAME, {STREAM_NAME: ">"}, count=10, block=5000
        )
        if not response:
            continue
        for _stream, messages in response:
            for message_id, fields in messages:
                code = fields.get("code")
                if code:
                    count_click(conn, code)
                    log.info("counted click for %s", code)
                client.xack(STREAM_NAME, GROUP_NAME, message_id)


if __name__ == "__main__":
    main()
