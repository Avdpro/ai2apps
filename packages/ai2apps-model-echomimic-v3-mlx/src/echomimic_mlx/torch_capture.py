"""Read-only PyTorch hooks for the pinned upstream block-0 reference capture."""

from __future__ import annotations

import importlib
import os
import sys
import types
from collections.abc import Mapping
from importlib.util import find_spec
from typing import Any

BLOCK0_REFERENCE_NAMES = frozenset(
    {
        "transformer.block_00.input",
        "transformer.block_00.timestep_modulation",
        "transformer.block_00.sequence_lengths",
        "transformer.block_00.grid_sizes",
        "transformer.block_00.context",
        "transformer.block_00.audio_context",
        "transformer.block_00.norm1",
        "transformer.block_00.self_attention",
        "transformer.block_00.cross_input",
        "transformer.block_00.text_image_attention",
        "transformer.block_00.audio_attention",
        "transformer.block_00.cross_attention",
        "transformer.block_00.ffn_input",
        "transformer.block_00.ffn",
        "transformer.block_00.output",
    }
)
AUDIO_PROJECTION_REFERENCE_NAMES = frozenset(
    {
        "transformer.audio_projection.first_frame_input",
        "transformer.audio_projection.later_frame_input",
        "transformer.audio_projection.output",
    }
)

_REQUIRED_UPSTREAM_ARGUMENTS = frozenset(
    {
        "--config_path",
        "--model_name",
        "--transformer_path",
        "--wav2vec_model_dir",
        "--image_path",
        "--audio_path",
        "--prompt",
    }
)
_DISALLOWED_UPSTREAM_FLAGS = frozenset(
    {
        "--enable_teacache",
        "--enable_riflex",
        "--fsdp_dit",
        "--use_dynamic_cfg",
        "--use_dynamic_acfg",
        "--use_un_ip_mask",
    }
)


def validate_upstream_capture_arguments(arguments: list[str]) -> None:
    """Reject upstream options that would make the fixed block fixture ambiguous."""

    supplied = {value for value in arguments if value.startswith("--")}
    missing = sorted(_REQUIRED_UPSTREAM_ARGUMENTS - supplied)
    if missing:
        raise ValueError(f"capture requires explicit upstream arguments: {missing}")
    disallowed = sorted(_DISALLOWED_UPSTREAM_FLAGS & supplied)
    if disallowed:
        raise ValueError(f"capture forbids non-reference upstream flags: {disallowed}")
    for option in ("--ulysses_degree", "--ring_degree"):
        if option in arguments:
            index = arguments.index(option)
            if index + 1 >= len(arguments) or arguments[index + 1] != "1":
                raise ValueError(f"capture requires {option} 1")


class BlockCaptureComplete(RuntimeError):
    """Internal control-flow signal used to stop inference after block 0."""


class DenoisingCaptureComplete(RuntimeError):
    """Internal control-flow signal used to stop after the eighth scheduler step."""


class _UnavailableDecord(types.ModuleType):
    def __getattr__(self, name: str) -> object:
        if name.startswith("__"):
            raise AttributeError(name)
        raise RuntimeError(
            f"decord.{name} is unavailable on this platform; the fixed image reference "
            "run must not enter a video-decoding path"
        )


def install_unused_decord_stub() -> bool:
    """Allow the image-only upstream run to import on platforms without decord wheels."""
    if "decord" in sys.modules:
        return False
    if find_spec("decord") is not None:
        return False
    sys.modules.setdefault("decord", _UnavailableDecord("decord"))
    return True


def _cpu_tensor(value: Any) -> Any:
    return value.detach().to(device="cpu", copy=True).contiguous()


