"""MLX CTC forced-alignment backend for the standalone experiment."""

from __future__ import annotations

import json
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Literal

import numpy as np

from .audio import read_audio
from .ctc import ctc_viterbi_align, log_softmax
from .schema import Segment, Word


class UnsupportedAlignmentLanguageError(ValueError):
    pass


class MLXCTCAligner:
    name = "mlx_audio_wav2vec2_ctc"
    alignment_method = "ctc_forced_alignment"

    def __init__(
        self,
        model: str,
        *,
        revision: str | None = None,
        min_word_score: float = 0.0,
        segment_padding: float = 0.12,
        max_window_seconds: float = 30.0,
        supported_languages: set[str] | None = None,
        unknown_character_policy: Literal["skip", "reject"] = "skip",
    ) -> None:
        if not 0.0 <= min_word_score <= 1.0:
            raise ValueError("min_word_score must be between 0 and 1")
        self.model_source = model
        self.revision = revision
        self.min_word_score = min_word_score
        self.segment_padding = max(0.0, segment_padding)
        if max_window_seconds <= 0:
            raise ValueError("max_window_seconds must be positive")
        self.max_window_seconds = max_window_seconds
        if unknown_character_policy not in {"skip", "reject"}:
            raise ValueError("unknown_character_policy must be skip or reject")
        self.unknown_character_policy = unknown_character_policy
        self.skipped_characters: Counter[str] = Counter()
        self._configured_languages = (
            frozenset(value.lower() for value in supported_languages)
            if supported_languages
            else None
        )
        self._model: Any | None = None
        self._vocab: dict[str, int] | None = None

    def _model_path(self) -> Path:
        path = Path(self.model_source).expanduser()
        if path.is_dir():
            return path
        from mlx_audio.utils import get_model_path

        kwargs = {"revision": self.revision} if self.revision else {}
        return get_model_path(self.model_source, **kwargs)

    def _load(self) -> Any:
        if self._model is None:
            import mlx.core as mx
            from mlx_audio.stt.models.mms import Model, ModelConfig
            from mlx_audio.utils import apply_quantization, load_config, load_weights

            path = self._model_path()
            config = load_config(path)
            model = Model(ModelConfig.from_dict(config))
            weights = model.sanitize(load_weights(path))
            apply_quantization(model, config, weights)
            model.load_weights(list(weights.items()), strict=False)
            mx.eval(model.parameters())
            model.eval()
            self._model = model
        return self._model

    def _load_vocab(self) -> dict[str, int]:
        if self._vocab is not None:
            return self._vocab
        path = self._model_path()
        vocab_path = path / "vocab.json"
        if not vocab_path.is_file():
            raise ValueError(f"CTC checkpoint has no vocab.json: {path}")
        value = json.loads(vocab_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not value:
            raise ValueError("CTC vocabulary must be a non-empty object")
        self._vocab = {str(token): int(index) for token, index in value.items()}
        return self._vocab

    def _supported_languages(self) -> frozenset[str]:
        if self._configured_languages is not None:
            return self._configured_languages
        config_path = self._model_path() / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        declared = config.get("ai2apps_alignment_languages", ["en"])
        return frozenset(str(value).lower() for value in declared)

    def align(
        self,
        audio_path: str | Path,
        segments: list[Segment],
        *,
        language: str | None,
    ) -> list[Segment]:
        language_code = (language or "").lower().split("-", 1)[0]
        supported_languages = self._supported_languages()
        if language_code not in supported_languages:
            raise UnsupportedAlignmentLanguageError(
                f"CTC aligner supports {sorted(supported_languages)}, got "
                f"{language or 'unknown'}"
            )
        audio = read_audio(audio_path)
        if not segments or not audio.duration:
            return segments
        self.skipped_characters.clear()
        vocab = self._load_vocab()
        model = self._load()
        import mlx.core as mx

        aligned_segments: list[Segment] = []
        blank_id = int(getattr(model.config, "pad_token_id", 0))
        for group in self._groups(segments):
            words = self._ensure_words(group, language=language_code)
            target, word_ranges = self._target(
                words,
                vocab,
                use_delimiter=language_code != "zh",
            )
            if not target:
                aligned_segments.extend(self._finalize_group(group, set()))
                continue
            chunk_start = max(0.0, group[0].start - self.segment_padding)
            chunk_end = min(audio.duration, group[-1].end + self.segment_padding)
            chunk = audio.slice(chunk_start, chunk_end)
            values = mx.array(chunk.samples)[None, :]
            values = (values - mx.mean(values, axis=-1, keepdims=True)) / (
                mx.std(values, axis=-1, keepdims=True) + 1e-7
            )
            logits = model(values)
            mx.eval(logits)
            emissions = log_softmax(np.asarray(logits[0]))
            token_alignment = ctc_viterbi_align(
                emissions,
                target,
                duration=chunk.duration,
                blank_id=blank_id,
            )

            aligned_word_ids: set[int] = set()
            for word, (first, last) in zip(words, word_ranges, strict=True):
                if first == last:
                    continue
                pieces = token_alignment[first:last]
                word.start = chunk_start + pieces[0].start
                word.end = chunk_start + pieces[-1].end
                word.score = float(np.mean([piece.score for piece in pieces]))
                if word.score >= self.min_word_score:
                    aligned_word_ids.add(id(word))
            aligned_segments.extend(
                self._finalize_group(group, aligned_word_ids)
            )
        return aligned_segments

    def _finalize_group(
        self, group: list[Segment], aligned_word_ids: set[int]
    ) -> list[Segment]:
        finalized: list[Segment] = []
        for segment in group:
            segment.words = [
                word for word in segment.words if id(word) in aligned_word_ids
            ]
            if not segment.words:
                finalized.append(segment)
                continue
            if self.min_word_score > 0:
                segment.text = " ".join(
                    word.word.strip()
                    for word in segment.words
                    if word.word.strip()
                )
            segment.start = segment.words[0].start or 0.0
            segment.end = segment.words[-1].end or segment.start
            finalized.append(segment)
        return finalized

    def _groups(self, segments: list[Segment]) -> list[list[Segment]]:
        groups: list[list[Segment]] = []
        current: list[Segment] = []
        window_start = 0.0
        for segment in sorted(segments, key=lambda item: (item.start, item.end)):
            if segment.end - segment.start > self.max_window_seconds:
                raise ValueError(
                    "Transcript segment exceeds the configured CTC alignment window"
                )
            if current and segment.end - window_start > self.max_window_seconds:
                groups.append(current)
                current = []
            if not current:
                window_start = segment.start
            current.append(segment)
        if current:
            groups.append(current)
        return groups

    @staticmethod
    def _ensure_words(segments: list[Segment], *, language: str) -> list[Word]:
        words: list[Word] = []
        for segment in segments:
            if language == "zh":
                segment.words = [
                    Word(word=character)
                    for character in segment.text
                    if not character.isspace()
                ]
            elif not segment.words:
                segment.words = [Word(word=value) for value in segment.text.split()]
            words.extend(segment.words)
        return words

    def _normalize(self, value: str, vocab: dict[str, int]) -> list[str]:
        decomposed = unicodedata.normalize("NFKD", value.upper())
        supported: list[str] = []
        unsupported: list[str] = []
        for character in decomposed:
            if character in vocab:
                supported.append(character)
                continue
            category = unicodedata.category(character)
            if character.isspace() or category[0] in {"M", "P", "S"}:
                continue
            if category[0] in {"L", "N"}:
                unsupported.append(character)
        if unsupported:
            rendered = "".join(dict.fromkeys(unsupported))
            if self.unknown_character_policy == "reject":
                raise ValueError(
                    f"CTC vocabulary cannot align characters: {rendered}"
                )
            self.skipped_characters.update(unsupported)
        return supported

    def _target(
        self,
        words: list[Word],
        vocab: dict[str, int],
        *,
        use_delimiter: bool = True,
    ) -> tuple[list[int], list[tuple[int, int]]]:
        delimiter = vocab.get("|") if use_delimiter else None
        target: list[int] = []
        ranges: list[tuple[int, int]] = []
        emitted_word = False
        for word in words:
            characters = self._normalize(word.word, vocab)
            if characters and emitted_word and delimiter is not None:
                target.append(delimiter)
            first = len(target)
            target.extend(vocab[character] for character in characters)
            ranges.append((first, len(target)))
            emitted_word = emitted_word or bool(characters)
        return target, ranges


class MLXQwen3ForcedAligner:
    """Multilingual Qwen3 forced alignment with bounded MLX inference windows."""

    name = "mlx_audio_qwen3_forced_aligner"
    alignment_method = "qwen3_forced_alignment"

    _LANGUAGES = {
        "zh": "Chinese",
        "cmn": "Chinese",
        "yue": "Cantonese",
        "en": "English",
        "de": "German",
        "es": "Spanish",
        "fr": "French",
        "it": "Italian",
        "pt": "Portuguese",
        "ru": "Russian",
        "ko": "Korean",
        "ja": "Japanese",
    }

    def __init__(
        self,
        model: str,
        *,
        revision: str | None = None,
        segment_padding: float = 0.12,
        max_window_seconds: float = 240.0,
    ) -> None:
        if max_window_seconds <= 0 or max_window_seconds > 300:
            raise ValueError("Qwen3 alignment window must be in (0, 300] seconds")
        self.model_source = model
        self.revision = revision
        self.segment_padding = max(0.0, segment_padding)
        self.max_window_seconds = max_window_seconds
        self._model: Any | None = None
        self.alignment_stats: dict[str, int | float] = {}

    @classmethod
    def _language_name(cls, language: str | None) -> str:
        normalized = (language or "").strip().lower()
        for name in cls._LANGUAGES.values():
            if normalized == name.lower():
                return name
        code = normalized.replace("_", "-").split("-", 1)[0]
        try:
            return cls._LANGUAGES[code]
        except KeyError as error:
            raise UnsupportedAlignmentLanguageError(
                f"Qwen3 ForcedAligner supports {sorted(cls._LANGUAGES)}, got "
                f"{language or 'unknown'}"
            ) from error

    def _model_path(self) -> Path:
        path = Path(self.model_source).expanduser()
        if path.is_dir():
            return path
        from mlx_audio.utils import get_model_path

        kwargs = {"revision": self.revision} if self.revision else {}
        return get_model_path(self.model_source, **kwargs)

    def _load(self) -> Any:
        if self._model is None:
            from mlx_audio.stt.utils import load_model

            self._model = load_model(self._model_path())
        return self._model

    def _groups(self, segments: list[Segment]) -> list[list[Segment]]:
        groups: list[list[Segment]] = []
        current: list[Segment] = []
        window_start = 0.0
        for segment in sorted(segments, key=lambda item: (item.start, item.end)):
            if segment.end - segment.start > self.max_window_seconds:
                raise ValueError(
                    "Transcript segment exceeds the configured Qwen3 alignment window"
                )
            if current and segment.end - window_start > self.max_window_seconds:
                groups.append(current)
                current = []
            if not current:
                window_start = segment.start
            current.append(segment)
        if current:
            groups.append(current)
        return groups

    @staticmethod
    def _alignment_text_key(value: str) -> str:
        """Compare transcript text without alignment-neutral presentation marks."""

        return "".join(
            character.casefold()
            for character in unicodedata.normalize("NFKC", value)
            if character.isalnum()
        )

    @classmethod
    def _should_replace_transcript_text(cls, original: str, aligned: str) -> bool:
        """Replace only when alignment removed a substantial amount of content.

        Qwen3-ASR owns transcript wording, casing, and punctuation.  The forced
        aligner normally returns only timestamp-bearing lexical units, so rebuilding
        ``Segment.text`` from those units would silently discard native punctuation.
        A large coverage loss still indicates the aligner's existing hallucination
        safeguard should win.
        """

        original_key = cls._alignment_text_key(original)
        aligned_key = cls._alignment_text_key(aligned)
        if not aligned_key or aligned_key == original_key:
            return False
        return len(aligned_key) < len(original_key) * 0.65

    def _apply_items(
        self,
        group: list[Segment],
        token_counts: list[int],
        items: list[Any],
        *,
        offset: float,
        language_name: str = "English",
    ) -> list[Segment]:
        if sum(token_counts) != len(items):
            raise ValueError(
                "Qwen3 ForcedAligner returned a different number of timestamp units"
            )
        cursor = 0
        valid_units = 0
        discarded_unaligned_units = 0
        rewritten_segments = 0
        removed_text_characters = 0
        for segment, count in zip(group, token_counts, strict=True):
            original_text = segment.text
            selected = items[cursor : cursor + count]
            cursor += count
            candidates = [
                Word(
                    word=str(item.text),
                    start=offset + float(item.start_time),
                    end=offset + float(item.end_time),
                )
                for item in selected
            ]
            segment.words = [
                word
                for word in candidates
                if word.start is not None
                and word.end is not None
                and word.end > word.start
            ]
            discarded_unaligned_units += len(candidates) - len(segment.words)
            separator = "" if language_name in {"Chinese", "Cantonese", "Japanese"} else " "
            aligned_text = separator.join(
                word.word.strip() for word in segment.words if word.word.strip()
            ).strip()
            if aligned_text and self._should_replace_transcript_text(
                original_text, aligned_text
            ):
                segment.text = aligned_text
                rewritten_segments += 1
                removed_text_characters += max(
                    0, len(original_text.strip()) - len(aligned_text)
                )
            valid_units += len(segment.words)
            if segment.words:
                segment.start = segment.words[0].start or segment.start
                segment.end = segment.words[-1].end or segment.end
        total_units = sum(token_counts)
        self.alignment_stats = {
            "total_units": int(self.alignment_stats.get("total_units", 0))
            + total_units,
            "aligned_units": int(self.alignment_stats.get("aligned_units", 0))
            + valid_units,
            "discarded_unaligned_units": int(
                self.alignment_stats.get("discarded_unaligned_units", 0)
            )
            + discarded_unaligned_units,
            "rewritten_segments": int(
                self.alignment_stats.get("rewritten_segments", 0)
            )
            + rewritten_segments,
            "removed_text_characters": int(
                self.alignment_stats.get("removed_text_characters", 0)
            )
            + removed_text_characters,
        }
        total = int(self.alignment_stats["total_units"])
        self.alignment_stats["coverage"] = (
            float(self.alignment_stats["aligned_units"]) / total if total else 1.0
        )
        return group

    def align(
        self,
        audio_path: str | Path,
        segments: list[Segment],
        *,
        language: str | None,
    ) -> list[Segment]:
        language_name = self._language_name(language)
        audio = read_audio(audio_path)
        if not segments or not audio.duration:
            return segments
        self.alignment_stats = {}
        model = self._load()
        processor = model.aligner_processor
        aligned: list[Segment] = []
        for group in self._groups(segments):
            texts = [segment.text.strip() for segment in group]
            token_counts = [
                len(processor.encode_timestamp(text, language_name)[0])
                for text in texts
            ]
            if not sum(token_counts):
                aligned.extend(group)
                continue
            chunk_start = max(0.0, group[0].start - self.segment_padding)
            chunk_end = min(audio.duration, group[-1].end + self.segment_padding)
            chunk = audio.slice(chunk_start, chunk_end)
            result = model.generate(
                chunk.samples,
                text=" ".join(texts),
                language=language_name,
            )
            aligned.extend(
                self._apply_items(
                    group,
                    token_counts,
                    list(result.items),
                    offset=chunk_start,
                    language_name=language_name,
                )
            )
        return aligned
