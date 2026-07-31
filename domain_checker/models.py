from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RegistryStatus(StrEnum):
    REGISTERED = "registered"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"
    INVALID = "invalid"


class AvailabilityStatus(StrEnum):
    AVAILABLE = "available"
    PREMIUM_AVAILABLE = "premium_available"
    REGISTERED = "registered"
    RESERVED = "reserved"
    UNSUPPORTED_TLD = "unsupported_tld"
    UNKNOWN = "unknown"


class HistoryStatus(StrEnum):
    CONFIRMED = "confirmed_registration_history"
    INDIRECT = "web_or_dns_history_only"
    NONE = "no_history_found"
    NOT_CHECKED = "not_checked"
    UNKNOWN = "unknown"


class Evidence(BaseModel):
    source: str
    checked_at: datetime
    detail: str


class RegistryResult(BaseModel):
    status: RegistryStatus
    source: str
    current_creation_date: datetime | None = None
    current_expiration_date: datetime | None = None
    registrar: str | None = None
    nameservers: list[str] = Field(default_factory=list)
    detail: str = ""


class AvailabilityResult(BaseModel):
    status: AvailabilityStatus
    source: str
    price: float | None = None
    currency: str | None = None
    detail: str = ""


class HistoryResult(BaseModel):
    confirmed_registration_date: datetime | None = None
    earliest_web_capture: datetime | None = None
    earliest_certificate_date: datetime | None = None
    earliest_passive_dns_date: datetime | None = None
    errors: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class DomainResult(BaseModel):
    input_name: str
    domain_unicode: str
    domain_ascii: str
    tld: str
    checked_at: datetime
    registry_status: RegistryStatus
    availability_status: AvailabilityStatus
    availability_provider: str | None = None
    price: float | None = None
    currency: str | None = None
    premium: bool = False
    current_creation_date: datetime | None = None
    current_expiration_date: datetime | None = None
    registrar: str | None = None
    historical_registration_date: datetime | None = None
    earliest_web_capture: datetime | None = None
    earliest_certificate_date: datetime | None = None
    earliest_passive_dns_date: datetime | None = None
    earliest_observed_date: datetime | None = None
    history_status: HistoryStatus = HistoryStatus.NOT_CHECKED
    confidence: str = "low"
    evidence: list[Evidence] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    conflict_reason: str | None = None

    def as_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
