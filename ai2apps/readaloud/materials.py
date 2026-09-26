"""Private character references, independent of Gallery asset lifetime."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from pathlib import Path

from ai2apps.core import ResourceNotFoundError, RepositoryError
from ai2apps.gallery import GalleryRepository


class VoiceMaterials:
    def __init__(self, database, artifacts_path):
        self.database = database
        self.root = Path(artifacts_path) / 'voice-materials'
        self.gallery = GalleryRepository(database, Path(artifacts_path) / 'gallery')

    def _paths(self, owner, asset_id):
        folder = self.root / hashlib.sha256(owner.encode()).hexdigest()
        stem = hashlib.sha256(asset_id.encode()).hexdigest()
        return folder / (stem + '.json'), folder / (stem + '.audio')

    def save(self, owner, content, name, media_type, *, asset_id=None):
        if not media_type.startswith('audio/') or not content or len(content) > 64 * 1024 * 1024:
            raise ValueError('Reference must be non-empty audio under 64 MiB.')
        asset_id = asset_id or 'vref_' + uuid.uuid4().hex
        metadata, audio = self._paths(owner, asset_id)
        metadata.parent.mkdir(parents=True, exist_ok=True)
        asset = {'id': asset_id, 'name': Path(name).name, 'media_type': media_type,
                 'content_hash': hashlib.sha256(content).hexdigest()}
        # Publish metadata last so partially written audio is never visible.
        for target, data in ((audio, content), (metadata, json.dumps(asset).encode())):
            temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.tmp')
            try:
                temporary.write_bytes(data)
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        return asset

    def asset_path(self, owner, asset_id):
        metadata, audio = self._paths(owner, asset_id)
        if not metadata.is_file() or not audio.is_file():
            raise ResourceNotFoundError('voice_reference', asset_id)
        return json.loads(metadata.read_text()), audio

    def import_gallery(self, owner, asset_id):
        try:
            return self.asset_path(owner, asset_id)[0]
        except ResourceNotFoundError:
            asset, path = self.gallery.asset_path(owner, asset_id)
            return self.save(owner, path.read_bytes(), asset['name'], asset['media_type'], asset_id=asset_id)

    def migrate_profiles(self):
        with self.database.transaction() as connection:
            profiles = connection.execute("SELECT owner_user_id, reference_asset_id, training_json FROM readaloud_voice_profiles WHERE status!='deleted'").fetchall()
        migrated, missing = 0, 0
        for profile in profiles:
            training = json.loads(profile['training_json'] or '{}')
            ids = {sample['asset_id'] for sample in training.get('samples', [])}
            if profile['reference_asset_id']:
                ids.add(profile['reference_asset_id'])
            for asset_id in ids:
                try:
                    self.import_gallery(profile['owner_user_id'], asset_id)
                    migrated += 1
                except (RepositoryError, OSError, ValueError):
                    missing += 1
                    logging.getLogger(__name__).warning('A legacy voice reference could not be migrated; re-import is required.')
        return {'references': migrated, 'missing': missing}
