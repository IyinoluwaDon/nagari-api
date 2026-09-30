import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from .config import get_settings

_hits: dict[str, deque[float]] = defaultdict(deque)
WINDOW_SECONDS = 3600


def client_ip(request: Request) -> str:
    # If deployed behind a proxy (Render, Railway, Nginx), run uvicorn with
    # --proxy-headers so request.client reflects the real visitor IP.
    return request.client.host if request.client else "unknown"


def check_rate_limit(request: Request) -> None:
    limit = get_settings().rate_limit_per_hour
    if limit <= 0:
        return
    now = time.monotonic()
    hits = _hits[client_ip(request)]
    while hits and now - hits[0] > WINDOW_SECONDS:
        hits.popleft()
    if len(hits) >= limit:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later or call us directly.",
        )
    hits.append(now)


def reset() -> None:
    _hits.clear()
