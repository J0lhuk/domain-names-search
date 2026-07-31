from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx

from .config import Settings
from .models import (
    AvailabilityResult,
    AvailabilityStatus,
    DomainResult,
    HistoryStatus,
    RegistryResult,
    RegistryStatus,
)
from .normalization import NormalizedDomain
from .providers.base import AvailabilityProvider, HistoryProvider
from .providers.history import (
    CertificateTransparencyProvider,
    HistoricalWhoisProvider,
    WaybackProvider,
    merge_history,
)
from .providers.iana import IanaBootstrapProvider
from .providers.rdap import RdapProvider
from .providers.registrar import (
    GenericRegistrarProvider,
    GoDaddyRegistrarProvider,
    NoRegistrarProvider,
)
from .providers.whois_ru import RuWhoisProvider
from .reconciliation import reconcile
from .storage import ResultStore


class Checker:
    def __init__(self, settings: Settings, store: ResultStore, client: httpx.AsyncClient, offline: dict[str, dict[str, str]] | None = None) -> None:
        self.settings, self.store, self.client, self.offline = settings, store, client, offline or {}
        bootstrap = IanaBootstrapProvider(client, settings.cache_ttl_seconds)
        self.rdap = RdapProvider(client, bootstrap)
        self.ru_whois = RuWhoisProvider()
        registrar_kind = settings.registrar.kind.lower()
        self.registrar: AvailabilityProvider
        if registrar_kind == "godaddy" and settings.registrar.token:
            self.registrar = GoDaddyRegistrarProvider(
                client,
                settings.registrar.endpoint or "https://api.godaddy.com/v3/domains/check-availability",
                settings.registrar.token,
            )
        elif settings.registrar.endpoint:
            self.registrar = GenericRegistrarProvider(client, settings.registrar.endpoint, settings.registrar.token)
        else:
            self.registrar = NoRegistrarProvider()
        self.history: list[HistoryProvider] = [HistoricalWhoisProvider(client, settings.history.historical_whois_endpoint, settings.history.historical_whois_token)]
        if settings.history.wayback:
            self.history.append(WaybackProvider(client))
        if settings.history.certificate_transparency:
            self.history.append(CertificateTransparencyProvider(client))

    async def registry_lookup(self, domain: str) -> RegistryResult:
        fixture = self.offline.get(domain, {})
        if fixture:
            status = RegistryStatus(fixture.get("registry_status", "not_found"))
            return RegistryResult(status=status, source="offline_fixture", detail="offline fixture")
        result = await self.rdap.lookup(domain)
        if result.status == RegistryStatus.UNKNOWN and result.detail == "no IANA RDAP endpoint" and domain.endswith((".ru", ".xn--p1ai")):
            return await self.ru_whois.lookup(domain)
        return result

    async def availability_lookup(self, domain: str) -> AvailabilityResult:
        fixture = self.offline.get(domain, {})
        if fixture:
            return AvailabilityResult(status=AvailabilityStatus(fixture.get("availability_status", "unknown")), source="offline_fixture", detail="offline fixture")
        return await self.registrar.check(domain)

    async def check_one(self, item: NormalizedDomain, force_refresh: bool = False) -> DomainResult:
        if not force_refresh:
            saved = self.store.get(item.ascii)
            if saved:
                return saved
        registry, availability = await asyncio.gather(self.registry_lookup(item.ascii), self.availability_lookup(item.ascii))
        status, confidence, conflict, evidence = reconcile(registry, availability)
        now = datetime.now(UTC)
        history_status = HistoryStatus.NOT_CHECKED
        historical = None
        if status in {AvailabilityStatus.AVAILABLE, AvailabilityStatus.PREMIUM_AVAILABLE}:
            parts = [] if self.offline else await asyncio.gather(*(provider.lookup(item.ascii) for provider in self.history))
            historical = merge_history(list(parts))
            evidence.extend(historical.evidence)
            if historical.confirmed_registration_date:
                history_status = HistoryStatus.CONFIRMED
            elif any([historical.earliest_web_capture, historical.earliest_certificate_date, historical.earliest_passive_dns_date]):
                history_status = HistoryStatus.INDIRECT
            elif historical.errors:
                history_status = HistoryStatus.UNKNOWN
            else:
                history_status = HistoryStatus.NONE
        dates = [date for date in ([historical.confirmed_registration_date, historical.earliest_web_capture, historical.earliest_certificate_date, historical.earliest_passive_dns_date] if historical else []) if date]
        result = DomainResult(input_name=item.input_name, domain_unicode=item.unicode, domain_ascii=item.ascii, tld=item.tld, checked_at=now, registry_status=registry.status, availability_status=status, availability_provider=availability.source, price=availability.price, currency=availability.currency, premium=status == AvailabilityStatus.PREMIUM_AVAILABLE, current_creation_date=registry.current_creation_date, current_expiration_date=registry.current_expiration_date, registrar=registry.registrar, historical_registration_date=historical.confirmed_registration_date if historical else None, earliest_web_capture=historical.earliest_web_capture if historical else None, earliest_certificate_date=historical.earliest_certificate_date if historical else None, earliest_passive_dns_date=historical.earliest_passive_dns_date if historical else None, earliest_observed_date=min(dates) if dates else None, history_status=history_status, confidence=confidence, evidence=evidence, errors=historical.errors if historical else [], conflict_reason=conflict)
        self.store.put(result)
        return result

    async def check_all(self, items: list[NormalizedDomain], force_refresh: bool = False) -> list[DomainResult]:
        semaphore = asyncio.Semaphore(self.settings.concurrency)
        async def guarded(item: NormalizedDomain) -> DomainResult:
            async with semaphore:
                return await self.check_one(item, force_refresh)
        return await asyncio.gather(*(guarded(item) for item in items))
