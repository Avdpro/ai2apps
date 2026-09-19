# MLX-RVC experiment

This directory contains the validation harness for the native MLX-RVC source
now owned by `packages/omlx-model-rvc/src/mlx_rvc`. It remains isolated from
installed model state until quality, Package, and sandbox gates pass.

## Fixed upstream

- Repository: `RVC-Project/Retrieval-based-Voice-Conversion-WebUI`
- Revision: `81eed5e8f68b6bed1789f682fe78cdd324495afc`
- Initial target: RVC v2, F0-enabled, 48 kHz, RMVPE

PyTorch is permitted only in the offline oracle and trusted checkpoint
conversion environment. Shipping inference consumes safetensors and executes
the content encoder, pitch extractor, retrieval, synthesizer, and audio
pipeline with MLX or ordinary bounded audio I/O code.

## Checkpoint boundary

Legacy RVC `.pth` files are pickle containers and are not accepted by the
shipping worker. `checkpoint.export_legacy_checkpoint()` loads a trusted model
offline with `weights_only=True`, removes training-only posterior encoder
weights, and emits:

```text
model.safetensors
model.json
```

The retrieval index will similarly be converted offline from FAISS `.index`
to a versioned safetensors vector bank. Runtime retrieval uses MLX exact Top-K,
so the production Runtime does not require Torch or FAISS.

## Planned parity order

1. RVC config, pitch binning, retrieval, weight normalization, and convolution
   layout primitives.
2. Text/content encoder, followed by ContentVec/HuBERT v2 feature extraction.
3. RMVPE mel frontend and E2E network.
4. Reverse residual coupling flow.
5. NSF source generator and decoder.
6. Audio-to-audio composition, chunking, RMS mixing, and crossfade.
7. File and streaming benchmarks on Mandarin, English, and singing fixtures.

See `VALIDATION.md` for gates and recorded evidence.

Run the contract tests with:

```bash
.venv/bin/python -m pytest experiments/mlx_rvc/tests -q
```

## Synthetic Serena test voice

`qwen_serena_corpus.jsonl` is a 48-Mandarin/24-English script for producing a
clearly labelled synthetic development voice from the Qwen3-TTS CustomVoice
`serena` preset. Generate the source corpus with:

```bash
.venv/bin/python -m experiments.mlx_rvc.generate_qwen_voice_dataset \
  --model /path/to/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit \
  --output /path/to/qwen-serena-dataset
```

The pinned RVC trainer needs the MPS compatibility changes in
`patches/rvc-81eed5e-mps-training.patch`. Training is an offline developer
operation and may use Torch; it is not part of the Runtime or Package. Once a
v2/48 kHz/F0 checkpoint and FAISS index have been trained, create the three
non-executable MLX distributions (voice, shared ContentVec, and shared RMVPE):

```bash
.venv/bin/python -m experiments.mlx_rvc.build_qwen_serena_checkpoint \
  /path/to/voice.pth /path/to/voice.index /path/to/hubert_base \
  /path/to/rmvpe.pt /path/to/dataset/manifest.json /path/to/output \
  --training-revision 81eed5e8f68b6bed1789f682fe78cdd324495afc \
  --asset-revision e6d0c1a17da07c33557852f9dfa2bd44cc75737d
```

The voice is for local development and validation. Its metadata must retain
`synthetic: true`; it is not a recording of a real person and must not be
presented as an official Qwen RVC voice.

## Native MLX training

The Package now contains the complete native path in `mlx_rvc.training` and
`mlx_rvc.voice_training`: MLX ContentVec/RMVPE preprocessing, posterior
encoding, forward Flow, NSF Generator, RVC v2 nine-branch discriminator,
float32 losses, BF16 optimization, bounded retrieval-bank construction,
periodic safetensors checkpoints, progress/cancellation, and final Voice
Bundle manifests. Run it through `packages/omlx-model-rvc/src/train_voice.py`.

On the 72-file, 370.8-second Serena fixture, unrestricted 100-epoch training
completed 1,800 G/D updates in 667.57 seconds, versus roughly 35 minutes for
the Torch/MPS oracle. It failed the ASR content gate, so it is retained only as
diagnostic evidence. The shipping default is `adaptation=safe`, which freezes
`enc_p` and `flow`; a 10-epoch/180-step validation completed in 58.02 seconds
and preserved the complete Mandarin sentence structure in independent Qwen3
ASR. Matrix-form exact L2 retrieval reduced the 36,936-vector inference peak
from 64.9 GB to 5.85 GB and RTF from 0.205 to 0.0448 on the same 11.04-second
fixture.

The original 30-epoch BF16 safe candidate was rejected after listening exposed
stronger tremolo and output roughly 10.4 dB below the Torch oracle. The repaired
trainer restores the pinned upstream 48 Hz high-pass, overlapping chunk and
blended peak normalization, plus its 128-bin log-mel L1 objective at weight 45.
Pure FP16 optimization is non-finite; FP16 compute with FP32 Adam master weights
completed a deterministic 30-epoch, 1,080-step run in 418.38 seconds. Its same-
source preview measured -22.95 dBFS RMS, -5.70 dBFS peak, RTF 0.0418, and an
8.43-cent frame-delta pitch-error MAD. It remains a listening candidate pending
content transcription and speaker-similarity gates.

The resumable trajectory subsequently completed 60 epochs/2,160 steps in
858.65 seconds, then restored its full G/D and Adam state and continued to 100
epochs/3,600 steps in another 577.47 seconds. The 100-epoch preview measured
-24.27 dBFS RMS, -7.93 dBFS peak, and RTF 0.0417. Its pitch-error delta MAD rose
from 8.40 cents at epoch 60 and 8.22 at epoch 70 to 10.56 at epoch 100, so the
latest checkpoint is not automatically considered the best; 60/70/80/90/100
remain listening candidates pending content and speaker-similarity evaluation.

After downloading the fixed official `pretrained_v2/f0G48k.pth`, validate real
checkpoint primitives on Metal with:

```bash
.venv/bin/python -m experiments.mlx_rvc.validate_primitives /path/to/f0G48k.pth
```

Validate the complete six-layer RVC v2 TextEncoder with:

```bash
.venv/bin/python -m experiments.mlx_rvc.validate_text_encoder \
  /path/to/f0G48k.pth --upstream /path/to/pinned/rvc/source
```

The remaining model-block validators are:

```bash
.venv/bin/python -m experiments.mlx_rvc.validate_flow CHECKPOINT --upstream RVC_SOURCE
.venv/bin/python -m experiments.mlx_rvc.validate_generator CHECKPOINT --upstream RVC_SOURCE
.venv/bin/python -m experiments.mlx_rvc.validate_synthesizer CHECKPOINT --upstream RVC_SOURCE
.venv/bin/python -m experiments.mlx_rvc.validate_contentvec HUBERT_DIRECTORY
.venv/bin/python -m experiments.mlx_rvc.validate_rmvpe RMVPE_CHECKPOINT \
  --upstream RVC_SOURCE
```
