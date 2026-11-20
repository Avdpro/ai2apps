"""Gallery-owned reusable identities and versioned appearance settings."""
import json
from io import BytesIO
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field
from ai2apps.core import utc_now_text, ResourceNotFoundError
from ai2apps.gallery.repository import GalleryError

MIME = 'application/vnd.ai2apps.character+json'
SCHEMA = 'ai2apps.character/v1'

class Appearance(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    name: str = Field(min_length=1, max_length=100)
    style: str = Field(default='', max_length=2000)
    style_id: str = Field(default='', max_length=100)
    proportions: str = Field(default='', max_length=500)
    outfit: str = Field(default='', max_length=2000)
    description: str = Field(default='', max_length=4000)
    summary: str = Field(default='', max_length=6000)
    reference_ids: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(default_factory=list, max_length=4)
    definition_image_id: str = Field(default='', max_length=100)
    approved: bool = False

class CharacterInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default='', max_length=4000)
    aliases: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(default_factory=list, max_length=20)
    appearances: list[Appearance] = Field(default_factory=list, max_length=50)
    default_appearance_id: str = Field(default='', max_length=80)
    revision: int = Field(default=0, ge=0)

class Characters:
    def __init__(self, gallery, owner):
        self.gallery, self.owner = gallery, owner

    def get(self, identifier):
        asset = self.gallery.get_asset(self.owner, identifier)
        if asset['status'] != 'active' or asset['media_type'] != MIME or asset['metadata'].get('schema') != SCHEMA:
            raise GalleryError('character_unavailable', 'Active character required.')
        return {'id': identifier, **asset['metadata']}

    def list(self):
        return [{k:v for k,v in self.get(a['id']).items() if k != 'history'} for a in self.gallery.list_assets(self.owner, kind='character', limit=500)]

    def definitions(self):
        """Reusable public view: one finalized image and prose, never authoring inputs."""
        items=[]
        for character in self.list():
            appearances=[]
            for a in character['appearances']:
                image=a.get('definition_image_id');text=a.get('summary','').strip()
                if not a.get('approved') or not image or not text:continue
                try:
                    asset,_=self.gallery.asset_path(self.owner,image)
                except (GalleryError,ResourceNotFoundError,FileNotFoundError):continue
                if asset['status']!='active' or asset['media_type'] not in {'image/png','image/jpeg','image/webp'}:continue
                appearances.append({'id':a['id'],'name':a['name'],'revision':a['revision'],
                    'definition_image_id':image,'summary':text,'approved':True})
            if appearances:items.append({'id':character['id'],'name':character['name'],'revision':character['revision'],
                'default_appearance_id':character['default_appearance_id'],'appearances':appearances})
        return items

    def save(self, value, identifier=None):
        body = value.model_dump()
        ids = [a.id for a in value.appearances]
        if len(ids) != len(set(ids)) or (value.default_appearance_id and value.default_appearance_id not in ids):
            raise GalleryError('character_appearance_invalid', 'Appearance IDs must be unique and the default must exist.')
        for appearance in value.appearances:
            if appearance.approved and not (appearance.definition_image_id and appearance.summary.strip()):
                raise GalleryError('character_reference_required', 'Finalize an appearance only after choosing its definition image and description.')
            for ref in [*appearance.reference_ids,*([appearance.definition_image_id] if appearance.definition_image_id else [])]:
                a, _ = self.gallery.asset_path(self.owner, ref)
                if a['status'] != 'active' or a['media_type'] not in {'image/png','image/jpeg','image/webp'}:
                    raise GalleryError('character_reference_invalid', 'An active PNG, JPEG or WebP reference is required.')
        if not identifier:
            if value.revision != 0:
                raise GalleryError('character_revision_conflict', 'New character revision must be zero.')
            for a in body['appearances']: a['revision'] = 1
            body.update(schema=SCHEMA, revision=1, updated_at=utc_now_text())
            asset, _ = self.gallery.import_stream(self.owner, BytesIO(json.dumps(body,ensure_ascii=False).encode()),
                name=value.name.replace('/','／')+'.character', media_type=MIME, metadata=body)
            return {'id':asset['id'], **body}
        with self.gallery.database.transaction(write=True) as db:
            asset = self.gallery._decode(self.gallery._asset_row(db, self.owner, identifier, include_trashed=False))
            if asset['media_type'] != MIME or asset['metadata'].get('schema') != SCHEMA:
                raise GalleryError('character_unavailable', 'Active character required.')
            old = asset['metadata']
            if (old and value.revision != old['revision']) or (not old and value.revision != 0):
                raise GalleryError('character_revision_conflict', 'Character changed. Reload before saving.')
            previous = {a['id']: a for a in old['appearances']} if old else {}
            for a in body['appearances']:
                prev = previous.get(a['id'])
                content = lambda x: {k:v for k,v in x.items() if k not in {'revision','approved','generated_images'}}
                changed = not prev or content(prev) != content(a)
                a['generated_images'] = list(prev.get('generated_images', [])) if prev else []
                a['revision'] = (prev['revision'] if prev else 0) + int(changed)
                if prev and (changed or old['description'] != value.description):
                    a['approved'] = False
            body.update(schema=SCHEMA, revision=value.revision+1, updated_at=utc_now_text())
            history = list(old.get('history', []))
            if len(history) >= 200:
                raise GalleryError('character_history_full', 'This character has 200 saved revisions. Create a new character to continue.')
            history.append({k:v for k,v in old.items() if k not in {'id','history'}})
            body['history'] = history
            body['removed_generated_images'] = list(old.get('removed_generated_images', []))
            db.execute('UPDATE gallery_assets SET name=?,metadata_json=?,updated_at=? WHERE id=? AND owner_user_id=?',
                (value.name.replace('/','／')+'.character',json.dumps(body,ensure_ascii=False),body['updated_at'],identifier,self.owner))
            self.gallery._append_event(db,event_type='gallery.character.updated',subject_id=identifier,owner_user_id=self.owner,payload={'revision':body['revision']})
        return {'id':identifier, **body}

    def attach_generated(self, identifier, appearance_id, image, *, appearance_revision, run_id, artifact_id, parameters=None):
        linked,_=self.gallery.asset_path(self.owner, image['id'])
        if linked['status']!='active' or linked['media_type'] not in {'image/png','image/jpeg','image/webp'}:
            raise GalleryError('character_image_unavailable','An active generated image is required.')
        with self.gallery.database.transaction(write=True) as db:
            asset = self.gallery._decode(self.gallery._asset_row(db,self.owner,identifier,include_trashed=False))
            if asset['media_type'] != MIME: raise GalleryError('character_unavailable','Character required.')
            body=asset['metadata'];a=next((a for a in body['appearances'] if a['id']==appearance_id),None)
            if a is None: raise GalleryError('character_appearance_missing','The original appearance was removed; image remains in Output.')
            if [appearance_id,run_id,artifact_id] in body.get('removed_generated_images',[]):
                return {'id':identifier,**body}
            images=a.setdefault('generated_images',[])
            if any(i['artifact_id']==artifact_id and i['run_id']==run_id for i in images):
                return {'id':identifier,**body}
            if len(images)>=100: raise GalleryError('character_images_full','This appearance already contains 100 generated images.')
            images.append({'asset_id':image['id'],'content_hash':image['content_hash'],'artifact_id':artifact_id,
                'run_id':run_id,'appearance_revision':appearance_revision,'parameters':parameters or {},'created_at':utc_now_text()})
            body['revision']+=1;body['updated_at']=utc_now_text()
            db.execute('UPDATE gallery_assets SET metadata_json=?,updated_at=? WHERE id=? AND owner_user_id=?',
                (json.dumps(body,ensure_ascii=False),body['updated_at'],identifier,self.owner))
            self.gallery._append_event(db,event_type='gallery.character.image_added',subject_id=identifier,owner_user_id=self.owner,payload={'run_id':run_id})
        return {'id':identifier,**body}

    def remove_generated(self, identifier, appearance_id, artifact_id, *, revision):
        with self.gallery.database.transaction(write=True) as db:
            asset=self.gallery._decode(self.gallery._asset_row(db,self.owner,identifier,include_trashed=False))
            body=asset['metadata']
            if asset['media_type']!=MIME or body.get('schema')!=SCHEMA:
                raise GalleryError('character_unavailable','Active character required.')
            if body['revision']!=revision:
                raise GalleryError('character_revision_conflict','Character changed. Reload before removing an image.')
            a=next((a for a in body['appearances'] if a['id']==appearance_id),None)
            if a is None:raise GalleryError('character_appearance_missing','Appearance unavailable.')
            matches=[i for i in a.get('generated_images',[]) if i['artifact_id']==artifact_id]
            if not matches:return {'id':identifier,**body}
            removed=body.setdefault('removed_generated_images',[])
            if len(removed)+len(matches)>5000:raise GalleryError('character_history_full','Image removal history is full.')
            for image in matches:
                key=[appearance_id,image['run_id'],image['artifact_id']]
                if key not in removed:removed.append(key)
            a['generated_images']=[i for i in a['generated_images'] if i['artifact_id']!=artifact_id]
            body['revision']+=1;body['updated_at']=utc_now_text()
            db.execute('UPDATE gallery_assets SET metadata_json=?,updated_at=? WHERE id=? AND owner_user_id=?',
                (json.dumps(body,ensure_ascii=False),body['updated_at'],identifier,self.owner))
            self.gallery._append_event(db,event_type='gallery.character.image_removed',subject_id=identifier,owner_user_id=self.owner,payload={'appearance_id':appearance_id,'artifact_id':artifact_id})
        return {'id':identifier,**body}
