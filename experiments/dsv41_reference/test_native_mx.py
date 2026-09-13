import unittest
import numpy as np
import torch
import mlx.core as mx
from native_mx import linear

class NativeTests(unittest.TestCase):
    def test_original_fp4_encoding_and_gather(self):
        # Every sign/magnitude code, varying scales, repeated/unsorted slots.
        raw=np.tile(np.arange(256,dtype=np.uint8),(3,32,1))
        scales=np.full((3,32,16),127,dtype=np.uint8);scales[1]=126;scales[2]=128
        w=mx.array(raw);s=mx.array(scales)
        dequant=mx.dequantize(w.view(mx.uint32),s,group_size=32,bits=4,mode='mxfp4')
        lut=np.array([0,.5,1,1.5,2,3,4,6],dtype=np.float32)
        codes=np.stack([raw&15,raw>>4],axis=-1).reshape(3,32,512)
        expected=lut[codes&7]*np.where(codes&8,-1.,1.)*np.exp2(scales.astype(np.float32)-127).repeat(32,axis=-1)
        self.assertTrue(np.array_equal(np.array(dequant.astype(mx.float32)),expected))
        slots=mx.array([2,0,2,1],dtype=mx.int32)
        inputs=np.random.default_rng(17).integers(-2,3,size=(4,512)).astype(np.float32)
        x=mx.array(inputs).astype(mx.bfloat16)
        result=linear(x,w,s,slots);mx.eval(result)
        target=np.einsum("mnk,mk->mn",expected[[2,0,2,1]],inputs)
        target=np.array(mx.array(target).astype(mx.bfloat16).astype(mx.float32))
        self.assertTrue(np.array_equal(np.array(result.astype(mx.float32)),target))

if __name__=='__main__':unittest.main()
