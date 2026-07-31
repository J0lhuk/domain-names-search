# Implementation plan

1. Establish typed domain models, normalization and deterministic status reconciliation.
2. Add authoritative registry lookups (IANA-bootstrap RDAP and RU/RF WHOIS fallback), optional registrar confirmation, and opt-in history sources.
3. Persist every completed result to SQLite and JSONL, then export review-friendly CSV/JSON.
4. Cover all decisions with offline tests; live requests remain an explicit user action.
