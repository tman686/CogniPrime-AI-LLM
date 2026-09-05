# CogniPrime Architecture

CogniPrime is an **Agentic-OS**: a recursive, self-healing operating layer that
reads across an entire corporate ecosystem and acts on it autonomously. Rather
than a chat interface, it exposes a control loop — `tick()` — that maps the
empire, heals its production code, and spins off new lines of business.

This document describes the architecture implemented in this repository. It is
a working scaffold: the control flow, subsystem boundaries, and safety gates are
real and tested; connectors to live systems (vector DBs, cloud providers, git
hosts) are defined as interfaces with dependency-free reference implementations.

## System overview

```
                         ┌─────────────────────────────┐
                         │      CogniPrime (OS)         │
                         │      orchestrator.tick()     │
                         └──────────────┬──────────────┘
             map │ heal │ spin-off      │
        ┌───────────────────────────────┼───────────────────────────────┐
        ▼                               ▼                               ▼
┌───────────────────┐        ┌───────────────────┐         ┌───────────────────┐
│ Infinite-Context  │        │  Self-Healing     │         │   Snap-Off        │
│ Core              │        │  Compiler         │         │   Engine          │
│ recursive RAG     │◀──────▶│ monitor→diagnose  │         │ opportunity→      │
│ over data layers  │  query │ →patch (gated)    │         │ scaffold→provision│
└─────────┬─────────┘        └─────────┬─────────┘         └─────────┬─────────┘
          │                            │                             │
          ▼                            ▼                             ▼
   MemoryStore (RAG index)      ProductionMonitor            Provisioner + ApprovalGate
   DataLayer × {code, infra,    (telemetry / static          (infrastructure, gated
    financial, operational}      smells)                       venture launch)
```

Every subsystem reasons through a single `LLMClient` (Claude, adaptive
thinking), and every irreversible action passes through an `ApprovalGate`.

## Shared foundation

| Module | Responsibility |
|---|---|
| `cogniprime.config` | `CogniPrimeConfig` — one declarative object (model, effort, recursion depth, approval policy) threaded through everything. |
| `cogniprime.llm` | `LLMClient` — the only place the Anthropic SDK is touched. Uniform `reason()` / `structured()` calls with adaptive thinking. Accepts an injected client for tests. |
| `cogniprime.agents.base` | `Agent` — a named reasoning unit that returns an `AgentResult` carrying both a value and an audit trail. Subsystems compose agents rather than calling the LLM ad hoc. |
| `cogniprime.approval` | `ApprovalGate` — decides whether hard-to-reverse actions proceed. Defaults to **deny**, so an unconfigured OS plans but never acts. |

## Subsystem 1 — Infinite-Context Core (`cogniprime.core`)

A continuous **recursive RAG loop** that maps the whole ecosystem into one
queryable context.

- **Data layers** (`data_layers.py`): the empire is read through `DataLayer`
  sources across four `LayerKind`s — `CODE`, `INFRASTRUCTURE`, `FINANCIAL`,
  `OPERATIONAL`. Live connectors implement the protocol; `StaticLayer` backs
  tests and seeding.
- **Memory** (`memory.py`): `MemoryStore` is the retrieval surface.
  `InMemoryStore` is a deterministic lexical-cosine reference implementation;
  swap in a vector DB behind the same interface without touching anything above.
- **Context core** (`context_core.py`): `map()` indexes every layer; `query()`
  runs the recursion — retrieve, ask the model whether context is *sufficient*,
  expand with model-proposed follow-up queries, and repeat until convergence or
  `max_recursion_depth`. This is what makes the context "infinite" in practice.

## Subsystem 2 — Snap-Off Engine (`cogniprime.snapoff`)

An automated **venture-deployment pipeline**: detect → build → provision →
(gated) launch.

- **Opportunity** (`opportunity.py`): `OpportunityScanner` queries the Context
  Core and extracts ranked `Opportunity` objects (bottleneck or market), scored
  by `impact × confidence`.
- **Scaffolder** (`scaffolder.py`): `RepoScaffolder` designs a service's API
  surface and generates an in-memory `GeneratedRepo`. Nothing is written to disk
  until `materialize()` is called on an approved launch.
- **Provisioner** (`provisioner.py`): `Provisioner` plans and applies
  infrastructure. `DryRunProvisioner` is the safe default — it plans a
  server/db/load-balancer topology but creates nothing.
- **Engine** (`engine.py`): `SnapOffEngine` runs the pipeline. Generation always
  runs; provisioning and marking a venture *launched* run only when the
  `ApprovalGate` approves.

## Subsystem 3 — Self-Healing Compiler (`cogniprime.healing`)

An autonomous **developer framework** that keeps production code healthy:
monitor → diagnose → patch → (gated) apply.

- **Monitor** (`monitor.py`): `ProductionMonitor` surfaces unhealthy
  `CodeUnit`s as `HealthSignal`s. `HeuristicMonitor` uses static code smells
  (hard-coded credentials, `eval`, bare `except`, disabled TLS) so the pipeline
  runs without live telemetry; a real monitor uses runtime signals.
- **Diagnostics** (`diagnostics.py`): `Diagnostician` reasons over the actual
  source at **max effort** and produces an authoritative `Diagnosis` — category,
  `Severity`, and whether the fix is safely `auto_patchable`.
- **Patcher** (`patcher.py`): `Patcher` proposes a minimal corrected source as a
  `Patch`. It never writes; it can decline (no unsafe fixes).
- **Compiler** (`compiler.py`): `SelfHealingCompiler` runs the loop. Diagnosis
  and patch generation always run; **applying** a patch is gated, and any
  non-`auto_patchable` fix is escalated for human review regardless of the gate.

## Safety model

CogniPrime is autonomous by design, so the guardrails are structural, not
optional:

1. **Deny-by-default approval.** The default `AutoDenyGate` blocks every
   irreversible action. Action requires explicitly supplying a gate (a human
   callback, a policy engine).
2. **Generate/act split.** Every subsystem separates reasoning/generation (always
   safe) from side effects (gated). Repos are generated in memory; patches are
   proposed as data; infrastructure is planned before it is applied.
3. **Bounded recursion.** The Infinite-Context loop is capped by
   `max_recursion_depth`, preventing runaway self-expansion.
4. **Escalation.** Fixes the diagnostician does not consider low-risk are never
   auto-applied, even under an approve-all gate.
5. **Auditability.** Every agent returns an `AgentResult`/report `trace`, so any
   autonomous decision can be explained after the fact.

## Extending CogniPrime

| To add… | Implement… |
|---|---|
| A live data source | `DataLayer` (e.g. a git or ledger connector) |
| A production-grade RAG index | `MemoryStore` (e.g. pgvector) |
| Runtime health signals | `ProductionMonitor` |
| Real cloud/bare-metal provisioning | `Provisioner` |
| A human-in-the-loop / policy gate | `ApprovalGate` (see `CallbackGate`) |

Each is a small protocol; nothing above the boundary changes when you swap the
implementation.
