# AI2Apps AaAT architecture boundary

These rules supplement the repository-root AGENTS.md and apply throughout
`ai2apps/`. They do not replace its development, security, or release contracts.

Before changing Agentic execution, Tool discovery/routing, App/Mini-App integration,
parameter forms, continuations, or result processing, read:

- [AaAT declaration and Context contract](docs/aaat-declaration-context-v1.md)
- [App/Mini-App integration guide](docs/app-mini-app-agent-tool-integration.md)

## Ownership is mandatory

- General Agent and shared Agentic infrastructure MUST remain independent of
  business Tool names, App/Mini-App IDs, project names, sites, and domain semantics.
  Do not add name/prefix branches, App-specific global prompts, imports of business
  validators, or special result-field handling to fix an individual case.
- App/Mini-App owners supply business semantics, supported scope, entity resolution,
  hierarchy/counting, input validation, confirmation policy, and evidence/result
  interpretation through trusted AaAT declarations and owner adapters. UI and Tools
  must reuse the same business services and access checks.
- Agentic supplies generic discovery, selected-declaration review, invocation,
  durable interactions, authorization, progress, budgets, cancellation, recovery,
  context bounds, and dispatch of capability-scoped owner result policies.
- A bug exposed by one App may justify a generic infrastructure fix. Describe the
  missing abstraction, implement it without knowing the business identity, and
  verify it with arbitrary/different provider identities. Do not disguise a
  name-based special case as a generic hook or move it into another shared file.
- Platform control protocols and explicitly specialized workflow executors may
  have their own contracts. This does not authorize copying domain rules into the
  General Agent. Registration/composition code may identify its owner; shared
  execution decisions must consume declarations, not business identifiers.
- Declarations, returned context, and next actions never grant authority. Preserve
  ownership/version/confirmation guards; never turn cancellation or uncertain
  execution into automatic effectful retries through another Tool.

## Required review and evidence

For every AaAT behavior change, check the contract's development/review gate,
update its owner declaration/documentation as needed, and run the relevant generic
contract and owner tests. New generic mechanisms need cross-provider coverage;
changed user flows need end-to-end evidence with fixture versus live execution
clearly distinguished. Update the repository release ledger when required by the
root instructions. Historical acceptance notes do not override the current contract.

The automated boundary gate is mandatory for changes to shared Agentic execution,
AaAT routing/declarations, interactions, or result policies. From the Git root run
`python ai2apps/tests/run_aaat_boundaries.py`; the existing CI Python matrix runs
the same command. See [gate scope and maintenance](docs/aaat-boundary-regression.md).
Do not weaken positive dependency classifications or add business exceptions to
make the gate pass. Any legitimate new shared dependency/control protocol requires
an architectural rationale and review of the policy change alongside its tests.
