"""
A small in-memory deploy history.

The agent's rollback rule needs to know "did this thing get deployed
recently", so we need some deploy records to check against. Timestamps are
generated relative to process start time (not hard-coded dates) so that one
deploy always lands "recently" shortly after the app boots - otherwise
anyone running this a week from now would never see the rollback rule fire.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from app.registry import all_canonical_ids


@dataclass
class DeployRecord:
    entity_id: str
    deployed_at: float
    version: str


_DEPLOY_HISTORY: list[DeployRecord] = []


def init_deploy_history() -> None:
    """Called once on app startup. Seeds one "just happened" deploy for the
    checkout service (so you can watch the rollback rule fire soon after
    boot) and a handful of older deploys for everything else.
    """
    _DEPLOY_HISTORY.clear()
    now = time.time()

    # This one is recent on purpose - it's what triggers the rollback rule
    # once checkout starts looking unhealthy.
    _DEPLOY_HISTORY.append(
        DeployRecord(entity_id="service:checkout", deployed_at=now - 90, version="v2.14.0")
    )

    # Everything else got deployed "a while ago" (outside the rollback
    # window), so those entities fall through to the other rules instead.
    stale_offset = 60 * 60 * 6  # 6 hours ago
    for i, entity_id in enumerate(all_canonical_ids()):
        if entity_id == "service:checkout":
            continue
        _DEPLOY_HISTORY.append(
            DeployRecord(
                entity_id=entity_id,
                deployed_at=now - stale_offset - i * 300,
                version=f"v1.{i}.0",
            )
        )


def recent_deploys_for(entity_id: str, window_seconds: float = 600, limit: int = 5) -> list[DeployRecord]:
    """Deploys for this entity within the last `window_seconds`, newest
    first. The agent uses an empty result here to mean "no recent deploy".
    """
    now = time.time()
    matches = [
        d
        for d in _DEPLOY_HISTORY
        if d.entity_id == entity_id and (now - d.deployed_at) <= window_seconds
    ]
    return sorted(matches, key=lambda d: d.deployed_at, reverse=True)[:limit]


def all_deploys_for(entity_id: str, limit: int = 5) -> list[DeployRecord]:
    matches = [d for d in _DEPLOY_HISTORY if d.entity_id == entity_id]
    return sorted(matches, key=lambda d: d.deployed_at, reverse=True)[:limit]
