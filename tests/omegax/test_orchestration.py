"""Tests for orchestration: swarm, hooks, episodic memory, red-team."""

from __future__ import annotations

from omegax.core.orchestration.episodic_memory import Episode, EpisodicMemory
from omegax.core.orchestration.hooks import (
    HookDispatcher,
    HookEvent,
    ToolCall,
    secret_guard,
    shell_sanitizer,
)
from omegax.core.orchestration.red_team import (
    AdversarialProbe,
    RedTeamArbitrator,
    Verdict,
)
from omegax.core.orchestration.swarm import SubAgentSwarm, SwarmTask
from omegax.sandbox.runner import InProcessValidator


# -- swarm -------------------------------------------------------------------


def test_swarm_runs_tasks_concurrently_and_isolates_failures() -> None:
    def ok(n: int):
        return lambda: n * 2

    def boom():
        raise ValueError("fail")

    tasks = [
        SwarmTask("a", ok(1)),
        SwarmTask("b", ok(5)),
        SwarmTask("c", boom),
    ]
    result = SubAgentSwarm(max_workers=8).run(tasks)
    assert result.results["a"] == 2
    assert result.results["b"] == 10
    assert "c" in result.errors
    assert result.ok is False
    assert result.completed == 2


def test_swarm_worker_cap_enforced() -> None:
    swarm = SubAgentSwarm(max_workers=1000)
    assert swarm.max_workers == 64  # MAX_WORKERS_CAP


# -- hooks -------------------------------------------------------------------


def test_pre_tool_use_veto_blocks_dangerous_shell() -> None:
    dispatcher = HookDispatcher()
    dispatcher.register(HookEvent.PRE_TOOL_USE, shell_sanitizer)

    danger = ToolCall(tool="bash", args={"command": "rm -rf / --no-preserve-root"})
    safe = ToolCall(tool="bash", args={"command": "pytest -q"})

    assert dispatcher.pre_tool_use(danger).allowed is False
    assert dispatcher.pre_tool_use(safe).allowed is True


def test_secret_guard_blocks_env_access() -> None:
    dispatcher = HookDispatcher()
    dispatcher.register(HookEvent.PRE_TOOL_USE, secret_guard)
    call = ToolCall(tool="read", args={"path": "/app/.env"})
    assert dispatcher.pre_tool_use(call).allowed is False


def test_post_tool_use_and_stop_run_observers() -> None:
    dispatcher = HookDispatcher()
    seen: list[str] = []
    dispatcher.register(HookEvent.POST_TOOL_USE, lambda c: (seen.append(c.tool), (True, ""))[1])
    dispatcher.register(HookEvent.STOP, lambda c: (seen.append("stop"), (True, ""))[1])

    dispatcher.post_tool_use(ToolCall(tool="edit"))
    dispatcher.stop()
    assert seen == ["edit", "stop"]
    assert any("PostToolUse edit" in line for line in dispatcher.audit_log)


# -- episodic memory ---------------------------------------------------------


def test_episodic_memory_records_and_recalls() -> None:
    mem = EpisodicMemory()
    mem.record(Episode("e1", "fix flaky auth test", "root-caused a race", True, "add a lock"))
    mem.record(Episode("e2", "optimize image pipeline", "cut latency 30%", True, "batch resizes"))

    hits = mem.recall("auth test race")
    assert hits and hits[0].episode_id == "e1"
    assert "add a lock" in mem.lessons(successful_only=True)


# -- red-team arbitrator -----------------------------------------------------


def test_red_team_blocks_on_critical_probe_failure() -> None:
    # The probe "passes" only if the candidate contains a guard clause.
    runner = InProcessValidator(lambda code: ("validate(" in code, "needs input validation"))
    probe = AdversarialProbe(
        name="input-validation",
        build=lambda candidate: candidate,  # feed candidate straight to the checker
        critical=True,
    )
    arbitrator = RedTeamArbitrator(runner, [probe])

    vulnerable = arbitrator.arbitrate("def handler(x): return run(x)")
    assert vulnerable.verdict is Verdict.BLOCK
    assert vulnerable.training_items()  # findings become training targets

    hardened = arbitrator.arbitrate("def handler(x):\n    validate(x)\n    return run(x)")
    assert hardened.verdict is Verdict.APPROVE
    assert hardened.approved
