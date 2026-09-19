"""Official compressed-token mapping and n-gram layout, GPU uint64 hash arithmetic."""
import numpy as np
import mlx.core as mx
from tokenizers import Regex,normalizers


def _is_prime(value):
    """Deterministic Miller-Rabin for the 32-bit Engram modulus range."""
    if value < 2:return False
    for prime in (2,3,5,7,11,13,17,19,23,29,31,37):
        if value % prime == 0:return value == prime
    exponent=value-1;shift=0
    while exponent % 2 == 0:shift+=1;exponent//=2
    for base in (2,3,5,7):
        if base >= value:continue
        result=pow(base,exponent,value)
        if result in (1,value-1):continue
        for _ in range(shift-1):
            result=result*result%value
            if result == value-1:break
        else:return False
    return True

class HashState:
    def __init__(self,c,tokenizer,max_seq):
        sentinel='\ue000'
        normalizer=normalizers.Sequence([normalizers.NFKC(),normalizers.NFD(),normalizers.StripAccents(),normalizers.Lowercase(),normalizers.Replace(Regex(r'[ \t\r\n]+'),' '),normalizers.Replace(Regex(r'^ $'),sentinel),normalizers.Strip(),normalizers.Replace(sentinel,' ')])
        seen={};lookup=[]
        for i in range(tokenizer.get_vocab_size(with_added_tokens=True)):
            text=tokenizer.decode([i],skip_special_tokens=False)
            key=tokenizer.id_to_token(i) if '\ufffd' in text else (normalizer.normalize_str(text) or text)
            if key not in seen:seen[key]=len(seen)
            lookup.append(seen[key])
        if len(seen)!=c.engram_compressed_vocab_size:raise ValueError(('compressed vocab',len(seen)))
        self.pad=lookup[c.engram_pad_id];self.map=mx.array(lookup,dtype=mx.int32);self.cache=mx.full((max_seq,),self.pad,dtype=mx.int32)
        primes=[];used=set();mult=[]
        for layer in c.engram_layer_ids:
            ps=[]
            for _ in range(c.engram_max_ngram_size-1):
                cur=c.engram_vocab_size-1
                for _ in range(c.engram_n_heads):
                    cur+=1
                    while not _is_prime(cur) or cur in used:cur+=1
                    used.add(cur);ps.append(cur)
            primes.append(ps)
            bound=(np.iinfo(np.int64).max//len(seen))//2
            v=np.random.default_rng(10007*layer).integers(0,bound,size=c.engram_max_ngram_size,dtype=np.int64)*2+1
            mult.append(v)
        if [sum(p) for p in primes]!=c.engram_num_embeddings:raise ValueError('Engram prime layout')
        offsets=[np.cumsum([0,*p[:-1]]) for p in primes]
        self.primes=mx.array(np.array(primes,dtype=np.uint32));self.offsets=mx.array(np.array(offsets,dtype=np.uint32))
        self.mult=mx.array(np.array(mult,dtype=np.uint64).view(np.uint32));self.layers=len(primes);self.cols=len(primes[0]);self.heads=c.engram_n_heads;self.ngram=c.engram_max_ngram_size
        self.kernel=mx.fast.metal_kernel(name='dsv41_ngram_uint64',input_names=['cache','mult','primes','offsets','start'],output_names=['hashes'],source=r'''
          uint i=thread_position_in_grid.x;
          uint col=i%C,layer=(i/C)%L,pos=i/(C*L)+uint(start[0]);
          uint n=col/H+2;ulong rolling=0;bool blocked=false;
          for(uint j=0;j<n;j++){
            blocked=blocked||(pos<j);
            uint token=pos>=j?uint(cache[pos-j]):PAD;
            blocked=blocked||(token==0xffffffffu);
            if(blocked)token=PAD;
            uint mi=(layer*N+j)*2;
            ulong m=(ulong(mult[mi+1])<<32)|ulong(mult[mi]);
            rolling^=ulong(token)*m;
          }
          uint k=layer*C+col;
          hashes[i]=int(rolling%ulong(primes[k])+ulong(offsets[k]));
        ''')
    def __call__(self,ids,start,token_mask=None):
        if ids.shape[0]!=1:raise ValueError('batch1')
        mapped=self.map[ids[0]]
        if token_mask is not None:mapped=mx.where(token_mask[0],mapped,-1)
        self.cache[start:start+ids.shape[1]]=mapped
        shape=(1,ids.shape[1],self.layers,self.cols)
        return self.kernel(inputs=[self.cache,self.mult,self.primes,self.offsets,mx.array([start],dtype=mx.uint32)],template=[('C',self.cols),('L',self.layers),('H',self.heads),('N',self.ngram),('PAD',self.pad)],grid=(ids.shape[1]*self.layers*self.cols,1,1),threadgroup=(128,1,1),output_shapes=[shape],output_dtypes=[mx.int32])[0]
