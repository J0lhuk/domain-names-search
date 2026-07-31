from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedDomain:
    input_name: str
    unicode: str
    ascii: str
    tld: str


class DomainValidationError(ValueError):
    pass


def _idna(value: str) -> str:
    try:
        return value.encode("idna").decode("ascii")
    except UnicodeError as error:
        raise DomainValidationError(f"IDNA conversion failed: {error}") from error


def normalize_domain(value: str) -> NormalizedDomain:
    original = value
    text = value.strip().rstrip(".").lstrip(".").lower()
    if not text or "." not in text:
        raise DomainValidationError("a full domain with a TLD is required")
    labels = text.split(".")
    ascii_labels = [_idna(label) for label in labels]
    if any(not label or len(label) > 63 for label in ascii_labels):
        raise DomainValidationError("empty label or label longer than 63 characters")
    for label in ascii_labels:
        if label.startswith("-") or label.endswith("-") or not all(
            char.isalnum() or char == "-" for char in label
        ):
            raise DomainValidationError(f"invalid label: {label}")
    ascii_domain = ".".join(ascii_labels)
    if len(ascii_domain) > 253:
        raise DomainValidationError("domain is longer than 253 characters")
    return NormalizedDomain(original, text, ascii_domain, ascii_labels[-1])


def expand_names(names: list[str], tlds: list[str]) -> list[NormalizedDomain]:
    expanded: dict[str, NormalizedDomain] = {}
    cleaned_tlds = [t.strip().lstrip(".").lower() for t in tlds if t.strip()]
    for raw in names:
        name = raw.strip()
        if not name:
            continue
        candidates = [name] if "." in name else [f"{name}.{tld}" for tld in cleaned_tlds]
        for candidate in candidates:
            domain = normalize_domain(candidate)
            expanded.setdefault(domain.ascii, domain)
    return list(expanded.values())
