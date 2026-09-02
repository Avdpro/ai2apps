#!/usr/bin/env python3
"""Apply the Runtime 1.5 MLX-only mflux patch to an installed environment."""

import importlib.metadata
from pathlib import Path


def main():
    if importlib.metadata.version("mflux") != "0.19.0":
        raise RuntimeError("this patch is audited only for mflux 0.19.0")
    root = Path(importlib.metadata.distribution("mflux").locate_file("mflux"))
    loader = root / "models/common/weights/loading/weight_loader.py"
    source = loader.read_text()
    if "import torch\n" in source:
        source = source.replace("import torch\n", "")
        source = source.replace("from safetensors.torch import load_file as torch_load_file\n", "")
        start = source.index("    @staticmethod\n    def _load_torch_checkpoint")
        end = source.index("    @staticmethod\n    def _load_safetensors", start)
        source = source[:start] + "    @staticmethod\n    def _load_torch_checkpoint(file_path: Path) -> dict[str, mx.array]:\n        raise RuntimeError('torch conversion is not included')\n\n" + source[end:]
        start = source.index("    @staticmethod\n    def _load_torch_convert")
        end = source.index("    @staticmethod\n    def _load_multi_json", start)
        source = source[:start] + "    @staticmethod\n    def _load_torch_convert(path: Path, weight_files=None) -> dict[str, mx.array]:\n        raise RuntimeError('torch conversion is not included')\n\n" + source[end:]
        start = source.index("    @staticmethod\n    def _load_torch_bfloat16")
        end = source.index("    @staticmethod\n    def _load_single", start)
        source = source[:start] + "    @staticmethod\n    def _load_torch_bfloat16(path: Path) -> dict[str, mx.array]:\n        raise RuntimeError('torch conversion is not included')\n\n" + source[end:]
        loader.write_text(source)

    klein = root / "models/flux2/variants/txt2img/flux2_klein.py"
    source = klein.read_text()
    pid_import = "from mflux.models.common.pid_decoder.pid_decoder import pid_decode_latents\n"
    lazy_pid_import = "            from mflux.models.common.pid_decoder.pid_decoder import pid_decode_latents\n"
    if source.startswith(pid_import) or f"\n{pid_import}" in source:
        source = source.replace(pid_import, "", 1)
        source = source.replace(
            "        if pid_decode:\n",
            "        if pid_decode:\n" + lazy_pid_import,
            1,
        )
        klein.write_text(source)
    elif lazy_pid_import not in source:
        raise RuntimeError("FLUX.2 PiD import layout changed")

    print(f"patched mflux 0.19.0 at {root}")


if __name__ == "__main__":
    main()
