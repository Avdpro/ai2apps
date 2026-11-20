# SPDX-License-Identifier: Apache-2.0
"""Pure NumPy checkpoint layout adapter reused from the Mac Demucs implementation.
Source: packages/omlx-model-demucs/src/mlx_demucs/mlx_model.py.
Restores PyTorch names/layout from the same fixed safetensors without pickle.
"""
import re
from pathlib import Path
import numpy as np

_DCONV_COMPONENT = re.compile(
    r"(\.dconv\.layers\.\d+)\.layers\.(\d+)(?:\.conv)?\."
)


def load_converted_safetensors(path: str | Path) -> dict[str, np.ndarray]:
    """Adapt ``mlx-community/demucs-mlx`` weights to the explicit op boundary.

    That public artifact stores convolution weights in MLX layout and splits
    PyTorch's packed Q/K/V tensors. The returned mapping deliberately restores
    the original PyTorch names/layout consumed by this experiment's parity-
    tested operators; it does not write or duplicate another checkpoint file.
    """
    from safetensors import safe_open

    values: dict[str, np.ndarray] = {}
    attention: dict[tuple[str, str], dict[str, np.ndarray]] = {}
    with safe_open(str(Path(path)), framework="numpy") as package:
        for stored_name in package.keys():  # noqa: SIM118 - safe_open is not iterable
            if not stored_name.startswith("model_0."):
                raise ValueError(f"Unsupported safetensors key: {stored_name}")
            name = stored_name.removeprefix("model_0.")
            array = np.asarray(package.get_tensor(stored_name))

            match = re.match(
                r"(.+\.(?:attn|cross_attn))\.(query_proj|key_proj|value_proj)\.(weight|bias)$",
                name,
            )
            if match:
                root, projection, kind = match.groups()
                if root.endswith(".attn"):
                    root = root.removesuffix(".attn") + ".self_attn"
                attention.setdefault((root, kind), {})[projection] = array
                continue

            if ".attn.out_proj." in name:
                name = name.replace(".attn.out_proj.", ".self_attn.out_proj.")
            name = name.replace(".norm_out.gn.", ".norm_out.")
            name = _DCONV_COMPONENT.sub(r"\1.\2.", name)
            name = name.replace(".conv_tr.conv.", ".conv_tr.")
            name = name.replace(".rewrite.conv.", ".rewrite.")
            name = name.replace(".conv.conv.", ".conv.")
            if name.startswith("channel_"):
                name = name.replace(".conv.", ".", 1)

            if stored_name.endswith(".weight") and ".conv" in stored_name:
                if ".conv_tr.conv.weight" in stored_name:
                    axes = (3, 0, 1, 2) if array.ndim == 4 else (2, 0, 1)
                else:
                    axes = (0, 3, 1, 2) if array.ndim == 4 else (0, 2, 1)
                array = np.transpose(array, axes)
            if name in values:
                raise ValueError(f"Duplicate adapted safetensors key: {name}")
            values[name] = array

    order = ("query_proj", "key_proj", "value_proj")
    for (root, kind), projections in attention.items():
        if set(projections) != set(order):
            raise ValueError(f"Incomplete attention projections: {root}.{kind}")
        values[f"{root}.in_proj_{kind}"] = np.concatenate(
            [projections[item] for item in order], axis=0
        )
    return values

