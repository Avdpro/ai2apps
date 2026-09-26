# QwenEmotion — text->emotion-vector predictor (MLX port of windextts/models/qwen_emotion.py).
# qwen0.6bemo4-merge is a Qwen3-0.6B fine-tune emitting a JSON dict of 8 emotion
# scores; greedy decode via mlx Qwen3ForCausalLM, then parse (same fallbacks).
import json
import re
from pathlib import Path

from omlx.vendor.indextts25.models.qwen3 import load_qwen3

CN_KEY_TO_EN = {"高兴": "happy", "愤怒": "angry", "悲伤": "sad", "恐惧": "afraid",
                "反感": "disgusted", "低落": "melancholic", "惊讶": "surprised", "自然": "calm"}
DESIRED_VECTOR_ORDER = ["高兴", "愤怒", "悲伤", "恐惧", "反感", "低落", "惊讶", "自然"]
MELANCHOLIC_WORDS = {"低落", "melancholy", "melancholic", "depression", "depressed", "gloomy"}
EOS_TOKEN_ID = 151643
THINK_END_ID = 151668
MAX_NEW_TOKENS = 80


def _build_chat_prompt(text_input: str) -> str:
    # hardcoded official jinja render (enable_thinking=False); \x00 -> <|endoftext|>
    return (f"System: 文本情感分类{chr(0)}\nHuman: {text_input}{chr(0)}\nAssistant:"
            .replace(chr(0), "<|endoftext|>"))


class QwenEmotion:
    def __init__(self, model_dir, tokenizer_dir=None, dtype=None):
        # model_dir: mlx weights dir; tokenizer_dir: original qwen0.6bemo4-merge dir
        from tokenizers import Tokenizer  # lightweight Rust BPE (not transformers)

        self.model = load_qwen3(model_dir, dtype)
        tdir = Path(tokenizer_dir) if tokenizer_dir else Path(model_dir) / "qwen0.6bemo4-merge"
        self.tokenizer = Tokenizer.from_file(str(tdir / "tokenizer.json"))
        self.max_score, self.min_score = 1.2, 0.0

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.2, value))

    def _normalize_content(self, content) -> dict:
        def to_cn(v):
            if isinstance(v, str):
                v = v.strip()
                if v in CN_KEY_TO_EN:
                    return v
                for k, e in CN_KEY_TO_EN.items():
                    if v.lower() == e:
                        return k
            return None

        n = dict(content) if isinstance(content, dict) else {}
        d = to_cn(content) if isinstance(content, str) else None
        if d is None:
            for a in ("emotion", "emotion_label", "label", "情感", "情绪"):
                if (d := to_cn(n.get(a))) is not None:
                    break
        if d is not None and all(k not in n for k in DESIRED_VECTOR_ORDER):
            n[d] = 1.0
        for k in DESIRED_VECTOR_ORDER:
            det = to_cn(n.get(k))
            if det is not None:
                n[k] = 1.0 if det == k else 0.0
                if det != k:
                    n[det] = 1.0
        return n

    def _convert(self, content) -> list[float]:
        content = self._normalize_content(content)
        vec = [self._clamp(float(content.get(k, 0.0))) for k in DESIRED_VECTOR_ORDER]
        if all(v <= 0.0 for v in vec):
            vec[-1] = 1.0  # calm
        return vec

    def inference(self, text_input: str) -> list[float]:
        import mlx.core as mx

        enc = self.tokenizer.encode(_build_chat_prompt(text_input))
        input_ids = mx.array([enc.ids], dtype=mx.int32)
        full = self.model.generate(input_ids, max_new_tokens=MAX_NEW_TOKENS, eos_token_id=EOS_TOKEN_ID)
        gen = full[0, input_ids.shape[1]:].tolist()
        try:
            idx = len(gen) - gen[::-1].index(THINK_END_ID)
        except ValueError:
            idx = 0
        content = self.tokenizer.decode(gen[idx:])
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = {m.group(1): float(m.group(2))
                      for m in re.finditer(r'([^\s":.,]+?)"?\s*:\s*([\d.]+)', content)}
        if any(w in text_input.lower() for w in MELANCHOLIC_WORDS):
            parsed["悲伤"], parsed["低落"] = parsed.get("低落", 0.0), parsed.get("悲伤", 0.0)
        return self._convert(parsed)
