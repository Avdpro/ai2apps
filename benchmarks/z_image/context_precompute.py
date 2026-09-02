"""Benchmark-only invariant caption-context precomputation for Z-Image."""

import mlx.core as mx


def install_context_precompute() -> None:
    from mflux.models.z_image.model.z_image_transformer.transformer import ZImageTransformer
    from mflux.models.z_image.variants.z_image import ZImage

    original_patchify = ZImageTransformer._patchify

    def prepare(self, cap_feats):
        if getattr(self, "_ai2apps_cap_source", None) is cap_feats:
            return self._ai2apps_cap_emb, self._ai2apps_cap_freqs
        cap_len = cap_feats.shape[0]
        padding = (-cap_len) % 32
        pos = self._create_coord_grid((cap_len + padding, 1, 1), (1, 0, 0)).reshape(-1, 3)
        pad_mask = mx.concatenate(
            [mx.zeros((cap_len,), dtype=mx.bool_), mx.ones((padding,), dtype=mx.bool_)]
        )
        padded = (
            mx.concatenate([cap_feats, mx.repeat(cap_feats[-1:], padding, axis=0)], axis=0)
            if padding
            else cap_feats
        )
        embedded = self.cap_embedder[1](self.cap_embedder[0](padded))
        embedded = mx.where(pad_mask[:, None], self.cap_pad_token, embedded)
        freqs = self.rope_embedder(pos)
        embedded = mx.expand_dims(embedded, axis=0)
        mask = mx.ones((1, embedded.shape[1]), dtype=mx.bool_)
        for layer in self.context_refiner:
            embedded = layer(x=embedded, attn_mask=mask, freqs_cis=freqs)
        mx.eval(embedded, freqs)
        object.__setattr__(self, "_ai2apps_cap_source", cap_feats)
        object.__setattr__(self, "_ai2apps_cap_emb", embedded)
        object.__setattr__(self, "_ai2apps_cap_freqs", freqs)
        return embedded, freqs

    def optimized_call(self, x, timestep, sigmas, cap_feats, controlnet_block_samples=None):
        key = f"{self.patch_size}-{self.f_patch_size}"
        if not isinstance(timestep, mx.array):
            if isinstance(timestep, int):
                sigma_t = sigmas[timestep].reshape((1,))
                timestep = mx.ones_like(sigma_t) - sigma_t
            else:
                timestep = mx.array(timestep, dtype=mx.float32)
        if timestep.ndim == 0:
            timestep = timestep.reshape((1,))
        t_emb = self.t_embedder(timestep.astype(mx.float32) * self.t_scale)

        image, _cap, size, image_pos, _cap_pos, image_pad, _cap_pad = original_patchify(
            image=x,
            cap_feats=cap_feats,
            patch_size=self.patch_size,
            f_patch_size=self.f_patch_size,
        )
        image = self.all_x_embedder[key](image)
        image = mx.where(image_pad[:, None], self.x_pad_token, image)
        image_freqs = self.rope_embedder(image_pos)
        image = mx.expand_dims(image, axis=0)
        image_mask = mx.ones((1, image.shape[1]), dtype=mx.bool_)
        for layer in self.noise_refiner:
            image = layer(x=image, attn_mask=image_mask, freqs_cis=image_freqs, t_emb=t_emb)

        cap, cap_freqs = prepare(self, cap_feats)
        image_len = image.shape[1]
        unified = mx.concatenate([image, cap], axis=1)
        freqs = mx.concatenate([image_freqs, cap_freqs], axis=0)
        mask = mx.ones((1, unified.shape[1]), dtype=mx.bool_)
        for layer_index, layer in enumerate(self.layers):
            unified = layer(x=unified, attn_mask=mask, freqs_cis=freqs, t_emb=t_emb)
            if controlnet_block_samples is not None:
                sample = self._get_controlnet_sample(layer_index, self.layers, controlnet_block_samples)
                if sample is not None:
                    unified = unified + sample
        unified = self.all_final_layer[key](unified, t_emb)
        output = self._unpatchify(
            x=unified[0, :image_len],
            size=size,
            patch_size=self.patch_size,
            f_patch_size=self.f_patch_size,
            out_channels=self.out_channels,
        )
        return -output

    ZImageTransformer.__call__ = optimized_call
    ZImageTransformer._ai2apps_prepare_context = prepare

    def optimized_predict(transformer):
        compiled = None
        compiled_source = None

        def predict(latents, timestep, sigmas, text_encodings, negative_encodings, guidance):
            nonlocal compiled, compiled_source
            if negative_encodings is not None:
                raise ValueError("context-precompute prototype currently supports Turbo only")
            if compiled is None or compiled_source is not text_encodings:
                prepare(transformer, text_encodings)
                compiled_source = text_encodings
                compiled = mx.compile(
                    lambda current_latents, current_timestep, current_sigmas: transformer(
                        timestep=current_timestep,
                        x=current_latents,
                        cap_feats=compiled_source,
                        sigmas=current_sigmas,
                    )
                )
            return compiled(latents, timestep, sigmas)

        return predict

    ZImage._predict = staticmethod(optimized_predict)
