# MLX personalized actor-model training plan

Date: 2026-09-05

## Decision

Keep native GhostV2 MLX as the single default for immediate, one-shot actor
replacement. Add a separate **Personalized/Studio** workflow inspired by
DeepFaceLab SAEHD and compatible with the useful parts of the DFM inference
contract. This workflow trains a dedicated identity model for repeated use on
one actor or production; it is not a fallback for small-memory machines.

The upstream DeepFaceLab and DeepFaceLive repositories were archived on
2024-11-13. Their code is GPL-3.0 and their original training stack is
TensorFlow/CUDA-oriented. Treat them as an architecture and file-contract
reference, pin the audited revisions, preserve notices, and implement native
MLX modules rather than depending on an abandoned executable environment.

## Why this is worth doing

GhostV2 accepts one or more reference images and works immediately. That is the
right default and remains the best interactive experience. A pair-trained
autoencoder can spend hours learning the destination actor's lighting, pose,
facial structure, and mask distribution. For a long film with the same source
and destination identities, that specialization can improve consistency,
profiles, skin detail, and shot-to-shot stability.

The trade-off is substantial: users need diverse, consented footage, face
extraction and curation, training time, checkpoints, and manual quality review.
It should therefore appear as `Train personalized actor model`, never as a
second instant-swap quality toggle.

## Proposed capability pipeline

1. `actor.dataset.extract`: decode media, detect/track the selected person,
   align faces, score blur/occlusion/pose, and deduplicate near-identical crops.
2. `actor.dataset.review`: present source/destination sets with coverage and
   quality warnings; allow deletion before training.
3. `actor.model.train`: train an MLX SAEHD-style shared encoder/intermediate
   plus identity-specific decoder and mask heads using FP16 weights with FP32
   optimizer state where numerical stability requires it.
4. `actor.model.resume`: save model, optimizer, scheduler, iteration, random
   state, and dataset fingerprint so every training job can continue rather
   than restart.
5. `actor.model.preview`: emit a fixed validation sheet at intervals so the
   user can stop at the visually best checkpoint instead of assuming the last
   iteration is best.
6. `actor.model.export`: publish an AI2Apps native trained-model asset. Add DFM
   import/export only after the DFM graph variants and license boundary have
   been audited.
7. `actor.replace.image/video`: reuse the GhostV2 detector, tracker,
   color-match, mask, compositing, audio, progress, and cancellation layers;
   replace only the aligned-face generator.

## First MLX experiment

Use a 224 or 256 pixel whole-face model, a small consented two-identity fixture,
and a pretrained shared encoder/intermediate if its provenance permits
redistribution. Establish Torch/TensorFlow reference tensors only for parity;
the measured production path must be MLX.

The first gate is deliberately narrow:

- loss decreases after resume exactly as it would in an uninterrupted run;
- fixed validation previews show identity improvement without new flicker;
- no NaN/Inf over a sustained FP16 training run;
- peak unified memory is measured at batch sizes 2, 4, and 8;
- MLX training is materially faster than CPU and competitive with the available
  Mac GPU reference path;
- the trained MLX model runs through the existing video pipeline.

Only after this gate should we implement full SAEHD options such as face type,
random warp schedules, GAN/patch loss, yaw balancing, eyes/mouth priority, and
DFM interoperability.

## Runtime and Package boundary

The current MLX Runtime already contains the basic tensor, convolution,
autograd, optimizer, image, and video primitives needed for the first training
prototype. Start outside the App and Runtime, as with GhostV2. A Runtime update
is justified only if profiling identifies a reusable missing Metal operation
or training-state service; dataset tooling and model-specific losses belong in
the personalized Package.

Trained identity checkpoints are user assets. They must not be uploaded or
published by default. The Package should record provenance and consent metadata,
support local deletion, and make export/share an explicit action.
