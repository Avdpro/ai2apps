# Worker SSD prefix KV reuse

The shared `OmlxChatAdapter` configures standard oMLX batched/VLM engines before
startup, including engines constructed by installed Model Package adapters.
Specialized engines without the scheduler configuration surface retain their own
cache contract. No Agent business routing, declarations, approvals or model
weights change.

Defaults:

- Worker-owned `data_root/prefix-kv-v1/<checkpoint identity>/blocks/` SSD storage.
- 20 GiB LRU limit per model revision/checkpoint location. RAM-only mode and
  optional hot-cache retention are disabled; active inference still uses RAM/GPU.
- 24-hour idle Session lease. Host-derived actor/installation/membership/Session
  identity is hashed, then associated with a persisted random generation.
  Expiry or a different owner rotates the key; the caller cannot supply that key.
- SSD block idle eviction runs at activation and at most once per minute on the
  cache writer. A stopped Worker performs no background work; activation sweeps
  its directory again. Pending writes are excluded from expiry. Eviction may
  reduce the retained lifetime below 24 hours under capacity/disk pressure.
- Private cache directory0700, lease/index database0600. Cache directories derive
  from checkpoint identity, never user-supplied filesystem paths.

The Session lease and exact-boundary index survive Worker restart. For hybrid
recurrent attention, plain full-block matching can encounter placeholder state;
that rejection remains intact. The optional Scheduler `persistent_prefix_store`
records only a lineage digest, token count and token digest for the safe boundary
already selected by the existing runtime. It does not store prompt text or token
IDs. Recovery hashes the candidate current prefix, then requires the existing
all-or-nothing KV chain reconstruction and layout/image checks. Missing, expired,
corrupt, incompatible or evicted state falls back to recomputation. KV tensor
payloads themselves remain private conversation-derived cache data.

Tools, system/developer instruction placement, tokenizer templates and image
identities remain part of the actual token/hash chain. A changed prefix may
legitimately miss. This mechanism does not change user/tool authority, weaken
hybrid state validation or manufacture a cache hit. Missing SSD/lease storage
also recomputes rather than preventing the model call.

## Validation, 2026-10-30

Evidence lives in `ai2apps/.build/worker-prefix-cache-20261030/` (local only).
The live fixtures use the Test instance's existing read-only Qwen3.8 weights with
source Runtime in isolated temporary cache directories. They do not alter Test
Packages, conversations or dispatch predicted Tool calls. Separate checks cover
A/B/A, identical text in different Session owners, actual tool-result
continuation, SSD restore after engine restart, lease expiry and cold recompute.
Regression includes arbitrary Provider/revision identities, private paths,
forged-key rejection, image boundary mismatch, pending-write protection and
Host invocation ownership. This is source Runtime acceptance, not a signed
published Runtime or native Test upgrade claim.

Final results:1062 focused regressions and701 AaAT boundary cases passed. The
real Qwen fixture restored2048/3315 tokens after A/B/A and again from SSD after
engine restart; an artificially aged isolated lease then reported0 cached tokens
and produced the same correct completion. Expiry unit tests advance a clock;
these checks do not claim a24-hour wall-clock soak.

The saved panda/fox Agent-request replay additionally exposed a continuity-store
bug: captured intermediate recurrent snapshots were discarded. Exact-prefix
storage now forwards those snapshots, preserving each valid boundary's own
state. A numerical SSD restart regression verifies partial-prefix recurrent
state equals that boundary, not the final turn's state; missing/placeholder
state rejection is unchanged.

For the identical current request (23285 input tokens), cold took56.679s;
after A/B/A,12288 tokens were cached (52.8%) and the request took33.686s
(40.6% less). Worker-estimated first-token latency was49.924s cold vs27.123s
warm (45.7% less). This is one paired source-runtime run using the same weights
and inference parameters, not a general speedup guarantee. Request normalization
in this source Runtime yields slightly different token counts from the earlier
installed Runtime record. Predicted Tools were never dispatched. Changed Tool
schemas/trusted instructions legitimately limit the reusable prefix.
