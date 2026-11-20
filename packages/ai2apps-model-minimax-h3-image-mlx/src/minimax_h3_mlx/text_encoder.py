"""MiniMax-H3's Qwen3-VL-32B conditioner, in MLX.

H3 does not use Qwen3-VL as a language model. It reads the **unnormalized** hidden state after the
50th of its 64 decoder layers (``hidden_states[50]``, where ``hidden_states[0]`` is the embedding
output) and feeds that straight into the DiT's ``condition_proj``. The language-model head, the
final norm and the last 14 decoder layers are never evaluated.

That is worth exploiting: the port loads **only the 50 layers it reads**, skipping ``lm_head``
(151936 x 5120) and layers 50-63 entirely. For a text-only request the vision tower is skipped too.

The transformer stack itself is mlx-vlm's ``qwen3_vl`` implementation — it already has the
interleaved M-RoPE, the ``mrope_section`` split and the deepstack visual merge — so this module only
supplies H3's request presentation, the truncated forward, and a loader that reads a subset.

**Request presentation** (from the reference; no chat template and no special tokens anywhere):
each keyframe contributes a ``"<Picture i>: "`` label followed by a vision block
(``<|vision_start|>``, one ``<|image_pad|>`` per merged patch, ``<|vision_end|>``), then the prompt
verbatim. The rows of a vision block are tagged **video**, not text — that tag is what the DiT's
AdaLN modulation keys off.
"""

from __future__ import annotations

import glob
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import mlx.core as mx
import mlx.nn as nn
import numpy as np

from .config import TAG_TEXT, TAG_VIDEO
from .packing import TEXT_ENCODER_LAYER


VisionFeatures = tuple[mx.array, list[mx.array]]


@dataclass(frozen=True)
class ReferencePresentation:
    """One prepared Ref2VA item in semantic request order.

    Image references contain one PIL image. Video references contain frames
    already sampled at 2 fps for Qwen's presentation. Audio-only references
    have no frames and set ``has_audio``.
    """

    kind: str
    frames: tuple[object, ...] = ()
    has_audio: bool = False

    def __post_init__(self) -> None:
        if self.kind not in {"image", "video", "audio"}:
            raise ValueError(f"Unsupported Ref2VA reference kind: {self.kind!r}.")
        if self.kind == "image" and len(self.frames) != 1:
            raise ValueError("An image reference must contain exactly one frame.")
        if self.kind == "video" and not self.frames:
            raise ValueError("A video reference must contain sampled frames.")
        if self.kind == "audio" and (self.frames or not self.has_audio):
            raise ValueError("An audio reference must contain audio and no frames.")
        if self.kind == "image" and self.has_audio:
            raise ValueError("An image reference cannot carry audio.")


