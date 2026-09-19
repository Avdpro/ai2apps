from __future__ import annotations

import sys
from pathlib import Path


SYSTEM_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SYSTEM_ROOT.parent

for path in (SYSTEM_ROOT / "src", REPO_ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)
