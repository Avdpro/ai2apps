"""Original safetensor bytes -> MLX. CPU work is limited to I/O and addressing."""
import hashlib,json,os,struct
from pathlib import Path
from collections import OrderedDict
import numpy as np
import mlx.core as mx

class Storage:
    def __init__(self,root):
        self.root=Path(root);self.entries={};self.fds=[];self.params={};self.rows=OrderedDict();self.row_bytes=0
        self.source_index_sha256=hashlib.sha256((self.root/'model.safetensors.index.json').read_bytes()).hexdigest()
        marker=self.root/'ssd-checkpoint.json'
        if marker.is_file():
            info=json.loads(marker.read_text())
            if (info.get('schema')!='ai2apps.ssd-checkpoint/v1' or info.get('family')!='deepseek_v41'
                or info.get('layout')!='dsv41-original-fp4-six-segment-v1'
                or info.get('index_sha256')!=self.source_index_sha256
                or info.get('verification')!='all_tensor_payloads_equal'):
                raise ValueError('unsupported or inconsistent SSD checkpoint')
            self.source_index_sha256=info['source']['index_sha256']
        self.read_bytes=0;self.read_calls=0;self.payload_bytes=0
        for p in sorted(self.root.glob('*.safetensors')):
            fd=os.open(p,os.O_RDONLY);self.fds.append(fd);n=struct.unpack('<Q',os.pread(fd,8,0))[0]
            for k,e in json.loads(os.pread(fd,n,8)).items():
                if k!='__metadata__':self.entries[k]=(fd,n+8,e)
    def raw(self,name,rows=None):
        fd,base,e=self.entries[name];lo,hi=e['data_offsets'];shape=e['shape']
        def read(off,size):
            b=os.pread(fd,size,off)
            if len(b)!=size:raise IOError(name)
            self.read_bytes+=size;self.read_calls+=1;return b
        if rows is None:b=read(base+lo,hi-lo)
        else:
            stride=(hi-lo)//shape[0];parts=[]
            for row in rows:
                if not 0<=row<shape[0]:raise IndexError((name,row))
                key=(name,row)
                if key in self.rows:v=self.rows.pop(key);self.rows[key]=v
                else:
                    v=read(base+lo+row*stride,stride)
                    while self.rows and self.row_bytes+stride>8*2**20:
                        _,old=self.rows.popitem(last=False);self.row_bytes-=len(old)
                    self.rows[key]=v;self.row_bytes+=stride
                parts.append(v)
            b=b''.join(parts);shape=[len(rows),*shape[1:]]
        dtype=e['dtype'];npdtype={'BF16':np.uint16,'F32':np.float32,'F8_E4M3':np.uint8,'F8_E8M0':np.uint8,'I32':np.int32,'I64':np.int64}[dtype]
        a=mx.array(np.frombuffer(b,dtype=npdtype).copy().reshape(shape))
        return a.view(mx.bfloat16) if dtype=='BF16' else a
    def weight(self,name,dtype=None):
        key=(name,str(dtype))
        if key not in self.params:
            a=self.raw(name)
            if dtype is not None:a=a.astype(dtype)
            mx.eval(a);self.params[key]=a;self.payload_bytes+=a.nbytes
        return self.params[key]
    def fp8(self,name):
        key=(name,'packed8')
        if key not in self.params:
            w=self.raw(name+'.weight');s=self.raw(name+'.scale');s=mx.repeat(s,32,axis=0)[:w.shape[0]]
            w=w.view(mx.uint32);mx.eval(w,s);self.params[key]=(w,s);self.payload_bytes+=w.nbytes+s.nbytes
        return self.params[key]
    def grouped(self,name):
        key=(name,'grouped_bf16')
        if key not in self.params:
            w=self.raw(name+'.weight');s=mx.repeat(self.raw(name+'.scale'),32,axis=0)[:w.shape[0]]
            y=mx.dequantize(w.view(mx.uint32),s,group_size=32,bits=8,mode='mxfp8').astype(mx.bfloat16);mx.eval(y)
            self.params[key]=y;self.payload_bytes+=y.nbytes
        return self.params[key]
    def embedding(self,name,ids,fp8=False):
        # Only row addresses cross to host; all dequantization stays on GPU.
        mx.eval(ids);host=np.array(ids).reshape(-1);unique,inverse=np.unique(host,return_inverse=True)
        w=self.raw(name+'.weight',unique.tolist())
        if fp8:
            from .kernels import fp8_decode
            scale=self.raw(name+'.scale',unique.tolist())
            w=(fp8_decode(w).reshape(len(unique),-1,32)*mx.power(2.,scale.astype(mx.float32)-127)[:,:,None]).reshape(w.shape).astype(mx.bfloat16)
        return w[mx.array(inverse.astype(np.int32))].reshape(*ids.shape,w.shape[-1])
    def close(self):
        mx.synchronize()
        for fd in self.fds:os.close(fd)
