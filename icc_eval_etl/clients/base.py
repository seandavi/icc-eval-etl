import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)


class BaseClient:
    """Async HTTP client with rate limiting and retry logic."""

    def __init__(
        self,
        base_url: str,
        rate_limit: float = 1.0,
        max_retries: int = 3,
        client: httpx.AsyncClient | None = None,
    ):
        self.base_url = base_url
        self._min_interval = 1.0 / rate_limit
        self._max_retries = max_retries
        self._lock = asyncio.Lock()
        self._last_request_time = 0.0
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=60.0)

    async def _throttle(self) -> None:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> httpx.Response:
        for attempt in range(self._max_retries + 1):
            await self._throttle()
            try:
                response = await self._client.request(method, path, **kwargs)
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < self._max_retries:
                        wait = 2**attempt
                        logger.warning(
                            "Request %s %s returned %d, retrying in %ds (attempt %d/%d)",
                            method, path, response.status_code, wait, attempt + 1, self._max_retries,
                        )
                        await asyncio.sleep(wait)
                        continue
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError:
                raise
            except httpx.HTTPError as exc:
                if attempt < self._max_retries:
                    wait = 2**attempt
                    logger.warning(
                        "Request %s %s failed (%s), retrying in %ds (attempt %d/%d)",
                        method, path, exc, wait, attempt + 1, self._max_retries,
                    )
                    await asyncio.sleep(wait)
                    continue
                raise
        raise RuntimeError("Unreachable")

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
