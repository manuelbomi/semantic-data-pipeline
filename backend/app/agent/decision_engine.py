"""
The example agent.

To be upfront about what this is: it's a small, rule-based decision engine,
not a machine-learning model and not an LLM. That's a deliberate choice,
not a shortcut - the point of this project is to prove the data substrate
underneath an agent is trustworthy and queryable, and a rule-based engine
makes every decision traceable back to the exact facts and rule that
produced it, which is exactly what you'd want before trusting *any* kind of
agent (rule-based or ML) to act on production infrastructure.

`decide()` is a pure function on purpose: given the same facts, it always
returns the same decision, and it doesn't touch the store, the clock (other
than what's passed in), or anything else with side effects. That's what
makes backend/tests/test_decision_engine.py able to test the rules with
plain fixtures instead of having to spin up the whole pipeline.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict

from app.models import Decision

# How long a recent deploy still counts as "recent" for the rollback rule.
ROLLBACK_DEPLOY_WINDOW_SECONDS = 600

# Don't re-decide for the same entity more often than this. Without a
# cooldown, an entity that stays unhealthy for a full minute would produce
# twenty near-identical decisions instead of one, which isn't how you'd
# want an on-call engineer paged either.
DECISION_COOLDOWN_SECONDS = 30


def decide(
    entity_id: str,
    health: str,
    recent_deploys: list[dict],
    dependency_healths: dict[str, str],
    now: float,
) -> dict | None:
    """Returns a plain dict with action/rule/reasoning/facts, or None if
    this entity doesn't need a decision right now (it's healthy).
    """
    if health != "unhealthy":
        return None

    facts = {
        "health": health,
        "recent_deploys": recent_deploys,
        "dependency_healths": dependency_healths,
    }

    if recent_deploys:
        deploy = recent_deploys[0]
        age_s = round(now - deploy["deployed_at"])
        return {
            "action": "rollback",
            "rule": "recent_deploy_before_incident",
            "reasoning": (
                f"{entity_id} is unhealthy and version {deploy['version']} was deployed "
                f"{age_s}s ago, inside the {ROLLBACK_DEPLOY_WINDOW_SECONDS}s rollback "
                f"window. The most likely cause is the new code, so rolling back is safer "
                f"than restarting into the same build."
            ),
            "facts": facts,
        }

    unhealthy_deps = [dep for dep, h in dependency_healths.items() if h == "unhealthy"]
    if unhealthy_deps:
        return {
            "action": "investigate_dependency",
            "rule": "unhealthy_dependency",
            "reasoning": (
                f"{entity_id} is unhealthy, but it has no recent deploy, and it depends on "
                f"{unhealthy_deps[0]}, which is also unhealthy right now. The dependency is "
                f"the more likely root cause, so investigate {unhealthy_deps[0]} before "
                f"touching {entity_id}."
            ),
            "facts": facts,
        }

    return {
        "action": "restart",
        "rule": "isolated_failure",
        "reasoning": (
            f"{entity_id} is unhealthy, has no recent deploy, and everything it depends on "
            f"is healthy. This looks like an isolated failure (a stuck process, a bad node), "
            f"so a restart is the reasonable first move."
        ),
        "facts": facts,
    }


class DecisionEngine:
    """Wires the pure `decide()` function up to the semantic layer store:
    reads current facts for each entity, applies the cooldown, and records
    any decision it makes.
    """

    def __init__(self, store) -> None:
        self._store = store
        self._decisions: list[Decision] = []
        self._last_decision_at: dict[str, float] = {}

    def evaluate_all(self) -> list[Decision]:
        now = time.time()
        new_decisions: list[Decision] = []
        for state in self._store.all_states():
            last = self._last_decision_at.get(state.entity_id)
            if last is not None and now - last < DECISION_COOLDOWN_SECONDS:
                continue

            dependency_healths = {}
            for dep_id in state.dependency_context.get("depends_on", []):
                dep_state = self._store.get(dep_id)
                if dep_state is not None:
                    dependency_healths[dep_id] = dep_state.health(now)

            result = decide(
                entity_id=state.entity_id,
                health=state.health(now),
                recent_deploys=state.recent_deploys,
                dependency_healths=dependency_healths,
                now=now,
            )
            if result is None:
                continue

            decision = Decision(
                decision_id=str(uuid.uuid4()),
                entity_id=state.entity_id,
                created_at=now,
                action=result["action"],
                rule=result["rule"],
                reasoning=result["reasoning"],
                facts=result["facts"],
            )
            self._decisions.append(decision)
            self._last_decision_at[state.entity_id] = now
            new_decisions.append(decision)

        return new_decisions

    def recent(self, limit: int = 50) -> list[dict]:
        return [asdict(d) for d in self._decisions[-limit:][::-1]]
