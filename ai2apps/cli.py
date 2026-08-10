"""Public AI2Apps command-line entry point.

The server implementation intentionally remains in :mod:`omlx` so upstream
runtime patches stay reviewable.  This module is the stable product boundary.
"""

from __future__ import annotations

import os
import sys


def _apply_environment_compatibility() -> None:
    """Map public controls onto the embedded oMLX runtime variables.

    ``DYNAMOE_*`` remains a read-only compatibility input for development
    checkouts created before the AI2Apps rename. New documentation and emitted
    configuration use ``AI2APPS_*`` exclusively.
    """
    explicit_runtime = {name for name in os.environ if name.startswith("OMLX_")}

    # Pre-rename values are the lowest-priority input.
    for name, value in tuple(os.environ.items()):
        if name.startswith("DYNAMOE_") and name != "DYNAMOE_PRODUCT":
            runtime_name = "OMLX_" + name.removeprefix("DYNAMOE_")
            os.environ.setdefault(runtime_name, value)

    # Public AI2Apps controls override legacy values, but never an explicitly
    # supplied embedded-runtime value.
    for name, value in tuple(os.environ.items()):
        if name.startswith("AI2APPS_") and name != "AI2APPS_PRODUCT":
            runtime_name = "OMLX_" + name.removeprefix("AI2APPS_")
            if runtime_name not in explicit_runtime:
                os.environ[runtime_name] = value


def main() -> None:
    """Run the AI2Apps CLI backed by the embedded oMLX runtime."""
    os.environ["AI2APPS_PRODUCT"] = "1"
    _apply_environment_compatibility()
    try:
        from omlx.cli import main as runtime_main

        runtime_main()
    except ModuleNotFoundError as exc:
        if exc.name == "huggingface_hub" or (
            exc.name and exc.name.startswith("huggingface_hub.")
        ):
            print(
                "AI2Apps cannot start because huggingface-hub is missing.\n"
                "Install the complete package with:\n"
                "  pip install -U ai2apps\n"
                "or repair this source environment with:\n"
                "  pip install 'huggingface-hub>=1.19.0'",
                file=sys.stderr,
            )
            raise SystemExit(2) from exc
        raise


if __name__ == "__main__":
    main()