class MiniMaxH3TextEncoder:
    """Qwen3-VL-32B truncated to the layers MiniMax-H3 actually conditions on."""

    def __init__(
        self,
        model_dir: str | Path,
        num_layers: int = TEXT_ENCODER_LAYER,
        dtype: mx.Dtype = mx.bfloat16,
        load_vision: bool = True,
        verbose: bool = False,
    ):
        from mlx_vlm.models.qwen3_vl.config import ModelConfig, TextConfig, VisionConfig
        from mlx_vlm.models.qwen3_vl.language import Qwen3VLModel
        from mlx_vlm.models.qwen3_vl.vision import VisionModel

        model_dir = Path(model_dir)
        with open(model_dir / "config.json") as fh:
            raw = json.load(fh)

        self._flat_checkpoint = "text_encoder" in raw and "text_config" not in raw
        if self._flat_checkpoint:
            raw = self._flat_model_config(raw)

        full_layers = raw["text_config"]["num_hidden_layers"]
        if full_layers < num_layers:
            raise ValueError(
                f"MiniMax-H3 conditions on hidden_states[{num_layers}] of its Qwen3-VL conditioner, "
                f"which needs at least {num_layers} decoder layers, but the checkpoint has "
                f"{full_layers}. The last hidden state of a stack truncated to exactly {num_layers} "
                "layers is post-norm and is not the conditioning MiniMax-H3 expects."
            )

        self.num_layers = num_layers
        self.full_layers = full_layers
        self.dtype = dtype

        text_raw = dict(raw["text_config"])
        text_raw["num_hidden_layers"] = num_layers  # build only what we evaluate
        self.text_config = TextConfig.from_dict(text_raw)
        self.vision_config = VisionConfig.from_dict(raw["vision_config"])
        self.model_config = ModelConfig.from_dict(
            {
                **raw,
                "text_config": text_raw,
                "vision_config": raw["vision_config"],
                "model_type": raw.get("model_type", "qwen3_vl"),
            }
        )
        self.model_config.text_config = self.text_config
        self.model_config.vision_config = self.vision_config

        self.language = Qwen3VLModel(self.text_config)
        self.vision = VisionModel(self.vision_config) if load_vision else None
        self._load_weights(model_dir, dtype, verbose)

        self.image_token_id = raw["image_token_id"]
        self.vision_start_token_id = raw["vision_start_token_id"]
        self.vision_end_token_id = raw["vision_end_token_id"]
        self.merge_size = self.vision_config.spatial_merge_size

        self._tokenizer = None
        self._processor = None
        self._model_dir = model_dir

    @staticmethod
    def _flat_model_config(raw: dict) -> dict:
        """Expand MLX-Serve's compact conditioner config into mlx-vlm's Qwen3-VL config."""
        text = raw["text_encoder"]
        return {
            "model_type": "qwen3_vl",
            "image_token_id": 151655,
            "vision_start_token_id": 151652,
            "vision_end_token_id": 151653,
            "text_config": {
                "model_type": "qwen3_vl_text", "vocab_size": 151936,
                "hidden_size": text["hidden"], "intermediate_size": text["intermediate"],
                "num_hidden_layers": text["layers"], "num_attention_heads": text["heads"],
                "num_key_value_heads": text["kv_heads"], "head_dim": text["head_dim"],
                "hidden_act": "silu", "rms_norm_eps": 1e-6,
                "max_position_embeddings": 262144, "rope_theta": text["theta"],
                "rope_scaling": {"type": "default", "mrope_section": [24, 20, 20],
                                 "mrope_interleaved": True},
            },
            "vision_config": {
                "model_type": "qwen3_vl", "depth": 27, "hidden_size": 1152,
                "intermediate_size": 4304, "num_heads": 16, "out_hidden_size": 5120,
                "in_channels": 3, "patch_size": 16, "spatial_merge_size": 2,
                "temporal_patch_size": 2, "num_position_embeddings": 2304,
                "deepstack_visual_indexes": [8, 16, 24],
            },
        }

    # -- loading ---------------------------------------------------------------------------

    def _wanted(self, key: str) -> str | None:
        """Map a checkpoint key onto this module's parameter path, or ``None`` to skip it."""
        if key.startswith("lm_head"):
            return None  # never evaluated
        if key.startswith("model.language_model."):
            rest = key[len("model.language_model.") :]
            if rest.startswith("layers."):
                index = int(rest.split(".")[1])
                if index >= self.num_layers:
                    return None  # beyond the conditioning layer
            # `norm` is loaded (it is 5120 floats) to keep the module tree complete, but it is never
            # applied: H3 reads the hidden state *before* the final norm.
            return ("language", rest)
        if key.startswith("model.visual."):
            if self.vision is None:
                return None
            return ("vision", key[len("model.visual.") :])
        if self._flat_checkpoint and key.startswith("model."):
            rest = key[len("model.") :]
            if rest.startswith("layers.") and int(rest.split(".")[1]) >= self.num_layers:
                return None
            return ("language", rest)
        if self._flat_checkpoint and key.startswith("visual."):
            if self.vision is None:
                return None
            return ("vision", key[len("visual.") :])
        return None

    def _apply_flat_quantization(self, raw: dict) -> None:
        recipe = raw["quantization"]
        bits, group_size = int(recipe["bits"]), int(recipe["group_size"])

        def language_predicate(path, module):
            selected = (".self_attn." in path or ".mlp." in path)
            compatible = isinstance(module, nn.Linear) and module.weight.shape[-1] % group_size == 0
            return {"bits": bits, "group_size": group_size} if selected and compatible else False

        def vision_predicate(path, module):
            selected = (
                (path.startswith("blocks.") and (".attn." in path or path.endswith(".mlp.linear_fc1")))
                or path.startswith("merger.") or path.startswith("deepstack_merger_list.")
            )
            compatible = isinstance(module, nn.Linear) and module.weight.shape[-1] % group_size == 0
            return {"bits": bits, "group_size": group_size} if selected and compatible else False

        nn.quantize(self.language, bits=bits, group_size=group_size, class_predicate=language_predicate)
        if self.vision is not None:
            nn.quantize(self.vision, bits=bits, group_size=group_size, class_predicate=vision_predicate)

    def _load_weights(self, model_dir: Path, dtype: mx.Dtype, verbose: bool) -> None:
        from mlx.utils import tree_flatten, tree_unflatten

        if self._flat_checkpoint:
            with open(model_dir / "config.json") as fh:
                self._apply_flat_quantization(json.load(fh))
            shards = [str(model_dir / "text_encoder.safetensors")]
        else:
            shards = sorted(glob.glob(str(model_dir / "*.safetensors")))
        if not shards:
            raise FileNotFoundError(f"No safetensors in {model_dir}.")

        buckets: dict[str, dict[str, mx.array]] = {"language": {}, "vision": {}}
        expected = {
            "language": {k for k, _ in tree_flatten(self.language.parameters())},
            "vision": set() if self.vision is None else {k for k, _ in tree_flatten(self.vision.parameters())},
        }
        skipped = 0
        for shard in shards:
            for key, tensor in mx.load(shard).items():
                target = self._wanted(key)
                if target is None:
                    skipped += 1
                    continue
                bucket, path = target
                if path not in expected[bucket]:
                    skipped += 1
                    continue
                if bucket == "vision" and path == "patch_embed.proj.weight" and tensor.ndim == 5:
                    # Hugging Face stores Conv3d as Torch [O,C,T,H,W]; MLX Conv3d uses
                    # [O,T,H,W,C]. Text-only FL2VA never exercises this tensor, which is
                    # why the mismatch only surfaced once the Ref2VA vision path ran.
                    tensor = tensor.transpose(0, 2, 3, 4, 1)
                # Packed uint32 quantized weights must never be cast. Scales/biases are already in
                # the precision selected by the checkpoint producer.
                buckets[bucket][path] = tensor if self._flat_checkpoint else tensor.astype(dtype)
            if verbose:
                print(f"  {Path(shard).name}: kept {len(buckets['language']) + len(buckets['vision'])}")

        for bucket, module in (("language", self.language), ("vision", self.vision)):
            if module is None:
                continue
            missing = sorted(expected[bucket] - buckets[bucket].keys())
            if self._flat_checkpoint and bucket == "language":
                # MLX-Serve intentionally omits the final RMSNorm: H3 consumes the unnormalized
                # state after layer 50, so this parameter is never read by `_hidden_states`.
                missing = [key for key in missing if key != "norm.weight"]
            if missing:
                raise KeyError(
                    f"{bucket} encoder missing {len(missing)} tensors, e.g. {missing[:4]}."
                )
            module.update(tree_unflatten(list(buckets[bucket].items())))
        mx.eval(self.language.parameters())
        if self.vision is not None:
            mx.eval(self.vision.parameters())
        self.skipped_tensors = skipped

    # -- tokenizer / processor -------------------------------------------------------------

    @property
    def tokenizer(self):
        if self._tokenizer is None:
            from transformers import AutoTokenizer

            root = self._model_dir if (self._model_dir / "tokenizer.json").exists() else self._model_dir.parent
            path = root / "tokenizer" if (root / "tokenizer").exists() else self._model_dir
            self._tokenizer = AutoTokenizer.from_pretrained(str(path))
        return self._tokenizer

    @property
    def processor(self):
        if self._processor is None:
            # Use the PIL backend explicitly. The Runtime intentionally has no torch/torchvision,
            # while current transformers resolves the historical `...Fast` name to its torchvision
            # backend. These are the exact 390-byte processor-sidecar values pinned upstream and
            # also cover flat Q4/Q8 repositories, which omit that sidecar.
            from transformers.models.qwen2_vl.image_processing_pil_qwen2_vl import (
                Qwen2VLImageProcessorPil,
            )
            image_processor = Qwen2VLImageProcessorPil(
                size={"longest_edge": 16777216, "shortest_edge": 65536},
                patch_size=16, temporal_patch_size=2, merge_size=2,
                image_mean=[0.5, 0.5, 0.5], image_std=[0.5, 0.5, 0.5],
            )
            self._processor = SimpleNamespace(image_processor=image_processor)
        return self._processor

    # -- request presentation --------------------------------------------------------------

    def build_request(
        self, prompt: str, images: list | None = None, *, picture_label: str = "<Picture {}>: ",
    ):
        """Build H3's token sequence and its per-row modality tags.

        Returns ``(input_ids, token_tags, vision_inputs)``; ``vision_inputs`` is ``None`` for a
        text-only request, otherwise the processor's ``pixel_values`` / ``image_grid_thw``.
        """
        if not isinstance(prompt, str):
            raise ValueError(f"`prompt` must be a single string, got {type(prompt).__name__}.")

        token_ids: list[int] = []
        token_tags: list[int] = []
        vision_inputs = None

        if images:
            vision = self.processor.image_processor(images=images, return_tensors="np")
            pixel_values = np.asarray(vision["pixel_values"])
            grid_thw = np.asarray(vision["image_grid_thw"])
            merge = self.processor.image_processor.merge_size**2
            start = self.tokenizer.convert_tokens_to_ids("<|vision_start|>")
            pad = self.tokenizer.convert_tokens_to_ids("<|image_pad|>")
            end = self.tokenizer.convert_tokens_to_ids("<|vision_end|>")

            for index in range(len(images)):
                num_image_tokens = int(grid_thw[index].prod()) // merge
                label_ids = self.tokenizer(picture_label.format(index + 1), add_special_tokens=False)["input_ids"]
                vision_ids = [start] + [pad] * num_image_tokens + [end]
                token_ids += label_ids + vision_ids
                # The whole vision block is tagged *video*; only the label stays text.
                token_tags += [TAG_TEXT] * len(label_ids) + [TAG_VIDEO] * len(vision_ids)
            vision_inputs = (pixel_values, grid_thw)

        prompt_ids = self.tokenizer(prompt, add_special_tokens=False)["input_ids"]
        token_ids += prompt_ids
        token_tags += [TAG_TEXT] * len(prompt_ids)

        return (
            mx.array(np.array([token_ids], dtype=np.int32)),
            np.array(token_tags, dtype=np.int64),
            vision_inputs,
        )

    def _process_video_pair(self, frames: tuple[object, object]) -> tuple[np.ndarray, np.ndarray]:
        """Pack two 2-fps presentation frames into one Qwen temporal vision block."""
        from PIL import Image

        arrays = []
        width, height = frames[0].size
        factor = int(self.vision_config.patch_size * self.merge_size)
        h_bar = round(height / factor) * factor
        w_bar = round(width / factor) * factor
        min_pixels, max_pixels = 3136, 12845056
        if h_bar * w_bar > max_pixels:
            beta = ((height * width) / max_pixels) ** 0.5
            h_bar = max(factor, int(height / beta / factor) * factor)
            w_bar = max(factor, int(width / beta / factor) * factor)
        elif h_bar * w_bar < min_pixels:
            beta = (min_pixels / (height * width)) ** 0.5
            h_bar = int(np.ceil(height * beta / factor)) * factor
            w_bar = int(np.ceil(width * beta / factor)) * factor
        for frame in frames:
            if frame.size != (width, height):
                raise ValueError("All frames of a Ref2VA video must share one canvas.")
            image = frame.convert("RGB")
            if image.size != (w_bar, h_bar):
                image = image.resize((w_bar, h_bar), Image.Resampling.BILINEAR)
            arrays.append(np.asarray(image, dtype=np.float32) / 255.0)
        pixels = np.stack(arrays).transpose(0, 3, 1, 2)
        pixels = (pixels - 0.5) / 0.5
        patch = int(self.vision_config.patch_size)
        temporal = int(self.vision_config.temporal_patch_size)
        merge = int(self.merge_size)
        grid_h, grid_w = h_bar // patch, w_bar // patch
        packed = pixels.reshape(
            1, temporal, 3, grid_h // merge, merge, patch,
            grid_w // merge, merge, patch,
        ).transpose(0, 3, 6, 4, 7, 2, 1, 5, 8)
        packed = packed.reshape(grid_h * grid_w, 3 * temporal * patch * patch)
        return packed.astype(np.float32), np.array([[1, grid_h, grid_w]], dtype=np.int32)

    def build_reference_request(
        self, prompt: str, references: tuple[ReferencePresentation, ...]
    ):
        """Build the exact ordered image/video/audio Ref2VA presentation."""
        if not references:
            raise ValueError("Ref2VA requires at least one reference.")
        if not any(reference.kind != "audio" for reference in references):
            raise ValueError("Ref2VA audio requires an image or video reference.")

        token_ids: list[int] = []
        token_tags: list[int] = []
        pixel_chunks: list[np.ndarray] = []
        grid_chunks: list[np.ndarray] = []
        counts = {"image": 0, "video": 0, "audio": 0}
        start = self.tokenizer.convert_tokens_to_ids("<|vision_start|>")
        pad = self.tokenizer.convert_tokens_to_ids("<|image_pad|>")
        end = self.tokenizer.convert_tokens_to_ids("<|vision_end|>")

        def add_text(value: str) -> None:
            ids = self.tokenizer(value, add_special_tokens=False)["input_ids"]
            token_ids.extend(ids)
            token_tags.extend([TAG_TEXT] * len(ids))

        def add_vision(pixels: np.ndarray, grid: np.ndarray) -> None:
            tokens = int(grid[0].prod()) // (self.merge_size**2)
            ids = [start] + [pad] * tokens + [end]
            token_ids.extend(ids)
            token_tags.extend([TAG_VIDEO] * len(ids))
            pixel_chunks.append(pixels)
            grid_chunks.append(grid)

        for reference in references:
            if reference.has_audio:
                counts["audio"] += 1
                add_text(f"<Audio {counts['audio']}>: ")
            if reference.kind == "audio":
                continue
            if reference.kind == "image":
                counts["image"] += 1
                add_text(f"<Picture {counts['image']}>: ")
                vision = self.processor.image_processor(
                    images=[reference.frames[0]], return_tensors="np"
                )
                add_vision(
                    np.asarray(vision["pixel_values"], dtype=np.float32),
                    np.asarray(vision["image_grid_thw"], dtype=np.int32),
                )
                continue

            counts["video"] += 1
            add_text(f"<Video {counts['video']}>: ")
            frames = list(reference.frames)
            timestamps = [index / 2.0 for index in range(len(frames))]
            if len(frames) % 2:
                frames.append(frames[-1])
                timestamps.append(timestamps[-1])
            for index in range(0, len(frames), 2):
                add_text(f"<{(timestamps[index] + timestamps[index + 1]) / 2.0:.1f} seconds>")
                pixels, grid = self._process_video_pair((frames[index], frames[index + 1]))
                add_vision(pixels, grid)

        add_text(prompt)
        vision_inputs = (
            np.concatenate(pixel_chunks, axis=0),
            np.concatenate(grid_chunks, axis=0),
        )
        return (
            mx.array(np.array([token_ids], dtype=np.int32)),
            np.array(token_tags, dtype=np.int64),
            vision_inputs,
        )

    # -- forward ---------------------------------------------------------------------------

    def _hidden_states(
        self,
        input_ids: mx.array,
        position_ids: mx.array,
        inputs_embeds: mx.array | None = None,
        visual_pos_masks: mx.array | None = None,
        deepstack_visual_embeds: list | None = None,
    ) -> mx.array:
        """Run the truncated stack and return the hidden state **before** the final norm."""
        from mlx_vlm.models.base import create_attention_mask

        model = self.language
        h = model.embed_tokens(input_ids) if inputs_embeds is None else inputs_embeds
        mask = create_attention_mask(h, None)

        position_embeddings = None
        if position_ids is not None and not model.layers[0].self_attn.rotary_emb.fused_apply:
            position_embeddings = model.layers[0].self_attn.rotary_emb(h, position_ids)

        for layer_idx, layer in enumerate(model.layers):
            h = layer(h, mask, None, position_ids, position_embeddings)
            if deepstack_visual_embeds is not None and layer_idx < len(deepstack_visual_embeds):
                h = model._deepstack_process(h, visual_pos_masks, deepstack_visual_embeds[layer_idx])
        # No `model.norm(h)`: H3 conditions on the unnormalized state.
        return h

    def _encode_request(
        self, built_request, *,
        vision_features: VisionFeatures | None = None,
        on_vision: Callable[[VisionFeatures], None] | None = None,
    ) -> tuple[mx.array, np.ndarray]:
        """Evaluate one already-built text/vision request."""
        from mlx_vlm.models.qwen3_vl.language import LanguageModel

        input_ids, token_tags, vision_inputs = built_request

        inputs_embeds = None
        visual_pos_masks = None
        deepstack_embeds = None
        grid_thw = None

        if vision_inputs is not None:
            pixel_values, grid_np = vision_inputs
            grid_thw = mx.array(grid_np.astype(np.int32))
            if vision_features is None:
                if self.vision is None:
                    raise ValueError("Image input needs a vision tower or its precomputed features.")
                hidden, deepstack_embeds = self.vision(
                    mx.array(pixel_values).astype(self.dtype), grid_thw, output_hidden_states=True
                )
                if on_vision is not None:
                    mx.eval(hidden, deepstack_embeds)
                    on_vision((hidden, deepstack_embeds))
            else:
                hidden, deepstack_embeds = vision_features
            inputs_embeds = self.language.embed_tokens(input_ids)
            image_mask = input_ids == self.image_token_id
            from mlx_vlm.models.qwen3_vl.qwen3_vl import masked_scatter
            inputs_embeds = masked_scatter(
                inputs_embeds,
                mx.broadcast_to(image_mask[..., None], inputs_embeds.shape),
                hidden.astype(inputs_embeds.dtype),
            )
            visual_pos_masks = image_mask

        # Qwen3-VL's 3D M-RoPE index, derived from the vision-start/pad token ids.
        position_ids, _ = LanguageModel.get_rope_index(
            self, input_ids, image_grid_thw=grid_thw, video_grid_thw=None, attention_mask=None
        )

        hidden_states = self._hidden_states(
            input_ids,
            position_ids,
            inputs_embeds=inputs_embeds,
            visual_pos_masks=visual_pos_masks,
            deepstack_visual_embeds=deepstack_embeds,
        )
        mx.eval(hidden_states)
        return hidden_states, token_tags

    def encode(
        self, prompt: str, images: list | None = None, *, picture_label: str = "<Picture {}>: ",
        vision_features: VisionFeatures | None = None,
        on_vision: Callable[[VisionFeatures], None] | None = None,
    ) -> tuple[mx.array, np.ndarray]:
        """Encode a text/FL2VA request."""
        return self._encode_request(
            self.build_request(prompt, images, picture_label=picture_label),
            vision_features=vision_features, on_vision=on_vision,
        )

    def encode_references(
        self, prompt: str, references: tuple[ReferencePresentation, ...]
    ) -> tuple[mx.array, np.ndarray]:
        """Encode an ordered Ref2VA multimodal request."""
        return self._encode_request(self.build_reference_request(prompt, references))

    # `LanguageModel.get_rope_index` reads `self.config`; expose the same attribute.
    @property
    def config(self):
        return self.model_config
