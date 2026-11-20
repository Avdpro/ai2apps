"""Trusted host adapters declared by the built-in Imagine Mini-Apps."""
MINI_APP_CAPABILITIES = {
    "ai2apps.imagine.text-to-image": "image.generate",
    "ai2apps.imagine.image-edit": "image.edit",
}

from .mini_parameters import WORKFLOWS
MINI_APP_CAPABILITIES.update(WORKFLOWS)

# Image-owned producers with specialized contracts rather than image.* forms.
STICKER_GENERATE_CAPABILITY = 'sticker.generate'
COMIC_TRANSLATION_CAPABILITY = 'comic.translation'
IMAGE_RESULT_CAPABILITIES = tuple(dict.fromkeys((*MINI_APP_CAPABILITIES.values(), STICKER_GENERATE_CAPABILITY)))
