# AI2Apps Bring-Your-Own Checkpoint Requirements v1

## Objective

Allow an Installation owner to bind a locally obtained, appropriately licensed
checkpoint to a signed model Package without granting that Package arbitrary
filesystem access and without weakening AI2Apps checkpoint integrity checks.

The first consumer is `ai2apps/model-face-swap-mlx`, whose executable Package
can be distributed under Apache-2.0 while compatible identity-recognition and
face-swap weights may require the user to obtain separate rights.

## Non-goals

- Do not upload user checkpoint bytes to AI2Apps Cloud.
- Do not let Apps or Model Workers submit or resolve host filesystem paths.
- Do not treat user attestation as permission for AI2Apps to redistribute a
  third-party checkpoint.
- Do not bypass the signed Registry manifest, file list, size, or SHA-256 checks.
- Do not make imported checkpoints visible to unrelated Packages.

## Registry and Cloud requirements

Checkpoint distribution schema v2 must support a `local_import` acquisition
mode. A local-import distribution remains immutable and signed and contains:

- the exact Package model ID, logical repository ID, and immutable revision;
- every required checkpoint-relative file path, byte size, and SHA-256 digest;
- the concatenated piece hashes already used by resumable verification;
- license ID, terms URL/hash, usage policy, redistribution policy, and required
  owner attestation;
- `distribution.localImport.allowed: true` and an owner-facing explanation;
- zero downloadable sources when redistribution is prohibited, or the normal
  verified Hugging Face/ModelScope sources when redistribution is allowed.

Cloud stores and serves only the signed metadata/envelope for a local-only
distribution. It must never receive the selected local files or leak their
names outside the checkpoint-relative manifest paths. Package publication must
accept a local-only distribution as satisfying `weights.distribution_id`.

The Cloud implementation should return a distinct `local_import_required`
state instead of reporting that every download source is disabled.

## Preferred official-source acquisition

When the rights holder publishes the checkpoint itself, ACPF should prefer a
direct official-source download over local import. For the initial face-swap
stack these sources are:

- `inswapper_128.onnx` and the compatible `buffalo_l` recognition pack from
  `deepinsight/insightface` GitHub Releases;
- YuNet from the official `opencv/opencv_zoo` repository.

Checkpoint distribution schema v2 must therefore also support an immutable
`github_release` source. The signed Registry manifest pins the repository
owner/name, release tag or release ID, asset name, expected byte size, and
SHA-256. Local downloads the bytes directly from GitHub after ACPF license
confirmation; neither AI2Apps Cloud nor an AI2Apps-controlled redirect proxies
or caches the payload. Redirects are restricted to GitHub's documented release
asset hosts, every redirect hop must remain HTTPS, and the final bytes must
match the signed manifest.

For a private rights-holder delivery, the source may require a user-scoped
credential or expiring URL. That secret remains in the trusted Local secret
store, is sent only to the manifest-authorized rights-holder host, and is never
included in ACPF state, telemetry, logs, or Cloud requests.

Runtime 1.6.2 already exposes the `onnx` capability. The face-swap Package can
therefore accept the verified official ONNX layout, perform a deterministic
one-time local conversion into parser-free `.omlx` graph/weight bundles, and
cache the converted result under its private data directory. The converter
must record source hashes, conversion version, output hashes, and precision;
it must rebuild rather than reuse output when any of those inputs changes.

## Trusted Local requirements

Only the Installation owner in a first-party Core surface may begin an import.
The native file/folder picker returns a security-scoped selection directly to
trusted Local code; Local HTML receives only an opaque import operation ID.

The importer must:

1. fetch and verify the signed distribution envelope before opening model
   bytes;
2. present the manifest-bound license challenge and record the selected
   acceptance decision;
3. reject symlinks, devices, sockets, absolute paths, traversal, duplicate
   normalized paths, unexpected files, and archives that exceed declared
   limits;
4. stream-verify every declared file size/SHA-256 and the concatenated piece
   hashes, with cancellation and progress;
5. clone/copy verified bytes into a private partial cache, fsync metadata, and
   atomically publish the standard distribution snapshot;
6. write the usual completion marker and distribution manifest so
   `checkpoint_is_complete` and Model Worker startup need no alternate trust
   path;
7. grant the Worker read-only access only to the verified repository root
   already selected by `_model_worker_checkpoints`;
8. erase incomplete staging data after failure or cancellation while leaving
   the user's selected source untouched.

The import API must accept only the opaque picker grant/operation ID and the
manifest-bound license consent. It must not accept a caller-controlled path.

## Package contract

The face-swap Package will declare normal immutable weights metadata and the
local-only distribution ID. Its checkpoint root must contain:

```json
{
  "schema": "ai2apps.mlx-face-swap-checkpoint/v1",
  "components": {
    "detector": "models/face_detection_yunet_2023mar.omlx",
    "recognizer": "models/w600k_r50.omlx",
    "swapper": "models/inswapper_128.fp16.omlx"
  }
}
```

Optional semantic-mask and restoration components may be declared by the
checkpoint, but the signed file manifest remains authoritative. The Worker
must continue to reject missing, escaping, or schema-mismatched components.

## User experience

Discover shows the Package as installable and labels the weights as “Bring
your own licensed checkpoint.” Provisioning offers **Select checkpoint** instead
of **Download** when no network source exists. The UI displays required file
names, expected total bytes, license terms, verification progress, and a clear
hash-mismatch error without exposing internal cache paths.

For InsightFace/InSwapper, ACPF must show both official destinations before any
checkpoint acquisition:

- licensing information: `https://www.insightface.ai/`;
- the upstream model/license policy:
  `https://github.com/deepinsight/insightface#license`.

The confirmation is a manifest-bound owner attestation, not a generic checkbox.
It must say that the owner has obtained authorization from the model rights
holder for the intended usage and accepts responsibility for complying with its
scope. The submitted decision is the existing
`obtained_separate_license`; ACPF records the distribution ID, signed manifest
digest, terms hash, decision, confirmation time, Installation/account identity,
and Package version. It must not request or store contract terms, order details,
license keys, or other confidential proof.

After confirmation, ACPF may continue only through one of these byte paths:

1. trusted local import of the checkpoint obtained by the user; or
2. a rights-holder-controlled authenticated download delegated to that user.

The attestation alone must not unlock an AI2Apps-hosted mirror unless AI2Apps
also has an explicit redistribution grant. If the supplied model directory
contains an official signed `MODEL.LICENSE`, trusted Local should verify its
issuer signature, model ID, grant, and validity period and retain only the
non-secret verification summary.

Once verification succeeds, model selection and invocation behave exactly like
a downloaded checkpoint. Removing the model deletes the verified cache copy
but never modifies the user's original folder/archive.

## Acceptance criteria

- A matching local face-swap checkpoint imports with no network request and the
  real installed `.ai2service` completes image and video replacement.
- No checkpoint byte is read before the owner completes the exact signed
  license challenge with `obtained_separate_license`.
- Declining or dismissing the challenge leaves the Package uninstalled and
  creates no model cache files.
- A one-byte mutation, missing file, extra file, unsafe archive member, stale
  manifest, stale consent, non-owner request, or arbitrary path request fails
  before Worker access.
- The Worker sandbox cannot read the original selected folder or any other
  model cache.
- Existing v1 dual-source distributions and cached installations are unchanged.
- Import, cancellation, restart recovery, removal, and concurrent-import tests
  pass on the App Dev environment.
