import json
from importlib import resources

import numpy as np
import pytest

from ai2apps.model_worker.haru_mlx.prompt import (
    CARD_FIELDS,
    build_prompt,
    card_templates,
    prompt_length,
    reference_frames,
    reference_ids,
    render_card,
    system_prompt_ids,
)


def test_render_card_orders_fields_and_skips_empty_ones():
    template = card_templates()["templates"]["en"]
    card = {"name": "Haru", "persona": "A nurse.", "gender": "female", "backchannel": "", "situation": "  "}
    lines = render_card(card, template).split("\n")
    assert lines[0] == template["lead"]
    assert lines[1:] == [
        template["headers"]["persona"], "A nurse.",
        template["headers"]["name"], "Haru",
        template["headers"]["gender"], template["gender"]["female"],
    ]


def test_render_card_ignores_unknown_options():
    template = card_templates()["templates"]["ja"]
    assert render_card({"gender": "other", "backchannel": "sometimes"}, template) == template["lead"]


def test_every_language_has_a_template_and_example_cards():
    templates = card_templates()
    assets = resources.files("ai2apps.model_worker.haru_mlx") / "assets"
    for entry in templates["languages"]:
        code = entry["code"]
        template = templates["templates"][code]
        assert set(template["headers"]) == set(CARD_FIELDS)
        cards = json.loads((assets / "cards" / f"{code}.json").read_text(encoding="utf-8"))
        assert cards, code
        for card in cards.values():
            assert card["persona"].strip()
            assert set(card) <= set(CARD_FIELDS)
            assert len(render_card(card, template)) <= 4000


def test_reference_layout():
    assert reference_ids(0, 7, 9) == []
    assert reference_ids(3, 7, 9) == [7, 7, 9]
    assert reference_frames(3200, 3200) == 1
    assert reference_frames(3201, 3200) == 2


class Encoding:
    def __init__(self, ids):
        self.ids = ids


class CharTokenizer:
    def encode(self, text, add_special_tokens=False):
        self.text = text
        return Encoding([ord(c) for c in text])


def test_system_prompt_is_a_chatml_system_turn():
    tokenizer = CharTokenizer()
    assert system_prompt_ids(tokenizer, "") == []
    ids = system_prompt_ids(tokenizer, "card")
    assert tokenizer.text == "<|im_start|>system\ncard<|im_end|>\n"
    assert len(ids) == len(tokenizer.text)


def test_prompt_length_counts_card_reference_and_opening_turn():
    tokenizer = CharTokenizer()
    assert prompt_length(tokenizer, "", 0, False, 3200) == 1  # a lone PAD
    assert prompt_length(tokenizer, "", 3201, False, 3200) == 2
    assert prompt_length(tokenizer, "", 3201, True, 3200) == 4
    card = len("<|im_start|>system\ncard<|im_end|>\n")
    assert prompt_length(tokenizer, "card", 6400, False, 3200) == card + 2


def test_build_prompt_layout():
    mx = pytest.importorskip("mlx.core")
    from ai2apps.model_worker.haru_mlx.config import HaruConfig

    class Codec:
        """Stands in for the codec: frame ``i`` of a clip encodes to the value ``i``."""

        config = HaruConfig().codec

        def encode(self, audio):
            frames = -(-audio.shape[0] // 3200)
            return mx.broadcast_to(mx.arange(frames).reshape(1, frames, 1), (1, frames, 64)).astype(mx.float32)

        def sample(self, mean, key=None):
            return mean

    config = HaruConfig()
    reference = np.ones(3 * 3200 + 5, dtype=np.float32)
    reference[3200:6400] = 0.01  # frame 1 is the quietest: the room tone
    prompt = build_prompt(config, Codec(), CharTokenizer(), "card", reference, speak_first=True)
    card = len("<|im_start|>system\ncard<|im_end|>\n")
    assert prompt.length == card + 4 + 2
    tokens = prompt.tokens.tolist()
    assert tokens[card:] == [config.pad_token_id] * 3 + [config.eop_token_id, config.pad_token_id, config.eop_token_id]
    assert prompt.model_mask.tolist() == [False] * card + [True] * 6
    assert prompt.user_mask.tolist() == [False] * (card + 4) + [True] * 2
    assert prompt.model_latents[:, 0].tolist() == [0.0] * card + [0.0, 1.0, 2.0, 3.0, 1.0, 1.0]
    assert prompt.user_latents[:, 0].tolist() == [0.0] * (card + 4) + [15.0, 15.0]  # last frame of 16 of silence
