# DeepSeek V4 Flash 2-bit vs 4-bit benchmark (2026-08-10)

## Test setup

- Device: local Apple Silicon Mac, 128 GiB unified memory.
- Engine: `DeepseekV4FleshEngine`, Exact/Natural decode path, Top60 cache bank.
- Prompt: `帮我写一个网页，中间有个按钮，点击后开始放礼花。请给出完整的单文件 HTML、CSS 和 JavaScript 实现，并继续解释性能与无障碍处理。`
- Workload: one warm-up token followed by 1,024 generated tokens; the final 128 tokens are measured separately.
- Scope selection: both checkpoints selected `coding`.
- Auto mode: adaptive L1 enabled, with one interval update and one turn-end update in both runs.
- Memory: MLX allocator values are the primary numbers. `active` is sampled after generation; `peak` includes transient L1 rebuilding.

## Results

| Checkpoint | L1 mode | Load | TTFT | Decode | Final 128 | MLX active | MLX peak |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2-bit DQ | Off | 6.74 s | 1.34 s | 9.75 TPS | 9.10 TPS | 31.23 GiB | 31.46 GiB |
| 2-bit DQ | Auto | 7.97 s | 1.34 s | 10.12 TPS | 10.85 TPS | 31.23 GiB | 50.40 GiB |
| 4-bit | Off | 25.69 s | 1.91 s | 7.21 TPS | 7.33 TPS | 51.83 GiB | 54.17 GiB |
| 4-bit | Auto | 25.61 s | 1.93 s | 7.61 TPS | 8.66 TPS | 51.83 GiB | 82.47 GiB |

## Comparison

At the same L1 setting, 2-bit is faster and uses materially less steady memory:

- Off: decode is 35.2% faster and final-128 throughput is 24.1% faster.
- Auto: decode is 33.0% faster and final-128 throughput is 25.3% faster.
- MLX active memory is 39.8% lower in both modes (31.23 vs 51.83 GiB).
- Peak memory is 41.9% lower with L1 Off and 38.9% lower with L1 Auto.
- TTFT is about 30% lower. Model load is also much shorter in these warm-filesystem runs, but load time is sensitive to the OS page cache and should not be treated as a cold-SSD result.

Adaptive L1 improved both checkpoints on this long, initially mismatched HTML workload:

- 2-bit: average decode +3.8%, final 128 tokens +19.3%.
- 4-bit: average decode +5.6%, final 128 tokens +18.1%.
- Off and Auto produced identical text within each checkpoint. The 2-bit and 4-bit outputs differ, as expected from quantization.

The important memory caveat is that L1 rebuilding currently duplicates a substantial part of the bank transiently. Auto therefore peaks at 50.40 GiB for 2-bit and 82.47 GiB for 4-bit even though post-generation active memory returns to 31.23 and 51.83 GiB. On lower-memory Macs, Auto update scheduling or in-place/staged rebuilding needs a memory-pressure guard.

## Artifacts

- `artifacts/release-gate/deepseek2bit-html-off-1024-memory.json`
- `artifacts/release-gate/deepseek2bit-html-auto-enabled-1024-memory.json`
- `artifacts/release-gate/deepseek4bit-html-off-1024-memory.json`
- `artifacts/release-gate/deepseek4bit-html-auto-1024-memory.json`

`deepseek2bit-html-auto-1024-memory.json` is intentionally excluded: that exploratory run omitted the global adaptive-L1 environment switch, so it behaved as Off rather than Auto.