class TorchBlock0Capture:
    """Capture the first selected transformer invocation without patching upstream files."""

    def __init__(self, *, transformer_call: int = 0) -> None:
        if transformer_call < 0:
            raise ValueError("transformer_call must be non-negative")
        self.transformer_call = transformer_call
        self.tensors: dict[str, Any] = {}
        self._call_index = -1
        self._active = False
        self._handles: list[Any] = []
        self._module: Any = None
        self._original_attention: Any = None
        self._original_audio_attention: Any = None
        self._cross_active = False
        self._cross_attention_outputs: list[Any] = []
        self._audio_heads: Any = None
        self._modulation_chunks: tuple[Any, ...] | None = None

    def _add(self, name: str, value: Any) -> None:
        if self._active and name not in self.tensors:
            self.tensors[name] = _cpu_tensor(value)
            if os.environ.get("ECHOMIMIC_CAPTURE_PROGRESS"):
                print(f"captured {name}", flush=True)

    def attach(self, transformer: Any) -> None:
        """Attach hooks to a constructed pinned Wan transformer."""

        if self._handles:
            raise RuntimeError("capture is already attached")
        if not hasattr(transformer, "blocks") or not transformer.blocks:
            raise TypeError("transformer does not expose a non-empty blocks collection")
        block = transformer.blocks[0]
        self._module = importlib.import_module(type(block).__module__)
        self._patch_attention_functions()
        self._handles.extend(
            [
                transformer.register_forward_pre_hook(self._transformer_pre, with_kwargs=True),
                transformer.audio_injection.register_forward_pre_hook(
                    self._audio_projection_pre, with_kwargs=True
                ),
                transformer.audio_injection.register_forward_hook(self._audio_projection_post),
                block.register_forward_pre_hook(self._block_pre, with_kwargs=True),
                block.norm1.register_forward_hook(self._norm1_post),
                block.self_attn.register_forward_hook(self._self_attention_post),
                block.norm3.register_forward_hook(self._norm3_post),
                block.cross_attn.register_forward_pre_hook(self._cross_pre, with_kwargs=True),
                block.cross_attn.register_forward_hook(self._cross_post),
                block.ffn.register_forward_pre_hook(self._ffn_pre, with_kwargs=True),
                block.ffn.register_forward_hook(self._ffn_post),
                block.register_forward_hook(self._block_post),
            ]
        )

    def _patch_attention_functions(self) -> None:
        self._original_attention = self._module.attention
        self._original_audio_attention = self._module.audio_mask_attention

        def attention_wrapper(*args: Any, **kwargs: Any) -> Any:
            output = self._original_attention(*args, **kwargs)
            if self._active and self._cross_active:
                self._cross_attention_outputs.append(output)
            return output

        def audio_wrapper(*args: Any, **kwargs: Any) -> Any:
            output = self._original_audio_attention(*args, **kwargs)
            if self._active and self._cross_active:
                self._audio_heads = output
            return output

        self._module.attention = attention_wrapper
        self._module.audio_mask_attention = audio_wrapper

    def detach(self) -> None:
        """Restore all hooks and upstream module functions."""

        for handle in self._handles:
            handle.remove()
        self._handles.clear()
        if self._module is not None:
            if self._original_attention is not None:
                self._module.attention = self._original_attention
            if self._original_audio_attention is not None:
                self._module.audio_mask_attention = self._original_audio_attention

    def validate_fixed_geometry(self) -> None:
        """Reject captures that drift from the locked 512x512, 81-frame run."""

        missing = sorted(
            (BLOCK0_REFERENCE_NAMES | AUDIO_PROJECTION_REFERENCE_NAMES) - self.tensors.keys()
        )
        if missing:
            raise ValueError(f"block-0 capture is incomplete: {missing}")

        def shape(name: str) -> tuple[int, ...]:
            return tuple(self.tensors[name].shape)

        hidden_shape = (1, 21 * 32 * 32, 1536)
        for suffix in (
            "input",
            "norm1",
            "self_attention",
            "cross_input",
            "text_image_attention",
            "audio_attention",
            "cross_attention",
            "ffn_input",
            "ffn",
            "output",
        ):
            name = f"transformer.block_00.{suffix}"
            if shape(name) != hidden_shape:
                raise ValueError(f"fixed block-0 geometry mismatch for {name}: {shape(name)}")
        expected_shapes = {
            "transformer.block_00.timestep_modulation": (1, 6, 1536),
            "transformer.block_00.sequence_lengths": (1,),
            "transformer.block_00.grid_sizes": (1, 3),
            "transformer.block_00.context": (1, 769, 1536),
            "transformer.block_00.audio_context": (1, 21, 32, 1536),
            "transformer.audio_projection.first_frame_input": (1, 1, 5, 12, 768),
            "transformer.audio_projection.later_frame_input": (1, 20, 8, 12, 768),
            "transformer.audio_projection.output": (1, 21, 32, 1536),
        }
        for name, expected in expected_shapes.items():
            if shape(name) != expected:
                raise ValueError(f"fixed block-0 geometry mismatch for {name}: {shape(name)}")
        if self.tensors["transformer.block_00.sequence_lengths"].tolist() != [21 * 32 * 32]:
            raise ValueError("fixed block-0 sequence length value mismatch")
        if self.tensors["transformer.block_00.grid_sizes"].tolist() != [[21, 32, 32]]:
            raise ValueError("fixed block-0 grid value mismatch")

    def _transformer_pre(
        self, _module: Any, _args: tuple[Any, ...], _kwargs: Mapping[str, Any]
    ) -> None:
        self._call_index += 1
        self._active = self._call_index == self.transformer_call

    def _audio_projection_pre(
        self, _module: Any, args: tuple[Any, ...], _kwargs: Mapping[str, Any]
    ) -> None:
        if self._active:
            self._add("transformer.audio_projection.first_frame_input", args[0])
            self._add("transformer.audio_projection.later_frame_input", args[1])

    def _audio_projection_post(self, _module: Any, _args: tuple[Any, ...], output: Any) -> None:
        self._add("transformer.audio_projection.output", output)

    def _block_pre(self, block: Any, args: tuple[Any, ...], kwargs: Mapping[str, Any]) -> None:
        if not self._active:
            return
        x = args[0]
        e = kwargs["e"]
        self._modulation_chunks = tuple((block.modulation + e).chunk(6, dim=1))
        self._add("transformer.block_00.input", x)
        self._add("transformer.block_00.timestep_modulation", e)
        self._add("transformer.block_00.sequence_lengths", kwargs["seq_lens"])
        self._add("transformer.block_00.grid_sizes", kwargs["grid_sizes"])
        context = kwargs["context"]
        self._add("transformer.block_00.context", context[0])
        self._add("transformer.block_00.audio_context", context[1])

    def _norm1_post(self, _module: Any, _args: tuple[Any, ...], output: Any) -> None:
        if self._active:
            if self._modulation_chunks is None:
                raise RuntimeError("block modulation was not captured before norm1")
            shift, scale = self._modulation_chunks[:2]
            self._add("transformer.block_00.norm1", output * (1 + scale) + shift)

    def _self_attention_post(self, _module: Any, _args: tuple[Any, ...], output: Any) -> None:
        self._add("transformer.block_00.self_attention", output)

    def _norm3_post(self, _module: Any, _args: tuple[Any, ...], output: Any) -> None:
        self._add("transformer.block_00.cross_input", output)

    def _cross_pre(self, _module: Any, _args: tuple[Any, ...], _kwargs: Mapping[str, Any]) -> None:
        if self._active:
            self._cross_active = True
            self._cross_attention_outputs.clear()
            self._audio_heads = None

    def _cross_post(self, _module: Any, _args: tuple[Any, ...], output: Any) -> None:
        if not self._active:
            return
        self._cross_active = False
        if len(self._cross_attention_outputs) != 2 or self._audio_heads is None:
            raise RuntimeError("unexpected pinned cross-attention branch call sequence")
        image_heads, text_heads = self._cross_attention_outputs
        self._add(
            "transformer.block_00.text_image_attention", (image_heads + text_heads).flatten(2)
        )
        # Upstream evaluates audio attention as (batch * latent_frames, spatial, heads, dim)
        # before restoring it to the main (batch, sequence, hidden) layout.
        self._add("transformer.block_00.audio_attention", self._audio_heads.reshape(output.shape))
        self._add("transformer.block_00.cross_attention", output)

    def _ffn_pre(self, _module: Any, args: tuple[Any, ...], _kwargs: Mapping[str, Any]) -> None:
        self._add("transformer.block_00.ffn_input", args[0])

    def _ffn_post(self, _module: Any, _args: tuple[Any, ...], output: Any) -> None:
        self._add("transformer.block_00.ffn", output)

    def _block_post(self, _module: Any, _args: tuple[Any, ...], output: Any) -> None:
        if self._active:
            self._add("transformer.block_00.output", output)
            raise BlockCaptureComplete("pinned block-0 capture is complete")


