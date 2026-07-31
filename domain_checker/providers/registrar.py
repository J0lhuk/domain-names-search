from __future__ import annotations

import httpx

from ..models import AvailabilityResult, AvailabilityStatus
from .http import request_with_retry


class NoRegistrarProvider:
    async def check(self, domain: str) -> AvailabilityResult:
        return AvailabilityResult(status=AvailabilityStatus.UNKNOWN, source="registrar", detail="registrar API is not configured")


class GoDaddyRegistrarProvider:
    """Read-only GoDaddy Domains v3 availability check using a PAT Bearer token."""

    def __init__(self, client: httpx.AsyncClient, endpoint: str, token: str) -> None:
        self.client, self.endpoint, self.token = client, endpoint, token

    async def check(self, domain: str) -> AvailabilityResult:
        try:
            response = await request_with_retry(
                lambda: self.client.get(
                    self.endpoint,
                    params={"domain": domain, "optimizeFor": "ACCURACY"},
                    headers={"Authorization": f"Bearer {self.token}"},
                )
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as error:
            return AvailabilityResult(status=AvailabilityStatus.UNKNOWN, source="godaddy", detail=f"provider error: {type(error).__name__}")
        if not isinstance(data, dict):
            return AvailabilityResult(status=AvailabilityStatus.UNKNOWN, source="godaddy", detail="unexpected response")
        if data.get("available") is not True:
            return AvailabilityResult(status=AvailabilityStatus.REGISTERED, source="godaddy", detail="GoDaddy reports unavailable")
        prices = data.get("prices")
        first_price = prices[0] if isinstance(prices, list) and prices and isinstance(prices[0], dict) else {}
        price_data = first_price.get("price", {}) if isinstance(first_price, dict) else {}
        raw_price = price_data.get("value") if isinstance(price_data, dict) else None
        price = float(raw_price) / 100 if isinstance(raw_price, (int, float)) else None
        currency = str(price_data["currencyCode"]) if isinstance(price_data, dict) and price_data.get("currencyCode") else None
        return AvailabilityResult(status=AvailabilityStatus.AVAILABLE, source="godaddy", price=price, currency=currency, detail="GoDaddy reports available")


class GenericRegistrarProvider:
    """Adapter for a documented registrar endpoint returning a simple JSON contract."""

    def __init__(self, client: httpx.AsyncClient, endpoint: str, token: str | None) -> None:
        self.client, self.endpoint, self.token = client, endpoint, token

    async def check(self, domain: str) -> AvailabilityResult:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        try:
            response = await request_with_retry(
                lambda: self.client.post(self.endpoint, json={"domain": domain}, headers=headers)
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as error:
            return AvailabilityResult(status=AvailabilityStatus.UNKNOWN, source="registrar", detail=f"provider error: {type(error).__name__}")
        mapping = {"available": AvailabilityStatus.AVAILABLE, "premium": AvailabilityStatus.PREMIUM_AVAILABLE, "registered": AvailabilityStatus.REGISTERED, "reserved": AvailabilityStatus.RESERVED, "unsupported_tld": AvailabilityStatus.UNSUPPORTED_TLD}
        status = mapping.get(str(data.get("status", "")).lower(), AvailabilityStatus.UNKNOWN)
        price = data.get("price")
        return AvailabilityResult(status=status, source="registrar", price=float(price) if isinstance(price, (int, float)) else None, currency=str(data["currency"]) if data.get("currency") else None, detail=f"registrar status: {data.get('status', 'unknown')}")
