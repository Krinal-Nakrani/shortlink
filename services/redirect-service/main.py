import os
import time

import redis
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
STREAM_NAME = os.getenv("STREAM_NAME", "clicks")

app = FastAPI(title="ShortLink redirect-service")
cache = redis.Redis.from_url(REDIS_URL, decode_responses=True)


@app.get("/{code}")
def redirect(code: str, request: Request):
    target = cache.get(f"url:{code}")
    if target is None:
        raise HTTPException(status_code=404, detail="short code not found")
    cache.xadd(
        STREAM_NAME,
        {
            "code": code,
            "ts": str(time.time()),
            "user_agent": request.headers.get("user-agent", ""),
        },
        maxlen=100000,
        approximate=True,
    )
    return RedirectResponse(url=target, status_code=302)
