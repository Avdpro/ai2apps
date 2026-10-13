# Cloud change request: Frozen Time Mobile exact routes

## Confirmed failure

2026-10-11 08:39–08:41 UTC, Dev public origin:
`https://device-55e5e8695abeba14497c4a5cacc933a7.ai2apps.com`.

The phone successfully mounts Frozen Time, then fails restoring its durable draft.
The mount `mnt_49100edbd7e545f285d6e6ed0220323b` exists in Dev, status `mounted`,
and declares Imagine Studio and the correct Studio instance.

Unauthenticated read-only probes, no Cookie or authorization credentials:

| Request | Public edge | Dev Local, same Host |
| --- | --- | --- |
| GET `/v1/platform/studios/ai2apps.imagine-studio/mini-app-mounts/mnt_49100edbd7e545f285d6e6ed0220323b/draft` | 404, `text/html`, Nginx default error page | 403, JSON `Public route is not allowed`, Uvicorn |
| GET same mount `/capabilities` | 403, JSON `Public route is not allowed`, no-store | Existing exported route |
| GET `/v1/platform/imagine-studio/frozen-time/models` | 404, `text/html`, Nginx default error page | Local exact inventory includes it |

The raw Local loopback draft endpoint returns authentication-required 401, not route-not-found.
Full Owner/PublicDeviceBoundary draft GET regression passes; 49 Owner Studio tests pass.
These establish a public routing mismatch, not a missing saved draft. Do not treat 404 as an empty draft.
Earlier probes using `mnt_test` were insufficient: use realistic `mnt_` + 32 hex IDs.

## Required Cloud implementation

Inspect the actual device wildcard edge/Nginx route configuration and its generator.
Add the following exact method/path rules, forwarding to the same Local Mobile gateway
as existing Studio capabilities. Local remains authoritative for lease, CSRF,
actor, installation, App-instance and live Mini-App mount checks.

| Methods | Path |
| --- | --- |
| GET, PUT, DELETE | `/v1/platform/studios/{studio_id}/mini-app-mounts/{mount_id}/draft` |
| GET | `/v1/platform/imagine-studio/frozen-time/models` |
| POST | `/v1/platform/imagine-studio/frozen-time/mounts/{mount_id}/previews` |
| GET, DELETE | `/v1/platform/imagine-studio/frozen-time/previews/{key}` |
| GET | `/v1/platform/imagine-studio/frozen-time/previews/{key}/video` |
| POST | `/v1/platform/imagine-studio/frozen-time/mounts/{mount_id}/runs` |
| POST | `/v1/platform/imagine-studio/runs/{run_id}/frozen-time` |
| GET | `/v1/platform/imagine-studio/runs/{run_id}/frozen-content/{filename}` |
| POST | `/v1/platform/imagine-studio/frozen-time/mounts/{mount_id}/runs/{source_id}/convert` |

Restrict `studio_id` to `ai2apps.imagine-studio`, `ai2apps.video-studio`, `ai2apps.readaloud`.
Match actual accepted identifier formats; reject path traversal and unsupported methods.
Do not enable arbitrary `/v1/platform/*`, `/admin/*`, native filesystem export,
`save-live-photo`, or `/client/native-export/*` remotely.
Preserve Cookie/Origin forwarding to Local, Range support, no-store behavior and lease validation.
Do not cache edge errors for authenticated private paths.

Source of truth: `ai2apps/web/owner_studio_routes.json`,
`ai2apps/web/owner_studio_gateway.py`, `ai2apps/web/public_boundary.py`.
No Cloud code or deployment was changed from the Desktop repository.

## Acceptance

1. Realistic valid-ID anonymous requests reach Local and return its JSON authorization rejection,
   never the Nginx HTML 404. Anonymous success is NOT expected.
2. With the user's existing Owner lease, live mount draft GET returns 200 `value` (possibly null);
   PUT/GET round-trip persists settings across refresh/port change; DELETE clears only that scope.
3. Wrong owner, installation, Studio or mount is denied; cross-origin writes remain denied;
   privileged/non-Studio/native routes remain inaccessible.
4. On iPhone: list → Frozen Time → startup → model status → image → geometry preview →
   render → shared Output → convert/download, including video Range requests.
5. Record deployed configuration revision and actual phone acceptance result. No tokens in receipts.
