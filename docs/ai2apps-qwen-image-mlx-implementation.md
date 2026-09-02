# Qwen Image MLX implementation and optimization receipt

Date: 2026-08-25

## Package contract

- Package: `ai2apps/model-qwen-image-mlx` 0.1.0 development
- Runtime: `ai2apps/runtime-omlx >=1.5.1,<2.0.0`
- Generation: `Qwen/Qwen-Image-2512` at
  `25468b98e3276ca6700de15c6628e51b7de54a26`
- Editing: `Qwen/Qwen-Image-Edit-2511` at
  `6f3ccc0b56e431dc6a0c2b2039706d7d26f22cb9`
- Preferred mirror: ModelScope, with its resolved revisions recorded separately
  from the immutable Hugging Face identity.
- Operations: text-to-image plus ordered one-to-three-reference editing.
- Default quantization: Q8; Q4 is exposed as a low-memory option, not the
  recommended quality/performance mode.

The adapter returns both OpenAI `data[].b64_json` and AI2Apps `image.dataUrl`
shapes. Generation and edit checkpoints cannot be used for the wrong operation.
The Edit-2511 model name is set on a private mflux config copy, avoiding mflux
0.19's older Edit-2509 default without mutating its shared cached config.

Development artifact:

- `packages/ai2apps-model-qwen-image-mlx/dist/ai2apps.model.qwen-image-mlx-0.1.0-development.ai2service`
- file SHA-256: `f7ebc76c4727af5c65bda94127f65c70675facbd2fe1e75a74c2f0f29f6a305a`
- package digest: `sha256:26451e9e358fec6b33d6029551d927ef3e96357f6fae1646859d8800db7578b6`
- publisher key ID: `ai2apps:development-1.5.1-qwen`

## Implemented MLX optimizations

1. A Worker retains one loaded pipeline for each active model/quantization key.
2. Revision-, operation- and quantization-scoped Q8/Q4 checkpoints are written
   through a staging directory and committed atomically under a file lock.
3. Generation prompt embeddings use an evaluated eight-entry LRU instead of
   mflux's unbounded dictionary, preventing retained lazy graphs and unbounded
   memory growth.
4. Editing uses an evaluated two-entry prompt/reference cache keyed by reference
   image content hashes, so temporary request paths do not defeat cache reuse.
5. Runtime `mlx-only-v2` lazily imports the optional PiD/torch conversion stack;
   normal Qwen generation and editing remain torch-free.
6. When callers explicitly select `guidance=1`, the optimized generator skips
   the mathematically unused negative transformer branch. The default
   guidance-four quality path remains unchanged.

The first Q8 materialization, save, atomic commit and native reload took 10.000
seconds and produced 36,119,518,505 bytes. A new Worker loaded that native tree
in 0.641 seconds. Source checkpoints remain read-only.

## Mac baseline

The initial fixed-seed smoke uses one Chinese poster prompt. These measurements
are for comparison and include the current machine's sustained thermal behavior.

| Mode | Geometry / steps | Request time | MLX peak | Finding |
| --- | ---: | ---: | ---: | --- |
| mflux online Q8, warm | 512 x 512 / 4 | 5.346 s | 39.81 GB | reference |
| AI2Apps bounded-cache Q8, warm | 512 x 512 / 4 | 5.310 s | 39.81 GB | same denoiser speed |
| AI2Apps Q4, warm | 512 x 512 / 4 | 6.527 s | 31.34 GB | 22.1% slower; lower text fidelity |
| native Q8 | 1024 x 1024 / 20 | 174.783 s | 44.55 GB | exact requested Chinese text |
| native Q8 | 1024 x 1024 / 12 | 94.619 s | 44.55 GB | exact requested Chinese text |
| native Q8, guidance-one Fast | 1024 x 1024 / 12 | 40.553 s | 44.55 GB | 57.1% faster; weaker title typography |
| native Q8, fixed-seed hard pair | 1024 x 1024 / 20 | 161.836 s median | 44.55 GB | better primary date/title fidelity than 12 steps |

Q4 reduces peak memory by about 21% but is slower on this workload and produced
less reliable small text. It remains useful for lower-memory Macs only.

The 20-step 1024 run started near 6.3 seconds/step and ended near 10.4
seconds/step, so sustained thermals materially affect long generations. The
shipping generation default is 20 steps; it takes roughly 2.6-3.0 minutes on
this machine. Twelve steps is a useful Draft setting at roughly 1.6-1.9
minutes, but the fixed-seed layout test showed more date/title errors. Twenty
steps improved the primary title, subtitle and date, although dense labels are
still not perfectly reliable and quality is not monotonic for every label.

