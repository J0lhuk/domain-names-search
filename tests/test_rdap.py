import httpx
import pytest

from domain_checker.models import RegistryStatus
from domain_checker.providers.iana import IanaBootstrapProvider
from domain_checker.providers.rdap import RdapProvider
from domain_checker.providers.registrar import GoDaddyRegistrarProvider


@pytest.mark.asyncio
async def test_iana_longest_match() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"services": [[['com'], ['https://com.example/']], [['uk', 'co.uk'], ['https://uk.example/']]]}))
    async with httpx.AsyncClient(transport=transport) as client:
        provider = IanaBootstrapProvider(client)
        assert await provider.endpoint_for("a.co.uk") == "https://uk.example/"


@pytest.mark.asyncio
async def test_rdap_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "data.iana.org":
            return httpx.Response(200, json={"services": [[['com'], ['https://rdap.example/']]]})
        return httpx.Response(404)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await RdapProvider(client, IanaBootstrapProvider(client)).lookup("free.com")
    assert result.status == RegistryStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_rdap_registered_dates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "data.iana.org":
            return httpx.Response(200, json={"services": [[['com'], ['https://rdap.example/']]]})
        return httpx.Response(200, json={"objectClassName": "domain", "events": [{"eventAction": "registration", "eventDate": "2020-01-01T00:00:00Z"}], "nameservers": [{"ldhName": "ns.example"}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await RdapProvider(client, IanaBootstrapProvider(client)).lookup("taken.com")
    assert result.status == RegistryStatus.REGISTERED
    assert result.current_creation_date is not None


@pytest.mark.asyncio
async def test_rdap_rate_limited_is_unknown() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "data.iana.org":
            return httpx.Response(200, json={"services": [[['com'], ['https://rdap.example/']]]})
        return httpx.Response(429)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await RdapProvider(client, IanaBootstrapProvider(client)).lookup("slow.com")
    assert result.status == RegistryStatus.UNKNOWN
    assert result.detail == "rate limited"


@pytest.mark.asyncio
async def test_rdap_malformed_json_is_unknown() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "data.iana.org":
            return httpx.Response(200, json={"services": [[['com'], ['https://rdap.example/']]]})
        return httpx.Response(200, content=b"not JSON")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await RdapProvider(client, IanaBootstrapProvider(client)).lookup("broken.com")
    assert result.status == RegistryStatus.UNKNOWN


@pytest.mark.asyncio
async def test_godaddy_available_and_price() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-token"
        return httpx.Response(200, json={"domain": "free.com", "available": True, "prices": [{"price": {"value": 1199, "currencyCode": "USD"}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await GoDaddyRegistrarProvider(client, "https://api.godaddy.test/v3/domains/check-availability", "test-token").check("free.com")
    assert result.status.value == "available"
    assert result.price == 11.99
    assert result.currency == "USD"
