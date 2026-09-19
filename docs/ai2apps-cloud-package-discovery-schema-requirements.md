# AI2Apps Cloud Package discovery schema change requirements

Date: 2026-09-05 (Asia/Shanghai)

## Problem

Current Local Package Contract v1 accepts and requires signed top-level
`discovery`, `modelProfile`, and `modelInstall` metadata for new model Packages.
The production Cloud submission validator rejects these additions as additional properties. This
was reproduced while submitting `ai2apps/model-rvc-mlx 0.1.0`; no submission
was created by that rejected request.

RVC and Seed-VC v2 0.1.0 were released through the existing explicit,
version-bounded Local legacy mapping. That mapping must not be extended past
0.1.0. Cloud support is required before either Package publishes a later
version with signed discovery metadata.

## Required Cloud changes

1. Extend the Package manifest v1 submission schema with optional top-level
   `discovery`, `modelProfile`, and `modelInstall` properties without weakening rejection of
   unrelated properties.
2. Validate `discovery` as exactly:
   - `kind`: literal `model`;
   - `categories`: a non-empty unique subset of `text`, `speech`,
     `multimodal`, `image`, `video`, and `embedding`;
   - `tasks`: 1–32 unique lower-kebab-case identifiers, each no longer than 64
     characters.
3. Permit model discovery only for Service Packages with a non-empty
   `service.yaml` `models` list. Require both `modelProfile` and `modelInstall`
   whenever `discovery` is present.
4. Validate `modelProfile` as exactly `sizeBytes`, `minimumMemoryBytes`,
   `scores`, and `benchmark`. Sizes must be positive integers; `scores` must be
   exactly integer `speed` and `capability` values from 1 through 5;
   `benchmark` must contain non-empty `label` and `device` strings no longer
   than 120 characters.
5. Validate `modelInstall` as exactly `serviceKey` and `models`. Require 1–32
   unique model entries, each exactly `id`, `label`, and boolean `recommended`;
   exactly one entry must be recommended. `serviceKey` must equal the Service
   entrypoint ID, and every model ID must use that prefix and identify a model
   with a non-empty `weights` declaration in the entrypoint.
6. Preserve the accepted manifest values exactly as covered by the submitted
   artifact manifest digest. Public Package detail, catalog, search, and
   recommendation responses must project these fields from the published
   release instead of inferring them from names or descriptions.
7. Keep existing Packages without these fields valid. Do not synthesize or
   overwrite Publisher-signed values on the Cloud side.

## Acceptance tests

- A valid model Service submission containing all three fields reaches candidate,
  review, and published states, and the public API returns the same values.
- Missing `modelProfile` or `modelInstall`, mismatched Service/model IDs,
  unsupported categories, duplicate tasks, malformed
  task names, out-of-range scores, model metadata on non-Service Packages, and
  unknown additional fields are rejected.
- Existing manifest v1 submissions without the fields continue to publish.
- The signed Repository snapshot and artifact/envelope verification behavior
  remains unchanged.

This document is the handoff for the AI2Apps Cloud development project. No
Cloud-side code or production deployment is performed from this repository.
