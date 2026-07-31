from __future__ import annotations

from datetime import datetime

import httpx

from ..models import RegistryResult, RegistryStatus
from .http import request_with_retry
from .iana import IanaBootstrapProvider


def _parse_date(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class RdapProvider:
    def __init__(self, client: httpx.AsyncClient, bootstrap: IanaBootstrapProvider) -> None:
        self.client = client
        self.bootstrap = bootstrap

    async def lookup(self, domain: str) -> RegistryResult:
        endpoint = await self.bootstrap.endpoint_for(domain)
        if endpoint is None:
            return RegistryResult(status=RegistryStatus.UNKNOWN, source="rdap", detail="no IANA RDAP endpoint")
        try:
            response = await request_with_retry(lambda: self.client.get(f"{endpoint}domain/{domain}"))
        except httpx.HTTPError as error:
            return RegistryResult(status=RegistryStatus.UNKNOWN, source="rdap", detail=f"network error: {type(error).__name__}")
        if response.status_code == 404:
            return RegistryResult(status=RegistryStatus.NOT_FOUND, source="rdap", detail="authoritative endpoint returned 404")
        if response.status_code == 429:
            return RegistryResult(status=RegistryStatus.UNKNOWN, source="rdap", detail="rate limited")
        if response.status_code >= 400:
            return RegistryResult(status=RegistryStatus.UNKNOWN, source="rdap", detail=f"HTTP {response.status_code}")
        try:
            data = response.json()
        except ValueError:
            return RegistryResult(status=RegistryStatus.UNKNOWN, source="rdap", detail="invalid JSON")
        if data.get("objectClassName") != "domain":
            return RegistryResult(status=RegistryStatus.UNKNOWN, source="rdap", detail="not a domain object")
        events = {event.get("eventAction"): _parse_date(event.get("eventDate")) for event in data.get("events", []) if isinstance(event, dict)}
        registrar = None
        for entity in data.get("entities", []):
            if isinstance(entity, dict) and "registrar" in entity.get("roles", []):
                vcard = entity.get("vcardArray", [None, []])
                if isinstance(vcard, list) and len(vcard) > 1:
                    for item in vcard[1]:
                        if isinstance(item, list) and item and item[0] == "fn" and len(item) > 3:
                            registrar = str(item[3])
                            break
        nameservers = [str(item.get("ldhName")) for item in data.get("nameservers", []) if isinstance(item, dict) and item.get("ldhName")]
        return RegistryResult(status=RegistryStatus.REGISTERED, source="rdap", current_creation_date=events.get("registration"), current_expiration_date=events.get("expiration"), registrar=registrar, nameservers=nameservers, detail="authoritative RDAP domain object")
