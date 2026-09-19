"""Persistent text KV/cache audit: fixed same-topic and topic-switch history, then greedy Decode."""
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
import numpy as np
from tokenizers import Tokenizer
ROOT=Path('artifacts/dsv41-l1-shape-20260915')
CKPT=Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD')

def fixtures(language):
    turns={
        'zh':[
            ('请用一句话说明缓存命中。','缓存命中是请求的数据已在缓存中，无需再次从较慢的存储读取。'),
            ('继续这个话题：缓存淘汰解决什么问题？','缓存淘汰在容量不足时移除部分已有数据，为新的数据腾出空间。'),
            ('现在换个话题：用一句话解释二分查找。','二分查找利用数据有序这一条件，每次比较中间元素并排除不可能包含目标的一半区间，反复缩小范围；如果边界相交仍未找到目标，就返回不存在。更新上下界时必须确保区间严格缩小，避免死循环。'),
            ('回到缓存话题：为什么提高命中率未必按比例提高整体吞吐？',None)],
        'en':[
            ('Explain a cache hit in one sentence.','A cache hit means the requested data is already cached, so slower storage need not be read again.'),
            ('Continue this topic: what problem does cache eviction solve?','Eviction removes some cached data when capacity is limited, making room for new entries.'),
            ('Now change topics: explain binary search in one sentence.','Binary search relies on sorted data: compare the middle element, discard the half that cannot contain the target, and repeat until the target is found or the interval becomes empty. Each update must strictly shrink the search interval; otherwise an off-by-one boundary error can cause an infinite loop.'),
            ('Return to caching: why might a higher hit rate fail to yield a proportional throughput improvement?',None)]}
    spec=importlib.util.spec_from_file_location('official_encoding',CKPT/'encoding/encoding.py');enc=importlib.util.module_from_spec(spec);spec.loader.exec_module(enc)
    tok=Tokenizer.from_file(str(CKPT/'tokenizer.json'));messages=[];result=[]
    for user,answer in turns[language]:
        messages.append({'role':'user','content':user});prompt=enc.encode_messages(messages,thinking_mode='chat');ids=tok.encode(prompt).ids
        if result and ids[:len(result[-1]['ids'])]!=result[-1]['ids']:raise ValueError('canonical fixture is not append-only')
        result.append({'prompt':prompt,'ids':ids})
        if answer is not None:messages.append({'role':'assistant','content':answer})
    return tok,result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--language',choices=['zh','en'],required=True);ap.add_argument('--variant',choices=['40','shape']);ap.add_argument('--prepare-only',action='store_true');args=ap.parse_args()
    tokenizer,turns=fixtures(args.language)
    if args.prepare_only:print([len(t['ids']) for t in turns]);return
    if args.variant is None:ap.error('--variant is required')
    fixture_sha=hashlib.sha256(json.dumps(turns,ensure_ascii=False).encode()).hexdigest()
    marker_sha=hashlib.sha256((CKPT/'ssd-checkpoint.json').read_bytes()).hexdigest()
    expected_caps=json.loads((ROOT/'candidate/frozen.json').read_text())['capacities'] if args.variant=='shape' else [40]*40
    out=ROOT/f'persistent-{args.language}-{args.variant}'
    if (out/'manifest.json').exists():
        prior=json.loads((out/'manifest.json').read_text())
        if prior['status']=='complete':
            assert prior['fixture_sha256']==fixture_sha and prior['main_capacities']==expected_caps and prior['checkpoint_manifest_sha256']==marker_sha, 'persistent configuration changed'
            return
        raise RuntimeError('incomplete persistent audit: '+str(out))
    out.mkdir(exist_ok=False)
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'dsv41_mlx'))
    import mlx.core as mx
    from run import Budget
    from storage import Storage
    from adaptive import AdaptiveModel
    from route_capture import captured_model
    from l1_shape import load_shape
    config=json.loads((CKPT/'inference/config.json').read_text());config.update(dspark_block_size=0,max_batch_size=1,temperature=0,vision_n_layers=0,max_seq_len=max(256,len(turns[-1]['ids'])+17))
    assert len(turns[-1]['ids'])>config['window_size'], 'fixture must cross the attention window'
    caps,_=load_shape(ROOT/'candidate/frozen.json',CKPT) if args.variant=='shape' else (None,None)
    budget=Budget();mx.set_cache_limit(2*2**30);mx.set_memory_limit(60_000_000_000)
    store=None;model=None;consumed=[];hashes=[];checks=[];generated=[]
    receipt={'status':'running','mode':'persistent Model; teacher-forced canonical history, same-topic follow-up and topic switch; final greedy <=16 tokens; single-token append, not chunked incremental Prefill or server integration','main_capacities':list(caps or (40,)*40),'fixture_sha256':fixture_sha,'checkpoint_manifest_sha256':marker_sha,'command_line':[sys.executable,*sys.argv]}
    def record(y):
        mx.eval(y,model.cache_counters,*model.ages.values());budget.check()
        a=np.array(y.astype(mx.float32));assert np.isfinite(a).all();hashes.append(hashlib.sha256(a.tobytes()).hexdigest())
    try:
        store=Storage(CKPT);cls=captured_model(AdaptiveModel,out)
        model=cls(config,store,tokenizer,CKPT/'experts',config['max_seq_len'],40,prefill_slots=64,main_shape=caps)
        identities=None
        for turn,t in enumerate(turns):
            ids=t['ids'];before=len(consumed)
            if not consumed:
                y=model(mx.array([ids],dtype=mx.int32),0);record(y);consumed=list(ids);model.prefill_executor.release()
                identities={l:id(b) for l,b in model.banks.items()}
            else:
                assert ids[:len(consumed)]==consumed
                for token in ids[len(consumed):]:
                    y=model(mx.array([[token]],dtype=mx.int32),len(consumed));record(y);consumed.append(token)
            assert identities=={l:id(b) for l,b in model.banks.items()}
            mx.save_safetensors(str(out/f'turn-{turn}.safetensors'),{'logits':y})
            checks.append({'turn':turn,'consumed':len(consumed),'appended':len(consumed)-before,'decode_step':model.decode_step,'banks_preserved':True,'counts':model.cache_counters.tolist()})
        for i in range(16):
            token=int(mx.argmax(y,axis=-1).item());generated.append(token)
            if token==1 or i==15:break
            y=model(mx.array([[token]],dtype=mx.int32),len(consumed));record(y);consumed.append(token)
        receipt.update(status='complete',attention_window_crossed=len(consumed)>config['window_size'],turns=checks,logits_sha256=hashes,generated_ids=generated,generated_text=tokenizer.decode(generated))
    except BaseException as e:receipt.update(status='failed',error=repr(e));raise
    finally:
        try:
            if model is not None:model.close();receipt['adaptive_l1']=model.adaptive_report
            elif store is not None:store.close()
            budget.close()
        except BaseException as e:receipt.update(status='failed',error=repr(e))
        receipt['sampled_physical_footprint_peak_bytes']=budget.peak
        receipt['source_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),*Path('experiments/dsv41_mlx').glob('*.py')]}
        (out/'manifest.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    if receipt['status']!='complete':raise RuntimeError(receipt.get('error'))
    print(json.dumps({'persistent':args.language,'variant':args.variant,'steps':len(hashes),'peak_gb':budget.peak/1e9}),flush=True)
if __name__=='__main__':main()
