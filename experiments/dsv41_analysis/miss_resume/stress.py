"""Diagnostic ONLY: invalidate all expert tags before every Decode MoE.

Both reference and candidate use the same invalidation and native SSD loader.
No weights/route IDs change; all six experts really reload at every layer.
"""
import os
import mlx.core as mx

class AllMissStress:
    def invalidate_stress_layer(self,l,start):
        if start and os.environ.get('DSV41_RESUME_STRESS_ALL_MISS')=='1':
            bank=self.banks[l]
            bank.main.clear();bank.hot.clear()
            self.lookups[l]=mx.full((self.c.n_routed_experts,),-1,dtype=mx.int32)
            self.main_slot_masks[l]=mx.zeros((bank.capacity,),dtype=mx.bool_)
            if l not in self.ages:
                self.ages[l]=mx.zeros((bank.capacity,),dtype=mx.int32);self.ticks[l]=bank.capacity

    def moe(self,l,x,start):
        self.invalidate_stress_layer(l,start)
        return super().moe(l,x,start)

    def _layer(self,l,h,pre,hashes,start):
        self.invalidate_stress_layer(l,start)
        return super()._layer(l,h,pre,hashes,start)
