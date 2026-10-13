# Shared Asset Slot v1

Canonical implementation: `ai2apps/web/static/js/asset_slot.js` and
`ai2apps/web/static/css/asset_slot.css`. Styles target only `[data-asset-slot]`
with explicit `image`, `video`, and `audio` kinds; they must never be global
`label`, `img`, `button` or Studio-specific `.vs-drop` rules.

`AI2AppsAssetSlot.bind(element, {select(file), clear(), drop(event), error(error)})`
owns file picking, Enter/Space, drag highlighting, file replacement, clear controls,
and disabled behavior. The element supplies one file input, one image, an empty-state
span and one clear button. `update({preview, disabled, label, clearLabel})` supplies
the current state and localized accessible names. Hosts own Blob URLs and release
them on replace/clear/unmount. Only the adapters resolve Gallery/Output references
through authorized APIs or the mount-bound MessageChannel; the component never
fetches URLs, reads credentials, chooses models, or stores files.

For video or audio, pass `kind: 'video'` or `kind: 'audio'` to `bind`. Video
slots supply a muted, non-interactive `<video>` preview; audio slots show a
filename rather than attempting to play during selection. Both may supply
`[data-slot-filled]` for the selected name/count. Multi-file inputs pass the
entire snapshot to `selectFiles(files)`; single-file inputs keep `select(file)`.
The host validates types and limits before committing a multi-file batch,
maintains ordering, and revokes Blob preview URLs when replaced or cleared.
The mobile Studio picker uses the same file input/change event and accepts
`[data-asset-slot]` as a Gallery drag target. The component never reads Gallery
credentials or turns arbitrary metadata URLs into previews.

Preview uses a stable 220px surface and `object-fit:contain`; choosing an image hides
empty-state instructions and exposes the same top-right clear button everywhere.
Image source pixels are never cropped or modified by the slot.

Consumers: all Imagine Studio shared reference slots (including the adjustment
source image; its processing Canvas stays separate); Video Studio first/last
frames, reference image/video/audio slots, Extract Audio source, and Video Upscaling
source; and the Frozen Time Package's source image. Composer multi-file import,
batch/project files, mask editing and other Package-owned media controls remain
specialized rather than pretending to be a single asset slot.

Opaque Package delivery includes identical vendored copies under the Package's web
directory (classic JS and relative CSS; no remote imports). `asset_slot.test.cjs`
requires byte parity with the canonical sources. Any component change must update
these copies atomically and retain this parity test before Package signing. Installed
Package resources remain governed by their signed index and sandbox CSP.
