"""Text normalization (TN) for IndexTTS-2.5 — zero transformers/modelscope.
Port of ``indextts/utils/front.py`` ``TextNormalizer`` (digits, dates, percents,
pinyin tones, tech terms, names → spoken form for the tiktoken tokenizer).
Uses ``tn`` directly (wetext is a thin wrapper; we unify on tn), TN grammar
cache in ``{tmp}/windextts_tn_cache``, lazy-load on first ``normalize()``.
"""
from __future__ import annotations

import os
import re
import tempfile
import traceback
from functools import lru_cache

class TextNormalizer:
    PINYIN_TONE_PATTERN = r"(?<![a-z])((?:[bpmfdtnlgkhjqxzcsryw]|[zcs]h)?(?:[aeiouüv]|[ae]i|u[aio]|ao|ou|i[aue]|[uüv]e|[uvü]ang?|uai|[aeiuv]n|[aeio]ng|ia[no]|i[ao]ng)|ng|er)([1-5])"
    # 拼音+数字声调(1-5,5=轻声): xuan4,jve2,ying1… 不匹配 beta1,voice2
    NAME_PATTERN = r"[\u4e00-\u9fff]+(?:[-·—][\u4e00-\u9fff]+){1,2}"
    # 人名: 中文·中文[-中文]，如 克里斯托弗·诺兰
    TECH_TERM_PATTERN = r"[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+"
    # 技术术语(字母开头,防误匹配电话 135-4567-8900): GPT-5-nano, F5-TTS
    ENGLISH_CONTRACTION_PATTERN = r"(what|where|who|which|how|t?here|it|s?he|that|this)'s"
    G2P_PRONUNCIATION_ANNOTATION_PATTERN = re.compile(r"<([^|>\n]+)\|([^>\n]+)>")

    def __init__(self, enable_glossary: bool = False):
        self.zh_normalizer = None
        self.en_normalizer = None
        self.char_rep_map = {
            "：": ",", "；": ",", ";": ",", "，": ",", "。": ".", "！": "!", "？": "?",
            "\n": " ", "·": "-", "、": ",", "...": "…", ",,,": "…", "，，，": "…",
            "……": "…", "“": "'", "”": "'", '"': "'", "‘": "'", "’": "'",
            "（": "'", "）": "'", "(": "'", ")": "'", "《": "'", "》": "'",
            "【": "'", "】": "'", "[": "'", "]": "'", "—": "-", "～": "-", "~": "-",
            "「": "'", "」": "'", ":": ",",
        }
        self.zh_char_rep_map = {"$": ".", **self.char_rep_map}
        self.clean_pattern = re.compile("|".join(re.escape(p) for p in self.char_rep_map.keys()))
        self.enable_glossary = enable_glossary
        self.term_glossary = dict()

    def match_email(self, email: str) -> bool:
        return re.match(r"^[a-zA-Z0-9]+@[a-zA-Z0-9]+\.[a-zA-Z]+$", email) is not None

    def use_chinese(self, s: str) -> bool:
        # 含中文/无字母/邮箱/拼音声调 → 走中文 TN
        return (bool(re.search(r"[\u4e00-\u9fff]", s)) or not re.search(r"[a-zA-Z]", s)
                or self.match_email(s)
                or bool(re.search(TextNormalizer.PINYIN_TONE_PATTERN, s, re.IGNORECASE)))

    def load(self) -> None:
        """Lazily build zh/en TN normalizers (NeMo ``tn`` grammar)."""
        if self.zh_normalizer is not None and self.en_normalizer is not None:
            return
        try:
            from tn.chinese.normalizer import Normalizer as NormalizerZh
            from tn.english.normalizer import Normalizer as NormalizerEn
        except ImportError:
            # macOS: pynini has no arm64 wheels -> wetext runtime (same API)
            from wetext import Normalizer as _W

            class NormalizerZh:
                def __init__(self, cache_dir=None, remove_interjections=False, remove_erhua=False, overwrite_cache=False):
                    self._n = _W(lang="zh", operator="tn", remove_interjections=remove_interjections,
                                 remove_erhua=remove_erhua)

                def normalize(self, text):
                    return self._n.normalize(text)

            class NormalizerEn:
                def __init__(self, overwrite_cache=False):
                    self._n = _W(lang="en", operator="tn")

                def normalize(self, text):
                    return self._n.normalize(text)

        cache_dir = os.path.join(tempfile.gettempdir(), "windextts_tn_cache")
        os.makedirs(cache_dir, exist_ok=True)
        self.zh_normalizer = NormalizerZh(cache_dir=cache_dir, remove_interjections=False,
                                          remove_erhua=False, overwrite_cache=False)
        self.en_normalizer = NormalizerEn(overwrite_cache=False)

    # ---------- G2P 发音标注 <字|读音> 保护 ----------

    def _protect_pronunciation_annotations(self, text: str):
        # 在 normalize 前把 <字|读音> 换成纯字母占位符，防 normalizer 展开
        # 标注内数字/符号（如 XING2 -> XING二）
        placeholders = {}

        def _idx_to_alpha(n):  # bijective base-26: 0->a, 25->z, 26->aa
            return "" if n < 0 else _idx_to_alpha(n // 26 - 1) + chr(ord("a") + n % 26)

        def _replacer(m):
            key = f"PRONPLACEHOLDER{_idx_to_alpha(len(placeholders))}PRONPLACEHOLDER"
            placeholders[key] = m.group(0)
            return key

        return self.G2P_PRONUNCIATION_ANNOTATION_PATTERN.sub(_replacer, text), placeholders

    @staticmethod
    def _restore_pronunciation_annotations(text: str, placeholders: dict) -> str:
        for key, val in placeholders.items():
            text = text.replace(key, val)
        return text

    def normalize(self, text: str) -> str:
        if self.zh_normalizer is None or self.en_normalizer is None:
            self.load()
        if not self.zh_normalizer or not self.en_normalizer:
            print("Error, text normalizer is not initialized !!!")
            return ""
        text, _pron_placeholders = self._protect_pronunciation_annotations(text)
        if self.use_chinese(text):
            text = re.sub(TextNormalizer.ENGLISH_CONTRACTION_PATTERN, r"\1 is", text, flags=re.IGNORECASE)
            if self.enable_glossary:
                text = self.apply_glossary_terms(text, lang="zh")
            # 保护技术术语/拼音声调/人名 → zh normalizer → 恢复
            rt, tech = self.save_tech_terms(text.rstrip())
            rt, pinyin = self.save_pinyin_tones(rt)
            rt, names = self.save_names(rt)
            try:
                result = self.zh_normalizer.normalize(rt)
            except Exception:
                result = ""
                print(traceback.format_exc())
            result = self.restore_names(result, names)
            result = self.restore_pinyin_tones(result, pinyin)
            result = self.restore_tech_terms(result, tech)
            pattern = re.compile("|".join(re.escape(p) for p in self.zh_char_rep_map.keys()))
            result = pattern.sub(lambda x: self.zh_char_rep_map[x.group()], result)
        else:
            try:
                text = re.sub(TextNormalizer.ENGLISH_CONTRACTION_PATTERN, r"\1 is", text, flags=re.IGNORECASE)
                if self.enable_glossary:
                    text = self.apply_glossary_terms(text, lang="en")
                rt, tech = self.save_tech_terms(text)
                result = self.en_normalizer.normalize(rt)
                result = self.restore_tech_terms(result, tech)
            except Exception:
                result = text
                print(traceback.format_exc())
            pattern = re.compile("|".join(re.escape(p) for p in self.char_rep_map.keys()))
            result = pattern.sub(lambda x: self.char_rep_map[x.group()], result)
        return self._restore_pronunciation_annotations(result, _pron_placeholders)

    def correct_pinyin(self, pinyin: str) -> str:
        # jqx 后韵母 u/ü → v：ju→JV, que→QVE, xün→XVN
        if pinyin[0] not in "jqxJQX":
            return pinyin
        return re.sub(r"([jqx])[uü](n|e|an)*(\d)", r"\g<1>v\g<2>\g<3>", pinyin,
                      flags=re.IGNORECASE).upper()

    # ---------- 人名/拼音 占位符保护（通用 save/restore 对） ----------

    def _save_ph(self, text, pattern, prefix):
        # 匹配项 → <prefix_a>, <prefix_b>…（如 克里斯托弗·诺兰 → <n_a>）
        lst = re.findall(re.compile(pattern, re.IGNORECASE), text)
        if not lst:
            return text, None
        lst = list(set("".join(x) for x in lst))
        for i, s in enumerate(lst):
            text = text.replace(s, f"<{prefix}_{chr(ord('a') + i)}>")
        return text, lst

    def _restore_ph(self, text, lst, prefix, fix=None):
        if not lst:
            return text
        for i, s in enumerate(lst):
            text = text.replace(f"<{prefix}_{chr(ord('a') + i)}>", fix(s) if fix else s)
        return text

    def save_names(self, text): return self._save_ph(text, TextNormalizer.NAME_PATTERN, "n")

    def restore_names(self, text, lst): return self._restore_ph(text, lst, "n")

    def save_pinyin_tones(self, text): return self._save_ph(text, TextNormalizer.PINYIN_TONE_PATTERN, "pinyin")

    def restore_pinyin_tones(self, text, lst): return self._restore_ph(text, lst, "pinyin", self.correct_pinyin)

    def save_tech_terms(self, original_text):
        # 术语连字符 → <H> 防中文 normalizer 解析为减号：GPT-5-nano → GPT<H>5<H>nano
        tech_list = re.compile(TextNormalizer.TECH_TERM_PATTERN).findall(original_text)
        if not tech_list:
            return original_text, None
        # 去重 + 按长度降序（短匹配先替换会破坏长术语）
        tech_list = sorted(set(tech_list), key=len, reverse=True)
        for term in tech_list:
            original_text = original_text.replace(term, term.replace("-", "<H>"))
        return original_text, tech_list

    def restore_tech_terms(self, normalized_text, original_tech_list):
        # <H> → -，同时清理占位符周围 normalizer 添加的空格
        if not original_tech_list or len(original_tech_list) == 0:
            return normalized_text
        return re.sub(r"\s*<H>\s*", "-", normalized_text)

    # ---------- 术语词汇表 ----------

    def apply_glossary_terms(self, text: str, lang: str = "zh") -> str:
        if not self.term_glossary:
            return text
        # 按长度降序，避免短术语先匹配
        sorted_terms = sorted(self.term_glossary.keys(), key=len, reverse=True)

        @lru_cache(maxsize=42)
        def get_term_pattern(term: str):
            return re.compile(re.escape(term), re.IGNORECASE)

        for term in sorted_terms:
            term_value = self.term_glossary[term]
            replacement = term_value.get(lang, term_value.get(lang, term)) if isinstance(term_value, dict) else term_value
            text = get_term_pattern(term).sub(replacement, text)
        return text

    def load_glossary(self, glossary_dict: dict) -> None:
        if glossary_dict and isinstance(glossary_dict, dict):
            self.term_glossary.update(glossary_dict)

    def load_glossary_from_yaml(self, glossary_path: str) -> bool:
        # YAML 格式: M.2: {en: M dot two, zh: M 二} / NVMe: N-V-M-E
        if glossary_path and os.path.exists(glossary_path):
            import yaml
            with open(glossary_path, "r", encoding="utf-8") as f:
                external_glossary = yaml.safe_load(f)
                if external_glossary and isinstance(external_glossary, dict):
                    self.term_glossary = external_glossary
                    return True
        return False

    def save_glossary_to_yaml(self, glossary_path: str) -> None:
        import yaml
        with open(glossary_path, "w", encoding="utf-8") as f:
            yaml.dump(self.term_glossary, f, allow_unicode=True, default_flow_style=False)

