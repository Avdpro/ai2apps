"""Long-text segmentation for GPT-AR — replicates infer_v2_5.py split_text_by_tokens/by_punctuation."""
import re

SPLIT_PROTECTED_PATTERN = re.compile(r"<\|SPECIAL_TOKEN_\d+\|>.*?<\|SPECIAL_TOKEN_\d+\|>")  # protect atomic spans
_PUNCT_SPLIT = re.compile(r"(?<=[，。！？、；：,\.!\?;:\n])")  # split AFTER punct; delimiter stays with preceding seg
_DEFAULT_CAPACITY = 602  # gpt.max_text_tokens=600 -> +2


def _split_atomic_pieces(text):
    # (chunk, is_atomic); atomic spans never re-split
    pieces, pos = [], 0
    for m in SPLIT_PROTECTED_PATTERN.finditer(text):
        if m.start() > pos:
            pieces.append((text[pos:m.start()], False))
        pieces.append((m.group(0), True))
        pos = m.end()
    return pieces + ([(text[pos:], False)] if pos < len(text) else [])


def split_text_by_tokens(text, tokenizer, max_tokens, lang_prefix="", capacity=_DEFAULT_CAPACITY):
    # budget = min(max_tokens, capacity-2) - tok(prefix), floor 1; whole-text short-circuit
    budget = max(1, min(max_tokens, capacity - 2) - len(tokenizer(lang_prefix)))
    if len(tokenizer(text)) <= budget:
        return [text]
    chunks = []
    for piece, atomic in _split_atomic_pieces(text):
        if atomic:
            chunks.append(piece)
            continue
        for part in _PUNCT_SPLIT.split(piece):
            if not part or len(tokenizer(part)) <= budget:
                if part:
                    chunks.append(part)
                continue
            cur = ""  # force-split over-budget part by character
            for ch in part:
                if cur and len(tokenizer(cur + ch)) > budget:
                    chunks.append(cur)
                    cur = ch
                else:
                    cur += ch
            if cur:
                chunks.append(cur)
    # greedy merge into budget-sized segments
    segments, cur = [], ""
    for chunk in chunks:
        if cur and len(tokenizer(cur + chunk)) > budget:
            segments.append(cur)
            cur = chunk
        else:
            cur += chunk
    if cur:
        segments.append(cur)
    return segments or [text]


def split_text_by_punctuation(text, max_chars=40):
    # low-VRAM mode: break at punct, delimiter attached to preceding segment;
    # over-long punct-free part kept whole to avoid mid-word splits
    segments, cur = [], ""
    for part in _PUNCT_SPLIT.split(text):
        if not part:
            continue
        if len(cur) + len(part) > max_chars and cur:
            segments.append(cur)
            cur = part
        else:
            cur += part
    if cur:
        segments.append(cur)
    return segments


