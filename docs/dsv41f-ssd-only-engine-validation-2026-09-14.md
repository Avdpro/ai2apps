# DS4.1F SSD-only engine validation — 2026-09-14

## Result

Current DS4.1F MLX runner, CPU reference reader and analysis entrypoints use `artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD`; experts come from its `experts/` directory. No executable old checkpoint/store path references remain in experiments, scripts, tests, configs, omlx or ai2apps scans. Historical receipts have not been rewritten.

Nine regression cases passed with macOS sandbox file-read access denied to both `artifacts/dsv41-download` and `artifacts/dsv41-full-expert-store`. Explicit read probes confirmed PermissionError before inference. Cases: raw text, single image, three text dialogue-history replays, four chronological image dialogue-history replays. Each performs prefill plus up to three decode forwards, greedy/full Top6, dynamic L1 40/L0 8, prefill64, image cap256, stop-at-EOS for chat cases. The histories are saved canonical conversations, not a claim of newly generated long multi-turn transcripts or incremental image KV support.

All 28 full-logit outputs were bitwise equal (max_abs=0) to saved baselines; prompt token IDs and generated token prefixes also match. Peak physical footprint 58,217,945,128 bytes, below65GB.

CPU Store independently reconstructed24 quantized tensors across layers0/39 and experts0/383; every original payload SHA256 matched while old directories were blocked. This preserves CPU reference checks without restoring an original expert safetensors copy.

## Changes

- Updated run, reference and analysis Python paths, including local image resources and official encoding/model sources.
- CPU reference Store maps external tensors to expert-file offsets with checkpoint metadata validation and bounds checks.
- Re-exporting experts requires an explicit output and refuses to overwrite the input checkpoint experts.
- Receipts now include explicit checkpoint/expert paths and source-index provenance; MLX-vs-CPU comparison can retain original source identity across layouts.
- Multi-turn benchmark accepts a separate output directory instead of overwriting historical fixtures.

## Remaining assets

Keep the complete SSD checkpoint, `artifacts/dsv41-native-build`, reference/native source modules, and saved regression baselines. Native modules are runtime code, not a dependency on the old weight store. Current tests establish removal eligibility for the two old weight directories from an inference-dependency perspective; no files were deleted in this task. Formal Runtime/Package publication remains separate and incomplete.

Evidence: `artifacts/dsv41-ssd-only-regression-20260914/deny-old.sb`, `verify.py`, `suite.log`, `results.json`, `cpu-reader.json`.


## Old expert store removed

After explicit user authorization, `artifacts/dsv41-full-expert-store` was deleted. Forty layer metadata records matched the independent new SSD files; no process held old files open. JSON metadata receipts were retained under `artifacts/storage-audit-20260914/old-dsv41-expert-store-deletion`. Logical size removed288,778,091,894 bytes (~268.95GiB), immediate free-space increase only147,456 bytes: APFS expert payload extents remain referenced by the new checkpoint. Background writes can affect filesystem free-space measurements. Original checkpoint, new SSD checkpoint and native loader are retained.


## Original checkpoint removed

User explicitly authorized deleting `artifacts/dsv41-download/DeepSeek-V4.1-Flash`. No process held its files open; all new SSD checkpoint files matched manifest sizes and were independent regular files. The old original index matched recorded source identity. After archiving original index/config/license/README and a size inventory, the original directory was deleted. Observed immediate free-space gain510,316,687,360 bytes (~475.27GiB); available space rose from~641GiB to~1116GiB. New checkpoint, native loader and regression evidence remain. Receipt: `artifacts/storage-audit-20260914/original-dsv41-checkpoint-deletion/deletion.json`.
