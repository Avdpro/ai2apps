# Agent default model selection — 2026-10-22

Automatic selection requires affirmative standard/complex work and reliable tool
calling declarations. Provider/model names never supply these quality claims.
The catalog now reports declaration status and literal true/false/unknown values;
missing provider metadata remains unknown, not a fabricated affirmative claim.

The settings UI lists available chat-capable models for manual Agent defaults,
ordered as qualified, partially declared/below automatic requirements, then
undeclared. Non-chat models, hidden/helper models, unavailable checkpoints and
HF cache-only entries remain excluded. Unknown manual choices can be saved in
Normal and Privacy independently. A saved Agent default is an explicit user
choice and wins over automatic fallback; missing/invalid saved IDs do not.
Automatic fallback still filters strictly. Notices explain no chat models,
no qualified automatic candidates, and manual unverified choices.

Backend save validation and the shared Desktop/Mobile browser policy enforce the
same distinction. This is generic model policy, without provider/App branches.
Cloud metadata is projected locally; no Cloud code or persistent capability
inventories are rewritten. English/Chinese UI copy describes the distinction.

Regression and live Dev acceptance recorded after verification.

## Regression and Dev acceptance

- Python model-default/profile suite: 29 passed, including manual undeclared save,
  GET/reopened-store persistence, profile separation, unavailable/hidden/non-chat
  rejection, explicit false/unknown metadata, and arbitrary model identities.
- JavaScript policy/settings suite: 9 passed. Covers declared-first ordering,
  explicit saved preference versus strict fallback, empty/unknown notices, and
  policy-script load ordering in both Dashboard and standalone System Apps.
- Mandatory AaAT boundaries: 245 passed (106.34s). Counts are separate suites and
  should not be summed as unique cases.

Live Dev 58879 exposed an additional existing defect: standalone System Apps
loaded dashboard.js without conversation_model_policy.js, unlike Dashboard.
The shared base now loads the policy first. Before this dependency correction,
Agent options and notices could fail even with the selection policy fixed.

After the correction, the real dropdown listed enabled BYOK/OpenAI/DeepSeek and
Cloud chat models with truthful undeclared labels, and displayed the no-qualified
automatic-candidate explanation. Selected cloud/deepseek/deepseek-flash in Normal,
clicked Save and observed 已保存. Force refresh retained the selection and manual
capability notice. The persisted work_agent route matches that ID. Privacy kept
its empty work_agent and displayed automatic-selection explanation; no Privacy
save or other model-route changes were made. Returned to Normal afterward.

App and Helper retain the fixed Dev identities and live-checkout source metadata.
Local restarted via standard Helper with zero active Agent/Browser tasks; startup
logs identify imported ai2apps modules under the checkout. Actual served
conversation_model_policy.js and dashboard.js match checkout bytes. Backend's
successful undeclared-model save verifies the changed manual validation path.
No credentials, provider capability files, Cloud code or production state changed.
