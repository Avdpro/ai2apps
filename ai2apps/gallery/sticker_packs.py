"""Gallery-owned character definitions and reusable sticker references."""

import json
import unicodedata
from io import BytesIO
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai2apps.core import ResourceNotFoundError, utc_now_text
from ai2apps.gallery.repository import GalleryError, STICKER_PACK_MIME


STATES = {
    state[0]: state[1:]
    for state in json.loads(
        (Path(__file__).parents[1] / 'web/static/js/sticker_states.json').read_text(encoding='utf-8')
    )
}
RASTER = {'image/png', 'image/jpeg', 'image/webp'}
SCHEMA = 'ai2apps.sticker-pack/v1'
FRAMING = {'half': 'waist-up with the entire head and gestures visible',
           'full': 'full body from head to feet, including the entire silhouette'}
FACING = {'center': 'forward toward the viewer', 'left': 'toward the left edge of the image',
          'right': 'toward the right edge of the image'}


class Character(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default='', max_length=1000)
    reference_ids: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(min_length=1, max_length=4)


class Variant(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    state: str
    framing: Literal['half', 'full'] = 'half'
    facing: Literal['center', 'left', 'right'] = 'center'
    background: Literal['white', 'transparent'] = 'white'

    @field_validator('state')
    @classmethod
    def known_state(cls, value):
        if value not in STATES:
            raise ValueError('Unknown sticker state')
        return value


class StickerEntry(Variant):
    asset_id: str = Field(min_length=1, max_length=100)
    description: str = Field(default='', max_length=1000)


def prompt(variant, character):
    background = ('Use a true transparent alpha background, not white or a checkerboard. '
                  if variant.background == 'transparent' else 'Use a plain white background. ')
    return (
        'Create one expressive die-cut sticker. Preserve the recognizable identity, hair, '
        'markings and distinctive accessories in the character references. Only one subject '
        'with a clean outline and white sticker border. No text. '
        f'{background}Frame {FRAMING[variant.framing]}. Face {FACING[variant.facing]}. '
        f'{STATES[variant.state][2]} Character details: {character["description"]}'
    )


def normalize(name):
    return unicodedata.normalize('NFKC', name).strip().casefold()


class StickerPacks:
    def __init__(self, gallery, owner):
        self.gallery = gallery
        self.owner = owner

    @staticmethod
    def manifest(asset):
        metadata = asset['metadata']
        if (asset['media_type'] != STICKER_PACK_MIME or asset['status'] != 'active'
                or metadata.get('schema') != SCHEMA):
            raise GalleryError('sticker_pack_unavailable', 'Active sticker pack required.')
        return metadata

    def get(self, pack_id):
        asset = self.gallery.get_asset(self.owner, pack_id)
        return {'id': asset['id'], 'name': asset['name'], **self.manifest(asset)}

    def list(self):
        return [
            {'id': asset['id'], 'name': asset['name'], **asset['metadata']}
            for asset in self.gallery.list_assets(self.owner, kind='sticker-pack', limit=500)
            if asset['metadata'].get('schema') == SCHEMA
        ]

    def create(self, character):
        reference_ids = list(dict.fromkeys(character.reference_ids))
        refs = []
        for identifier in reference_ids:
            asset, _ = self.image(identifier)
            if asset['size_bytes'] > 9 * 1024 * 1024:
                raise GalleryError('sticker_reference_too_large', 'A character reference exceeds 9 MiB.')
            refs.append({'id': identifier, 'content_hash': asset['content_hash']})
        manifest = {
            'schema': SCHEMA,
            'character': {'name': character.name, 'description': character.description,
                          'references': refs},
            'stickers': [],
            'pack_key': uuid4().hex,
        }
        asset, _ = self.gallery.import_stream(
            self.owner, BytesIO(json.dumps(manifest, ensure_ascii=False).encode()),
            name=f'{character.name.replace("/", "／")}.stickerpack',
            media_type=STICKER_PACK_MIME, metadata=manifest,
        )
        return {'id': asset['id'], 'name': asset['name'], **manifest}

    def image(self, identifier):
        asset, path = self.gallery.asset_path(self.owner, identifier)
        if asset['status'] != 'active' or asset['media_type'] not in RASTER:
            raise GalleryError('sticker_image_required', 'An active PNG, JPEG or WebP is required.')
        return asset, path

    def append(self, pack_id, entry):
        if entry.background == 'transparent':
            from ai2apps.images.background import validate_alpha
            _, path = self.image(entry.asset_id)
            try:
                validate_alpha(path.read_bytes())
            except ValueError as error:
                raise GalleryError('sticker_alpha_required', str(error)) from error
        with self.gallery.database.transaction(write=True) as db:
            pack = self.gallery._decode(self.gallery._asset_row(db, self.owner, pack_id))
            manifest = self.manifest(pack)
            asset = self.gallery._asset_row(db, self.owner, entry.asset_id, include_trashed=False)
            if asset['media_type'] not in RASTER:
                raise GalleryError('sticker_image_required', 'A PNG, JPEG or WebP is required.')
            items = manifest['stickers']
            item = entry.model_dump()
            item['content_hash'] = asset['content_hash']
            if item in items:
                return item
            if len(items) >= 500:
                raise GalleryError('sticker_pack_full', 'This sticker pack already contains 500 stickers.')
            items.append(item)
            db.execute('UPDATE gallery_assets SET metadata_json=?,updated_at=? WHERE id=? AND owner_user_id=?',
                       (json.dumps(manifest, ensure_ascii=False), utc_now_text(), pack_id, self.owner))
            self.gallery._append_event(db, event_type='gallery.sticker_pack.updated',
                                       subject_id=pack_id, owner_user_id=self.owner,
                                       payload={'sticker_count': len(items)})
        return item

    def find(self, pack, variant, *, flexible=False):
        criteria = variant.model_dump(exclude_unset=flexible)
        criteria['background'] = variant.background
        candidates = [item for item in reversed(pack['stickers'])
                      if all(item.get(key, 'white' if key == 'background' else None) == value for key, value in criteria.items())]
        candidates.sort(key=lambda item: (item['framing'] != variant.framing,
                                          item['facing'] != variant.facing))
        for item in candidates:
            try:
                asset, path = self.image(item['asset_id'])
            except (ResourceNotFoundError, FileNotFoundError, GalleryError):
                continue
            if item['content_hash'] == asset['content_hash']:
                return item, asset, path
        return None
