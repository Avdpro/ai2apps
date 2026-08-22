# Qwen3.8 27B NVFP4 real-checkpoint validation

## Result

The installable `omlx-model-qwen38` adapter successfully loaded and generated
with the complete Hugging Face checkpoint below through oMLX's
`VLMBatchedEngine`:

- repository: `unsloth/Qwen3.8-27B-NVFP4`;
- revision: `16b6615af3548b88e2d8e382457bc705b00479cf`;
- snapshot bytes: `23,444,511,709`;
- main weights: `22,568,192,096` bytes;
- MTP weights: `849,400,392` bytes;
- host: Apple Silicon, 128 GiB unified memory.

The snapshot was downloaded with the revision pinned, contained no residual
`.incomplete` files, and exposed 1,953 tensors in the primary safetensors file.
Its index maps 1,968 tensors across the primary and MTP files.

## Commands

```bash
HF_HUB_DISABLE_XET=1 .venv/bin/hf download \
  unsloth/Qwen3.8-27B-NVFP4 \
  --revision 16b6615af3548b88e2d8e382457bc705b00479cf \
  --local-dir ~/.omlx/models/unsloth/Qwen3.8-27B-NVFP4 \
  --max-workers 4

.venv/bin/python scripts/smoke_qwen38_vlm.py \
  ~/.omlx/models/unsloth/Qwen3.8-27B-NVFP4 \
  --max-tokens 24
```

## Generation checks

| Check | Prompt tokens | Generated tokens | End-to-end time | End-to-end TPS | Peak MLX |
|---|---:|---:|---:|---:|---:|
| Exact English response | 13 | 10 | 4.935 s | 2.026 | 22.329 GiB |
| Chinese explanation | 9 | 48 | 5.030 s | 9.543 | 22.313 GiB |
| oMLX dashboard screenshot | 7,685 | 64 | 28.742 s | 2.227 | 25.672 GiB |

The English check returned `Qwen3.8 local inference works.` exactly. The
Chinese check produced a relevant Rayleigh-scattering explanation. The image
check correctly identified the supplied screenshot as overlapping light and
dark oMLX Status/admin interfaces.

These results validate checkpoint download, adapter entry-point discovery,
mixed FP8/NVFP4 weight loading, text generation, and vision encoding. They are
the basis for the signed recommendation in
`packages/omlx-model-qwen38/release-checkpoints.json`.
