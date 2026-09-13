import json
import struct
import tempfile
import unittest
from pathlib import Path
import torch
from cached_store import CachedStore
from run_reference import Store

class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        header={}; payload=b''
        tensors={'dense':torch.arange(8,dtype=torch.float32).reshape(2,4),'rows':torch.arange(16,dtype=torch.float32).reshape(4,4)}
        for expert in range(3):
            for w in ('w1','w2','w3'):
                for part in ('weight','scale'):
                    tensors[f'layers.0.ffn.experts.{expert}.{w}.{part}']=torch.full((2,4),float(expert),dtype=torch.float32)
        for name,t in tensors.items():
            raw=t.numpy().tobytes(); header[name]={'dtype':'F32','shape':list(t.shape),'data_offsets':[len(payload),len(payload)+len(raw)]}; payload+=raw
        h=json.dumps(header).encode(); (self.root/'test.safetensors').write_bytes(struct.pack('<Q',len(h))+h+payload)
        self.cache=CachedStore(self.root,1,32,32); self.raw=Store(self.root)
    def tearDown(self): self.cache.close(); self.raw.close(); self.tmp.cleanup()
    def test_complete_expert_eviction_reload(self):
        for expert in [0,0,1,2,0]:
            for w in ('w1','w3','w2'):
                for part in ('weight','scale'):
                    key=f'layers.0.ffn.experts.{expert}.{w}.{part}'
                    self.assertTrue(torch.equal(self.cache.read(key),self.raw.read(key)))
            self.assertEqual(len(self.cache.layers['layers.0.ffn.experts']),1)
            self.assertEqual(self.cache.expert_bytes,192)
        self.assertEqual(self.cache.stats['expert_misses'],4)
        self.assertEqual(self.cache.stats['expert_evictions'],3)
    def test_rows_repeat_eviction_and_bounds(self):
        for ids in [torch.tensor([[0,0]]),torch.tensor([[1,2,0]])]:
            self.assertTrue(torch.equal(self.cache.read('rows',ids),self.raw.read('rows',ids)))
            self.assertLessEqual(self.cache.row_bytes,32)
        self.assertGreater(self.cache.stats['row_hits'],0)
        self.assertGreater(self.cache.stats['row_evictions'],0)
        with self.assertRaises(IndexError): self.cache.read('rows',torch.tensor([4]))
    def test_dense_limit_and_disabled_experts(self):
        self.cache.read('dense'); before=self.cache.bytes
        self.cache.read('dense'); self.assertEqual(before,self.cache.bytes)
        self.cache.read('rows'); self.assertEqual(self.cache.dense_bytes,32)
        self.cache.experts_per_layer=0
        key='layers.0.ffn.experts.0.w1.weight'
        self.cache.read(key); before=self.cache.bytes; self.cache.read(key)
        self.assertEqual(self.cache.bytes-before,32)
    def test_failed_expert_not_published(self):
        self.cache.entries.pop('layers.0.ffn.experts.1.w3.scale')
        with self.assertRaises(KeyError): self.cache.read('layers.0.ffn.experts.1.w1.weight')
        self.assertNotIn('1',self.cache.layers['layers.0.ffn.experts'])
        self.assertEqual(self.cache.expert_bytes,0)

if __name__=='__main__': unittest.main()
