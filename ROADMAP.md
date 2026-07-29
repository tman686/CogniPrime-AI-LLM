# CogniPrime / Omega-X Roadmap

This is the **"build later" backlog** — the scientifically grounded roadmap,
captured so nothing is lost. Each item is a real, buildable direction (no
pseudoscience). Status legend:

- ✅ **prototyped** — a working, tested scaffold already exists in this repo
- 🔜 **next** — a clear next increment on existing code
- 📋 **backlog** — grounded, not yet started

The positioning: **CogniPrime is an enterprise AI operating system that combines
memory, agents, automation, analytics, and decision intelligence into one
adaptive platform** — an *intelligence infrastructure layer*, not "one super AI."

## Guiding rules (kept from the current build)

1. Human approval gates every irreversible action; automated rollback is the
   only ungated self-action.
2. Generation/analysis always runs; side effects are gated.
3. Bounded recursion, sandbox verification, red-team arbitration, and a
   tamper-evident ledger back every self-modification.
4. **Capability frontier:** actively investigate speculative-but-plausible
   capabilities, but adopt only after grounding + verification (`omegax.frontier`).

---

## Foundational intelligence

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Long-term autonomous memory (episodic/semantic/working, forgetting) | ✅ | `omegax.core.orchestration.episodic_memory`, `cogniprime.core.memory` |
| 2 | Recursive / agentic RAG (Self-RAG, Corrective RAG, retrieval eval) | ✅ | `cogniprime.core.context_core` |
| 21/36 | Enterprise memory graph (short/long/semantic/relationship tiers) | 🔜 | extend memory with a graph tier (Neo4j) |
| 54 | Memory compression (hierarchical summarize → knowledge) | 📋 | frontier idea `working-memory-compression` |
| 9/31 | Knowledge graph intelligence / enterprise intelligence graph | 📋 | Neo4j + entity resolution |
| 16 | Neural data fabric (connect Drive/Slack/GitHub/DBs/CRM) | 📋 | see connectors (#37) |
| J/hyper_rag | Knowledge compression + active retrieval routing | 🔜 | router over `context_core` |

## Agents & orchestration

| # | Item | Status | Notes |
|---|------|--------|-------|
| 3 | Multi-agent collaboration (role-based, debate, protocols) | ✅ | `omegax.core.orchestration` (swarm), `cogniprime.agents` |
| D | Parallel sub-agent swarms (bounded concurrency) | ✅ | `omegax.core.orchestration.swarm` |
| 17 | Agent marketplace (specialized, verified agents) | 📋 | registry + verification |
| 18/40 | Agent training lab / evaluation (accuracy, cost, reliability) | ✅ | `omegax.eval.supremacy`, `hyper_evolution.optimization_loop` |
| 26/38 | Agent communication bus / protocol (Kafka/RabbitMQ) | 📋 | message bus |
| 33/35 | Intelligence kernel + planning engine (goal → task plan) | 🔜 | planner over agents |
| 52 | Agent factory (generate specialized agents from a need) | 🔜 | builds on `capability_synth` |
| 53 | Tool discovery system | 🔜 | builds on `capability_synth` + MCP |
| O | Adversarial red-team arbitrator (block-on-fail) | ✅ | `omegax.core.orchestration.red_team` |

## Software engineering & operations

| # | Item | Status | Notes |
|---|------|--------|-------|
| 4 | AI software engineering (bugs, tests, docs, PR review) | ✅ | `cogniprime.healing`, `omegax.core.hyper_evolution` |
| 5/29 | Autonomous operations (monitor → diagnose → recommend, gated) | ✅ | `cogniprime.healing`, `omegax.recovery` |
| 55 | Autonomous testing framework (simulate before act) | ✅ | `omegax.sandbox` staging + verification |
| 43 | Observability platform (agents, cost, latency, quality) | 🔜 | `omegax...telemetry` + dashboard |
| 24 | Cost optimization / model routing (small vs large) | 📋 | model router |

## Business intelligence & simulation

| # | Item | Status | Notes |
|---|------|--------|-------|
| 6/30 | Opportunity discovery / venture research (human decides) | ✅ | `cogniprime.snapoff` |
| 10/22 | Decision support engine (recommend + risk + confidence) | 🔜 | causal + forecasting layer |
| 7/19/42 | Simulation engine / digital twin (agent-based, Monte Carlo) | 📋 | `CogniSim` |
| 50/51 | Intent + context engine (goal understanding, company model) | 📋 | |
| 25 | Synthetic data factory (privacy-preserving) | ✅ | `omegax.data.hyper_synthesizer` (+ differential privacy later) |

## Governance, security & platform

| # | Item | Status | Notes |
|---|------|--------|-------|
| 8/23/44 | Governance / security layer (permissions, audit, sandbox) | ✅ | `cogniprime.approval`, `omegax...ledger`, `omegax...hooks` |
| 41 | Human control / approval center | ✅ | `cogniprime.approval` |
| 28 | Compliance engine (regulations, audit docs) | 📋 | |
| 14/18 | Continuous learning (RLHF/RLAIF/DPO, evaluation) | ✅ | `omegax...optimization_loop` |
| 37 | Data connector system (GitHub, Slack, cloud, CRM) | 📋 | connectors/ |
| 39/11 | Workflow engine (AI-native Zapier/Temporal/Airflow) | 📋 | `CogniFlow` |
| 45/46 | Revenue tiers + moat strategy | n/a | business, not code |

## Self-hosting (no paid dependencies)

| Item | Status | Notes |
|------|--------|-------|
| Reverse-proxy gateway (replace nginx/ingress) | ✅ | `omegax.infra.gateway` — pure stdlib |
| Local vector store (FAISS/Qdrant) behind `MemoryStore` | 🔜 | swap `InMemoryStore` |
| Postgres + Neo4j Community + Qdrant compose | 📋 | see `deploy/` |
| Runs on your own RAID box / self-built cloud | ✅ | all components are OSS/stdlib |

---

## Suggested build order (MVP → platform)

1. **MVP (now → next):** kernel/planner over the existing agents + memory +
   context RAG; wire the gateway + a local vector DB; ship the approval center.
2. **Enterprise intelligence:** knowledge/enterprise graph, connectors, workflow
   engine, observability dashboard.
3. **Autonomous operations:** CogniOps monitoring, simulation/digital-twin,
   decision engine.
4. **Verticals & marketplace:** industry agents, agent marketplace, compliance.

Explicitly **out of scope** (not physically groundable today; see
`ARCHITECTURE-OMEGAX.md` → *Out of scope*): quantum-state simulation, sub-Planck
interpolation, neural-spike BCI, bare-metal DVFS tuning from Python, holographic
4D rendering, "singularity event horizon." Real analogues of each already exist
in the codebase (telemetry profiling, the cryptographic ledger, the staging
evaluator).
