"""Gallery-owned portable character authoring data (not the one-image use document)."""
import copy
import hashlib
import io
import json
import uuid
from PIL import Image
from ai2apps.gallery.characters import Appearance, CharacterInput, Characters
from ai2apps.studio.portable_archive import encode, decode

SCHEMA = 'ai2apps.character-backup/v1'


def image_ids(character):
    result = set()
    for a in character['appearances']:
        result.update(a.get('reference_ids', []))
        if a.get('definition_image_id'): result.add(a['definition_image_id'])
        result.update(i['asset_id'] for i in a.get('generated_images', []))
    return result


def export_character(store, identifier, appearance_id=None):
    c = copy.deepcopy(store.get(identifier))
    if appearance_id:
        c['appearances'] = [a for a in c['appearances'] if a['id'] == appearance_id]
        if not c['appearances']: raise ValueError('Appearance unavailable')
        c['default_appearance_id'] = appearance_id
    # Only current authoring data; local revisions, deleted images and historical
    # credentials/Run receipts are not a portable dependency.
    c = {key:c[key] for key in ('name','description','aliases','appearances','default_appearance_id')}
    for a in c['appearances']:
        a['generated_images'] = [{'asset_id':i['asset_id'],'appearance_revision':i.get('appearance_revision',1)} for i in a.get('generated_images', [])]
    assets = {}
    for key in image_ids(c):
        asset, path = store.gallery.asset_path(store.owner, key)
        if asset['status'] != 'active' or not asset['media_type'].startswith('image/'):
            raise ValueError('Character image unavailable')
        assets[key] = path.read_bytes()
    return encode({'schema':SCHEMA,'character':c}, assets)


def inspect_character(data):
    document, assets = decode(data)
    if document.get('schema') != SCHEMA: raise ValueError('Choose a character backup ZIP')
    c = document.get('character')
    if not isinstance(c, dict) or not isinstance(c.get('appearances'),list): raise ValueError('Invalid character')
    # Validate complete data before importing any images.
    body = {k:v for k,v in c.items() if k in CharacterInput.model_fields}
    body['revision'] = 0
    body['appearances'] = [{k:v for k,v in a.items() if k in Appearance.model_fields} for a in c['appearances']]
    parsed = CharacterInput.model_validate(body)
    ids = [a.id for a in parsed.appearances]
    if len(ids) != len(set(ids)) or parsed.default_appearance_id and parsed.default_appearance_id not in ids:
        raise ValueError('Invalid appearance identities')
    for a in parsed.appearances:
        if a.approved and not (a.definition_image_id and a.summary.strip()): raise ValueError('Finalized appearance lacks definition')
    for a in c['appearances']:
        generated = a.get('generated_images', [])
        if not isinstance(generated,list) or len(generated)>100: raise ValueError('Too many generated images')
        for item in generated:
            if not isinstance(item,dict) or not isinstance(item.get('appearance_revision',1),int): raise ValueError('Invalid generated image')
    if image_ids(c) != set(assets): raise ValueError('Missing or unreferenced character image')
    return c, parsed, assets


def preview_character(data):
    c, _, assets = inspect_character(data)
    thumbnails=[]
    for a in c['appearances'][:12]:
        key=a.get('definition_image_id') or next(iter(a.get('reference_ids',[])),None)
        if key:
            import base64
            with Image.open(io.BytesIO(assets[key])) as image:
                image.thumbnail((180,180));out=io.BytesIO();image.convert('RGB').save(out,'JPEG',quality=75)
            thumbnails.append({'name':a['name'],'image':'data:image/jpeg;base64,'+base64.b64encode(out.getvalue()).decode()})
    return dict(name=c['name'],appearance_count=len(c['appearances']),image_count=len(assets),thumbnails=thumbnails)


def import_character(store, data):
    c, parsed, assets = inspect_character(data)
    body=parsed.model_dump();names={item['name'] for item in store.list()}
    base=body['name'];n=2
    while body['name'] in names: body['name']=base[:85]+f' ({n})';n+=1
    mapping={};created=[]
    try:
        for key,image in assets.items():
            with Image.open(io.BytesIO(image)) as source: mime=Image.MIME[source.format]
            asset,new=store.gallery.import_stream(store.owner,io.BytesIO(image),name='character-image'+{'image/png':'.png','image/jpeg':'.jpg','image/webp':'.webp'}[mime],media_type=mime,max_bytes=20*1024*1024)
            mapping[key]=asset['id']
            if new: created.append(asset['id'])
        appearance_map={a['id']:uuid.uuid4().hex for a in body['appearances']}
        for a in body['appearances']:
            a['id']=appearance_map[a['id']]
            a['reference_ids']=[mapping[key] for key in a['reference_ids']]
            a['definition_image_id']=mapping.get(a['definition_image_id'],'')
        body['default_appearance_id']=appearance_map.get(body['default_appearance_id'],'')
        saved=store.save(CharacterInput.model_validate(body))
        # Attach portable generated image inventory without carrying source Run IDs.
        by_new={a['id']:a for a in saved['appearances']}
        for a in c['appearances']:
            by_new[appearance_map[a['id']]]['generated_images']=[dict(asset_id=mapping[i['asset_id']],content_hash=hashlib.sha256(assets[i['asset_id']]).hexdigest(),artifact_id='import_'+uuid.uuid4().hex,run_id='portable-import',appearance_revision=i.get('appearance_revision',1),parameters={},created_at=saved['updated_at']) for i in a.get('generated_images',[])]
        with store.gallery.database.transaction(write=True) as db:
            db.execute('UPDATE gallery_assets SET metadata_json=? WHERE id=? AND owner_user_id=?',(json.dumps({k:v for k,v in saved.items() if k!='id'},ensure_ascii=False),saved['id'],store.owner))
        return saved
    except Exception:
        # Only new assets from this import, never pre-existing deduplicated images.
        if 'saved' in locals(): store.gallery.delete_asset(store.owner,saved['id'])
        for key in created: store.gallery.delete_asset(store.owner,key)
        raise
