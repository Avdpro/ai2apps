# EnhancedCodec (Amphion semantic codec) — MLX port of windextts/models/codec.py.
# NLC-layout throughout (mlx native): quantize x [B,T,D] -> codes [B,T//2];
# decode codes [B,T] -> latent [B,2T,1024]. VocosBackbone + FVQ (L2 cosine VQ).
import mlx.core as mx
import mlx.nn as nn

from omlx.vendor.indextts25.ops import Seq


class ConvNeXtBlock(nn.Module):
    def __init__(self, dim, intermediate_dim, layer_scale_init_value):
        super().__init__()
        self.dwconv = nn.Conv1d(dim, dim, 7, padding=3, groups=dim)
        self.norm = nn.LayerNorm(dim, eps=1e-6)
        self.pwconv1 = nn.Linear(dim, intermediate_dim)
        self.pwconv2 = nn.Linear(intermediate_dim, dim)
        self.gamma = mx.full((dim,), layer_scale_init_value)

    def __call__(self, x):  # [B,T,dim]
        r = x
        x = self.pwconv2(nn.GELU()(self.pwconv1(self.norm(self.dwconv(x)))))
        return r + self.gamma * x


class VocosBackbone(nn.Module):
    def __init__(self, input_channels, dim, intermediate_dim, num_layers):
        super().__init__()
        self.embed = nn.Conv1d(input_channels, dim, 7, padding=3)
        self.norm = nn.LayerNorm(dim, eps=1e-6)
        self.convnext = Seq({str(i): ConvNeXtBlock(dim, intermediate_dim, 1 / num_layers)
                             for i in range(num_layers)})
        self.final_layer_norm = nn.LayerNorm(dim, eps=1e-6)

    def __call__(self, x):  # [B,T,C] -> [B,T,dim]
        x = self.norm(self.embed(x))
        mx.eval(x)
        for i in self.convnext._order:
            x = getattr(self.convnext, i)(x)
            mx.eval(x)
        return self.final_layer_norm(x)


class FVQ(nn.Module):
    def __init__(self, input_dim, codebook_size, codebook_dim):
        super().__init__()
        self.in_project = nn.Conv1d(input_dim, codebook_dim, 1)
        self.out_project = nn.Conv1d(codebook_dim, input_dim, 1)
        self.codebook = nn.Embedding(codebook_size, codebook_dim)

    def decode_code(self, ids):  # [B,T] -> [B,T,cbd]
        return self.codebook(ids)

    def decode_latents(self, latents):  # [B,T,cbd] -> (z_q [B,T,cbd], idx [B,T])
        enc = latents.reshape(-1, latents.shape[-1])
        cb = self.codebook.weight
        enc = enc / mx.maximum(mx.sqrt(mx.sum(enc * enc, -1, keepdims=True)), 1e-12)
        cbn = cb / mx.maximum(mx.sqrt(mx.sum(cb * cb, -1, keepdims=True)), 1e-12)
        dist = mx.sum(enc * enc, -1, keepdims=True) - 2 * (enc @ cbn.T) + mx.sum(cbn * cbn, -1, keepdims=True).T
        idx = mx.argmin(dist, axis=-1).reshape(latents.shape[0], latents.shape[1])
        z_q = mx.take_along_axis(cb[None], idx[..., None], axis=1)
        return z_q, idx

    def vq2emb(self, ids, out_proj=True):  # [B,T] -> [B,T,input_dim]
        emb = self.decode_code(ids)
        return self.out_project(emb) if out_proj else emb


class ResidualVQ(nn.Module):
    def __init__(self, input_dim, num_quantizers, codebook_size, codebook_dim):
        super().__init__()
        self.quantizers = Seq({str(i): FVQ(input_dim, codebook_size, codebook_dim)
                               for i in range(num_quantizers)})

    def vq2emb(self, vq):  # vq [1,B,T] -> [B,T,input_dim] (single quantizer)
        return getattr(self.quantizers, "0").vq2emb(vq[0])


class EnhancedCodec(nn.Module):
    def __init__(self, codebook_size=8192, hidden_size=1024, codebook_dim=8, vocos_dim=384,
                 vocos_intermediate_dim=2048, vocos_num_layers=12, num_quantizers=1):
        super().__init__()
        self.down = nn.Conv1d(hidden_size, hidden_size, 3, stride=2, padding=1)
        self.up = nn.Conv1d(hidden_size, hidden_size, 3, padding=1)
        vb = lambda: Seq({"0": VocosBackbone(hidden_size, vocos_dim, vocos_intermediate_dim, vocos_num_layers),
                          "1": nn.Linear(vocos_dim, hidden_size)})
        self.encoder, self.decoder = vb(), vb()
        self.quantizer = ResidualVQ(hidden_size, num_quantizers, codebook_size, codebook_dim)

    def quantize(self, x):  # x [B,T,D] -> (codes [B,T//2] (squeezed if B==1), feat [B,T//2,D])
        x = nn.GELU()(self.down(x))
        x = self.encoder(x)
        q0 = getattr(self.quantizer.quantizers, "0")
        z_e = q0.in_project(x)
        z_q, idx = q0.decode_latents(z_e)
        return (idx[0] if idx.shape[0] == 1 else idx), q0.out_project(z_q)

    def decode(self, codes):  # codes [B,T] -> [B,2T,1024]
        if codes.ndim == 2:
            codes = codes[None]  # [1,B,T]
        x = self.decoder(self.quantizer.vq2emb(codes))  # [B,T,1024]
        mx.eval(x)
        x = mx.repeat(x, 2, axis=1)  # F.interpolate nearest x2
        mx.eval(x)
        return self.up(x)
