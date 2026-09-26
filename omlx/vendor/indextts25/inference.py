# WIndexTTS-MLX inference pipeline — same 6-stage IndexTTS-2.5 flow as
# windextts/inference.py, pure MLX on Apple Silicon (no torch in the runtime
# path). dtype: "fp32" | "fp16"; quantize=True -> W4A16 on GPT body + mel_head.
from __future__ import annotations

import os
from pathlib import Path

import mlx.core as mx
import numpy as np

from omlx.vendor.indextts25.weights import DEFAULT_MLX_DIR, load_into, load_mlx

OUTPUT_SR = 22050
REF_SR_W2V = 16000
REF_SR_MEL = 22050
REF_MAX_SECONDS = 15.0

# per-language text->mel ratio (measured; identical table to windextts.inference)
_MEL_RATIO_STR = "AF:13 AM:7 AR:14 AS:5 AZ:10 BA:6 BE:8 BG:9 BN:5 BO:4 BR:13 BS:13 CA:14 CS:11 CY:11 DA:13 DE:13 EL:7 EN:14 ES:14 ET:14 EU:13 FA:11 FI:11 FO:13 FR:14 GL:14 GU:4 HA:12 HAW:10 HE:9 HI:6 HR:12 HT:14 HU:12 HY:6 ID:13 IS:10 IT:13 JA:12 JW:10 KA:6 KK:6 KM:6 KN:6 KO:10 LA:14 LB:12 LN:11 LO:4 LT:12 LV:10 MG:14 MI:11 MK:8 ML:4 MN:6 MR:5 MS:13 MT:11 MY:6 NE:5 NL:14 NN:14 NO:14 OC:14 PA:4 PL:11 PS:9 PT:14 RO:11 RU:9 SA:6 SI:6 SK:12 SL:13 SN:13 SO:13 SQ:11 SR:10 SU:12 SV:13 SW:11 TA:6 TE:5 TG:7 TH:6 TK:11 TL:14 TR:12 TT:8 UK:9 UR:10 UZ:12 VI:10 YI:6 YO:10 ZH:13 YUE:13 MINNAN:13 WUYU:13"


def _load_audio(path, max_seconds=REF_MAX_SECONDS):
    import soundfile as sf

    data, sr = sf.read(path, dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)  # stereo -> mono
    maximum_samples = int(max_seconds * sr)
    if data.shape[0] > maximum_samples:
        raise ValueError(
            f"Reference audio exceeds the {max_seconds:g}-second IndexTTS 2.5 limit"
        )
    return data, sr


