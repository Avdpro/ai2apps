# Structured Bot model memories

Model memories are preferences, not Access grants. They reuse the Model App's
`DEFAULT_MODEL_PURPOSES`, live catalog and purpose compatibility classifier.
The host UI stores `{purpose, profile, model}` through the existing versioned
memory service. Each Bot has one active slot per purpose and normal/privacy
profile. Editing, conflict detection, evidence and undo use the existing memory
journal. These records are excluded from the prose memory prompt.

## Routing and lifetime

1. An explicitly selected model in an operation's arguments remains authoritative
   and is validated by the operation owner. An invalid explicit selection is an
   error; it is never silently replaced.
2. Otherwise, the current Bot's matching model memory is used.
3. Missing slots inherit the nearest parent Task/Bot chain's matching model
   memory. Only bounded model slots and their IDs/revisions are inherited, not
   other private memory, permissions, credentials or conversation history.
4. Missing, unavailable or operation-incompatible preferences fall back to the
   existing system default in the same profile. A missing privacy default never
   falls back to a normal route. Normal existing owner fallback behavior remains
   unchanged where that owner has no configured normal default.

Each new execution captures a snapshot. Later edits do not change an executing
Task or its continuation. Each scheduled occurrence captures a fresh snapshot at
start. Delegation merges the receiver's slots with its parent's frozen slots;
it never writes inherited preferences into either Bot's memory. Fixed-participant
collaboration similarly carries the reviewed parent model preference snapshot.

The trusted App Chat owner captures the snapshot; shared execution only carries
and scopes it. Context variables isolate concurrent executions and restore the
previous scope on exit. Provider descriptor/preparation/execution share the scope.
Current Model App readiness and purpose support are rechecked before use; the
consumer additionally checks operation support (e.g. generation versus editing).
Model App catalog discovery is shared across concurrent lookups and cached for up
to 120 seconds, invalidated by local provider/configuration/registration changes.
Refresh timestamps alone do not invalidate it. Invalidation reads registration
data rather than resolving unrelated worker credentials or checkpoint dependencies.
Image operation catalogs enumerate only image model declarations. This avoids
repeated remote catalog fetches and unrelated worker resolution exhausting
a Tool's read deadline. Operation-specific catalogs still validate readiness at
preparation, and the system fallback is resolved outside the preference scope so
a stale preferred model cannot become its own fallback. Catalog caching never
caches or replaces authorization, licensing or outbound-data checks.
The live delegation acceptance also exposed historical interaction scans in each
Tool visibility check. Indexed graph authorizations and budget-wait cards keep
the existing deadline calculation and per-call authorization checks intact while
avoiding scans of unrelated interaction history.
Delegation completion is presented as a host continuation event, with the
original request retained as background and the child result still marked as
untrusted evidence. Replaying the original "new task" wording as the latest
instruction must not cause the parent to repeat completed work. The original
authorization and result-uncertainty guards remain in force.
Registered private read workflows use the active, validated parent invocation's
model scope. Their child Run is not an independent App Chat admission. Executor,
Provider, Session, version, cancellation and owner checks are retained; arbitrary
child Runs cannot inherit a model scope by merely naming a parent.
Model catalog failure disables preferences for that resolution and preserves
same-profile system defaults. Selection provenance is outside parameter contract
identity, so explicit use of the same model does not invalidate a reviewed form.

## Boundaries

The Model Manager's purpose-level default resolver consumes the generic scoped
preferences. Existing image and speech parameter owners also use their current
operation-specific model catalog. Mini-Apps that explicitly require a fixed
model/pipeline retain that requirement: an arbitrary model memory cannot replace
an OCR engine, upscaler or architecture-specific model just because it is in a
broad Model App category. Missing installation, licensing, outbound-data approval,
App Access and uncertain-result recovery retain their existing gates.

Privacy is the platform's existing separate routing profile, not a new assertion
that every model listed under Privacy runs locally. Availability and network
policy continue to be enforced by Model App and the invocation owner.

Model memory creation is an explicit host configuration operation. Agent-extracted
prose memory candidates cannot create typed model memories or change authority.
Human model instructions within a particular operation should be expressed as
that operation's explicit model argument; ordinary unstructured text is not parsed
into hidden routing rules by shared Agentic execution.

## Validation

`tests/test_bot_model_memories.py` covers typed slots, versions and undo, arbitrary
model IDs, concurrent isolation, chain union, current catalog rejection, explicit
selection, incompatible fallback, privacy isolation, origin/owner protection and
no permission grants. It is included in `tests/run_aaat_boundaries.py`.
Live Dev evidence is recorded separately from deterministic fixtures.
