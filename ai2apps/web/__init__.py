"""AI2Apps-owned web interface resources.

The oMLX admin backend continues to provide authentication and API routes,
while templates, localization, and browser assets live in this package so
the product UI can evolve independently from the inference runtime.
"""

from pathlib import Path

WEB_ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_ROOT / "templates"
STATIC_DIR = WEB_ROOT / "static"
I18N_DIR = WEB_ROOT / "i18n"

__all__ = ["I18N_DIR", "STATIC_DIR", "TEMPLATES_DIR", "WEB_ROOT"]
