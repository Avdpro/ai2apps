import unittest
import torch
import cpu_kernel
from batched_attention import sparse_attn

class AttentionTests(unittest.TestCase):
    def test_query_batching_preserves_online_blocks_and_masks(self):
        torch.manual_seed(194);torch.set_num_threads(4)
        for tokens,window in [(1,64),(5,129),(26,128),(37,192)]:
            q=(torch.randn(1,tokens,64,512)*.1).bfloat16()
            kv=(torch.randn(1,257,512)*.1).bfloat16()
            ids=torch.randint(0,257,(1,tokens,window));ids[:,:,9:17]=-1;ids[:,:,-3:]=-1
            sink=torch.randn(64)
            expected=cpu_kernel.sparse_attn(q,kv,sink,ids,.125)
            actual=sparse_attn(q,kv,sink,ids,.125)
            self.assertTrue(torch.equal(expected.view(torch.uint8),actual.view(torch.uint8)),(tokens,window))

if __name__=='__main__':unittest.main()
