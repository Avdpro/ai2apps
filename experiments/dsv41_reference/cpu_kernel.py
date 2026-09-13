"""CPU translation of the downloaded TileLang kernels; NOT CUDA bitwise parity.
Keep block-32 scale accumulation and block-64 online attention rounding explicit.
"""
import torch

FP4 = torch.tensor([0., .5, 1., 1.5, 2., 3., 4., 6., -0., -.5, -1., -1.5, -2., -3., -4., -6.], dtype=torch.float32)


def act_quant(x, block_size=128, scale_fmt=None, scale_dtype=torch.float32, inplace=False):
    z = x.float().unflatten(-1, (-1, block_size))
    s = z.abs().amax(-1).clamp_min(1e-4) / 448
    if scale_fmt is not None:
        s = torch.exp2(torch.ceil(torch.log2(s)))
    q = (z / s[..., None]).clamp(-448, 448).to(torch.float8_e4m3fn)
    if inplace:
        x.copy_((q.float() * s[..., None]).flatten(-2).to(x.dtype))
        return x
    return q.flatten(-2).contiguous(), s.to(scale_dtype).contiguous()


def fp4_act_quant(x, block_size=32, inplace=False, scale_dtype=torch.float8_e8m0fnu):
    z = x.float().unflatten(-1, (-1, block_size))
    if scale_dtype == torch.float8_e4m3fn:
        s = (z.abs().amax(-1).clamp_min(6 * 2**-9) / 6).to(scale_dtype).float()
    else:
        s = torch.exp2(torch.ceil(torch.log2(z.abs().amax(-1).clamp_min(6 * 2**-126) / 6)))
    v = (z / s[..., None]).clamp(-6, 6)
    # Nearest, ties to even encoded mantissa. Odd codes lose ties to even codes.
    order = torch.tensor([0, 2, 4, 6, 1, 3, 5, 7])
    code = order[(v.abs()[..., None] - FP4[order]).abs().argmin(-1)]
    code = code + (torch.signbit(v).long() * 8)
    if inplace:
        x.copy_((FP4[code] * s[..., None]).flatten(-2).to(x.dtype))
        return x
    c = code.flatten(-2).to(torch.uint8)
    return (c[..., ::2] | (c[..., 1::2] << 4)).view(torch.float4_e2m1fn_x2), s.to(scale_dtype)


def _gemm(a, a_s, b, b_s, fp4, group):
    shape = a.shape[:-1]
    a = a.float().reshape(-1, a.shape[-1])
    sa, sb = a_s.float().reshape(a.shape[0], -1), b_s.float()
    out = torch.zeros(a.shape[0], b.shape[0], dtype=torch.float32)
    if fp4:
        raw = b.view(torch.uint8)
    else:
        raw = b.float()
    for k in range(a.shape[1] // 32):
        if fp4:
            packed = raw[:, k*16:(k+1)*16]
            w = torch.stack((FP4[(packed & 15).long()], FP4[(packed >> 4).long()]), -1).flatten(-2)
            ws = sb[:, k]
        else:
            w = raw[:, k*32:(k+1)*32]
            ws = sb[torch.arange(b.shape[0]) // group, k]
        part = a[:, k*32:(k+1)*32] @ w.T
        out += part * sa[:, k // (group // 32), None] * ws[None, :]
    return out.reshape(*shape, b.shape[0]).to(torch.get_default_dtype())


def fp4_gemm(a, a_s, b, b_s, scale_dtype=torch.float32, act_block_size=128):
    return _gemm(a, a_s, b, b_s, True, act_block_size)


def fp8_gemm(a, a_s, b, b_s, scale_dtype=torch.float32, block_size=128):
    if block_size != 32:
        raise NotImplementedError('This reference supports released V4.1 group32 only')
    return _gemm(a, a_s, b, b_s, False, block_size)


def hc_split_sinkhorn(mixes, hc_scale, hc_base, hc_mult=4, sinkhorn_iters=20, eps=1e-6):
    h = hc_mult
    pre = torch.sigmoid(mixes[..., :h] * hc_scale[0] + hc_base[:h]) + eps
    post = 2 * torch.sigmoid(mixes[..., h:2*h] * hc_scale[1] + hc_base[h:2*h])
    c = (mixes[..., 2*h:] * hc_scale[2] + hc_base[2*h:]).unflatten(-1, (h, h)).softmax(-1) + eps
    c = c / (c.sum(-2, keepdim=True) + eps)
    for _ in range(sinkhorn_iters - 1):
        c = c / (c.sum(-1, keepdim=True) + eps)
        c = c / (c.sum(-2, keepdim=True) + eps)
    return pre, post, c


def sparse_attn(q, kv, attn_sink, topk_idxs, softmax_scale):
    out = torch.empty_like(q)
    for b in range(q.shape[0]):
        for t in range(q.shape[1]):
            m = torch.full((q.shape[2],), -1e30, dtype=torch.float32)
            sums = torch.zeros_like(m)
            acc = torch.zeros(q.shape[2], q.shape[3], dtype=torch.float32)
            for start in range(0, topk_idxs.shape[-1], 64):
                idx = topk_idxs[b, t, start:start+64].long()
                valid = idx != -1
                v = kv[b, idx.clamp_min(0)].float().masked_fill(~valid[:, None], 0)
                scores = (q[b, t].float() @ v.T).masked_fill(~valid[None, :], -torch.inf) * softmax_scale
                new_m = torch.maximum(m, scores.amax(-1))
                correction = (m-new_m).exp()
                p = (scores-new_m[:, None]).exp()
                sums = sums * correction + p.sum(-1)
                acc = acc * correction[:, None] + p.bfloat16().float() @ v
                m = new_m
            sums += (attn_sink-m).exp()
            out[b, t] = (acc / sums[:, None]).to(q.dtype)
    return out
