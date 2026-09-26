"""IndexTTS-2.5 multilingual text tokenizer — pure tiktoken, zero whisper/transformers.

v2.5 only calls ``tokenizer.encode('<|{lang}|> ' + text, allowed_special='all')``;
the WhisperTokenizer tokenize/convert machinery is v1-only. BPE ranks from
multilingual_zh_ja_yue_char_del.tiktoken (58836 base) + specials appended in the
exact official order (id = 58836 + index) → encode() is bit-identical to official.
"""
import base64
import os
from functools import lru_cache

import tiktoken

# order matters: special-token id assignment depends on iteration order (copied
# 1:1 from indextts/utils/tokenizer.py)
LANGUAGES = dict(zip(
    "en zh de es ru ko fr ja pt tr pl ca nl ar sv it id hi fi vi he uk el ms cs ro da hu ta no th ur hr bg lt la mi ml cy sk te fa lv bn sr az sl kn et mk br eu is hy ne mn bs kk sq sw gl mr pa si km sn yo so af oc ka be tg sd gu am yi lo uz fo ht ps tk nn mt sa lb my bo tl mg as tt haw ln ha ba jw su yue minnan wuyu dialect zh/en en/zh common".split(),
    "english chinese german spanish russian korean french japanese portuguese turkish polish catalan dutch arabic swedish italian indonesian hindi finnish vietnamese hebrew ukrainian greek malay czech romanian danish hungarian tamil norwegian thai urdu croatian bulgarian lithuanian latin maori malayalam welsh slovak telugu persian latvian bengali serbian azerbaijani slovenian kannada estonian macedonian breton basque icelandic armenian nepali mongolian bosnian kazakh albanian swahili galician marathi punjabi sinhala khmer shona yoruba somali afrikaans occitan georgian belarusian tajik sindhi gujarati amharic yiddish lao uzbek faroese haitian creole pashto turkmen nynorsk maltese sanskrit luxembourgish myanmar tibetan tagalog malagasy assamese tatar hawaiian lingala hausa bashkir javanese sundanese cantonese minnan wuyu dialect zh/en en/zh common".split()))
LANGUAGE_DICT = {lang: index for index, lang in enumerate(LANGUAGES.keys())}

AUDIO_EVENT = {k: k for k in "ASR AED SER Speech /Speech BGM /BGM Laughter /Laughter Applause /Applause".split()}
EMOTION = {k: k for k in "HAPPY SAD ANGRY NEUTRAL".split()}
TTS_Vocal_Token = {k: k for k in "TTS/B TTS/O TTS/Q TTS/A TTS/CO TTS/CL TTS/H".split()} | \
    {f"TTS/SP{i:02d}": f"TTS/SP{i:02d}" for i in range(1, 14)}

# NOTE: default num_languages=99 — first 99 keys of LANGUAGES (through "su");
# yue/minnan/wuyu/dialect/zh-en/en-zh/common are NOT registered as special tokens.
_PAT_STR = r"""'s|'t|'re|'ve|'m|'ll|'d| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+(?!\S)|\s+"""


def lang_to_token(lang: str) -> int:
    # lang_embedding row index (GPT), NOT a token id; unknown -> "common"
    lang = lang.lower()
    return LANGUAGE_DICT[lang if lang in LANGUAGE_DICT else "common"]


def _build_specials(num_languages: int) -> list[str]:
    # exact official order (tokenizer.py:196-209)
    return [
        "<|endoftext|>", "<|startoftranscript|>",
        *[f"<|{l}|>" for l in list(LANGUAGES)[:num_languages]],
        *[f"<|{a}|>" for a in AUDIO_EVENT],
        *[f"<|{e}|>" for e in EMOTION],
        "<|translate|>", "<|transcribe|>", "<|startoflm|>", "<|startofprev|>",
        "<|nospeech|>", "<|notimestamps|>",
        *[f"<|SPECIAL_TOKEN_{i}|>" for i in range(1, 31)],
        *[f"<|{t}|>" for t in TTS_Vocal_Token],
        *[f"<|{i * 0.02:.2f}|>" for i in range(1501)],
    ]


def _load_ranks(vocab_path: str) -> dict[bytes, int]:
    # .tiktoken lines: "<base64 token> <rank>"
    ranks = {}
    with open(vocab_path) as f:
        for line in f:
            if line.strip():
                tok, rank = line.split()
                ranks[base64.b64decode(tok)] = int(rank)
    return ranks


@lru_cache(maxsize=None)
def build_tokenizer(
    name: str = "multilingual_zh_ja_yue_char_del",
    num_languages: int = 99,
    model_dir: str | None = None,
) -> tiktoken.Encoding:
    """tiktoken.Encoding identical to official get_encoding (ranks + specials)."""
    if model_dir is None:
        model_dir = os.environ.get("WINDEXTTS_WEIGHTS_DIR", "/root/IndexTTS-2.5")
    vocab_path = os.path.join(model_dir, f"{name}.tiktoken")
    ranks = _load_ranks(vocab_path)
    n_vocab = len(ranks)
    special_tokens = {t: n_vocab + i for i, t in enumerate(_build_specials(num_languages))}
    return tiktoken.Encoding(
        name=os.path.basename(vocab_path),
        explicit_n_vocab=n_vocab + len(special_tokens),
        pat_str=_PAT_STR,
        mergeable_ranks=ranks,
        special_tokens=special_tokens,
    )