The guidance-one implementation is a real compute optimization, not an
approximation of the requested guidance value: at guidance one the normalized
CFG equation reduces exactly to the positive prediction. Quality still differs
from guidance four because the caller selected a different guidance regime. In
the poster test it retained the requested subtitle but weakened the main title,
so it is suitable as an explicit Fast mode, not as the default text-rendering
mode.

## Optimization round: 2026-08-26

The shipping Q8 graph was held behind a fixed-seed quality gate. Candidates
needed a repeatable request-level improvement of at least 5% without material
text, composition, or edit regression. No approximate candidate was allowed to
replace the guidance-four default.

A one-step 1024 x 1024 Metal capture identified the dominant kernels as MLX's
Q8 affine QMM (`group_size=64`, `bits=8`) and BF16 Steel SDPA with head dimension
128. The temporary GPU trace was 43 GB and was deleted after inspection. This
puts the remaining material opportunity below the Python pipeline, in Qwen-
shape-specific QMM/attention execution.

| Candidate | Result | Decision |
| --- | --- | --- |
| Shared CFG invariants | 5.918 -> 5.910 s at 512² | reject; noise-level gain |
| Compiled 60-layer CFG branch | 4.81 s steady | reject; resident memory rose to ~79 GB and new prompts recompiled |
| Fused RoPE Metal kernel | 5.4% at 512², but 100.8 -> 117.4 s at 1024²/12 | reject; high-resolution regression |
| Fused norm/AdaLN Metal kernels | 5.260 -> 5.293 s at 512²; severe 1024² regression | reject |
| Negative branch every two steps | 16.77 -> 12.98 s in one steady test | reject; Chinese text and spatial-label quality failed |
| Mixed Q8 group-size 128/64 | 5.595 -> 5.519 s at 512²; 38.60 -> 38.32 s in matched hot 1024² runs | reject; 0.7-1.4% gain |
| Uniform Q6 | 5.595 -> 6.836 s at 512² | reject; 22% slower despite ~4.7 GB lower peak |
| Prepacked Q/K/V projections | 5.433 -> 5.222 s in adjacent 512² A/B | hold; 3.9% is below gate and pixels are not identical |
| Q/K/V plus cached attention mask | 5.222 -> 5.470 s | reject; forced evaluation harmed lazy scheduling |
| Combined image/text AdaLN projection | ~1.3 -> ~4.7 s per step | reject and abort; unfavorable wide-output QMM tile |

The Q/K/V prototype releases the six source projection tensors after packing,
so steady resident and peak memory return to the unmodified Q8 baseline. Its
fixed-seed image remained visually close, but channel mean absolute pixel
differences were approximately 0.50, 0.99, and 2.15 on a 0-255 scale. Since the
speed result did not clear the gate, it remains benchmark-only and was not
added to the model package.

The next optimization stage should prototype a Qwen-specific Metal Q8 denoiser
path around the captured 3072-wide affine QMM shapes, starting with fused
Q/K/V output and epilogue scheduling without materializing duplicate packed
weights. A worthwhile implementation target is at least 10% denoiser or 8%
end-to-end improvement at 1024²/12 and 20 steps, with Q8 quality parity and no
peak-memory regression. Until that target is demonstrated, the product stays
on the audited MLX Q8 graph plus the exact guidance-one Fast mode.

## Earlier rejected experiment

A benchmark-only batched-CFG pipeline combines positive and negative branches
into one transformer call. At 512 x 512 it improved the warm request by only
4.4% (5.346 to 5.110 seconds) with visually equivalent output. At 1024 x 1024
it regressed to 36.54-37.99 seconds versus 27.06-33.40 seconds for the standard
path because batch-two activations increase Metal memory-bandwidth pressure.
It is not enabled in the product adapter.

## Spark parity status

The current Diffusers checkout on DGX Spark imports both `QwenImagePipeline`
and `QwenImageEditPipeline` with PyTorch 2.13/CUDA 13. The generation checkpoint
is downloading in the background from ModelScope at the locked
`ee3f7563eefa997af5a07dbe54a57e5babd3768b` revision. At handoff, 8.7 GB was
present and the process was actively writing; the remaining transfer is
limited by the Spark host's current CDN egress path. ModelScope's 8 MB ranged
downloader was retained because direct ModelScope CDN, Hugging Face Xet and
real-IP tests were slower.

Final CUDA BF16 speed, memory, image quality and fixed-seed contact-sheet
results must be appended only after every indexed shard is size-verified.
Interrupted SSH partial files were explicitly identified by a local/remote
size comparison and removed before the locked-revision resume. The final
fixed-seed benchmark scripts and prompt sets have already been copied to the
Spark benchmark directory.

Benchmark scripts and machine-readable results are under
`benchmarks/qwen_image`.