class TorchDenoisingCapture:
    """Capture compact full-Transformer and eight-step denoising boundaries."""

    _boundary_blocks = frozenset({4, 9, 14, 19, 24, 29})

    def __init__(self, *, steps: int = 8) -> None:
        if steps <= 0:
            raise ValueError("denoising capture step count must be positive")
        self.steps = steps
        self.tensors: dict[str, Any] = {}
        self._call_index = -1
        self._step_index = -1
        self._handles: list[Any] = []
        self._scheduler: Any = None
        self._original_scheduler_step: Any = None

    def _add(self, name: str, value: Any) -> None:
        if name not in self.tensors:
            self.tensors[name] = _cpu_tensor(value)
            if os.environ.get("ECHOMIMIC_CAPTURE_PROGRESS"):
                print(f"captured {name}", flush=True)

    def attach_transformer(self, transformer: Any) -> None:
        """Attach read-only hooks to the complete pinned Transformer."""

        if self._handles:
            raise RuntimeError("denoising capture is already attached")
        if not hasattr(transformer, "blocks") or len(transformer.blocks) != 30:
            raise TypeError("pinned denoising capture requires exactly 30 Transformer blocks")
        self._handles.extend(
            [
                transformer.register_forward_pre_hook(self._transformer_pre, with_kwargs=True),
                transformer.register_forward_hook(self._transformer_post),
                transformer.blocks[0].register_forward_pre_hook(self._block0_pre, with_kwargs=True),
                transformer.head.register_forward_pre_hook(self._head_pre, with_kwargs=True),
            ]
        )
        for block_index in sorted(self._boundary_blocks):
            self._handles.append(
                transformer.blocks[block_index].register_forward_hook(
                    self._boundary_hook(block_index)
                )
            )

    def attach_scheduler(self, scheduler: Any) -> None:
        """Wrap one scheduler instance and capture all fixed step boundaries."""

        if self._scheduler is not None:
            raise RuntimeError("scheduler capture is already attached")
        self._scheduler = scheduler
        self._original_scheduler_step = scheduler.step

        def step_wrapper(
            model_output: Any, timestep: Any, sample: Any, *args: Any, **kwargs: Any
        ) -> Any:
            self._step_index += 1
            prefix = f"denoising.step_{self._step_index:02d}"
            self._add(f"{prefix}.latent_input", sample)
            self._add(f"{prefix}.guided_noise", model_output)
            self._add(f"{prefix}.timestep", timestep)
            result = self._original_scheduler_step(model_output, timestep, sample, *args, **kwargs)
            output = result[0] if isinstance(result, tuple) else result.prev_sample
            self._add(f"{prefix}.latent_output", output)
            if self._step_index + 1 == self.steps:
                raise DenoisingCaptureComplete("fixed denoising capture is complete")
            return result

        scheduler.step = step_wrapper

    def detach(self) -> None:
        """Remove hooks and restore the scheduler instance."""

        for handle in self._handles:
            handle.remove()
        self._handles.clear()
        if self._scheduler is not None and self._original_scheduler_step is not None:
            self._scheduler.step = self._original_scheduler_step
        self._scheduler = None
        self._original_scheduler_step = None

    def _transformer_pre(
        self, _module: Any, _args: tuple[Any, ...], kwargs: Mapping[str, Any]
    ) -> None:
        self._call_index += 1
        if self._call_index != 0:
            return
        context = kwargs["context"][0]
        if not hasattr(context, "detach"):
            torch = importlib.import_module("torch")
            context = torch.stack(list(context))
        self._add("transformer.raw.text_context", context)
        self._add("transformer.raw.image_context", kwargs["clip_fea"])
        self._add("transformer.raw.inpaint_condition", kwargs["y"])

    def _transformer_post(self, _module: Any, _args: tuple[Any, ...], output: Any) -> None:
        self._add(f"transformer.call_{self._call_index:02d}.output", output)

    def _block0_pre(self, _module: Any, args: tuple[Any, ...], kwargs: Mapping[str, Any]) -> None:
        call_index = self._call_index
        step_index = call_index // 2
        if call_index % 2 == 0:
            prefix = f"denoising.step_{step_index:02d}"
            self._add(f"{prefix}.block_input", args[0])
            self._add(f"{prefix}.timestep_modulation", kwargs["e"])
        if call_index == 0:
            self._add("transformer.context", kwargs["context"][0])
            self._add("transformer.audio_context_cond", kwargs["context"][1])
            self._add("transformer.grid_sizes", kwargs["grid_sizes"])
        elif call_index == 1:
            self._add("transformer.audio_context_uncond", kwargs["context"][1])

    def _head_pre(self, _module: Any, args: tuple[Any, ...], _kwargs: Mapping[str, Any]) -> None:
        if self._call_index % 2 == 0:
            prefix = f"denoising.step_{self._call_index // 2:02d}"
            self._add(f"{prefix}.head_timestep_embedding", args[1])
        if self._call_index == 0:
            self._add("transformer.call_00.head_input", args[0])

    def _boundary_hook(self, block_index: int) -> Any:
        def hook(_module: Any, _args: tuple[Any, ...], output: Any) -> None:
            if self._call_index == 0:
                self._add(f"transformer.call_00.block_{block_index:02d}.output", output)

        return hook

    def validate_fixed_geometry(self) -> None:
        """Require the exact 8-step, two-call CFG capture contract."""

        if self._call_index + 1 != 2 * self.steps or self._step_index + 1 != self.steps:
            raise ValueError("denoising capture call or step count is incomplete")
        hidden_shape = (1, 21 * 32 * 32, 1536)
        latent_shape = (1, 16, 21, 64, 64)
        required = {
            "transformer.context": (1, 769, 1536),
            "transformer.audio_context_cond": (1, 21, 32, 1536),
            "transformer.audio_context_uncond": (1, 21, 32, 1536),
            "transformer.grid_sizes": (1, 3),
            "transformer.raw.image_context": (1, 257, 1280),
            "transformer.raw.inpaint_condition": (1, 20, 21, 64, 64),
            "transformer.call_00.head_input": hidden_shape,
        }
        for call_index in range(2 * self.steps):
            required[f"transformer.call_{call_index:02d}.output"] = latent_shape
        for step_index in range(self.steps):
            prefix = f"denoising.step_{step_index:02d}"
            required.update(
                {
                    f"{prefix}.block_input": hidden_shape,
                    f"{prefix}.timestep_modulation": (1, 6, 1536),
                    f"{prefix}.head_timestep_embedding": (1, 1536),
                    f"{prefix}.latent_input": latent_shape,
                    f"{prefix}.guided_noise": latent_shape,
                    f"{prefix}.timestep": (),
                    f"{prefix}.latent_output": latent_shape,
                }
            )
        for block_index in self._boundary_blocks:
            required[f"transformer.call_00.block_{block_index:02d}.output"] = hidden_shape
        required_names = set(required) | {"transformer.raw.text_context"}
        missing = sorted(required_names - self.tensors.keys())
        if missing:
            raise ValueError(f"denoising capture is incomplete: {missing}")
        for name, expected in required.items():
            actual = tuple(self.tensors[name].shape)
            if actual != expected:
                raise ValueError(f"fixed denoising geometry mismatch for {name}: {actual}")
        raw_text_shape = tuple(self.tensors["transformer.raw.text_context"].shape)
        if (
            len(raw_text_shape) != 3
            or raw_text_shape[0] != 1
            or raw_text_shape[1] > 512
            or raw_text_shape[2] != 4096
        ):
            raise ValueError(
                "fixed denoising geometry mismatch for transformer.raw.text_context: "
                f"{raw_text_shape}"
            )
        if self.tensors["transformer.grid_sizes"].tolist() != [[21, 32, 32]]:
            raise ValueError("fixed denoising grid value mismatch")