class WIndexTTSMLX:
    def __init__(self, cfg=None, weights_dir=DEFAULT_MLX_DIR, dtype="fp32", quantize=False,
                 enable_emo_ref=True, qwen_tokenizer_dir=None, w2v_fp16=True,
                 voc_fp16=True, cache_limit_gb=1.0):
        from omlx.vendor.indextts25.support.config import load_default_config

        self.cfg = cfg or load_default_config()
        self.dtype = dtype  # "fp32" | "fp16" | "fp64" (weights+compute)
        self.quantize = quantize  # W4A16 on GPT body + mel_head
        # fp16 mode: w2v_bert/vocoder (dit+bigvgan) weights run fp16 by default.
        # Rounding is ~5e-4 so codes/mel/audio diverge from the fp32 reference
        # (AR early flip; waveform cos ~0) but blind listening found zero
        # audible difference. w2v_fp16=False / voc_fp16=False restore strict
        # reference alignment at +1.16GB / +0.42GB.
        self.w2v_fp16 = w2v_fp16
        self.voc_fp16 = voc_fp16
        self.enable_emo_ref = enable_emo_ref
        self.weights_dir = Path(weights_dir)
        self.qwen_tokenizer_dir = qwen_tokenizer_dir
        # mlx's buffer cache pool is unbounded by default: released intermediates
        # stay resident (measured 7.6GB after one infer on a 16GB machine),
        # inflating system memory + swap pressure. Cap it so the process holds
        # ~active + cache_limit only. None = leave mlx default.
        if cache_limit_gb is not None:
            mx.set_cache_limit(int(cache_limit_gb * 1024**3))
        self._load_modules()
        self._ref_cache = {}
        self._normalizer = None
        self._qwen_emo = None

    def _load_modules(self):
        from omlx.vendor.indextts25.models.bigvgan import BigVGAN
        from omlx.vendor.indextts25.support.bigvgan_config import BigVGANConfig  # plain dict, torch-free use
        from omlx.vendor.indextts25.models.campplus import CAMPPlus
        from omlx.vendor.indextts25.models.codec import EnhancedCodec
        from omlx.vendor.indextts25.models.gpt import UnifiedVoice
        from omlx.vendor.indextts25.models.length_regulator import InterpolateRegulator
        from omlx.vendor.indextts25.models.s2mel_cfm import S2Mel, S2MelCFM
        from omlx.vendor.indextts25.models.s2mel_dit import DiT
        from omlx.vendor.indextts25.models.w2v2_bert import Wav2Vec2BertConformer

        w = self.weights_dir
        dt = {"fp16": mx.float16, "fp64": mx.float64}.get(self.dtype, mx.float32)
        # feature frontends stay fp32 ONLY in strict-alignment mode: their
        # rounding propagates into the GPT conditions and flips early (non-tie)
        # argmaxes vs the fp32 reference (spk_cond fp16 cos 0.999986 -> conds
        # drift -> step-2 flip; listening-equivalent, verified by ear).
        # Applies to fp16 mode and to w4a16 (dtype fp32 + quantize).
        self.w2v_bert = Wav2Vec2BertConformer()
        load_into(self.w2v_bert, load_mlx(w, "w2v_bert"), self._w2v_dtype())
        s = np.load(w / "stats.npz")
        self.w2v_mean = mx.array(s["mean"], dtype=mx.float32)
        self.w2v_std = mx.sqrt(mx.array(s["var"], dtype=mx.float32))

        self.campplus = CAMPPlus(feat_dim=80, embedding_size=192)
        load_into(self.campplus, load_mlx(w, "campplus"))  # stays fp32 (torch parity)

        sc = self.cfg.semantic_codec
        self.codec = EnhancedCodec(codebook_size=sc.codebook_size, hidden_size=sc.hidden_size,
                                   codebook_dim=sc.codebook_dim, vocos_dim=sc.vocos_dim,
                                   vocos_intermediate_dim=sc.vocos_intermediate_dim,
                                   vocos_num_layers=sc.vocos_num_layers)
        load_into(self.codec, load_mlx(w, "codec"), dt)

        self.gpt = UnifiedVoice()
        if self.enable_emo_ref:
            self.gpt.build_emo_conditioning()
        load_into(self.gpt, load_mlx(w, "gpt"), dt)

        f = np.load(w / "feat.npz")
        # torch.split uses SIZES; mx.split(list) means split-point indices -> cumsum
        emo_num = list(self.cfg._raw.get("emo_num", [3, 17, 2, 8, 4, 5, 10, 24]))
        cuts = list(np.cumsum(emo_num))[:-1]
        self.spk_matrix = mx.split(mx.array(f["spk"], dtype=mx.float32), cuts)
        self.emo_matrix = mx.split(mx.array(f["emo"], dtype=mx.float32), cuts)

        lr = self.cfg.s2mel.length_reg
        self.length_regulator = InterpolateRegulator(
            channels=lr.channels, sampling_ratios=lr.sampling_ratios, is_discrete=lr.is_discrete,
            in_channels=lr.in_channels, codebook_size=lr.content_codebook_size)
        st = load_mlx(w, "s2mel")
        lr_st = {k[len("length_regulator."):]: v for k, v in st.items() if k.startswith("length_regulator.")}
        # vocoder chain (dit+bigvgan) weights fp16 by default in fp16 mode
        # (mixed precision: activations stay fp32 via promotion; validated by
        # ear — waveform cos vs fp32 reference ~0 but no audible difference).
        # length_regulator stays fp32 (untested).
        dt_voc = mx.float16 if (self.dtype == "fp16" and self.voc_fp16) else None
        load_into(self.length_regulator, lr_st, None)
        self.dit = DiT()
        load_into(self.dit, st, dt_voc)
        self.s2mel = S2Mel(self.length_regulator, S2MelCFM(self.dit, in_channels=self.cfg.s2mel.dit.in_channels))

        bcfg = BigVGANConfig.from_json(w / "bigvgan_config.json")
        self.bigvgan = BigVGAN(bcfg)
        load_into(self.bigvgan, load_mlx(w, "bigvgan"), dt_voc)

        self.mel_fn = None
        self.featurizer = None
        self.fbank = None
        self._resample_cache = {}

        print(f">> WIndexTTS-MLX loaded on {mx.default_device()} [{self.dtype}"
              f"{' + W4A16' if self.quantize else ''}]")
        if self.quantize:
            self._apply_w4a16()

    def _w2v_dtype(self):
        w2v_dt = mx.float16 if (self.w2v_fp16 and (self.dtype == "fp16" or self.quantize)) else None
        return w2v_dt

    def _load_w2v_bert(self):  # reload path after _release_frontend()
        from omlx.vendor.indextts25.models.w2v2_bert import Wav2Vec2BertConformer

        self.w2v_bert = Wav2Vec2BertConformer()
        load_into(self.w2v_bert, load_mlx(self.weights_dir, "w2v_bert"), self._w2v_dtype())

    def _load_campplus(self):  # reload path after _release_frontend()
        from omlx.vendor.indextts25.models.campplus import CAMPPlus

        self.campplus = CAMPPlus(feat_dim=80, embedding_size=192)
        load_into(self.campplus, load_mlx(self.weights_dir, "campplus"))  # stays fp32 (torch parity)

    def _release_frontend(self):
        # One-shot frontends (w2v_bert ~1.1GB fp16 + campplus + featurizer /
        # fbank / mel_fn) are used once per uncached reference; drop them so
        # the GPT/CFM/vocoder stages run with a ~1.1GB lower resident set.
        # Next uncached reference (or emo_ref) reloads lazily via the
        # None-check in extract_spk_cond/extract_style. WINDEXTTS_KEEP_FRONTEND=1
        # keeps everything resident (previous behavior).
        if os.environ.get("WINDEXTTS_KEEP_FRONTEND"):
            return
        self.w2v_bert = self.campplus = None
        self.featurizer = self.fbank = self.mel_fn = None
        mx.clear_cache()

    def _apply_w4a16(self, group_size=128):
        import mlx.nn as nn

        # W4A16 on GPT transformer body only: mel_head (lm_head [1280,2048])
        # must stay fp32 — 4bit there destroys the argmax directly (prefill
        # logits cos 0.9957 -> 0.999993, forced-decode 13 -> 0 non-tie misses).
        # spk_emb_proj/emovec_layer stay fp32 too (they feed conds, not logits).
        # NOTE: leaf paths are `gpt.h.*` (UnifiedVoice.gpt is the GPT2
        # container); an earlier predicate `gpt.gpt.h.` matched NOTHING, so the
        # model silently stayed fp32. Restrict to Linear leaves (LayerNorm and
        # other leaves have no to_quantized() and would raise).
        n = [0]

        def pred(path, mod):
            if path.startswith("gpt.h.") and isinstance(mod, nn.Linear):
                n[0] += 1
                return True
            return False

        nn.quantize(self.gpt, group_size=group_size, bits=4, class_predicate=pred)
        print(f">> W4A16: quantized {n[0]} GPT-body Linear leaves (int4, group={group_size})")

    def _resample(self, sr, target):
        key = (sr, target)
        if key not in self._resample_cache:
            from omlx.vendor.indextts25.frontend import Resample

            self._resample_cache[key] = Resample(sr, target)
        return self._resample_cache[key]

    def _mel(self):
        if self.mel_fn is None:
            from omlx.vendor.indextts25.frontend import MelSpectrogram

            self.mel_fn = MelSpectrogram()
        return self.mel_fn

    def _feat(self):
        if self.featurizer is None:
            from omlx.vendor.indextts25.frontend import SeamlessM4TFeaturizer

            self.featurizer = SeamlessM4TFeaturizer()
        return self.featurizer

    def _fbank(self):
        if self.fbank is None:
            from omlx.vendor.indextts25.frontend import KaldiFbank

            self.fbank = KaldiFbank(num_mel_bins=80, sample_frequency=REF_SR_W2V)
        return self.fbank

    def extract_spk_cond(self, audio_16k):  # [B,N] 16k -> [B,T,1024] normalized
        if self.w2v_bert is None:
            self._load_w2v_bert()
        inp, am = self._feat()(audio_16k, return_mask=True)
        wb = self.w2v_bert.feature_projection.projection.weight.dtype
        out = (self.w2v_bert(inp.astype(wb), am, return_layer=17) - self.w2v_mean) / self.w2v_std
        return out

    def extract_style(self, audio_16k):  # [B,N] 16k -> [B,192]
        if self.campplus is None:
            self._load_campplus()
        f = self._fbank()(audio_16k)
        return self.campplus(f - f.mean(1, keepdims=True))  # per-column mean-subtract

    def _mat_lookup(self, style, emo_vector):
        w = mx.array(emo_vector, dtype=mx.float32)
        mat = self.gpt.emo_matrix_lookup(style, w, self.spk_matrix, self.emo_matrix)
        return w, mat

    def build_emo_vec(self, style, spk_cond, emo_vector=None):
        # emovec = emovec_mat(RAW w) + (1 - sum(RAW w)) * get_emovec(spk)
        if emo_vector is None:
            emo_vector = [0, 0, 0, 0, 0, 0, 0, 1.0]  # calm default
        w, mat = self._mat_lookup(style, emo_vector)
        dt = self.gpt.emovec_layer.weight.dtype
        return mat.astype(dt) + max(0.0, 1.0 - float(w.sum())) * self.gpt.get_emovec(spk_cond.astype(dt))

    def build_emo_vec_full(self, style, spk_cond, emo_vector, emo_ref_path, emo_alpha):
        if emo_ref_path is None:
            emo_cond = spk_cond
        else:
            ea, esr = _load_audio(emo_ref_path, REF_MAX_SECONDS)
            ea16 = self._resample(esr, REF_SR_W2V)(mx.array(ea)[None])
            emo_cond = self.extract_spk_cond(ea16)
            self._release_frontend()  # emo_ref is one-shot too (reloads on next use)
        dt = self.gpt.emovec_layer.weight.dtype
        emovec_audio = self.gpt.merge_emovec(spk_cond.astype(dt), emo_cond.astype(dt), alpha=emo_alpha)
        if emo_vector is None:
            return emovec_audio
        w, mat = self._mat_lookup(style, emo_vector)
        return mat.astype(dt) + max(0.0, 1.0 - float(w.sum())) * emovec_audio

    def _ensure_normalizer(self):
        if self._normalizer is None:
            from omlx.vendor.indextts25.support.normalizer import TextNormalizer

            self._normalizer = TextNormalizer()
        return self._normalizer

    def _ensure_qwen_emo(self):
        if self._qwen_emo is None:
            from omlx.vendor.indextts25.models.qwen_emotion import QwenEmotion

            dt = {"fp16": mx.float16, "fp64": mx.float64}.get(self.dtype, mx.float32)
            self._qwen_emo = QwenEmotion(self.weights_dir, self.qwen_tokenizer_dir, dtype=dt)
            print(">> QwenEmotion loaded (MLX Qwen3, text->emotion)")
        return self._qwen_emo

    def _tokenizer(self):
        from omlx.vendor.indextts25.support.tokenizer import build_tokenizer

        return build_tokenizer(model_dir=str(self.weights_dir))

    def warmup(self):
        # populate caches + run one short pass (no CUDA graphs on MLX)
        dummy = mx.zeros((1, REF_SR_W2V), dtype=mx.float32)
        a22 = mx.zeros((1, REF_SR_MEL), dtype=mx.float32)
        spk = self.extract_spk_cond(dummy)
        style = self.extract_style(dummy)
        refmel = self._mel()(a22)
        emo = self.build_emo_vec(style, spk)
        conds = self.gpt.build_conds_latent(style, emo)
        tt = mx.array([[1, 2, 3, 1]], dtype=mx.int32)
        from omlx.vendor.indextts25.support.tokenizer import lang_to_token

        lang = mx.array([lang_to_token("ZH")], dtype=mx.int32)
        codes = self.gpt.generate(conds, tt, lang, max_new_tokens=48, do_sample=True,
                                  top_k=30, top_p=0.8, temperature=0.8,
                                  stop_token=self.cfg.gpt.stop_mel_token, num_beams=3)
        if codes[0, -1].item() == self.cfg.gpt.stop_mel_token:
            codes = codes[:, :-1]
        s = self.codec.decode(codes)
        mel = self.s2mel.inference(spk, s, refmel, style, n_timesteps=8)
        _ = self.bigvgan(mel.astype(next(v for _, v in _flat(self.bigvgan)).dtype))

    def _ref_features(self, spk_audio_prompt):
        import os

        try:
            key = (spk_audio_prompt, os.path.getmtime(spk_audio_prompt))
        except OSError:
            key = None
        if key and key in self._ref_cache:
            return self._ref_cache[key]
        audio, sr = _load_audio(spk_audio_prompt, REF_MAX_SECONDS)
        a16 = mx.array(audio)[None]
        feats = (self.extract_spk_cond(self._resample(sr, REF_SR_W2V)(a16)),
                 self.extract_style(self._resample(sr, REF_SR_W2V)(a16)),
                 self._mel()(self._resample(sr, REF_SR_MEL)(a16).astype(mx.float32)))
        mx.eval(feats)  # split frontend graph: first-time Metal compile < watchdog
        if key is not None:
            self._ref_cache[key] = feats
        self._release_frontend()  # uncached ref: frontends are one-shot; reload on next new ref
        return feats

    def infer(self, spk_audio_prompt, text, lang="ZH", emo_vector=None, emo_text=None,
              emo_ref_path=None, emo_alpha=1.0, duration_factor=1.0, do_sample=True,
              top_p=0.8, top_k=30, temperature=0.8, max_mel_tokens=None, cfm_steps=15,
              cfg_rate=0.7, text_normalization=True, max_text_tokens_per_segment=120,
              interval_silence_ms=200, repetition_penalty=10.0, num_beams=3):
        _MEL_RATIO = dict((k, int(v)) for k, v in (p.split(":") for p in _MEL_RATIO_STR.split()))
        if text_normalization:
            text = self._ensure_normalizer().normalize(text)
        if emo_text is not None:
            emo_vector = self._ensure_qwen_emo().inference(emo_text)

        from omlx.vendor.indextts25.support.segmenter import split_text_by_tokens

        lang_prefix = f"<|{lang.lower()}|> "
        enc = lambda s: self._tokenizer().encode(s, allowed_special="all")
        segments = split_text_by_tokens(text, enc, max_tokens=max_text_tokens_per_segment, lang_prefix=lang_prefix)

        def _seg_mel_cap(seg):
            if max_mel_tokens is not None:
                return max_mel_tokens
            ratio = _MEL_RATIO.get(lang.upper(), 14)
            return max(int(len(enc(lang_prefix + seg)) * ratio * 2) + 8, 64)

        if len(segments) == 1:
            return self._infer_single(
                spk_audio_prompt, segments[0], lang, emo_vector, emo_ref_path, emo_alpha,
                duration_factor, do_sample, top_p, top_k, temperature,
                _seg_mel_cap(segments[0]), cfm_steps, cfg_rate, repetition_penalty, num_beams)

        wavs = [self._infer_single(
            spk_audio_prompt, seg, lang, emo_vector, emo_ref_path, emo_alpha,
            duration_factor, do_sample, top_p, top_k, temperature,
            _seg_mel_cap(seg), cfm_steps, cfg_rate, repetition_penalty, num_beams)[1]
            for seg in segments]
        silence = np.zeros(int(OUTPUT_SR * interval_silence_ms / 1000), dtype=np.float32)
        return OUTPUT_SR, np.concatenate(sum(([w, silence] for w in wavs[:-1]), []) + [wavs[-1]])

    def _infer_single(self, spk_audio_prompt, text, lang, emo_vector, emo_ref_path,
                      emo_alpha, duration_factor, do_sample, top_p, top_k, temperature,
                      max_mel_tokens, cfm_steps, cfg_rate, repetition_penalty=10.0, num_beams=3):
        spk_cond, style, ref_mel = self._ref_features(spk_audio_prompt)
        lang_prefix = f"<|{lang.lower()}|> "
        text_tokens = mx.array(self._tokenizer().encode(lang_prefix + text, allowed_special="all"), dtype=mx.int32)[None]
        text_tokens = mx.pad(text_tokens, [(0, 0), (0, 1)], constant_values=1)  # stop_text
        from omlx.vendor.indextts25.support.tokenizer import lang_to_token

        lang_id = mx.array([lang_to_token(lang)], dtype=mx.int32)
        if self.enable_emo_ref:
            emo_vec = self.build_emo_vec_full(
                style, spk_cond, emo_vector, emo_ref_path, emo_alpha
            )
        else:
            if emo_ref_path is not None:
                raise ValueError(
                    "Emotion reference audio requires enable_emo_ref=True"
                )
            emo_vec = self.build_emo_vec(style, spk_cond, emo_vector)
        mx.eval(emo_vec)
        conds_latent = self.gpt.build_conds_latent(style, emo_vec)
        mx.eval(conds_latent)
        codes = self.gpt.generate(conds_latent, text_tokens, lang_id, max_new_tokens=max_mel_tokens,
                                  do_sample=do_sample, top_k=top_k, top_p=top_p, temperature=temperature,
                                  stop_token=self.cfg.gpt.stop_mel_token,
                                  repetition_penalty=repetition_penalty, num_beams=num_beams)
        if codes[0, -1].item() == self.cfg.gpt.stop_mel_token:
            codes = codes[:, :-1]
        s_infer = self.codec.decode(codes)  # [1,2T,1024]
        mel = self.s2mel.inference(spk_cond, s_infer, ref_mel, style,
                                   duration_factor=duration_factor, n_timesteps=cfm_steps,
                                   inference_cfg_rate=cfg_rate)
        bg = self.bigvgan(mel.astype(next(v for _, v in _flat(self.bigvgan)).dtype))
        return OUTPUT_SR, np.asarray(mx.clip(bg, -1.0, 1.0)[0, 0], dtype=np.float32)


def _flat(m):
    from mlx.utils import tree_flatten

    return tree_flatten(m.parameters())
