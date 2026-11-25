import os
import secrets
import string
import time
from contextlib import asynccontextmanager

import psycopg
import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://shortlink:shortlink@localhost:5432/shortlink")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8001")

ALPHABET = string.ascii_letters + string.digits
CODE_LENGTH = 6

cache = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def get_conn():
    return psycopg.connect(DATABASE_URL)


def init_db(retries=30, delay=2):
    """Create the tables if they do not exist. Waits for PostgreSQL to be ready."""
    for attempt in range(1, retries + 1):
        try:
            with get_conn() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS urls (
                        code         TEXT PRIMARY KEY,
                        original_url TEXT NOT NULL,
                        created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS click_counts (
                        code   TEXT PRIMARY KEY,
                        clicks BIGINT NOT NULL DEFAULT 0
                    )
                    """
                )
            return
        except psycopg.OperationalError:
            print(f"database not ready (attempt {attempt}/{retries}), retrying...", flush=True)
            time.sleep(delay)
    raise RuntimeError("could not connect to the database")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="ShortLink url-api", lifespan=lifespan)


class ShortenRequest(BaseModel):
    url: HttpUrl


def new_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


@app.post("/shorten", status_code=201)
def shorten(req: ShortenRequest):
    original = str(req.url)
    with get_conn() as conn:
        for _ in range(5):
            code = new_code()
            try:
                conn.execute(
                    "INSERT INTO urls (code, original_url) VALUES (%s, %s)",
                    (code, original),
                )
                break
            except psycopg.errors.UniqueViolation:
                conn.rollback()
        else:
            raise HTTPException(status_code=500, detail="could not generate a unique code")
    cache.set(f"url:{code}", original)
    return {"code": code, "short_url": f"{BASE_URL}/{code}", "original_url": original}


@app.get("/stats/{code}")
def stats(code: str):
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT u.code, u.original_url, u.created_at, COALESCE(c.clicks, 0)
            FROM urls u
            LEFT JOIN click_counts c ON c.code = u.code
            WHERE u.code = %s
            """,
            (code,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="short code not found")
    return {
        "code": row[0],
        "original_url": row[1],
        "created_at": row[2].isoformat(),
        "clicks": row[3],
    }
