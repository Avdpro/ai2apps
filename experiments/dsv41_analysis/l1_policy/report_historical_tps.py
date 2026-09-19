"""Summarize matched historical-fixture regression investigation."""
import hashlib,json
from pathlib import Path
import numpy as np
from safetensors.numpy import load_file
root=Path('artifacts/dsv41-historical-tps-check-20260915')
oldroot=Path('artifacts/dsv41-decode-dispatch-ab-20260914/legacy1')
old=json.loads((oldroot/'manifest.json').read_text())
hashes=[hashlib.sha256(load_file(str(oldroot/f'{i:02d}_logits.safetensors'))['logits'].astype(np.float32).tobytes()).hexdigest() for i in range(129)]
rows=[]
for name,path in [('historical-legacy1',oldroot)]+[(n,root/n) for n in ['historical-reread','current-baseline','current-new','pre-l1-rerun','current-new-repeat','pre-l1-repeat']]:
 m=json.loads((path/'manifest.json').read_text());assert m['status']=='complete'
 assert m['input_ids']==old['input_ids'] and m['generated_ids']==old['generated_ids']
 if name!='historical-legacy1':assert m['logits_sha256']==hashes
 if 'new' not in name:assert m['cache_stats']==old['cache_stats'] and m['adaptive_l1']['promotions']==old['adaptive_l1']['promotions']
 t=m['step_seconds'];c=m['cache_stats']
 rows.append(dict(name=name,tps=128/sum(t[1:]),first_decode_s=t[1],tail112_tps=112/sum(t[17:]),hit_pct=100*(c['l1_hits']+c['l0_hits'])/c['route_requests'],misses=c['misses'],decode_io_s=sum(m['adaptive_l1']['decode_io_seconds'].values()),peak_gb=m['sampled_physical_footprint_peak_bytes']/1e9))
(root/'verified-comparison.json').write_text(json.dumps({'rows':rows,'all_129_logits_exact':True,'same_input_output':True},indent=2))
lines=['# DS4.1F 历史 TPS 回退核查（2026-09-15）','','## 方法','','历史锚点为重复科普输入 2048 tokens / Decode 128，Natural 完整 Top6，Main40/Hot8，Prefill64，legacy dispatch，关闭层回调。沿用同一 SSD checkpoint。Decode TPS 包含首个 Decode；另列排除前16个 Decode 的后112步吞吐，不能混作完整 TPS。所有新运行的129份 logits、输入和输出与历史逐字节一致。','','历史源码未能完整恢复到9月14日同一哈希；独立旧源码使用 L1 shape 初期归档，早于本轮 L1 策略及晋升复用改动。运行使用当前相同 Python/MLX/native 二进制，不能据此排除更早的环境或代码变化。原归档路径：`artifacts/dsv41-l1-shape-20260915/source-snapshot/initial-experimental-source.tar.gz`。','','| 版本 | 完整 Decode TPS | 首个 Decode 秒 | 后112步 TPS | 命中率 | Decode native IO 秒 | 峰值 GB |','|---|---:|---:|---:|---:|---:|---:|']
for r in rows:lines.append(f"| {r['name']} | {r['tps']:.3f} | {r['first_decode_s']:.3f} | {r['tail112_tps']:.3f} | {r['hit_pct']:.2f}% | {r['decode_io_s']:.3f} | {r['peak_gb']:.3f} |")
lines+=['','## 解释边界','','- 最近不到5 TPS 的测试换成代码和中文记录分析任务，命中率约71%–73%；历史重复科普输入约88%。跨输入 TPS 不能作为代码回退比例。此前报告未同时呈现历史锚点，容易造成误解。','- 原样本在当前代码上仍未恢复历史完整7.36 TPS；旧源码同环境也慢，首个 Decode 时间明显增长。这里只定位时间发生在哪一段，未证明是编译、I/O、调度或后台负载中的哪一种原因。','- 不能把低命中样本约1.1%的收益推广为所有输入受益；新策略在本高命中样本并未提升命中率。','- 当前 baseline 仍为默认，新 eviction_dual 仍需显式启用；本次调查未改 Runtime 默认或部署。','- I/O 是 native请求计时，允许系统页缓存，并非物理SSD测量。系统曾观察到浏览器GPU及其他后台负载，没有主动结束用户进程；系统无已记录的 thermal warning。这些观察不能单独证明因果。','','## 复现与证据','','入口：`experiments/dsv41_analysis/l1_policy/check_historical_tps.py`。独立旧源码和反序复测采用同样的 `--prompt-json experiments/dsv41_analysis/fixtures/prefill2048.json --decode 128 --prefill-slots 64 --main-slots 40 --decode-dispatch legacy --logits-mode hash`，旧源码入口位于结果目录 `pre-l1-source/experiments/dsv41_mlx/run.py`；新策略额外 `--l1-policy eviction_dual`。','','逐次 manifest、日志和比较 JSON：`artifacts/dsv41-historical-tps-check-20260915/`。']
Path('docs/dsv41f-historical-tps-regression-check-2026-09-15.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(rows,indent=2))
