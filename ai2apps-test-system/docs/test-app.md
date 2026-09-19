# AI2Apps-test release-test environment

`AI2Apps-test.app` is the fixed local environment for testing a release-shaped
AI2Apps Desktop build without using or changing the installed production App's
data.

## Fixed identity

- App path: `apps/ai2apps-acefox/.build/AI2Apps-test.app`
- Display name: `AI2Apps-test`
- Bundle identifier: `com.ai2apps.desktop.test`
- Instance ID: `test`
- Support data: `~/Library/Application Support/AI2Apps/instances/test`
- Instance cache: `~/Library/Caches/AI2Apps/instances/test`
- Helper icon: normal four-state AI2Apps artwork with purple diamonds in both
  upper corners
- App icon: the sphere's upper half is light blue

The build uses the same `build-release-app.sh` pipeline, embedded `cloud`
Runtime, signing stages, and `verify-release-app.sh` checks as the production
App. It is not marked as an AI2Apps Development Bundle and does not mount source
from the repository. The previous fixed test App is archived under
`apps/ai2apps-acefox/.build/archive/` before replacement.

Build it with:

```shell
apps/ai2apps-acefox/scripts/build-test-app.sh
```

`ACEFOX_APP`, `RUNTIME_LAYERS`, and `SIGN_IDENTITY` may be supplied in the same
way as the release builder. An ad-hoc signature is used when `SIGN_IDENTITY` is
not set.

## Reset data

This build and the fixed App-Dev build receive the signed
`AI2AppsAllowInstanceDataReset` capability; production and general Dev do not.
Its Helper menu therefore includes **重置数据…**. After explicit confirmation,
the Helper stops the Local service, closes the test Shell and browser agents,
deletes the two private `test` instance roots above, and exits. Reopen
`AI2Apps-test.app` to start with newly installed state.

The reset deliberately does not target the user-owned Hugging Face import cache
at `~/.cache/huggingface/hub`. Production, `dev`, and `app-dev` instance roots
are also outside the reset targets.

Automated fresh-install runs use this same reset implementation:

```shell
./bin/ai2apps-test run --priority P0 --fresh-install
```

The Harness sends an authenticated `instance.reset` request to the fixed Test
Helper. The Helper additionally requires its signed reset capability, the exact
Test bundle and instance identity, the Harness actor, and
`confirm_instance_id=test`. No arbitrary filesystem path is accepted.

## Automated acceptance

The layered, priority-selectable and unattended test mechanism for this fixed
environment is defined in
[`automated-test-system-v1.md`](automated-test-system-v1.md).
The runnable first-version commands are documented in
[`quickstart.md`](quickstart.md).
Its automation must validate the Test bundle and instance identity before any
state-changing action and must never target the production or development
instance roots.

All four Helper status SVGs receive matching purple diamonds in their upper-left
and upper-right corners. This keeps update and readiness states intact while
making Test visually distinct from production and App-Dev's single orange
circular badge.

The visual identity is enforced by the shared release builder, not merely by
this wrapper. Any direct build that uses one reserved Test identity field must
use the complete fixed Test identity; the builder then forces the light-blue
App/Shell tint and both tray badges and fails before signing if they are absent
or inconsistent.
