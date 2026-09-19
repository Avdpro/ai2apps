"""Audit and report the twenty-run growth experiment without changing defaults."""
import hashlib,json,math
from pathlib import Path
import numpy as np
from report import measure
from growth import ROOT,OLD,LAYERS

def main():
    state=json.loads((ROOT/'state.json').read_text());assert state['status']=='complete' and state['completed_runs']==20
    shape=json.loads((ROOT/'growth.json').read_text());assert hashlib.sha256((ROOT/'growth.json').read_bytes()).hexdigest()==state['shape_sha256']
    data=json.loads((OLD/'dataset/dataset-manifest.json').read_text());cases=[];peaks={'main40':[],'growth':[]};hashes=0
    for ident in state['case_ids']:
        row=next(r for r in data['samples'] if r['id']==ident);variants={}
        reference=json.loads((OLD/'test-main40'/(ident+'-r0')/'manifest.json').read_text())
        for variant in ['main40','growth']:
            runs=[]
            for repeat in range(2):
                path=ROOT/variant/(ident+f'-r{repeat}')/'manifest.json';m=json.loads(path.read_text())
                assert m['status']=='complete' and not m['collect_routes'] and not m['expert_no_cache']
                assert m['main_capacities']==(shape['capacities'] if variant=='growth' else [40]*40)
                assert m['checkpoint_index_sha256']==shape['checkpoint_index_sha256'] and m['ssd_checkpoint_manifest_sha256']==shape['checkpoint_manifest_sha256']
                for key in ['input_ids','generated_ids','logits_sha256']:assert m[key]==reference[key],(ident,key)
                assert m['sampled_physical_footprint_peak_bytes']<=65_000_000_000
                metrics=measure(m);assert all(math.isfinite(v) for v in metrics.values());hashes+=len(m['logits_sha256']);peaks[variant].append(metrics['peak'])
                times=m['step_seconds'][1:]
                if len(times)==512:metrics.update(first128=128/sum(times[:128]),later384=384/sum(times[128:]))
                runs.append({'manifest':str(path.resolve()),'metrics':metrics})
            variants[variant]={'runs':runs,'mean':{k:float(np.mean([r['metrics'][k] for r in runs])) for k in runs[0]['metrics']}}
        cases.append({'id':ident,'scope':row['scope'],'language':row['language'],'tokens':row['tokens'],'decode_steps':row['decode_steps'],'variants':variants})
    keys=['decode','prefill','cold_decode','tail','hit_pct','all_hit_pct','promotion_loads','io','kernel_decode_read_gb']
    macro={v:{k:float(np.mean([c['variants'][v]['mean'][k] for c in cases])) for k in keys} for v in ['main40','growth']}
    result={'status':'complete','case_count':5,'run_count':20,'all_logits_exact_including_previous_baseline':True,'logit_hashes_checked':hashes,'shape_sha256':state['shape_sha256'],'macro':macro,'decode_gain':macro['growth']['decode']/macro['main40']['decode']-1,'peak_gb':{v:max(p) for v,p in peaks.items()},'cases':cases,'default':'Main40 unchanged; small exploratory test'}
    (ROOT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    lines=['# DS4.1F L1只增不减实验','', '## 结果','',f"40槽底座保持不变，将层{LAYERS}增至48（0起始编号）。5用例×基线/增长×2轮，共20次自然Top6测试。宏平均Decode **{macro['main40']['decode']:.3f} → {macro['growth']['decode']:.3f} TPS（{result['decode_gain']*100:+.2f}%）**。",'',f"命中率{macro['main40']['hit_pct']:.3f}%→{macro['growth']['hit_pct']:.3f}%；全命中layer-step {macro['main40']['all_hit_pct']:.3f}%→{macro['growth']['all_hit_pct']:.3f}%。增长方案最大physical footprint **{max(peaks['growth']):.3f}GB**（基线{max(peaks['main40']):.3f}GB），低于65十进制GB。",'',f"全部{hashes:,}份logits摘要、生成tokens与本轮和上轮Main40基线一致。仅修改容量验证与配置，不改Router、量化、专家运算顺序或native preadv/覆写栅栏。默认Main40保持不变，本轮为小样本性能检查。",'', '## 容量','',f"总Main1664槽、Hot320槽；新增64条专家记录×18,800,640字节＝{64*18800640/1e9:.6f}GB有效载荷。实际进程峰值仍单独采样，不能把有效载荷当总内存。新配置使用`dsv41.l1-shape/growth-v1`，严格要求32层40、8层48、Hot8；原1600槽schema未放宽。",'', '```json',json.dumps(shape['capacities']),'```','', '层选择来自上一轮训练集的40→48边际读取收益，测试前固定。使用同5个已选用例，重新跑基线与候选并交错AB/BA，不把历史TPS当本轮基线。没有扩展为240次测试或根据测试成绩改层选择。','', '## 配对结果','', '| 用例 | 输入/Decode | Main40两轮TPS | 增长两轮TPS | 均值变化 |','|---|---:|---:|---:|---:|']
    for c in cases:
        a=c['variants']['main40'];b=c['variants']['growth'];ar='/'.join(f"{r['metrics']['decode']:.3f}" for r in a['runs']);br='/'.join(f"{r['metrics']['decode']:.3f}" for r in b['runs'])
        lines.append(f"| {c['scope']}/{c['language']} | {c['tokens']}/{c['decode_steps']} | {ar} | {br} | {(b['mean']['decode']/a['mean']['decode']-1)*100:+.2f}% |")
    lines+=['','| 五例等权宏平均 | Main40 | 增长 |','|---|---:|---:|']
    for key,label in [('cold_decode','前16步Decode TPS'),('tail','尾段Decode TPS'),('hit_pct','路由命中率%'),('all_hit_pct','全命中layer-step%'),('promotion_loads','每例晋升读取数'),('io','每例native Decode I/O秒数'),('kernel_decode_read_gb','每例OS记账Decode读取GB')]:lines.append(f"| {label} | {macro['main40'][key]:.4f} | {macro['growth'][key]:.4f} |")
    lines+=['','## 长输入与内存','', '| 用例 | Main40 Prefill TPS | 增长Prefill TPS | Main40峰值GB | 增长峰值GB |','|---|---:|---:|---:|---:|']
    segments=[]
    for c in cases:
        if c['tokens']<1000:continue
        a=c['variants']['main40'];b=c['variants']['growth'];lines.append(f"| {c['scope']}/{c['language']} | {a['mean']['prefill']:.3f} | {b['mean']['prefill']:.3f} | {max(r['metrics']['peak'] for r in a['runs']):.3f} | {max(r['metrics']['peak'] for r in b['runs']):.3f} |")
        if c['decode_steps']==512:segments+=['',f"512步长Decode前128步：{a['mean']['first128']:.3f}→{b['mean']['first128']:.3f}TPS；后384步：{a['mean']['later384']:.3f}→{b['mean']['later384']:.3f}TPS。",'']
    lines+=segments
    lines+=['','## 判断边界','', '五个用例只支持初步判断，需同时看重复运行波动，不能把均值或单例变化当成稳定跨任务收益。没有生成置信区间，也未验证更长上下文或多模态65GB预算。全Top6自然路径、Prefill bank64、Hot8，其余配置一致；不能拿本批真实题材成绩直接比较Burst或重复提示的最高TPS。','', 'native I/O包含miss与晋升读取，不能与其它wall时间直接相加。OS读取为Darwin记账流量，不代表SSD设备总物理字节。正式测速期间按已有流程暂停本任务上传并在finally恢复。没有发布Runtime或Package。','', '## 产物','',f'- [配置]({(ROOT/"growth.json").resolve()})',f'- [全部结果]({(ROOT/"results.json").resolve()})',f'- [完成状态]({(ROOT/"state.json").resolve()})','- 执行：`experiments/dsv41_analysis/l1_shape/growth.py`；审计/报告：`growth_report.py`。','']
    path=Path('docs/dsv41f-l1-growth-results-2026-09-15.md');path.write_text('\n'.join(lines));print(json.dumps({k:v for k,v in result.items() if k not in ['cases','macro']},indent=2));print(macro)
    explanation=f"\n本轮判断：只增不减改善了命中率，但整体TPS基本持平，暂不值得替换Main40默认。native Decode读取时间仅减少{(1-macro['growth']['io']/macro['main40']['io'])*100:.2f}%；增长后仍有{100-macro['growth']['all_hit_pct']:.2f}%的layer-step不是全命中。少量读取减少尚未转化成明显的端到端收益，不能据此断言更大缓存也无效。512步样本后384步约提升0.89%，幅度仍小。\n"
    text=path.read_text();text=text.replace('## 判断边界\n','## 判断边界\n'+explanation);path.write_text(text)

if __name__=='__main__':main()
