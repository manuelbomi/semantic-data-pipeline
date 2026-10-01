"""
The canonical entity registry.

In a real company this would be a table that's kept in sync with your CMDB
or cloud inventory. Here it's a static in-memory table, but the shape is the
same: a canonical id, plus every alias that different source systems use to
refer to the same thing.

Why this file exists at all: a metrics agent on a box might call itself
"use1-web-01", the logging pipeline might tag lines with "USE1-WEB-01", and
an alert rule might reference "web01.use1.internal". Three different
strings, one real host. If you let every downstream consumer match on the
raw string, you end up with three different "entities" that are actually
one, and nothing lines up. entity_link.py uses this table to collapse all
of those strings back down to a single canonical_id.
"""
from __future__ import annotations

# canonical_id -> {"type": "host" | "service", "aliases": [...]}
CANONICAL_ENTITIES: dict[str, dict] = {
    "host:use1-web-01": {
        "type": "host",
        "aliases": ["use1-web-01", "USE1-WEB-01", "web01.use1.internal", "i-0a1b2c3d"],
    },
    "host:use1-web-02": {
        "type": "host",
        "aliases": ["use1-web-02", "USE1-WEB-02", "web02.use1.internal", "i-0a1b2c3e"],
    },
    "host:use1-pay-01": {
        "type": "host",
        "aliases": ["use1-pay-01", "USE1-PAY-01", "pay01.use1.internal", "i-0b2c3d4f"],
    },
    "host:use1-inv-01": {
        "type": "host",
        "aliases": ["use1-inv-01", "USE1-INV-01", "inv01.use1.internal", "i-0c3d4e5a"],
    },
    "service:checkout": {
        "type": "service",
        "aliases": ["checkout", "svc-checkout", "Checkout-Service", "checkout_svc"],
    },
    "service:payments": {
        "type": "service",
        "aliases": ["payments", "svc-payments", "Payments-Service", "payments_svc"],
    },
    "service:inventory": {
        "type": "service",
        "aliases": ["inventory", "svc-inventory", "Inventory-Service", "inventory_svc"],
    },
}

# Which host(s) each service currently runs on. Used by enrich.py to build
# dependency_context for the frontend's entity state view.
SERVICE_HOSTS: dict[str, list[str]] = {
    "service:checkout": ["host:use1-web-01", "host:use1-web-02"],
    "service:payments": ["host:use1-pay-01"],
    "service:inventory": ["host:use1-inv-01"],
}

# A simplified, static stand-in for the dependency edges you'd normally read
# out of a live knowledge graph: which services does this service call.
SERVICE_DEPENDENCIES: dict[str, list[str]] = {
    "service:checkout": ["service:payments", "service:inventory"],
    "service:payments": [],
    "service:inventory": [],
}

# Build a flat alias -> canonical_id lookup once, at import time, instead of
# scanning the whole table on every single event.
_ALIAS_LOOKUP: dict[str, str] = {}
for _canonical_id, _info in CANONICAL_ENTITIES.items():
    for _alias in _info["aliases"]:
        _ALIAS_LOOKUP[_alias.strip().lower()] = _canonical_id


def resolve_alias(raw_ref: str) -> str | None:
    """Look up a raw, possibly messy entity reference and return the
    canonical id, or None if nothing in the registry matches it.

    We lowercase and strip whitespace before comparing because the three
    simulated sources deliberately use different casing/formatting for the
    same underlying host or service.
    """
    return _ALIAS_LOOKUP.get(raw_ref.strip().lower())


def entity_type(canonical_id: str) -> str:
    return CANONICAL_ENTITIES[canonical_id]["type"]


def dependencies_of(canonical_id: str) -> list[str]:
    """Services this entity calls (depends on)."""
    return SERVICE_DEPENDENCIES.get(canonical_id, [])


def dependents_of(canonical_id: str) -> list[str]:
    """Services that call this entity (depend on it)."""
    return [svc for svc, deps in SERVICE_DEPENDENCIES.items() if canonical_id in deps]


def all_canonical_ids() -> list[str]:
    return list(CANONICAL_ENTITIES.keys())
