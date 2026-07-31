import pytest

from domain_checker.normalization import DomainValidationError, expand_names, normalize_domain


def test_expands_deduplicates_and_normalizes() -> None:
    domains = expand_names([" Chat ", "chat", "пример"], ["com", ".ru"])
    assert [item.ascii for item in domains] == ["chat.com", "chat.ru", "xn--e1afmkfd.com", "xn--e1afmkfd.ru"]


def test_accepts_full_domain() -> None:
    assert expand_names(["Chat.COM."], ["ru"])[0].ascii == "chat.com"


@pytest.mark.parametrize("value", ["", "example", "-bad.com", "bad-.com", "a..com"])
def test_rejects_invalid_domain(value: str) -> None:
    with pytest.raises(DomainValidationError):
        normalize_domain(value)
