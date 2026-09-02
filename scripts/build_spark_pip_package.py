#!/usr/bin/env python3
"""Build the inference-free AI2Apps Spark wheel from this source tree."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _toml_array(values: list[str]) -> str:
    return "[\n" + "".join(f"  {json.dumps(value)},\n" for value in values) + "]"


def _copy_sources(staging: Path) -> None:
    ignored = shutil.ignore_patterns(
        "__pycache__",
        "*.pyc",
        "*.pyo",
        "*.so",
        "*.dylib",
        "*.metallib",
        ".DS_Store",
    )
    for package in ("ai2apps", "omlx"):
        shutil.copytree(ROOT / package, staging / package, ignore=ignored)
    for filename in ("README.md", "LICENSE", "NOTICE"):
        shutil.copy2(ROOT / filename, staging / filename)


def _write_pyproject(staging: Path) -> str:
    source = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version_namespace: dict[str, object] = {}
    exec((ROOT / "ai2apps" / "_version.py").read_text(encoding="utf-8"), version_namespace)
    version = str(version_namespace["__version__"])
    dependencies = list(source["project"]["optional-dependencies"]["control-plane"])
    content = f'''[build-system]
requires = ["setuptools>=77.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ai2apps-spark"
version = {json.dumps(version)}
description = "AI2Apps local-first web control plane for NVIDIA DGX Spark"
readme = "README.md"
requires-python = ">=3.11,<3.14"
license = "Apache-2.0"
license-files = ["LICENSE", "NOTICE"]
dependencies = {_toml_array(dependencies)}
classifiers = [
  "Development Status :: 3 - Alpha",
  "Operating System :: POSIX :: Linux",
  "Programming Language :: Python :: 3",
  "Topic :: Scientific/Engineering :: Artificial Intelligence",
]

[project.scripts]
ai2apps = "ai2apps.spark_cli:main"
ai2apps-spark = "ai2apps.spark_cli:main"
ai2apps-model-worker = "ai2apps.model_worker.harness:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["ai2apps*", "omlx*"]

[tool.setuptools.package-data]
"ai2apps" = ["engines/**/*.json"]
"ai2apps.remote" = ["frpc-device.toml", "frp-ca-2026.pem", "third_party/*"]
"ai2apps.browser" = ["readability.js"]
"ai2apps.web" = [
  "templates/**/*.html",
  "static/**/*",
  "i18n/*.json",
  "src/*.css",
  "tailwind.config.js",
]
"omlx" = ["oq_calibration_data.json", "oqe_calibration_data.json"]
"omlx.admin" = ["bench_corpora/*"]
'''
    (staging / "pyproject.toml").write_text(content, encoding="utf-8")
    return version


def build(output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ai2apps-spark-wheel-") as temporary:
        staging = Path(temporary)
        _copy_sources(staging)
        version = _write_pyproject(staging)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--no-build-isolation",
                "--wheel-dir",
                str(output),
                str(staging),
            ],
            check=True,
        )
    wheels = sorted(output.glob(f"ai2apps_spark-{version}-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected one AI2Apps Spark wheel, found {len(wheels)}")
    return wheels[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "spark")
    args = parser.parse_args()
    print(build(args.output.resolve()))


if __name__ == "__main__":
    main()
