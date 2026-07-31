from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx

from .http import request_with_retry


class IanaBootstrapProvider:
    URL = "https://data.iana.org/rdap/dns.json"

    def __init__(self, client: httpx.AsyncClient, ttl_seconds: int = 86400) -> None:
        self.client = client
        self.ttl = timedelta(seconds=ttl_seconds)
        self._services: list[tuple[list[str], str]] | None = None
        self._loaded_at: datetime | None = None

    async def services(self) -> list[tuple[list[str], str]]:
        now = datetime.now(UTC)
        if self._services is not None and self._loaded_at and now - self._loaded_at < self.ttl:
            return self._services
        response = await request_with_retry(lambda: self.client.get(self.URL))
        response.raise_for_status()
        document = response.json()
        services: list[tuple[list[str], str]] = []
        for entry in document.get("services", []):
            if not isinstance(entry, list) or len(entry) != 2:
                continue
            tlds, urls = entry
            if isinstance(tlds, list) and isinstance(urls, list) and urls and isinstance(urls[0], str):
                services.append(([str(tld).lower() for tld in tlds], urls[0].rstrip("/") + "/"))
        self._services, self._loaded_at = services, now
        return services

    async def endpoint_for(self, domain: str) -> str | None:
        labels = domain.lower().rstrip(".").split(".")
        services = await self.services()
        for index in range(len(labels)):
            suffix = ".".join(labels[index:])
            for tlds, endpoint in services:
                if suffix in tlds:
                    return endpoint
        return None
