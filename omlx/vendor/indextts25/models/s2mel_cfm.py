# S2Mel-CFM: Euler solver + CFG around the DiT estimator — MLX port of
# windextts/models/s2mel_cfm.py (no CUDA-graph path; arrays are immutable so
# the prompt region is re-zeroed via a keep mask instead of in-place writes).
import mlx.core as mx

from omlx.vendor.indextts25.models.s2mel_dit import DiT


class S2MelCFM:
    def __init__(self, estimator: DiT, in_channels: int = 80, sigma_min: float = 1e-6):
        self.estimator = estimator
        self.in_channels = in_channels
        self.sigma_min = sigma_min
        self._step_c = None
        self._step_seqs = None
        self._step_T = None

    def _ensure_compiled(self, T, no_mask=False):
        # O1: compiled DiT forward (no per-layer evals). Static shapes: rebuild
        # only when (T, no_mask) changes (B=2 cfg is constant).
        # WINDEXTTS_NO_O1_COMPILE=1 forces eager for A/B / diagnostics.
        import os

        if os.environ.get("WINDEXTTS_NO_O1_COMPILE"):
            self._step_c = None
            return
        if self._step_c is not None and self._step_T == (T, no_mask, not os.environ.get("WINDEXTTS_NO_WN_DECOUPLE")):
            return
        try:
            fn, seqs = self.estimator._compiled_forward(no_mask)
            self._step_c, self._step_seqs, self._step_T = fn, seqs, (T, no_mask, not os.environ.get("WINDEXTTS_NO_WN_DECOUPLE"))
        except Exception as e:
            print(f"[O1] compiled DiT disabled: {type(e).__name__}: {e}")
            self._step_c, self._step_seqs, self._step_T = None, None, None

    def _estim(self, x, prompt_x, x_lens, t, style, mu, T):
        if self._step_c is not None:
            freqs = mx.take(self.estimator.transformer._ensure_freqs(T),
                            self.estimator.input_pos[:T], 0)
            for s in self._step_seqs:
                s._no_sync = True  # needed only during lazy trace of first call
            try:
                if isinstance(self._step_c, tuple):  # Wave-5 decoupled WaveNet
                    fn, fn_head = self._step_c
                    xc, xr, xm, t1, t2 = fn(x, prompt_x, x_lens, t, style, mu, freqs)
                    mx.eval(xc, xr, xm, t1, t2)
                    g = self.estimator.wavenet(xc, xm, g=t2[:, None, :])
                    e = fn_head(g, xr, t1)
                    mx.eval(g, e)
                    return e
                d = self._step_c(x, prompt_x, x_lens, t, style, mu, freqs)
            finally:
                for s in self._step_seqs:
                    s._no_sync = False
            return d
        return self.estimator(x, prompt_x, x_lens, t, style, mu)

    def inference(self, mu, x_lens, prompt, style, f0, n_timesteps=25,
                  temperature=1.0, inference_cfg_rate=0.7, z=None):
        B, T = mu.shape[0], mu.shape[1]
        if z is None:
            z = mx.random.normal((B, self.in_channels, T)) * temperature
        else:
            z = z * temperature
        t_span = mx.linspace(0, 1, n_timesteps + 1, dtype=mu.dtype)
        return self.solve_euler(z, x_lens, prompt, mu, style, f0, t_span, inference_cfg_rate)

    def solve_euler(self, x, x_lens, prompt, mu, style, f0, t_span, inference_cfg_rate=0.7):
        B, _, T = x.shape
        prompt_len = prompt.shape[-1]
        prompt_x = mx.concatenate([prompt, mx.zeros((B, self.in_channels, T - prompt_len))], -1)
        keep = mx.concatenate([mx.zeros((1, 1, prompt_len)), mx.ones((1, 1, T - prompt_len))], -1)  # re-zero prompt region
        cfg = float(inference_cfg_rate)
        if cfg > 0:
            zero_style = mx.zeros_like(style)
            zero_mu = mx.zeros_like(mu)
            s_prompt_x = mx.concatenate([prompt_x, mx.zeros_like(prompt_x)], 0)  # uncond half: zero prompt (torch parity)
            s_style = mx.concatenate([style, zero_style], 0)
            s_mu = mx.concatenate([mu, zero_mu], 0)
            s_lens = mx.concatenate([x_lens, x_lens], 0)
        t = t_span[0]
        x = x * keep  # zero the prompt region of z BEFORE the first step (torch parity)
        # O5: x_lens == T always holds here (S2Mel sets it to the padded length),
        # so the additive attention mask is exactly zero — skip it (bit-identical;
        # env WINDEXTTS_NO_O5_NOMASK=1 restores the legacy always-mask path).
        import os

        no_mask = (not os.environ.get("WINDEXTTS_NO_O5_NOMASK")) and bool(mx.min(x_lens).item() >= T)
        self._ensure_compiled(T, no_mask)
        for step in range(1, len(t_span)):
            dt = t_span[step] - t_span[step - 1]
            if cfg > 0:
                s_x = mx.concatenate([x, x], 0)
                s_t = mx.concatenate([t[None], t[None]], 0)
                d = self._estim(s_x, s_prompt_x, s_lens, s_t, s_style, s_mu, T)
                dphi, cfg_dphi = mx.split(d, 2, axis=0)
                dphi = (1.0 + cfg) * dphi - cfg * cfg_dphi
            else:
                dphi = self._estim(x, prompt_x, x_lens, t[None], style, mu, T)
            x = (x + dt * dphi) * keep
            t = t + dt
            mx.eval(x)
        return x


class S2Mel:
    # Full S2Mel: length_regulator + CFM(DiT). gpt_layer not loaded (config off).
    def __init__(self, length_regulator, cfm):
        self.length_regulator = length_regulator
        self.cfm = cfm

    def length_regulate(self, spk_cond, s_infer, ref_mel, duration_factor=1.0):
        ref_target_lengths = mx.array([ref_mel.shape[2]], dtype=mx.int32)
        prompt_condition = self.length_regulator(spk_cond, ylens=ref_target_lengths, n_quantizers=3, f0=None)[0]
        target_lengths = mx.array([int(s_infer.shape[1] * 1.72 * duration_factor)], dtype=mx.int32)
        cond = self.length_regulator(s_infer, ylens=target_lengths, n_quantizers=3, f0=None)[0]
        cat_condition = mx.concatenate([prompt_condition, cond], 1)
        return prompt_condition, cond, cat_condition

    def inference(self, spk_cond, s_infer, ref_mel, style, duration_factor=1.0,
                  n_timesteps=25, inference_cfg_rate=0.7, z=None):
        _, _, cat_condition = self.length_regulate(spk_cond, s_infer, ref_mel, duration_factor)
        x_lens = mx.array([cat_condition.shape[1]], dtype=mx.int32)
        vc = self.cfm.inference(cat_condition, x_lens, ref_mel, style, None,
                                n_timesteps=n_timesteps, inference_cfg_rate=inference_cfg_rate, z=z)
        return vc[:, :, ref_mel.shape[-1]:]  # strip prompt region
