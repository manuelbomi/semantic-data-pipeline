import time

from app.agent.decision_engine import decide


def test_healthy_entity_gets_no_decision():
    result = decide("service:checkout", "healthy", [], {}, now=time.time())
    assert result is None


def test_recent_deploy_triggers_rollback():
    now = time.time()
    recent_deploys = [{"entity_id": "service:checkout", "deployed_at": now - 90, "version": "v2.14.0"}]
    result = decide("service:checkout", "unhealthy", recent_deploys, {}, now=now)
    assert result["action"] == "rollback"
    assert result["rule"] == "recent_deploy_before_incident"
    assert "v2.14.0" in result["reasoning"]


def test_unhealthy_dependency_triggers_investigate_dependency():
    now = time.time()
    result = decide(
        "service:checkout",
        "unhealthy",
        recent_deploys=[],
        dependency_healths={"service:payments": "unhealthy", "service:inventory": "healthy"},
        now=now,
    )
    assert result["action"] == "investigate_dependency"
    assert result["rule"] == "unhealthy_dependency"
    assert "service:payments" in result["reasoning"]


def test_isolated_failure_triggers_restart():
    now = time.time()
    result = decide(
        "host:use1-web-01",
        "unhealthy",
        recent_deploys=[],
        dependency_healths={"service:payments": "healthy"},
        now=now,
    )
    assert result["action"] == "restart"
    assert result["rule"] == "isolated_failure"


def test_recent_deploy_takes_priority_over_unhealthy_dependency():
    # If both conditions are true, rollback is checked first - a brand new
    # deploy is a more likely and more directly actionable cause than a
    # pre-existing dependency problem.
    now = time.time()
    recent_deploys = [{"entity_id": "service:checkout", "deployed_at": now - 30, "version": "v2.14.1"}]
    result = decide(
        "service:checkout",
        "unhealthy",
        recent_deploys,
        dependency_healths={"service:payments": "unhealthy"},
        now=now,
    )
    assert result["action"] == "rollback"


def test_facts_are_included_for_the_reasoning_trace():
    now = time.time()
    result = decide("service:checkout", "unhealthy", [], {"service:payments": "healthy"}, now=now)
    assert result["facts"]["health"] == "unhealthy"
    assert result["facts"]["dependency_healths"] == {"service:payments": "healthy"}
