# Web Agent capability calls

Use a Step with `operation: agent.call` and arguments `agent_id`, `capability`, optional `generation_id`, and `parameters`. The server resolves an owned active Web capability and snapshots its generation. Stale versions, caller-supplied IR, cycles, depth above four and static graphs above 100 steps are rejected.

Whole-value `${input.attachments}` bindings preserve file arrays; `${steps.login.output.field}` reads a prior call result. The child input and output schemas are validated. Calls replay namespaced frames inside the same durable parent AgentRun, preserving its Profile/context and nested evidence, rather than scheduling general model-agent delegation. Browser actions stay in the native BiDi Sidebar client.

Planning receives current-site exports. AI decides whether the actual task requires an account; public reading is not automatically gated. Website-owned login capabilities have priority. HTTP(S) sites also expose a versioned fallback `site.ensure-login`: inspect cleaned DOM plus opener windows, classify authenticated readiness, click the observed login entry automatically, pause only for actual QR/credentials/OTP/CAPTCHA, then reobserve after Continue. Clicking an entry or continuing manually never proves login.

Classifier outcome routing is opt-in through a JSON Schema outcome enum containing only success/not_found/needs_user/failed. Other classifiers keep data-output semantics. Revisited classifiers receive fresh durable model-call keys. Exploratory calls checkpoint their request key/run ID, resume the same call after refresh/assistance, and cancel it when exploration stops.

Automated tests cover binding types, parent/child continuation, owner/version/cycle guards, authentication pause and reobservation, API idempotency, capability-aware planning and Sidebar restoration. Live website/scan acceptance remains separate.
