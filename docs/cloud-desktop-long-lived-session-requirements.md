# AI2Apps Cloud requirement: long-lived desktop sign-in

## Context

The Local Installation now owns the desktop browser Session lifecycle. A Local
Session has a 30-day idle timeout, a 180-day device lifetime, and rotates within
seven days of expiry. Rotation is local and does not call Cloud.

Cloud must continue to provide the authority signals that can revoke a Local
Session even when the desktop App stays open for months.

## Required Cloud behavior

1. Keep `GET /v1/internal/installations/{installationId}/access` as the
   authoritative device-access projection. Return a changed access epoch when
   the device is suspended, deleted, transferred, or its organization binding
   changes.
2. Keep member projections versioned by `membershipEpoch`. Increment it for
   role changes, suspension, removal, organization transfer, and security
   revocation. Local rejects a Session when its stored epoch or role no longer
   matches the current projection.
3. Add an explicit device-session revocation timestamp or epoch to the access
   projection, for example `localSessionEpoch`. Increment it for “sign out this
   device”, “sign out all devices”, account compromise response, and owner
   security reset.
4. Ensure the Installation access endpoint remains available with device
   credentials and does not depend on an interactive Cloud browser Cookie.
5. Document caching semantics. `304 Not Modified` is supported, but a revoked
   device or member must become visible to Local within five minutes.

## Suggested response extension

```json
{
  "installationId": "...",
  "status": "active",
  "accessEpoch": 12,
  "localSessionEpoch": 4,
  "members": [
    {
      "userId": "...",
      "role": "core",
      "status": "active",
      "membershipEpoch": 9
    }
  ]
}
```

## Local integration contract

- Local stores `localSessionEpoch` in newly issued desktop Sessions.
- On every successful access refresh, Local compares the Cloud epoch with the
  stored epoch and deletes mismatched Sessions.
- Network failure does not immediately sign the user out. Local keeps local
  features available, reports Cloud connectivity separately, and retries with
  bounded backoff.
- An explicit revoked or suspended response fails closed immediately.

## Acceptance criteria

- A continuously used desktop App remains signed in for more than 180 days by
  rotating its Local Session.
- A Mac unused for more than 30 days requires Local sign-in again.
- Cloud “sign out this device” invalidates Local Sessions within five minutes.
- Role changes and member removal invalidate existing Local Sessions without
  requiring the desktop App to restart.
- Cloud outage never appears as Local Session expiry, and Local Session expiry
  never appears as “Cloud unavailable”.
