import pytest

from domain_checker.models import (
    AvailabilityResult,
    AvailabilityStatus,
    RegistryResult,
    RegistryStatus,
)
from domain_checker.reconciliation import reconcile


@pytest.mark.parametrize(
    ("registry", "registrar", "expected", "conflict"),
    [
        (RegistryStatus.REGISTERED, AvailabilityStatus.REGISTERED, AvailabilityStatus.REGISTERED, None),
        (RegistryStatus.NOT_FOUND, AvailabilityStatus.AVAILABLE, AvailabilityStatus.AVAILABLE, None),
        (RegistryStatus.NOT_FOUND, AvailabilityStatus.PREMIUM_AVAILABLE, AvailabilityStatus.PREMIUM_AVAILABLE, None),
        (RegistryStatus.NOT_FOUND, AvailabilityStatus.RESERVED, AvailabilityStatus.RESERVED, None),
        (RegistryStatus.UNKNOWN, AvailabilityStatus.AVAILABLE, AvailabilityStatus.UNKNOWN, None),
        (RegistryStatus.REGISTERED, AvailabilityStatus.AVAILABLE, AvailabilityStatus.UNKNOWN, "registry says registered, registrar says purchasable"),
        (RegistryStatus.NOT_FOUND, AvailabilityStatus.REGISTERED, AvailabilityStatus.UNKNOWN, "registry says not found, registrar says registered"),
    ],
)
def test_reconciliation_table(registry: RegistryStatus, registrar: AvailabilityStatus, expected: AvailabilityStatus, conflict: str | None) -> None:
    status, _, reason, _ = reconcile(RegistryResult(status=registry, source="test"), AvailabilityResult(status=registrar, source="test"))
    assert status == expected
    assert reason == conflict
