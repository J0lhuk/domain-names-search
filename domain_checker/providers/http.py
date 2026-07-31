from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable

import httpx


async def request_with_retry(
    request: Callable[[], Awaitable[httpx.Response]],
    attempts: int = 3,
) -> httpx.Response:
    """Retry only transient HTTP/network failures, respecting a bounded Retry-After."""
    last_error: httpx.HTTPError | None = None
    for attempt in range(attempts):
        try:
            response = await request()
            if response.status_code not in {429, 500, 502, 503, 504} or attempt == attempts - 1:
                return response
            retry_after = response.headers.get("Retry-After")
            delay = min(float(retry_after), 30.0) if retry_after and retry_after.isdigit() else min(0.5 * (2**attempt) + random.uniform(0, 0.25), 10.0)
        except httpx.HTTPError as error:
            last_error = error
            if attempt == attempts - 1:
                raise
            delay = min(0.5 * (2**attempt) + random.uniform(0, 0.25), 10.0)
        await asyncio.sleep(delay)
    if last_error:
        raise last_error
    raise RuntimeError("request retry loop ended unexpectedly")
