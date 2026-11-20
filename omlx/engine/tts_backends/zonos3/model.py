"""ZONOS3-Mini synthesis through mlx-audio's standard TTS interface."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import mlx.core as mx
import numpy as np
from mlx import nn

from mlx_audio.tts.models.base import GenerationResult
from .backbone import Backbone, LMState
from .config import LMConfig, ModelConfig
from .generation import (
    TextTokenizer,
    aligned_codes,
    condition_ids,
    delay_codes,
    output_audio,
    sample_row,
)


class Model(nn.Module):
    sample_rate = 44100
    preserve_ref_audio_path = True

    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config
        self.backbone = Backbone(LMConfig(**config.backbone), config.tensors)
        self._tokenizer = None
        self._decoder = None
        self._speaker_encoder = None
        self._voices = {}

    def __call__(self, ids, state=None, **kwargs):
        return self.backbone(ids, LMState() if state is None else state, **kwargs)

    @property
    def voices(self):
        return sorted(self._voices)

    @classmethod
    def post_load_hook(cls, model, model_path):
        root = Path(model_path)
        c = model.backbone.config
        model._tokenizer = TextTokenizer(root, c.text_tokenizer_spec, c.text_vocab)
        voices = root / "voices.json"
        if voices.is_file():
            model._voices = json.loads(voices.read_text())
        return model

    def _load_decoder(self):
        if self._decoder is None:
            from .codec import CodecDecoder

            self._decoder = CodecDecoder.load(Path(self.config.model_path) / "codec")
        return self._decoder

    def extract_speaker_embedding(self, audio):
        from mlx_audio.utils import load_audio

        from .speaker import SpeakerEncoder

        if self._speaker_encoder is None:
            path = Path(self.config.model_path) / "speaker_encoder"
            if not path.is_dir():
                raise ValueError("this checkpoint does not include a speaker encoder")
            self._speaker_encoder = SpeakerEncoder.load(path)
        if isinstance(audio, Path):
            audio = str(audio)
        if isinstance(audio, str):
            audio = load_audio(audio, sample_rate=self.sample_rate)
        pcm = np.asarray(audio, np.float32)
        if pcm.ndim != 1 or len(pcm) == 0 or not np.isfinite(pcm).all():
            raise ValueError("reference audio must be finite mono PCM at 44100 Hz")
        return self._speaker_encoder.embed(pcm[: 60 * self.sample_rate])

    def _embedding(self, voice, ref_audio, speaker_embedding):
        if ref_audio is not None and speaker_embedding is not None:
            raise ValueError("ref_audio and speaker_embedding are mutually exclusive")
        if ref_audio is not None:
            embedding = self.extract_speaker_embedding(ref_audio)
        elif speaker_embedding is not None:
            if isinstance(speaker_embedding, (str, Path)):
                loaded = np.load(speaker_embedding, allow_pickle=False)
                if isinstance(loaded, np.lib.npyio.NpzFile):
                    with loaded:
                        if "embedding" not in loaded:
                            raise ValueError(
                                "speaker archive must contain an embedding array"
                            )
                        embedding = loaded["embedding"]
                else:
                    embedding = loaded
            else:
                embedding = speaker_embedding
        else:
            name = (voice or "jett").lower()
            if name == "none":
                return None
            if name not in self._voices:
                raise ValueError(
                    f'unknown voice {voice!r}; available: {", ".join(self.voices)}'
                )
            with np.load(
                Path(self.config.model_path) / "voices" / self._voices[name],
                allow_pickle=False,
            ) as archive:
                embedding = archive["embedding"]
        embedding = np.asarray(embedding, np.float32)
        if embedding.ndim == 2 and embedding.shape[0] == 1:
            embedding = embedding[0]
        if (
            embedding.shape != (self.backbone.config.speaker_embedding_dim,)
            or not np.isfinite(embedding).all()
        ):
            raise ValueError(
                f"expected a finite {self.backbone.config.speaker_embedding_dim}-dimensional speaker embedding"
            )
        return embedding

    def generate(
        self,
        text,
        voice=None,
        speed=1.0,
        lang_code="en",
        ref_audio=None,
        ref_text=None,
        max_tokens=None,
        temperature=0.75,
        top_k=80,
        top_p=0.69,
        min_p=0.0,
        repetition_penalty=2.4,
        repetition_window=96,
        repetition_codebooks=6,
        seed=None,
        stream=False,
        streaming_interval=0.5,
        emotion=None,
        emotion_strength=2.0,
        speaker_embedding=None,
        speaker_cfg_scale=1.0,
        cfg_scale=None,
        condition_buckets=None,
        condition_values=None,
        min_frames=0,
        silence_prefill_frames=3,
        text_normalization=True,
        headroom_db=None,
        **kwargs,
    ):
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must not be empty")
        if not math.isfinite(speed) or speed <= 0:
            raise ValueError("speed must be finite and positive")
        if streaming_interval <= 0 or not math.isfinite(streaming_interval):
            raise ValueError("streaming_interval must be finite and positive")
        if (
            int(silence_prefill_frames) != silence_prefill_frames
            or not 0 <= silence_prefill_frames <= 30
        ):
            raise ValueError("silence_prefill_frames must be an integer in [0, 30]")
        silence_prefill_frames = int(silence_prefill_frames)
        if min_frames < 0 or int(min_frames) != min_frames:
            raise ValueError("min_frames must be a nonnegative integer")
        if not all(
            math.isfinite(float(v))
            for v in (temperature, top_p, min_p, repetition_penalty)
        ):
            raise ValueError("sampling parameters must be finite")
        scale = speaker_cfg_scale if cfg_scale is None else cfg_scale
        if not math.isfinite(scale) or scale < 0:
            raise ValueError("speaker_cfg_scale must be finite and nonnegative")
        if self._tokenizer is None:
            raise RuntimeError("load the model with mlx_audio.tts.utils.load")
        if text_normalization:
            from mlx_audio.tts.models.zonos2.textnorm import TTSTextNormalizer

            text = TTSTextNormalizer().normalize(
                text, lang_code.replace("-", "_").lower()
            )
        c = self.backbone.config
        from .steering import emotion_delta
        hidden_deltas = emotion_delta(emotion, emotion_strength, c)
        buckets = condition_ids(c, condition_buckets, condition_values)
        if speed != 1.0:
            if condition_buckets is not None or condition_values is not None:
                raise ValueError("speed cannot be combined with explicit conditions")
            buckets = condition_ids(c, values={"speaking_rate": 15.193 * speed})
        embedding = self._embedding(voice, ref_audio, speaker_embedding)
        if scale != 1 and embedding is None:
            raise ValueError("speaker CFG needs a speaker embedding or reference audio")
        tokens = self._tokenizer.encode(text)
        offset = int(embedding is not None)
        rows = mx.full(
            (offset + c.condition_count + len(tokens), c.n_codebooks + 1),
            c.audio_pad_id,
            mx.int32,
        )
        rows[:, -1] = c.text_vocab
        rows[offset + c.condition_count :, -1] = mx.array(tokens, mx.int32)
        silence = delay_codes(
            mx.broadcast_to(
                mx.array(c.silence_frame, mx.int32),
                (silence_prefill_frames, c.n_codebooks),
            ),
            c.audio_pad_id,
            flush=False,
        )
        if len(silence):
            opening = mx.concatenate(
                [silence, mx.full((len(silence), 1), c.text_vocab, mx.int32)], axis=-1
            )
            rows = mx.concatenate([rows, opening])
        budget = min(
            2000 if max_tokens is None else int(max_tokens), c.max_seqlen - len(rows)
        )
        if budget <= 0:
            raise ValueError(
                "max_tokens must be positive and the prompt must leave context for audio"
            )
        start = time.perf_counter()
        state = LMState()
        logits = self(
            rows,
            state,
            speaker_rows={0: embedding} if offset else None,
            condition_rows={offset + i: v for i, v in enumerate(buckets)},
        )[-1]
        twin_state = LMState() if scale != 1 else None
        if twin_state is not None:
            twin_logits = self(
                rows[1:],
                twin_state,
                condition_rows=dict(enumerate(c.condition_bucket_counts)),
            )[-1]
        mx.eval(logits, state.arrays())
        prefill_time = time.perf_counter() - start
        decoder = self._load_decoder()
        codec_stream = decoder.stream() if stream else None
        history = mx.zeros((len(silence) + budget, c.n_codebooks), mx.int32)
        history[: len(silence)] = silence
        eos_frame = None
        decoded = 0
        chunks = []
        interval = max(1, round(streaming_interval * 15))
        prompt_tokens = len(rows)
        step = -1
        for step in range(budget):
            t = len(silence) + step
            guided = (
                logits
                if twin_state is None
                else twin_logits + scale * (logits - twin_logits)
            )
            token = sample_row(
                guided,
                c,
                step=step,
                history=history[:t],
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                min_p=min_p,
                repetition_penalty=repetition_penalty,
                repetition_window=repetition_window,
                repetition_codebooks=repetition_codebooks,
                min_frames=min_frames,
                has_audio_prefix=bool(len(silence)),
                key=mx.random.key(seed + step) if seed is not None else None,
            )
            history[t] = token
            last_stop = mx.max(
                mx.where(token == c.eoa_id, mx.arange(c.n_codebooks), -1)
            )
            mx.eval(history, last_stop, state.arrays())
            # Only the stopping decision crosses to the host; token history
            # and repetition masks remain MLX arrays.
            stop_column = last_stop.item()
            if stop_column >= 0:
                aligned_stop = max(0, t - stop_column)
                eos_frame = (
                    aligned_stop if eos_frame is None else min(eos_frame, aligned_stop)
                )
            ready = max(0, t + 1 - c.n_codebooks + 1)
            if eos_frame is not None:
                ready = min(ready, eos_frame)
            if stream and ready - decoded >= interval:
                codes = aligned_codes(
                    history[: t + 1], c.n_codebooks, eos_frame, start=decoded
                )
                audio = codec_stream.decode(codes)
                decoded = ready
                if len(audio):
                    yield self._result(
                        audio,
                        decoder,
                        start,
                        prefill_time,
                        prompt_tokens,
                        step + 1,
                        stream=True,
                        final=False,
                        headroom_db=headroom_db,
                    )
            if eos_frame is not None and t >= eos_frame + c.n_codebooks - 1:
                break
            if step + 1 < budget:
                next_row = mx.concatenate([token, mx.array([c.text_vocab], mx.int32)])[
                    None
                ]
                logits = self(next_row, state, hidden_deltas=hidden_deltas)[-1]
                if twin_state is not None:
                    twin_logits = self(next_row, twin_state)[-1]
        codes = aligned_codes(
            history[: len(silence) + step + 1], c.n_codebooks, eos_frame
        )
        if stream:
            if len(codes) > decoded:
                chunks.append(codec_stream.decode(codes[decoded:]))
            chunks.append(codec_stream.flush())
            audio = mx.concatenate([mx.array(chunk, mx.float32) for chunk in chunks])
        else:
            audio = decoder.decode(codes)
        yield self._result(
            audio,
            decoder,
            start,
            prefill_time,
            prompt_tokens,
            step + 1,
            stream=stream,
            final=True,
            headroom_db=headroom_db,
        )

    def _result(
        self,
        audio,
        decoder,
        start,
        prefill_time,
        prompt_tokens,
        tokens,
        *,
        stream,
        final,
        headroom_db,
    ):
        audio = output_audio(audio, decoder.output_gain(headroom_db))
        elapsed = time.perf_counter() - start
        duration = len(audio) / self.sample_rate
        return GenerationResult(
            audio=audio,
            samples=len(audio),
            sample_rate=self.sample_rate,
            segment_idx=0,
            token_count=tokens,
            audio_duration=f"{duration:.2f}s",
            real_time_factor=elapsed / duration if duration else 0.0,
            prompt={
                "tokens": prompt_tokens,
                "time": prefill_time,
                "tokens-per-sec": prompt_tokens / max(prefill_time, 1e-9),
            },
            audio_samples={
                "samples": len(audio),
                "samples-per-sec": len(audio) / max(elapsed, 1e-9),
            },
            processing_time_seconds=elapsed,
            peak_memory_usage=mx.get_peak_memory() / 1e9,
            is_streaming_chunk=stream,
            is_final_chunk=final,
        )
