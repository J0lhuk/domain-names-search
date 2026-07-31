from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class RegistrarConfig(BaseModel):
    kind: str = "godaddy"
    endpoint_env: str = "GODADDY_AVAILABILITY_URL"
    token_env: str = "GODADDY_PAT"

    @property
    def endpoint(self) -> str | None:
        return os.getenv(self.endpoint_env) or None

    @property
    def token(self) -> str | None:
        return os.getenv(self.token_env) or None


class HistoryConfig(BaseModel):
    wayback: bool = True
    certificate_transparency: bool = False
    historical_whois_endpoint_env: str = "DOMAIN_CHECKER_HISTORICAL_WHOIS_URL"
    historical_whois_token_env: str = "DOMAIN_CHECKER_HISTORICAL_WHOIS_TOKEN"

    @property
    def historical_whois_endpoint(self) -> str | None:
        return os.getenv(self.historical_whois_endpoint_env) or None

    @property
    def historical_whois_token(self) -> str | None:
        return os.getenv(self.historical_whois_token_env) or None


class Settings(BaseModel):
    user_agent: str = "domain-availability-checker/0.1"
    concurrency: int = Field(default=8, ge=1, le=50)
    cache_ttl_seconds: int = Field(default=86400, ge=1)
    registrar: RegistrarConfig = Field(default_factory=RegistrarConfig)
    history: HistoryConfig = Field(default_factory=HistoryConfig)


def load_settings(path: Path | None) -> Settings:
    if path is None:
        return Settings()
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise TypeError("configuration root must be a mapping")
    return Settings.model_validate(data)
