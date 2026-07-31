from __future__ import annotations

from datetime import UTC, datetime

from .models import AvailabilityResult, AvailabilityStatus, Evidence, RegistryResult, RegistryStatus


def reconcile(registry: RegistryResult, availability: AvailabilityResult | None) -> tuple[
    AvailabilityStatus, str, str | None, list[Evidence]
]:
    """Return availability status, confidence, conflict reason and safe evidence."""
    checked_at = datetime.now(UTC)
    evidence = [
        Evidence(source=registry.source, checked_at=checked_at, detail=registry.detail or registry.status),
    ]
    if availability:
        evidence.append(Evidence(source=availability.source, checked_at=checked_at, detail=availability.detail or availability.status))

    if registry.status == RegistryStatus.INVALID:
        return AvailabilityStatus.UNKNOWN, "none", "invalid domain", evidence
    if registry.status == RegistryStatus.REGISTERED:
        if availability and availability.status in {AvailabilityStatus.AVAILABLE, AvailabilityStatus.PREMIUM_AVAILABLE}:
            return AvailabilityStatus.UNKNOWN, "low", "registry says registered, registrar says purchasable", evidence
        return AvailabilityStatus.REGISTERED, "high", None, evidence
    if registry.status != RegistryStatus.NOT_FOUND or availability is None:
        return AvailabilityStatus.UNKNOWN, "low", None, evidence
    if availability.status == AvailabilityStatus.AVAILABLE:
        return AvailabilityStatus.AVAILABLE, "high", None, evidence
    if availability.status == AvailabilityStatus.PREMIUM_AVAILABLE:
        return AvailabilityStatus.PREMIUM_AVAILABLE, "high", None, evidence
    if availability.status in {AvailabilityStatus.RESERVED, AvailabilityStatus.UNSUPPORTED_TLD}:
        return availability.status, "high", None, evidence
    if availability.status == AvailabilityStatus.REGISTERED:
        return AvailabilityStatus.UNKNOWN, "low", "registry says not found, registrar says registered", evidence
    return AvailabilityStatus.UNKNOWN, "low", None, evidence
