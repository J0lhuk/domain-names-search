from __future__ import annotations

import asyncio
import re
from datetime import datetime

from ..models import RegistryResult, RegistryStatus


class RuWhoisProvider:
    """Official TCI WHOIS fallback for .ru/.рф. Query only when RDAP has no endpoint."""

    host = "whois.tcinet.ru"
    port = 43

    async def lookup(self, domain: str) -> RegistryResult:
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(self.host, self.port), timeout=10)
            writer.write((domain + "\r\n").encode("ascii"))
            await writer.drain()
            payload = await asyncio.wait_for(reader.read(-1), timeout=10)
            writer.close()
            await writer.wait_closed()
        except (OSError, TimeoutError, UnicodeError) as error:
            return RegistryResult(status=RegistryStatus.UNKNOWN, source="whois_ru", detail=f"network error: {type(error).__name__}")
        text = payload.decode("utf-8", errors="replace")
        if re.search(r"No entries found|NOT FOUND|% No entries", text, re.IGNORECASE):
            return RegistryResult(status=RegistryStatus.NOT_FOUND, source="whois_ru", detail="official WHOIS did not find a record")
        if not re.search(r"^(domain|nserver):", text, re.IGNORECASE | re.MULTILINE):
            return RegistryResult(status=RegistryStatus.UNKNOWN, source="whois_ru", detail="unrecognised WHOIS response")
        fields = dict(re.findall(r"^([\w-]+):\s*(.+)$", text, re.MULTILINE))
        def date(name: str) -> datetime | None:
            value = fields.get(name)
            try:
                return datetime.fromisoformat(value) if value else None
            except ValueError:
                return None
        return RegistryResult(status=RegistryStatus.REGISTERED, source="whois_ru", current_creation_date=date("created"), current_expiration_date=date("paid-till"), registrar=fields.get("registrar"), nameservers=re.findall(r"^nserver:\s*(\S+)", text, re.MULTILINE | re.IGNORECASE), detail="official RU/RF WHOIS record")
