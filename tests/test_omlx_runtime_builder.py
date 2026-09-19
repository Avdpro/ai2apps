from __future__ import annotations

import plistlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_omlx_runtime_package import create_bundle  # noqa: E402


def _write(path: Path, content: str = "payload") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_omlx_runtime_bundle_keeps_only_worker_and_inference_payload(tmp_path: Path):
    layers = tmp_path / "layers"
    python = layers / "cpython-3.11"
    framework = layers / "framework-mlx-base"
    site = framework / "lib/python3.11/site-packages"
    _write(python / "bin/python3.11")
    _write(python / "lib/python3.11/os.py")
    _write(python / "lib/python3.11/test/test_os.py")
    _write(python / "lib/python3.11/__pycache__/os.pyc")

    _write(site / "mlx/__init__.py")
    _write(site / "mlx/tests/test_core.py")
    _write(site / "onnxruntime/__init__.py")
    _write(site / "sherpa_onnx/__init__.py")
    _write(site / "xgrammar/libxgrammar_bindings.dylib")
    _write(site / "xgrammar/lib/libxgrammar.a")
    for name in ("mcp", "mcp_types", "modelscope", "modelscope_hub", "selenium"):
        _write(site / name / "__init__.py")
        _write(site / f"{name}-1.0.0.dist-info/METADATA")

    source = tmp_path / "source"
    _write(source / "ai2apps/__init__.py")
    _write(source / "ai2apps/_version.py")
    _write(source / "ai2apps/model_worker/launcher.py")
    _write(source / "ai2apps/model_worker/server.py")
    _write(source / "ai2apps/web/index.html")
    _write(source / "ai2apps/remote/bin/darwin-x86_64/frpc")
    _write(source / "omlx/__init__.py")
    _write(source / "omlx/engine/batched.py")
    _write(source / "omlx/eval/data.json")

    bundle = create_bundle(
        layers,
        tmp_path / "output",
        "1.6.2",
        runtime_source_root=source,
    )
    runtime = bundle / "Contents/Resources/Runtime"
    copied_site = runtime / "Python/framework-mlx-base/lib/python3.11/site-packages"

    assert (runtime / "app/ai2apps/model_worker/launcher.py").is_file()
    assert not (runtime / "app/ai2apps/web").exists()
    assert not (runtime / "app/ai2apps/remote").exists()
    assert (runtime / "app/omlx/engine/batched.py").is_file()
    assert not (runtime / "app/omlx/eval").exists()
    assert (copied_site / "mlx/__init__.py").is_file()
    assert (copied_site / "onnxruntime/__init__.py").is_file()
    assert (copied_site / "sherpa_onnx/__init__.py").is_file()
    assert (copied_site / "xgrammar/libxgrammar_bindings.dylib").is_file()
    assert not (copied_site / "xgrammar/lib/libxgrammar.a").exists()
    assert not (copied_site / "mlx/tests").exists()
    assert not (runtime / "Python/cpython-3.11/lib/python3.11/test").exists()
    assert not (runtime / "Python/cpython-3.11/lib/python3.11/__pycache__").exists()
    for name in ("mcp", "mcp_types", "modelscope", "modelscope_hub", "selenium"):
        assert not (copied_site / name).exists()
        assert not (copied_site / f"{name}-1.0.0.dist-info").exists()

    info = plistlib.loads((bundle / "Contents/Info.plist").read_bytes())
    assert info["CFBundleShortVersionString"] == "1.6.2"
