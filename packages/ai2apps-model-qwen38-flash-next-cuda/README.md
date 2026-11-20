# Qwen3.8 Flash Next CUDA prototype

Unpublished, unsigned experimental source. Strict full-layer Top-10 parity and usable performance have NOT passed; do not promote this candidate to production.

Preserves the Mac service/model identity and pinned checkpoint distribution. Reads affine-Q4 experts in bounded ten-expert transfer batches and PLE rows on demand, dequantizes to BF16, preserves Top-10, and uses no replacement cache. No checkpoint bytes or framework dependencies are bundled. Uses the shared CUDA Qwen Worker frontend from the new Runtime candidate.

Full checkpoint SHA-256 verification and a clean whole-model math/EOS request passed. The rebuilt standalone Runtime passed standard isolated Worker image recognition, tool round trip, separated thinking, incremental streaming, explicit cancellation, disconnect cleanup and resumed generation. 128-tool selection and multiple-image coverage also passed; long-context performance remains pending. Text/image limits are the shared development limits (8192 total, 2048 output, 128 tools), not a long-context performance claim. Requires the exact Transformers 5.18.0 candidate environment; see spark/QWEN38-ALIGNMENT.md for limitations and raw evidence.

The contract requires one `modelInstall.models[].recommended` entry; it identifies the sole default variant, not production readiness. The candidate remains experimental and blocked from production promotion.

The current candidate enables batched expert transfers after bitwise-equal microchecks and a clean full-model math/EOS probe. Its full basic Worker regression passed again; both batched and unbatched receipts are retained.
