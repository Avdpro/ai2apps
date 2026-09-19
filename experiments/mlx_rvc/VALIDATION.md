# MLX-RVC validation

Date: 2026-09-05

## Boundary

- No App, Runtime, Registry, Package manifest, or installed model state is
  modified by this experiment.
- The shipping target has no Torch, torchaudio, or FAISS dependency.
- PyTorch may be used only as a fixed-revision numerical oracle and trusted
  offline checkpoint converter.
- Generated checkpoints, audio, and benchmark reports stay outside Git.

## Upstream baseline

- Source revision: `81eed5e8f68b6bed1789f682fe78cdd324495afc`
- Initial architecture: RVC v2, F0-enabled, 48 kHz
- Content features: final 768-dimensional HuBERT hidden state
- Pitch extractor: RMVPE
- Default retrieval neighbors: 8
- Decoder hop: 480 samples

## Acceptance gates

1. Every converted tensor is finite, named, shape-validated, and stored in a
   non-executable safetensors artifact with immutable source/output hashes.
2. Every model block matches the fixed PyTorch CPU oracle in shape and within a
   scale-aware numerical threshold recorded here.
3. End-to-end content CER/WER and speaker similarity retain at least 95% of the
   PyTorch oracle score on the same model and inputs.
4. F0 voiced/unvoiced decisions and pitch trajectory remain equivalent enough
   to avoid audible octave jumps.
5. Chunk boundaries introduce no click, discontinuity, or duration drift.
6. Warm RTF is below 0.25 for the realtime profile and below 0.5 for the
   quality profile on the recorded Apple Silicon test machine.
7. Runtime inspection proves that Torch, torchaudio, and FAISS are absent.

## Current result

The upstream revision and first inference target are locked. The repository now
contains validated legacy configuration parsing, RVC-compatible pitch binning,
a safe offline safetensors conversion boundary, and MLX-native exact Top-K
retrieval with inverse-squared-distance blending.

The first real-checkpoint primitive gate used the immutable Hugging Face
revision `e6d0c1a17da07c33557852f9dfa2bd44cc75737d` and
`pretrained_v2/f0G48k.pth`:

- Size: 75,465,569 bytes
- SHA-256: `b5d51f589cc3632d4eae36a315b4179397695042edc01d15312e1bddc2b764a4`
- Linear relative RMSE / peak-normalized error: 0.0412% / 0.0397%
- Conv1d relative RMSE / peak-normalized error: 0.000015% / 0.000028%
- ConvTranspose1d relative RMSE / peak-normalized error: 0.0721% / 0.0783%
- Output shapes matched for all three operations.

The experiment test suite is `12 passed`. All inference model blocks now run
natively in MLX. Real target-voice audio-to-audio quality, long-file chunking,
RTF, and resident-memory gates remain open; no listening-quality claim is made.

The complete six-layer v2 TextEncoder now passes the single-item inference
shape used by RVC, with no sequence padding:

- Output shape: `[1, 192, 31]`
- Mean relative RMSE / peak-normalized error: 0.1220% / 0.0868%
- Log-scale relative RMSE / peak-normalized error: 0.0053% / 0.0180%
- Mask: exact

A deliberately padded 27-of-31-frame diagnostic currently has 5.74% mean
relative RMSE and does not pass. The production RVC pipeline processes one
trimmed utterance at a time and does not require padded batching, but padded
batch parity remains an explicit open issue rather than being hidden by a
looser threshold.

The remaining RVC synthesizer blocks pass the same fixed 48 kHz checkpoint:

- Reverse flow relative RMSE: `1.4743e-7`
- NSF generator relative RMSE / peak-normalized error: `0.2617% / 0.3660%`
- Combined TextEncoder + flow + decoder latent relative RMSE: `0.0247%`
- Combined waveform relative RMSE / peak-normalized error: `3.7792% / 4.3714%`
- Combined waveform error SNR: `28.452 dB`

The phase-sensitive waveform gate is 5%; the substantially stricter per-block
gates above prevent that aggregate threshold from hiding a structural error.

The official RVC HuBERT/ContentVec checkpoint contains 94,567,808 converted
parameters. On 1.25 seconds of deterministic input, native MLX v2 output has:

- Shape: `[1, 62, 768]`
- Relative RMSE / peak-normalized error: `2.7620% / 2.0143%`
- Cosine similarity: `0.99961936`
- Layer 0 relative RMSE: `0.0213%`; layer 11: `1.1191%`; final layer: `2.7910%`

The fixed official RMVPE checkpoint also passes native MLX parity:

- Mel shape: `[1, 128, 101]`; relative RMSE: `0.0306%`
- U-Net / CNN relative RMSE: `0.000266% / 0.000263%`
- Bidirectional GRU relative RMSE: `0.0162%`
- Final 360-bin salience shape: `[1, 101, 360]`; relative RMSE: `0.1938%`

An initial `RVCInferencePipeline` now composes 16 kHz filtering, ContentVec,
optional MLX exact retrieval, feature protection, RMVPE, pitch shifting, and
the MLX synthesizer. Long-file segmentation is now implemented and measured
below; real target-voice listening and similarity tests remain required before
Package publication.

## Audio-to-audio results

Hardware: Apple M5 Max, 128 GiB unified memory. The elapsed interval includes
all native MLX inference stages but excludes checkpoint conversion/loading.

- 1.00 second unchunked: 0.98 second output, RTF `0.1071`
- 10.00 seconds unchunked: 9.98 second output, RTF `0.0360`
- 60.00 seconds unchunked: 59.98 second output, RTF `0.0376`, MLX peak
  `18,416,580,400` bytes
- 60.00 seconds, 10-second chunks, 1-second context and 40 ms crossfade:
  59.98 second output, RTF `0.0357`, MLX peak `6,200,394,044` bytes

The chunked path therefore cut observed peak MLX allocation by about 66.3%
without reducing throughput or changing output duration.

A final user-style RVC v2/48 kHz checkpoint also passed safe conversion and
execution. Its legacy IVF index was converted to an exact-search safetensors
bank containing 3,399 vectors of width 768. With retrieval rate 0.75:

- English fixture: 3.8396 seconds in / 3.8200 seconds out, RTF `0.0481`,
  MLX peak `3,734,968,112` bytes
- Mandarin fixture: 7.6148 seconds in / 7.6000 seconds out, RTF `0.0463`,
  MLX peak `6,036,257,792` bytes

Both outputs are finite 48 kHz WAV files. Listening review and an objective
speaker-similarity comparison are still required; engineering execution alone
is not presented as proof of target-voice quality.
