# CogniPrime — The Intelligence Architect

CogniPrime is an **Agentic-OS**: a recursive, self-healing operating layer that
reads across an entire corporate ecosystem and acts on it autonomously. Instead
of a chat interface, it runs a control loop that continuously maps your empire,
heals its production code, and spins off new lines of business — each
irreversible action gated behind explicit approval.

## The three subsystems

- **Infinite-Context Core** — a continuous recursive RAG loop that maps the
  corporate ecosystem, codebase, and financial architecture into one queryable
  context.
- **Snap-Off Engine** — detects operational bottlenecks and market
  opportunities, generates the repositories and APIs a new venture needs, and
  provisions its infrastructure.
- **Self-Healing Compiler** — monitors production code across all holdings,
  diagnoses vulnerabilities and logic errors, and proposes patches before
  systems experience downtime.

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full design.

## Install

```bash
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=sk-ant-...
```

CogniPrime reasons through Claude (`claude-opus-4-8` by default, adaptive
thinking). A credential is only needed to actually run the model — the library
imports and tests run without one.

## Quickstart

```python
from cogniprime import CogniPrime, CogniPrimeConfig
from cogniprime.approval import CallbackGate, ActionRequest
from cogniprime.core.data_layers import StaticLayer, Document, LayerKind
from cogniprime.healing.monitor import HeuristicMonitor, CodeUnit


def ask_human(req: ActionRequest) -> bool:
    return input(f"Approve: {req.summary}? [y/N] ").strip().lower() == "y"


config = CogniPrimeConfig(effort="high")
os = CogniPrime(config, approval=CallbackGate(ask_human))

# Map the empire through data layers.
os.register_layer(StaticLayer(LayerKind.OPERATIONAL, [
    Document("op1", LayerKind.OPERATIONAL, "Checkout", "checkout failure rate rising"),
]))

# Watch production code.
monitor = HeuristicMonitor()
monitor.register(CodeUnit("cfg", "app/config.py", "password = 'hunter2'\n", holding="acme"))
os.attach_monitor(monitor)

# Run one cycle of the operating system: map → heal → spin off.
result = os.tick()
for line in result.trace:
    print(line)
```

Or run a single inert tick from the CLI:

```bash
cogniprime --effort high
```

## Safety

CogniPrime is autonomous, so the guardrails are structural:

- **Deny-by-default approval** — nothing irreversible runs without an explicit
  approval gate.
- **Generate/act split** — reasoning and generation always run; side effects
  (provisioning, patching, launching) are gated.
- **Bounded recursion** — the context loop is capped by `max_recursion_depth`.
- **Escalation** — risky fixes are never auto-applied, even under approve-all.
- **Auditability** — every decision carries a trace.

## Development

```bash
pip install -e ".[dev]"
pytest        # 14 tests, no network required (LLM is injected)
ruff check .
```

The test suite injects a fake Claude client, so the full control flow — recursive
RAG, opportunity detection, healing, and the approval gates — is exercised
deterministically without API calls.
