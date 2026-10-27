"""Trusted host adapters declared by the built-in Imagine Mini-Apps."""
MINI_APP_CAPABILITIES = {
    "ai2apps.imagine.text-to-image": "image.generate",
    "ai2apps.imagine.image-edit": "image.edit",
}

from .mini_parameters import WORKFLOWS
MINI_APP_CAPABILITIES.update(WORKFLOWS)
