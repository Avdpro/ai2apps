"""Native alpha validation shared by generation and sticker storage."""
from io import BytesIO
from PIL import Image


def validate_alpha(content):
    with Image.open(BytesIO(content)) as image:
        if image.format not in ('PNG', 'WEBP') or image.convert('RGBA').getchannel('A').getextrema()[0] == 255:
            raise ValueError('Transparent background requested, but the model returned an opaque image. No background removal or provider retry was performed.')


def validate_background(value, output_format, supported):
    if value is None:
        return
    if value not in supported:
        raise ValueError('Selected model does not declare support for background mode: ' + str(value))
    if value == 'transparent' and output_format not in ('png', 'webp'):
        raise ValueError('Transparent background requires PNG or WebP output')
