# Omega-X Architecture

Omega-X (`omegax/`) extends the CogniPrime Agentic-OS with a **bounded,
auditable, gated recursive self-improvement loop**. It reuses CogniPrime's
foundation (LLM client, agents, approval gates, memory) and adds the machinery
for a system that profiles itself, proposes improvements, verifies them in a
sandbox, and adopts them only through explicit gates.

Everything here is real, tested engineering. Where the source vision reached
into physically-impossible territory, that is called out honestly in
[Out of scope](#out-of-scope) rather than faked.

## Design spine: gated autonomy

The whole system is organized around one rule: **generation is free; adoption is
gated.** Every subsystem separates reasoning/generation (always safe to run)
from side effects (always gated). Concretely:

- **Approval gates** (`cogniprime.approval`) block merges, production promotion,
  and capability registration by default.
- **Sandbox + atomic staging** (`omegax.sandbox`) verify a candidate in
  isolation and commit it atomically, or roll back.
- **Red-team arbitration** (`omegax.core.orchestration.red_team`) attacks a
  candidate and blocks deployment on any critical failure.
- **Regression shield** (`omegax.eval.supremacy.regression`) auto-rolls-back any
  change that fails to beat its baseline — the one ungated self-action, because
  restoring known-good state is always safe.
- **Cryptographic ledger** (`omegax.core.resilience.ledger`) records every
  self-modification in a tamper-evident hash chain.

## Module map

| Group | Package | What it does |
|---|---|---|
| A. Hyper-evolution | `omegax.core.hyper_evolution` | Telemetry profiling → source-rewrite proposals → capability synthesis → RLAIF/DPO preference data |
| B. Hyper-synthesizer | `omegax.data.hyper_synthesizer` | Adversarial curriculum → sandboxed formal verification → vector + hypergraph active memory |
| C. Supremacy eval | `omegax.eval.supremacy` | Benchmark harvesting → supremacy objective → zero-tolerance regression shield |
| D. Orchestration | `omegax.core.orchestration` | Bounded sub-agent swarm, lifecycle hooks (Pre/Post/Stop), episodic memory, red-team arbitrator |
| E. Resilience | `omegax.core.resilience` | Chaos fault injection, compliance-scoped distillation, cryptographic ledger |
| Sandbox / recovery | `omegax.sandbox`, `omegax.recovery` | Atomic staging + verification runners; self-healing diagnosis |
| Frontier | `omegax.frontier` | Capability-frontier backlog + the "keep investigating" personality directive |
| Infra | `omegax.infra` | Self-hosted pure-Python reverse-proxy gateway (no paid dependencies) |
| Matrix | `omegax.matrix` | The `OmegaMatrix.step()` control loop tying it all together, ledger-recorded |

## The control loop

`OmegaMatrix.step()` runs one cycle:

```
profile (telemetry)
   → propose rewrites for hot paths → sandbox-verify → (gated) atomically promote
   → evaluate on a benchmark suite → supremacy objective → regression shield (auto-rollback)
   → synthesize an adversarial challenge → verify solution → commit trajectory to memory
   → verify ledger integrity
```

Capabilities can also be synthesized and (gated) registered
(`synthesize_capability`), and faults diagnosed into gated fixes (`heal`).

## Capability frontier — structured curiosity

`omegax.frontier` holds the directive to "keep looking for groundbreaking
capabilities, including ideas that sound speculative but might be achievable."
It is a backlog with an **evidence-gated lifecycle**:

```
PROPOSED → INVESTIGATING → GROUNDED → ADOPTED
                        ↘ REJECTED ↙
```

An idea may be investigated freely, but the lifecycle **forbids jumping to
ADOPTED without first GROUNDING it** — reducing it to something that runs and
passes the sandbox / red-team / approval gates. `FRONTIER_DIRECTIVE` is the
personality text that carries this into the system prompt: ambition is expected;
unverified claims are not.

## Self-hosting (no paid dependencies)

`omegax.infra.gateway` is a pure-standard-library reverse proxy — longest-prefix
routing, health-aware round-robin load balancing — so you don't need a paid
nginx/ingress. `deploy/docker-compose.yml` brings up the rest of the stack from
open-source images only (Postgres, Qdrant, Neo4j Community, Redis). All of it
runs on hardware you own; see `deploy/gateway_example.py`.

## Out of scope

The source spec escalated into modules that describe **physically impossible or
pseudoscientific** capabilities. These were deliberately **not** implemented,
because shipping code that claims to do them would be fabrication, not
engineering:

| Claimed module | Why not built | Real analogue already in the repo |
|---|---|---|
| Quantum-state simulation / "phase-locked resonator" / sub-Planck interpolation | Not physically realizable in software | — |
| Neuromorphic "multi-verse tree search" | Marketing over a normal search/eval loop | Staging + candidate evaluation (`omegax.sandbox`) |
| Bare-metal kernel / DVFS / silicon tuning from Python | Not achievable from application code | Telemetry profiler (`...hyper_evolution.telemetry`) |
| Direct neural-spike BCI | Not a software artifact | — |
| Holographic 4D execution visualizer | Not a real rendering target | — |
| "Singularity event horizon" that "eliminates computational boundaries" | No coherent meaning | Bounded recursion + the matrix loop |
| Post-quantum ZK-proof ledger | ZK part is aspirational | SHA-256 hash-chained ledger (`...resilience.ledger`) |
| Self-modifying `Stop` daemon rewriting its own parameters unreviewed | Removes oversight by design | Lifecycle hooks that *audit and veto* (`...orchestration.hooks`) |

The scientifically grounded successors to the rest of the vision are captured in
[`ROADMAP.md`](./ROADMAP.md).
