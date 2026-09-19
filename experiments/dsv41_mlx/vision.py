"""MLX port of official dense ViT/aligner (see LICENSE.DeepSeek). Local images only."""
import math
from types import SimpleNamespace
import numpy as np
import mlx.core as mx
from PIL import Image,ImageOps

class Vision:
    def __init__(self,store,c):self.s=store;self.c=c
    def load(self):
        self.names=[k for k in self.s.entries if k.startswith(('vision.','aligner.','image_'))]
        for name in self.names:self.s.weight(name)
        return sum(self.s.params[(name,'None')].nbytes for name in self.names)
    def linear(self,p,x):
        w=self.s.weight(p+'.weight');bias=p+'.bias'
        return mx.addmm(self.s.weight(bias),x,w.T) if bias in self.s.entries else x@w.T
    def norm(self,p,x):
        f=x.astype(mx.float32)
        return (f*mx.rsqrt(mx.mean(f*f,axis=-1,keepdims=True)+1e-6)*self.s.weight(p+'.weight').astype(mx.float32)).astype(x.dtype)
    def __call__(self,patches,nh,nw):
        c=self.c;n=nh*nw;hd=c.vision_dim//c.vision_n_heads;rd=hd//2
        freq=1/(c.vision_rope_theta**(mx.arange(0,rd,2,dtype=mx.float32)/rd))
        pos=mx.stack([mx.repeat(mx.arange(nh),nw),mx.tile(mx.arange(nw),nh)],axis=-1)
        phase=(pos.astype(mx.float32)[...,None]*freq).reshape(n,1,hd//2);cos=mx.cos(phase);sin=mx.sin(phase)
        def rotary(x):
            a,b=mx.split(x.astype(mx.float32),2,axis=-1)
            return mx.concatenate([a*cos-b*sin,b*cos+a*sin],axis=-1).astype(x.dtype)
        x=self.linear('vision.patch_embed.proj',patches.reshape(n,-1))
        for i in range(c.vision_n_layers):
            p=f'vision.blocks.{i}';z=self.norm(p+'.norm1',x)
            q,k,v=[a.reshape(n,c.vision_n_heads,hd) for a in mx.split(self.linear(p+'.attn.wqkv',z),3,axis=-1)]
            q=rotary(q);k=rotary(k)
            o=mx.fast.scaled_dot_product_attention(q.transpose(1,0,2)[None],k.transpose(1,0,2)[None],v.transpose(1,0,2)[None],scale=hd**-.5)[0].transpose(1,0,2).reshape(n,-1)
            x=x+self.linear(p+'.attn.wo',o)
            gate,up=mx.split(self.linear(p+'.mlp.w1',self.norm(p+'.norm2',x)),2,axis=-1)
            g=gate.astype(mx.float32);act=(g*mx.sigmoid(g)).astype(gate.dtype)*up
            x=x+self.linear(p+'.mlp.w2',act);mx.eval(x)
        x=self.norm('vision.norm',x);r=c.vision_downsample_ratio
        padded=mx.pad(x.reshape(nh,nw,-1),[(0,-nh%r),(0,-nw%r),(0,0)])
        z=padded.reshape(math.ceil(nh/r),r,math.ceil(nw/r),r,c.vision_dim).transpose(0,2,4,1,3).reshape(-1,c.vision_dim*r*r)
        z=self.linear('aligner.w1',z);f=z.astype(mx.float32)
        z=(.5*f*(1+mx.erf(f/math.sqrt(2)))).astype(z.dtype)
        return self.linear('aligner.w2',z)

def prepare_images(paths,c):
    images=[];types=[];ids=[]
    for path in paths:
        with Image.open(path) as src:im=src.convert('RGB')
        lh,lw,bh,bw=plan_image_grid(im.width,im.height,c);p=c.vision_patch_size;nh,nw=bh//p,bw//p
        if c.vision_max_wh_ratio is not None and im.width>=c.vision_max_wh_ratio*im.height:im=im.resize((bw,bh))
        else:im=ImageOps.pad(im,(bw,bh),color=(127,127,127))
        x=mx.array(np.asarray(im,dtype=np.float32).transpose(2,0,1))/255
        x=((x-.5)/.5).astype(mx.bfloat16)
        patches=x.reshape(3,nh,p,nw,p).transpose(1,3,0,2,4).reshape(nh*nw,3,p,p)
        ts=[0]+([1]*lw+[2])*lh+[3]
        images.append(SimpleNamespace(start=len(ids),patches=patches,n_vit_h=nh,n_vit_w=nw,types=ts,path=str(path)))
        types+=ts;ids+=[c.image_token_id]*len(ts)
    return images,ids,types

def num_image_tokens(n_llm_h: int, n_llm_w: int) -> int:
    return n_llm_h * (n_llm_w + 1) + 2

def llm_grid(best_height: int, best_width: int, patch_size: int, downsample_ratio: int):
    """Token grid the aligner produces from a patch grid of this pixel size."""
    return (math.ceil(best_height // patch_size / downsample_ratio), math.ceil(best_width // patch_size / downsample_ratio))

def solve_resize_ratio(height, width, patch_size, downsample_ratio, max_n_token):
    """Largest aspect-preserving pixel size whose token grid still fits in max_n_token."""
    r = height / width
    max_w_float = math.sqrt((max_n_token - 2) / r + 0.25) - 0.5
    max_h_float = max_w_float * r
    cell = patch_size * downsample_ratio
    if max_w_float < 1.0:
        return ((max_n_token - 2) // 2 * cell, cell)
    if max_h_float < 1.0:
        return (cell, (max_n_token - 3) * cell)
    beta = min(math.floor(max_w_float) * cell / width, math.floor(max_h_float) * cell / height)
    return (math.floor(height * beta / patch_size) * patch_size, math.floor(width * beta / patch_size) * patch_size)

def safe_resize(height, width, best_height, best_width, patch_size, downsample_ratio, max_n_token):
    """Shrink the pixel size until the image costs at most max_n_token LLM tokens."""
    n_llm_h, n_llm_w = llm_grid(best_height, best_width, patch_size, downsample_ratio)
    if num_image_tokens(n_llm_h, n_llm_w) > max_n_token:
        best_height, best_width = solve_resize_ratio(height, width, patch_size, downsample_ratio, max_n_token)
        n_llm_h, n_llm_w = llm_grid(best_height, best_width, patch_size, downsample_ratio)
        assert num_image_tokens(n_llm_h, n_llm_w) <= max_n_token
    return (n_llm_h, n_llm_w, best_height, best_width)

def plan_image_grid(width: int, height: int, args):
    """Resize plan for an image of the given original size; a pure function of its arguments."""
    p = args.vision_patch_size
    if args.vision_max_wh_ratio is not None and width > height * args.vision_max_wh_ratio:
        width = height * args.vision_max_wh_ratio
    if 0 < width * height < args.vision_min_pixels:
        ratio = (args.vision_min_pixels / (width * height)) ** 0.5
        width = int(width * ratio)
        height = int(height * ratio)
    best_width = math.ceil(width / p) * p
    best_height = math.ceil(height / p) * p
    return safe_resize(height, width, best_height, best_width, p, args.vision_downsample_ratio, args.vision_max_n_token)
