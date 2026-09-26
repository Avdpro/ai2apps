# GPT-AR (24-layer GPT2-style, model_dim 1280, mel-code AR decoder) — MLX port of
# windextts/models/gpt.py. CUDA-graph paths deleted; sampling is pure; beam
# search mirrors the eager torch semantics (cumulative log-prob winner).
import os
import mlx.core as mx
import mlx.nn as nn

from omlx.vendor.indextts25 import ops
from omlx.vendor.indextts25.models.emo_conditioning import EmoConformerEncoder, EmoPerceiverEncoder, get_emovec
from omlx.vendor.indextts25.ops import Seq


class GPT2Attention(nn.Module):
    def __init__(self, model_dim, heads):
        super().__init__()
        self.embed_dim, self.num_heads, self.head_dim = model_dim, heads, model_dim // heads
        self.c_attn = nn.Linear(model_dim, 3 * model_dim)
        self.c_proj = nn.Linear(model_dim, model_dim)

    def __call__(self, h, mask=None, past_kv=None):  # h [B,T,dim]; mask 4D additive
        qkv = self.c_attn(h)
        q, k, v = mx.split(qkv, 3, axis=-1)
        B, T, _ = q.shape
        q = q.reshape(B, T, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        k = k.reshape(B, T, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        v = v.reshape(B, T, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        if past_kv is not None:
            pk, pv = past_kv
            k = mx.concatenate([pk, k], 2)
            v = mx.concatenate([pv, v], 2)
        # attention math in fp32: fp16 qk accumulates overflow (scores -> inf)
        # even at moderate activations (~96), which nans softmax on long decode
        f32 = q.dtype == mx.float16
        if f32:
            q, k, v = q.astype(mx.float32), k.astype(mx.float32), v.astype(mx.float32)
        s = q @ k.transpose(0, 1, 3, 2) / (self.head_dim ** 0.5)
        if mask is not None:
            s = s + mask.astype(mx.float32) if f32 else s + mask
        o = mx.softmax(s, -1) @ v
        if f32:
            o = o.astype(mx.float16)
        return self.c_proj(o.transpose(0, 2, 1, 3).reshape(B, T, self.embed_dim)), (k.astype(mx.float16) if f32 else k, v.astype(mx.float16) if f32 else v)


class GPT2MLP(nn.Module):
    def __init__(self, model_dim, intermediate_size):
        super().__init__()
        self.c_fc = nn.Linear(model_dim, intermediate_size)
        self.c_proj = nn.Linear(intermediate_size, model_dim)

    def __call__(self, x):
        return self.c_proj(nn.GELU()(self.c_fc(x)))


class GPT2Block(nn.Module):
    def __init__(self, model_dim, heads, intermediate_size):
        super().__init__()
        self.ln_1, self.attn = nn.LayerNorm(model_dim, eps=1e-5), GPT2Attention(model_dim, heads)
        self.ln_2, self.mlp = nn.LayerNorm(model_dim, eps=1e-5), GPT2MLP(model_dim, intermediate_size)

    def __call__(self, h, mask=None, past_kv=None):
        a, kv = self.attn(self.ln_1(h), mask, past_kv)
        h = h + a
        return h + self.mlp(self.ln_2(h)), kv


class GPT2Transformer(nn.Module):
    # embedding-free block stack + ln_f (caller provides full inputs_embeds)
    def __init__(self, layers, model_dim, heads, intermediate_size):
        super().__init__()
        self.h = Seq({str(i): GPT2Block(model_dim, heads, intermediate_size) for i in range(layers)})
        self.ln_f = nn.LayerNorm(model_dim, eps=1e-5)

    def __call__(self, inputs_embeds, attention_mask=None, past_key_values=None):
        # prefill: mask=[B,T] int (0=pad) -> 4D causal; decode: additive [B,1,1,t]
        # Layer-by-layer mx.eval: a first-time command buffer that compiles all
        # 24 layers takes ~30s and trips the Metal 2s watchdog on M-series GPUs;
        # per-layer eval keeps every submission tiny (compile cache then applies).
        h, kvs = inputs_embeds, []
        if past_key_values is None:
            m = self._build_4d_causal_mask(inputs_embeds, attention_mask)
            for i in self.h._order:
                h, kv = getattr(self.h, i)(h, m)
                kvs.append(kv)
                mx.eval(h)
        else:
            assert len(past_key_values) == len(self.h)
            for i, (pk, pv) in zip(self.h._order, past_key_values):
                h, kv = getattr(self.h, i)(h, attention_mask, (pk, pv))
                kvs.append(kv)
                mx.eval(h)
        return self.ln_f(h), kvs

    @staticmethod
    def _build_4d_causal_mask(hidden_states, attention_mask):
        # HF causal mask + _unmask_unattended: fully-masked rows (left-pad) all-attend
        if attention_mask is None:
            return None
        B, T = hidden_states.shape[:2]
        min_dt = mx.finfo(hidden_states.dtype).min
        causal = mx.triu(mx.full((T, T), min_dt, dtype=hidden_states.dtype), 1)
        m = mx.broadcast_to(causal[None, None], (B, 1, T, T))
        m = mx.where(attention_mask[:, None, None, :] != 0, m, min_dt)
        return mx.where((m == min_dt).all(-1, keepdims=True), 0.0, m)


class LearnedPositionEmbeddings(nn.Module):
    def __init__(self, seq_len, model_dim):
        super().__init__()
        self.emb = nn.Embedding(seq_len, model_dim)

    def __call__(self, x):
        return self.emb(mx.arange(x.shape[1], dtype=mx.int32))

    def get_fixed_embedding(self, ind):
        return self.emb(mx.array([ind], dtype=mx.int32))[None]


class UnifiedVoice(nn.Module):
    def __init__(self, layers=24, model_dim=1280, heads=20, max_text_tokens=600,
                 max_mel_tokens=1815, max_conditioning_inputs=1, number_text_tokens=60509,
                 number_mel_codes=8194):
        super().__init__()
        self.number_text_tokens, self.number_mel_codes = number_text_tokens, number_mel_codes
        self.start_text_token, self.stop_text_token = 0, 1
        self.start_mel_token, self.stop_mel_token = 8192, 8193
        self.layers, self.heads, self.model_dim = layers, heads, model_dim
        self.max_mel_tokens, self.max_text_tokens = max_mel_tokens, max_text_tokens
        self.spk_emb_proj = nn.Linear(192, model_dim)
        self.emo_layer = nn.Linear(model_dim, model_dim)
        self.emovec_layer = nn.Linear(1024, model_dim)
        self._compiled_steps = 0  # O6 engagement counter (diagnostics)
        self.emo_conditioning_encoder = None
        self.emo_perceiver_encoder = None
        self.lang_embedding = nn.Embedding(107, model_dim)
        self.text_embedding = nn.Embedding(number_text_tokens + 1, model_dim)
        self.mel_embedding = nn.Embedding(number_mel_codes, model_dim)
        self.gpt = GPT2Transformer(layers, model_dim, heads, 4 * model_dim)
        self.mel_pos_embedding = LearnedPositionEmbeddings(max_mel_tokens + 2 + max_conditioning_inputs, model_dim)
        self.text_pos_embedding = LearnedPositionEmbeddings(max_text_tokens + 2, model_dim)
        self.final_norm = nn.LayerNorm(model_dim)
        self.text_head = nn.Linear(model_dim, number_text_tokens + 1)
        self.mel_head = nn.Linear(model_dim, number_mel_codes)

    def build_emo_conditioning(self):
        self.emo_conditioning_encoder = EmoConformerEncoder()
        self.emo_perceiver_encoder = EmoPerceiverEncoder()

    def get_emovec(self, cond_emb):  # [B,T,1024] -> [B,1280]
        return get_emovec(self.emo_conditioning_encoder, self.emo_perceiver_encoder,
                          self.emovec_layer, self.emo_layer, cond_emb,
                          mx.array([cond_emb.shape[1]], dtype=mx.int32))

    def merge_emovec(self, spk_cond_emb, emo_cond_emb, alpha=1.0):
        emo_vec, base_vec = self.get_emovec(emo_cond_emb), self.get_emovec(spk_cond_emb)
        return base_vec + alpha * (emo_vec - base_vec)

    def emo_matrix_lookup(self, style, emo_vec, spk_matrix, emo_matrix):
        # sum_i w_i * emo_matrix[i][argmax cosine(style, spk_matrix[i])]
        wv = emo_vec.astype(mx.float32)
        sf = style.astype(mx.float32)
        idx = [int(mx.argmax(mx.sum(sf * c.astype(mx.float32), -1)
                             / (mx.linalg.norm(sf, axis=-1) * mx.linalg.norm(c.astype(mx.float32), axis=-1) + 1e-8)))
               for c in spk_matrix]
        mat = mx.stack([emo_matrix[i][j].astype(mx.float32) for i, j in enumerate(idx)])  # [8,1280]
        return mx.sum(wv[:, None] * mat, 0, keepdims=True)  # [1,1280]

    def build_conds_latent(self, campplus_emb, emo_vec):  # [1,3,1280]
        spk = self.spk_emb_proj(campplus_emb.astype(self.spk_emb_proj.weight.dtype))
        return mx.concatenate([spk + emo_vec.astype(spk.dtype)[:, None],
                               mx.zeros((1, 2, self.model_dim), dtype=spk.dtype)], 1)

    def prepare_gpt_inputs(self, conditional_latents, text_inputs, langs=None):
        # [pad][cond][start_text+text+stop_text] embeddings -> (ids, embeds, mask)
        b, L = text_inputs.shape[:2]
        single = conditional_latents.ndim == 3 and conditional_latents.shape[0] == 1
        target_len = conditional_latents.shape[1] + L + 2
        embs, masks = [], []
        for i in range(b):
            ti = text_inputs[i]
            # mlx lacks boolean-index/argwhere and argsort stability is not
            # guaranteed, so filter via a small python loop (b*L is tiny)
            keep = [(ti[j] != self.stop_text_token) and (ti[j] != self.start_text_token) for j in range(ti.shape[0])]
            t = mx.array([ti[j] for j in range(ti.shape[0]) if keep[j]], dtype=mx.int32)
            t = mx.concatenate([mx.array([self.start_text_token], dtype=mx.int32), t,
                                mx.array([self.stop_text_token], dtype=mx.int32)])
            # per-op eval: first-time Metal kernel compilation for the whole
            # embedding stack exceeds the GPU watchdog on M-series; each op
            # compiles in <1s so every submission stays safe (no-op on CPU).
            te = self.text_embedding(t)
            mx.eval(te)
            te = te + self.text_pos_embedding.emb(mx.arange(t.shape[0], dtype=mx.int32))
            mx.eval(te)
            if langs is not None:
                te = te + self.lang_embedding(langs[i])
                mx.eval(te)
            am = mx.ones(target_len + 1, dtype=mx.int32)
            parts = [conditional_latents[0] if single else conditional_latents[i], te]
            pad = L + 2 - t.shape[0]
            if pad > 0:
                parts.insert(0, mx.zeros((pad, conditional_latents.shape[-1]), dtype=te.dtype))
                am = am.at[:pad].multiply(0)
            embs.append(mx.concatenate(parts))
            masks.append(am)
        embs = mx.stack(embs)  # [B,S,dim]
        masks = mx.stack(masks)  # [B,S+1]
        ids = mx.ones((embs.shape[0], embs.shape[1] + 1), dtype=mx.int32)
        ids = ids.at[:, -1].add(self.start_mel_token - 1)  # ones base -> set(start_mel_token)
        return ids, embs, masks

    def _prefill(self, conditional_latents, text_inputs, langs):
        ids, embeds, attention_mask = self.prepare_gpt_inputs(conditional_latents, text_inputs, langs)
        S = embeds.shape[1]
        last = self.mel_embedding(ids[:, S:])
        mx.eval(last)
        last = last + self.mel_pos_embedding(ids[:, S:])
        mx.eval(last)
        emb = mx.concatenate([embeds, last], 1)
        mx.eval(emb)
        hidden, kvs = self.gpt(inputs_embeds=emb, attention_mask=attention_mask)
        out = self.mel_head(self.final_norm(hidden))
        mx.eval(out)
        return S, attention_mask, kvs, out

    def _build_decode_step(self, max_len):
        # O6: fused single-trace decode step over STATIC-LENGTH kv buffers.
        # Math is identical to _eager_step (incl. fp32 attention rounding):
        # positions > t are never attended (mask), unwritten kv slots are zero
        # and contribute exactly 0 to softmax @ v. mx.compile bakes the shapes
        # once (kv length max_len); positional/KV indices arrive as scalars so
        # the graph traces a single time per max_len. Beam search still uses
        # the dynamic _eager_step (its batch shrinks on EOS); this path is
        # greedy-only. Raises on any unsupported op (e.g. w4a16 quantized
        # matmul) — caller falls back to _eager_step.
        H, HD = self.heads, self.model_dim // self.heads
        D = self.model_dim
        from mlx.utils import tree_flatten

        mdtype = next(v for _, v in tree_flatten(self.parameters())).dtype
        min_dt = mx.finfo(mdtype).min
        pos3 = mx.arange(max_len, dtype=mx.int32)
        pos4 = pos3[None, None, :, None]

        def _attn(blk, h, m, pk, pv, t):
            qkv = blk.attn.c_attn(h)
            q, k, v = mx.split(qkv, 3, axis=-1)
            B, T, _ = q.shape
            q = q.reshape(B, T, H, HD).transpose(0, 2, 1, 3)
            k = k.reshape(B, T, H, HD).transpose(0, 2, 1, 3)
            v = v.reshape(B, T, H, HD).transpose(0, 2, 1, 3)
            k = mx.where(pos4 == t, k, pk)  # write new token at position t
            v = mx.where(pos4 == t, v, pv)
            f32 = q.dtype == mx.float16
            if f32:
                q, k, v = q.astype(mx.float32), k.astype(mx.float32), v.astype(mx.float32)
            s = q @ k.transpose(0, 1, 3, 2) / (HD ** 0.5)
            if m is not None:
                s = s + (m.astype(mx.float32) if f32 else m)
            o = mx.softmax(s, -1) @ v
            if f32:
                o = o.astype(mx.float16)
            return blk.attn.c_proj(o.transpose(0, 2, 1, 3).reshape(B, T, D)), (k, v)

        def step(nid, t_kv, t_pos, kvs, am):
            if nid.ndim == 1:
                nid = nid.reshape(-1, 1)
            e = self.mel_embedding(nid) + mx.take(self.mel_pos_embedding.emb.weight, t_pos, 0)
            # attended = pos<=t AND non-pad (am==1); identical set to _eager_step
            m = mx.where((pos3[None, None, None, :] <= t_kv) & (am[:, None, None, :] != 0),
                         0.0, min_dt).astype(mdtype)
            h, outs = e.astype(mdtype), []
            for pos, i in enumerate(self.gpt.h._order):
                blk = getattr(self.gpt.h, i)
                a, (nk, nv) = _attn(blk, blk.ln_1(h), m, kvs[pos][0], kvs[pos][1], t_kv)
                h = h + a
                h = h + blk.mlp(blk.ln_2(h))
                outs.append((nk, nv))
            o = self.mel_head(self.final_norm(self.gpt.ln_f(h)))[:, -1]
            return o, outs

        return mx.compile(step)

    def _eager_step(self, next_id, step, attention_mask, kvs, mdtype, K_sel=None):
        nid = next_id if K_sel is None else next_id[K_sel]
        nid = mx.reshape(nid, (-1, 1)) if nid.ndim == 1 else nid  # always [B,1]
        e = self.mel_embedding(nid)
        mx.eval(e)
        e = e + self.mel_pos_embedding.get_fixed_embedding(step + 2)  # nid [B,1] -> emb [B,1,dim]
        mx.eval(e)
        attention_mask = mx.concatenate([attention_mask, mx.ones((attention_mask.shape[0], 1), dtype=attention_mask.dtype)], -1)
        m = mx.where(attention_mask[:, None, None, :] != 0, 0.0, mx.finfo(mdtype).min).astype(mdtype)
        hidden, kvs = self.gpt(inputs_embeds=e.astype(mdtype), attention_mask=m, past_key_values=kvs)
        out = self.mel_head(self.final_norm(hidden))[:, -1]
        mx.eval(out)
        return attention_mask, kvs, out

    def _sample(self, logits, do_sample, top_k, top_p, temperature, generated_ids=None, repetition_penalty=1.0):
        # HF warper order: repetition_penalty -> temperature -> top_k -> top_p
        if repetition_penalty != 1.0 and generated_ids is not None:
            s = mx.take_along_axis(logits, generated_ids, axis=1)
            p = mx.where(s < 0, s * repetition_penalty, s / repetition_penalty)
            logits = mx.put_along_axis(logits, generated_ids, p, axis=1)
        if not do_sample:
            return logits, mx.argmax(logits, -1)
        if temperature != 1.0:
            logits = logits / temperature
        neg_inf = mx.finfo(logits.dtype).min
        if top_k and top_k > 0:
            thresh = mx.topk(logits, min(top_k, logits.shape[-1]), -1)[..., -1:]
            logits = mx.where(logits < thresh, neg_inf, logits)
        if top_p is not None and 0.0 < top_p < 1.0:
            si = mx.argsort(-logits, axis=-1)  # descending via negation (mlx argssort has no descending kw)
            sl = mx.take_along_axis(logits, si, -1)
            rm = mx.cumsum(mx.softmax(sl, -1), -1) > top_p
            rm = mx.concatenate([mx.zeros(rm[..., :1].shape, dtype=mx.bool_), rm[..., :-1]], -1)  # keep the top token (HF shift-right + rm[0]=False)
            logits = mx.where(mx.put_along_axis(mx.zeros(logits.shape, dtype=mx.bool_), si, rm, -1), neg_inf, logits)
        return logits, mx.random.categorical(logits).astype(mx.int32)

    def generate(self, conditional_latents, text_inputs, langs=None, max_new_tokens=500,
                 do_sample=False, top_k=30, top_p=0.8, temperature=0.8, stop_token=None,
                 repetition_penalty=1.0, num_beams=1):
        stop_token = self.stop_mel_token if stop_token is None else stop_token
        from mlx.utils import tree_flatten

        mdtype = next(v for _, v in tree_flatten(self.parameters())).dtype
        if conditional_latents.dtype != mdtype:
            conditional_latents = conditional_latents.astype(mdtype)
        a = (conditional_latents, text_inputs, langs, max_new_tokens,
             do_sample, top_k, top_p, temperature, stop_token)
        if num_beams > 1:
            return self._generate_beam_search(*a, num_beams, repetition_penalty)
        S, attention_mask, kvs, cur_logits = self._prefill(conditional_latents, text_inputs, langs)
        cur_logits = cur_logits[:, -1]
        # O6: compiled static-KV decode step (single trace per max_len); falls
        # back to the eager per-layer-eval path on any build/run failure
        # (e.g. w4a16 quantized matmul unsupported under mx.compile).
        max_len = S + 1 + max_new_tokens + 4
        padn = max_len - (S + 1)
        kvs_s = [(mx.pad(k, [(0, 0), (0, 0), (0, padn), (0, 0)]),
                  mx.pad(v, [(0, 0), (0, 0), (0, padn), (0, 0)])) for k, v in kvs]
        am_s = mx.pad(attention_mask, [(0, 0), (0, padn)], constant_values=1)
        t_kv = S + 1
        compiled_ok = False
        if os.environ.get("WINDEXTTS_NO_O6_COMPILE"):
            step_c = None  # explicit A/B / diagnostics switch (forces eager)
        else:
            try:
                step_c = self._build_decode_step(max_len)
            except Exception as e:
                # expose why the compiled path is unavailable (w4a16 quantized matmul
                # etc.) instead of silently falling back
                print(f"[O6] compiled decode step disabled: {type(e).__name__}: {e}")
                step_c = None
        self._compiled_steps = 0
        codes, gen_ids = [], mx.zeros((1, 0), dtype=mx.int32)
        for step in range(max_new_tokens):
            cur_logits, next_id = self._sample(cur_logits, do_sample, top_k, top_p, temperature, gen_ids, repetition_penalty)
            codes.append(next_id)
            gen_ids = mx.concatenate([gen_ids, next_id[:, None]], 1)
            if stop_token is not None and next_id.item() == stop_token:
                break  # stop token IS appended (torch ref parity)
            if step_c is not None:
                try:
                    cur_logits, kvs_s = step_c(next_id, mx.array([t_kv], mx.int32),
                                               mx.array([step + 2], mx.int32), kvs_s, am_s)
                    mx.eval(cur_logits)
                    t_kv += 1
                    compiled_ok = True
                    self._compiled_steps += 1
                    continue
                except Exception:
                    if compiled_ok:
                        # eager attention_mask/kvs were never advanced past the
                        # prefill state — mid-sequence fallback would silently
                        # misalign; fail loud instead.
                        raise
                    step_c = None  # first call failed: eager fallback, state intact
            attention_mask, kvs, cur_logits = self._eager_step(next_id, step, attention_mask, kvs, mdtype)
        return mx.stack(codes, 1)

    def _generate_beam_search(self, conditional_latents, text_inputs, langs, max_new_tokens,
                              do_sample, top_k, top_p, temperature, stop_token, num_beams,
                              repetition_penalty=1.0):
        from mlx.utils import tree_flatten

        mdtype = next(v for _, v in tree_flatten(self.parameters())).dtype
        S, attention_mask, kvs, cur_logits = self._prefill(conditional_latents, text_inputs, langs)
        cur_logits = cur_logits[:, -1]
        K = num_beams
        cur_logits = mx.broadcast_to(cur_logits, (K, cur_logits.shape[-1]))
        kvs = [(mx.broadcast_to(k, (K,) + k.shape[1:]), mx.broadcast_to(v, (K,) + v.shape[1:])) for k, v in kvs]
        attention_mask = mx.broadcast_to(attention_mask, (K, attention_mask.shape[1]))
        beam_scores = mx.zeros(K, dtype=mx.float32)
        gen_ids = mx.zeros((K, 0), dtype=mx.int32)
        finished = []

        for step in range(max_new_tokens):
            if cur_logits.shape[0] == 0:
                break
            cur_logits, next_id = self._sample(cur_logits, do_sample, top_k, top_p, temperature, gen_ids, repetition_penalty)
            tok_lp = mx.take_along_axis(cur_logits - mx.logsumexp(cur_logits, -1, keepdims=True), next_id[:, None], -1)[:, 0]
            cand_score = beam_scores + tok_lp  # fp32
            is_eos = next_id == stop_token
            if mx.any(is_eos):
                eos_idx = mx.argsort(mx.where(is_eos, 0, 1))[: int(mx.sum(is_eos.astype(mx.int32)))]
                for i in eos_idx.tolist():
                    finished.append((float(cand_score[i].item()), gen_ids[i].tolist()))
            keep = ~is_eos
            if not mx.any(keep):
                break
            keep_idx = mx.argsort(mx.where(keep, 0, 1))[: int(mx.sum(keep.astype(mx.int32)))]
            beam_scores = cand_score[keep_idx].astype(mx.float32)
            gen_ids = mx.concatenate([gen_ids[keep_idx], next_id[keep_idx][:, None]], 1)
            cur_logits = cur_logits[keep_idx]
            kvs = [(k[keep_idx], v[keep_idx]) for k, v in kvs]
            attention_mask = attention_mask[keep_idx]
            attention_mask, kvs, cur_logits = self._eager_step(next_id[keep_idx], step, attention_mask, kvs, mdtype)

        if finished:
            return mx.array([max(finished, key=lambda x: x[0])[1]], dtype=mx.int32)
        best = int(mx.argmax(beam_scores))
        return gen_ids[best][None]

    def forward(self, *a, **kw):
        raise NotImplementedError("use _prefill / generate")
