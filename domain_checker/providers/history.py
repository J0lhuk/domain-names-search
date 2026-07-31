from __future__ import annotations

from datetime import UTC, datetime

import httpx

from ..models import Evidence, HistoryResult
from .http import request_with_retry


def _date(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class WaybackProvider:
    URL = "https://web.archive.org/cdx/search/cdx"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def lookup(self, domain: str) -> HistoryResult:
        try:
            response = await request_with_retry(
                lambda: self.client.get(self.URL, params={"url": f"{domain}/*", "output": "json", "filter": "statuscode:200", "fl": "timestamp", "collapse": "timestamp:8", "limit": "1"})
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as error:
            return HistoryResult(errors=[f"wayback: {type(error).__name__}"])
        if not isinstance(data, list) or len(data) < 2 or not isinstance(data[1], list) or not data[1]:
            return HistoryResult()
        stamp = str(data[1][0])
        try:
            date = datetime.strptime(stamp[:14], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        except ValueError:
            return HistoryResult(errors=["wayback: invalid timestamp"])
        return HistoryResult(earliest_web_capture=date, evidence=[Evidence(source="wayback", checked_at=datetime.now().astimezone(), detail="earliest archived successful capture")])


class CertificateTransparencyProvider:
    """Optional crt.sh query. Its date is evidence of a certificate, not registration."""

    URL = "https://crt.sh/"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def lookup(self, domain: str) -> HistoryResult:
        try:
            response = await request_with_retry(
                lambda: self.client.get(self.URL, params={"q": domain, "output": "json"})
            )
            response.raise_for_status()
            rows = response.json()
        except (httpx.HTTPError, ValueError) as error:
            return HistoryResult(errors=[f"certificate_transparency: {type(error).__name__}"])
        dates: list[datetime] = []
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    date = _date(row.get("not_before"))
                    if date is not None:
                        dates.append(date)
        if not dates:
            return HistoryResult()
        return HistoryResult(earliest_certificate_date=min(dates), evidence=[Evidence(source="certificate_transparency", checked_at=datetime.now().astimezone(), detail="earliest public certificate")])


class HistoricalWhoisProvider:
    """Contract adapter; only runs when a legitimate historical API is configured."""

    def __init__(self, client: httpx.AsyncClient, endpoint: str | None, token: str | None) -> None:
        self.client, self.endpoint, self.token = client, endpoint, token

    async def lookup(self, domain: str) -> HistoryResult:
        endpoint = self.endpoint
        if not endpoint:
            return HistoryResult()
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        try:
            response = await request_with_retry(
                lambda: self.client.get(endpoint, params={"domain": domain}, headers=headers)
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as error:
            return HistoryResult(errors=[f"historical_whois: {type(error).__name__}"])
        date = _date(data.get("first_registration_date")) if isinstance(data, dict) else None
        evidence = [Evidence(source="historical_whois", checked_at=datetime.now().astimezone(), detail="provider supplied historical registration date")] if date else []
        return HistoryResult(confirmed_registration_date=date, evidence=evidence)


def merge_history(parts: list[HistoryResult]) -> HistoryResult:
    def earliest(field: str) -> datetime | None:
        values = [getattr(part, field) for part in parts if getattr(part, field) is not None]
        return min(values) if values else None
    return HistoryResult(confirmed_registration_date=earliest("confirmed_registration_date"), earliest_web_capture=earliest("earliest_web_capture"), earliest_certificate_date=earliest("earliest_certificate_date"), earliest_passive_dns_date=earliest("earliest_passive_dns_date"), errors=[error for part in parts for error in part.errors], evidence=[item for part in parts for item in part.evidence])
