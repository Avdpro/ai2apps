"""Owner-scoped, offline Intelligence ZIP transfer with preview and conservative merge."""
import copy
import hashlib
import io
import json
import re
import uuid
import zipfile
from datetime import datetime, timezone
from . import article_content
from .models import ChannelInput, SourceInput, public_url
from .store import stamp

MAX_BYTES = 128 * 1024 * 1024
FORMAT = 'ai2apps.intelligence.backup'
TABLES = ('channels', 'sources', 'articles', 'pages', 'drafts', 'preferences', 'conversations', 'filtered_posts', 'runs', 'entity_dossiers', 'entity_leads')

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()

def state(db, owner):
    present = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return {t: [dict(r) for r in db.execute(f'SELECT * FROM {t} WHERE owner=? ORDER BY rowid', (owner,))] if t in present else [] for t in TABLES}

def origin(row, table, namespace):
    return json.loads(row['data']).get('_transfer_origin') or f'{namespace}:{table}:{row.get("id", row.get("url", row.get("article", "")))}'

def parse_time(value):
    if not value: return None
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.tzinfo is None: raise ValueError()
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        raise ValueError('时间必须包含时区 / Timestamp must include timezone') from None


def selected_rows(store, owner, channel_id=None, *, since=None, until=None, changes='updated'):
    start, end = parse_time(since), parse_time(until)
    if changes not in ('created', 'updated'): raise ValueError('Invalid change mode')
    if start and end and start >= end: raise ValueError('开始时间必须早于结束时间 / Invalid time range')
    with store.connect() as db:
        saved = state(db, owner)
    channels = {r['id'] for r in saved['channels'] if channel_id is None or r['id'] == channel_id}
    if channel_id and not channels:
        raise KeyError('Channel not found')
    selected = {t: [r for r in rows if (r['id'] in channels if t == 'channels' else r.get('channel') in channels)] for t, rows in saved.items()}
    if start or end:
        def within(article):
            keys = ('created_at',) if changes == 'created' else ('created_at', 'updated_at', 'content_updated_at')
            times = [parse_time(article[k]) for k in keys if article.get(k)]
            value = max(times) if times else None
            return value is not None and (not start or value >= start) and (not end or value < end)
        selected['articles'] = [r for r in selected['articles'] if within(json.loads(r['data']))]
        ids = {r['id'] for r in selected['articles']}
        urls = set()
        for row in selected['articles']:
            article = json.loads(row['data'])
            for version in [article, *article.get('versions', [])]:
                urls.update(ref['url'] for ref in [*version.get('sources', []), *version.get('related_sources', [])] if ref.get('url'))
        selected['pages'] = [r for r in selected['pages'] if r['url'] in urls]
        selected['preferences'] = [r for r in selected['preferences'] if r['article'] in ids]
        selected['drafts'] = [r for r in selected['drafts'] if (lambda d: bool(d.get('evidence')) and {e['id'] for e in d['evidence']}.issubset(ids))(json.loads(r['data']))]
        for table in ('conversations', 'runs', 'filtered_posts'): selected[table] = []
    articles = {r['id'] for r in selected['articles']}
    namespace = digest([str(store.root.resolve()), owner])[:32]
    # Entity dossiers are account-scoped; include only evidence inside the selection.
    entities = []
    facts = set()
    for row in saved['entity_dossiers']:
        value = json.loads(row['data'])
        value['facts'] = [f for f in value.get('facts', []) if f.get('article_id') in articles]
        if not value['facts'] and (channel_id is not None or start or end):
            continue
        if channel_id is not None or start or end: value['attributes'] = [a for a in value.get('attributes', []) if a.get('article_id') in articles]
        facts.update(f['id'] for f in value['facts'])
        entities.append({**row, 'data': json.dumps(value)})
    selected['entity_dossiers'] = entities
    entity_ids = {r['id'] for r in entities}
    selected['entity_leads'] = [r for r in saved['entity_leads'] if (lambda d: d.get('entity_id') in entity_ids and set(d.get('fact_ids', [])).issubset(facts))(json.loads(r['data']))]
    for table, rows in selected.items():
        for row in rows:
            value = json.loads(row['data'])
            value['_transfer_origin'] = origin(row, table, namespace)
            if table == 'channels':
                value = {k: v for k, v in value.items() if k in {*ChannelInput.model_fields, 'created_at', 'updated_at', '_transfer_origin', 'entity_taxonomy'}}
            if table == 'sources':
                value = {k: v for k, v in value.items() if k in {*SourceInput.model_fields, '_transfer_origin'}}
                value.pop('profile_key', None)
                value.pop('list_agent_generation_id', None)
                value.pop('article_agent_generation_id', None)
            if table == 'runs':
                value = {k: v for k, v in value.items() if k in ('message', 'started_at', 'finished_at', 'created_at', 'article_count', '_transfer_origin')}
            if table in ('drafts', 'conversations'):
                for k in ('run_id', 'session_id', 'interaction_id', 'pending', 'request_id'):
                    value.pop(k, None)
            row['data'] = value
            row.pop('owner', None)
    return selected


def export_backup(store, owner, channel_id=None, *, since=None, until=None, changes='updated'):
    selected = selected_rows(store, owner, channel_id, since=since, until=until, changes=changes)
    from .manual_import import asset_path
    tokens = set(re.findall(r'/v1/platform/intelligence/imports/([0-9a-f]{64})/', json.dumps(selected)))
    blobs = {}
    for token in tokens:
        path = asset_path(store, owner, token)
        if not path.is_file(): raise ValueError('Local article attachment is missing')
        blob = path.read_bytes()
        if hashlib.sha256(blob).hexdigest() != token: raise ValueError('Attachment integrity check failed')
        blobs[token] = blob
    payload = {'format': FORMAT, 'version': 1, 'exported_at': stamp(), 'image_mode': 'remote_references', 'tables': selected, 'attachments': list(blobs), 'scope': {'since': since, 'until': until, 'changes': changes, 'mode': 'recent' if since or until else 'all'}}
    raw = json.dumps(payload, ensure_ascii=False).encode()
    if len(raw) + sum(map(len, blobs.values())) > MAX_BYTES:
        raise ValueError('Backup exceeds 128 MiB')
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('intelligence.json', raw)
        for token, blob in blobs.items(): archive.writestr('attachments/' + token, blob)
        archive.writestr('README.txt', 'Intelligence backup v1. Images retain original remote URLs; this is not an offline image archive. No credentials or running tasks are migrated.\n')
    if out.tell() > MAX_BYTES: raise ValueError('Backup exceeds 128 MiB')
    return out.getvalue()

def parse_backup(content):
    try:
        if len(content) > MAX_BYTES:
            raise ValueError('Backup exceeds 128 MiB')
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            entries = z.infolist()
            if len(entries) > 100002 or len({e.filename for e in entries}) != len(entries) or any(e.filename not in ('intelligence.json', 'README.txt') and not re.fullmatch(r'attachments/[0-9a-f]{64}', e.filename) for e in entries) or sum(e.file_size for e in entries) > MAX_BYTES:
                raise ValueError('Invalid archive entries or size')
            data = json.loads(z.read('intelligence.json'))
            blobs = {}
            for token in data.get('attachments', []):
                if not re.fullmatch(r'[0-9a-f]{64}', token): raise ValueError('Invalid attachment identity')
                blob = z.read('attachments/' + token)
                if len(blob) > 20 * 1024 * 1024 or hashlib.sha256(blob).hexdigest() != token: raise ValueError('Invalid attachment hash or size')
                blobs[token] = blob
            referenced = set(re.findall(r'/v1/platform/intelligence/imports/([0-9a-f]{64})/', json.dumps(data['tables'])))
            if referenced != set(blobs): raise ValueError('Missing or unreferenced attachments')
        if data['format'] != FORMAT or data['version'] != 1 or set(data['tables']) != set(TABLES):
            raise ValueError('Unsupported Intelligence backup')
        tables = data['tables']
        if sum(len(rows) for rows in tables.values()) > 100000:
            raise ValueError('Too many records')
        channel_ids = {r['id'] for r in tables['channels']}
        article_ids = {r['id'] for r in tables['articles']}
        for table, rows in tables.items():
            seen = set()
            for row in rows:
                value = row['data']
                marker = value['_transfer_origin']
                if not isinstance(marker, str) or not marker or len(marker) > 512 or marker in seen:
                    raise ValueError('Invalid or duplicate transfer identity')
                seen.add(marker)
                if 'owner' in row or not isinstance(value, dict):
                    raise ValueError('Invalid record')
                if table not in ('channels', 'entity_dossiers', 'entity_leads') and row['channel'] not in channel_ids:
                    raise ValueError('Missing channel reference')
                if table == 'channels': ChannelInput.model_validate(value)
                if table == 'sources': SourceInput.model_validate(value)
                if table == 'articles':
                    for field in ('title', 'summary', 'body'):
                        if not isinstance(value.get(field), str): raise ValueError('Invalid article text')
                    if not isinstance(value.get('sources'), list) or not isinstance(value.get('images', []), list): raise ValueError('Invalid article references')
                    if not isinstance(value.get('created_at'), str) or not isinstance(value.get('updated_at'), str): raise ValueError('Missing article timestamps')
                    for ref in value['sources']:
                        if not isinstance(ref, dict) or not isinstance(ref.get('url'), str): raise ValueError('Invalid source reference')
                        if not ref['url'].startswith('/v1/platform/intelligence/imports/'): public_url(ref['url'])
                    article_content.validate_content(value)
                    for conflict in value.get('_transfer_conflicts', []):
                        if not isinstance(conflict.get('hash'), str) or not isinstance(conflict.get('data'), dict): raise ValueError('Invalid conflict version')
                        article_content.validate_content(conflict['data'])
                if table == 'pages': public_url(row['url'])
                if table == 'preferences' and row['article'] not in article_ids: raise ValueError('Missing article reference')
        for table in ('channels', 'sources', 'articles', 'drafts', 'runs', 'entity_dossiers', 'entity_leads'):
            ids = [r['id'] for r in tables[table]]
            if len(ids) != len(set(ids)) or any(not isinstance(i, str) or not i or len(i) > 256 for i in ids):
                raise ValueError('Invalid record IDs')
        return tables, blobs
    except (KeyError, TypeError, AttributeError, zipfile.BadZipFile, NotImplementedError, UnicodeError, json.JSONDecodeError, RuntimeError) as e:
        raise ValueError('Invalid Intelligence backup') from e

def rewrite(value, mapping):
    if isinstance(value, str): return mapping.get(value, value)
    if isinstance(value, list): return [rewrite(v, mapping) for v in value]
    if isinstance(value, dict): return {k: rewrite(v, mapping) if k != '_transfer_origin' else v for k, v in value.items()}
    return value

def semantic(value):
    return {k: v for k, v in value.items() if k not in ('id', 'channel_id', '_transfer_origin', '_transfer_conflicts', 'created_at', 'updated_at', 'run_id', 'read', 'favorite', 'feedback', 'versions')}

def merge_backup(store, owner, content, expected=None):
    written = []
    try:
        return _merge_backup(store, owner, content, expected, written)
    except BaseException:
        for path in written: path.unlink(missing_ok=True)
        raise


def _merge_backup(store, owner, content, expected, written):
    incoming, blobs = parse_backup(content)
    with store.connect() as db:
        local = state(db, owner)
        mapping, matches = {}, {}
        # Prefer durable provenance, then exact existing ID; channel names bridge installations.
        for table in ('channels', 'sources', 'articles', 'drafts', 'runs', 'entity_dossiers', 'entity_leads'):
            namespace = digest([str(store.root.resolve()), owner])[:32]
            by_origin = {origin(r, table, namespace): r for r in local[table]}
            by_id = {r['id']: r for r in local[table]}
            for row in incoming[table]:
                old = by_origin.get(row['data']['_transfer_origin'])
                if not old and row['id'] in by_id:
                    # Original backups can return to their source without creating duplicates.
                    candidate = by_id[row['id']]
                    if table == 'channels' or candidate.get('channel') == mapping.get(row.get('channel')):
                        old = candidate
                if not old and table == 'channels':
                    found = [r for r in local[table] if json.loads(r['data']).get('name', '').casefold() == row['data']['name'].casefold()]
                    if len(found) > 1: raise ValueError('同名频道不唯一，请先重命名 / Ambiguous channel name')
                    old = next(iter(found), None)
                if not old and table == 'sources':
                    def source_key(d):
                        return (public_url(d['url']), d.get('kind', 'website'), d.get('x_mode', ''), tuple(d.get('x_values', [])))
                    old = next((r for r in local[table] if r['channel'] == mapping[row['channel']] and source_key(json.loads(r['data'])) == source_key(row['data'])), None)
                if not old and table == 'articles':
                    old = next((r for r in local[table] if r['channel'] == mapping[row['channel']] and semantic(json.loads(r['data'])) == semantic(row['data'])), None)
                if not old and table == 'entity_dossiers':
                    names = {str(v).casefold().strip() for v in [row['data'].get('name', ''), *row['data'].get('aliases', [])]} - {''}
                    candidates = [r for r in local[table] if (lambda d: d.get('kind') == row['data'].get('kind') and bool(names & {str(v).casefold().strip() for v in [d.get('name', ''), *d.get('aliases', [])]}))(json.loads(r['data']))]
                    if len(candidates) == 1: old = candidates[0]
                if not old and table == 'articles':
                    def article_key(d):
                        urls = tuple(sorted({s.get('url', '') for s in d.get('sources', []) if s.get('url')}))
                        return (d.get('manual_import', False), d.get('import_identity', ''), d.get('title', ''), urls)
                    key = article_key(row['data'])
                    candidates = [r for r in local[table] if r['channel'] == mapping[row['channel']] and article_key(json.loads(r['data'])) == key]
                    if key[-1] and len(candidates) == 1: old = candidates[0]
                mapping[row['id']] = old['id'] if old else uuid.uuid5(uuid.NAMESPACE_URL, owner + ':' + row['data']['_transfer_origin']).hex
                matches[(table, row['id'])] = old
        for row in incoming['entity_dossiers']:
            old = matches[('entity_dossiers', row['id'])]
            existing_facts = json.loads(old['data']).get('facts', []) if old else []
            for fact in row['data'].get('facts', []):
                same = next((f for f in existing_facts if f.get('article_id') == mapping.get(fact.get('article_id')) and f.get('quote') == fact.get('quote')), None)
                mapping[fact['id']] = same['id'] if same else uuid.uuid5(uuid.NAMESPACE_URL, owner + ':' + row['data']['_transfer_origin'] + ':' + fact['id']).hex
        section_maps, channel_sections = {}, {}
        for row in incoming['channels']:
            old = matches[('channels', row['id'])]
            sections = copy.deepcopy(json.loads(old['data']).get('sections', [])) if old else []
            names = {v['name'].casefold(): v['id'] for v in sections}
            used = {v['id'] for v in sections}
            section_maps[row['id']] = {}
            for section in row['data'].get('sections') or []:
                sid = names.get(section['name'].casefold())
                if not sid:
                    sid = section['id'] if section['id'] not in used else 's_' + uuid.uuid4().hex[:24]
                    sections.append({**section, 'id': sid});used.add(sid);names[section['name'].casefold()] = sid
                section_maps[row['id']][section['id']] = sid
            if len(sections) > 32: raise ValueError('合并后栏目超过 32 个 / Too many sections after merge')
            channel_sections[row['id']] = sections
        affected = {mapping[r['id']] for r in incoming['channels']}
        scoped = {t: [r for r in rows if (r['id'] in affected if t == 'channels' else r.get('channel') in affected or t in ('entity_dossiers', 'entity_leads'))] for t, rows in local.items()}
        fingerprint = digest([hashlib.sha256(content).hexdigest(), scoped])
        if expected is not None and expected != fingerprint:
            raise ValueError('预览后备份或目标数据已变化，请重新预览 / Backup or target data changed; preview again')
        if any(r['channel'] in affected and r['status'] == 'running' for r in local['runs']):
            raise ValueError('目标频道正在更新，请完成后再导入 / Target channel is updating')
        result = {'expected': fingerprint, 'create': 0, 'update': 0, 'keep': 0, 'conflict': 0, 'items': [], 'image_mode': 'remote_references'}
        writes = []
        for table, rows in incoming.items():
            for row in rows:
                value = rewrite(copy.deepcopy(row['data']), mapping)
                target = mapping.get(row.get('id'))
                channel = mapping.get(row.get('channel'))
                old = matches.get((table, row.get('id')))
                keys = {'owner': owner}
                if table in ('pages', 'preferences', 'conversations', 'filtered_posts'):
                    keys['channel'] = channel
                    if table == 'pages': keys['url'] = public_url(row['url'])
                    elif table == 'preferences': keys['article'] = mapping[row['article']]
                    else: keys['id'] = uuid.uuid5(uuid.NAMESPACE_URL, owner + ':' + value['_transfer_origin']).hex
                    old = next((r for r in local[table] if all(r.get(k) == v for k, v in keys.items())), None)
                else:
                    keys['id'] = target
                    if 'channel' in row: keys['channel'] = channel
                if table in ('conversations', 'filtered_posts') and 'id' in value: value['id'] = keys['id']
                if table == 'articles' and value.get('section_id'):
                    value['section_id'] = section_maps[row['channel']].get(value['section_id'])
                if table == 'entity_dossiers':
                    for field in ('facts', 'aliases', 'attributes'): value.setdefault(field, [])
                if table == 'channels':
                    value['sections'] = channel_sections[row['id']]
                    value.update(interval_hours=0, knowledge_bucket_ids=[])
                    for k in ('schedule_anchor', 'next_due', 'last_run', 'knowledge_sync', 'hot_topics'):
                        value.pop(k, None)
                if table == 'sources':
                    value['profile_key'] = 'default'
                    value['enabled'] = False
                    for k in list(value):
                        if k.startswith('social_') and k != 'social_interval_hours' or k in ('list_agent_generation_id', 'article_agent_generation_id'):
                            value.pop(k, None)
                if table == 'runs':
                    value = {k: value[k] for k in ('message', 'started_at', 'finished_at', 'created_at', 'article_count', '_transfer_origin') if k in value}
                    value.update(imported_history=True)
                # Exported drafts are text only, never resumable generation/interaction jobs.
                if table == 'drafts':
                    for k in ('run_id', 'session_id', 'interaction_id', 'pending', 'request_id'):
                        value.pop(k, None)
                action = 'create'
                if old:
                    existing = json.loads(old['data'])
                    action = 'keep'
                    if table in ('articles', 'drafts') and semantic(existing) != semantic(value):
                        conflicts = existing.get('_transfer_conflicts', [])
                        signature = digest(semantic(value))
                        if not any(c['hash'] == signature for c in conflicts):
                            existing['_transfer_conflicts'] = [*conflicts, {'hash': signature, 'imported_at': stamp(), 'data': value}]
                            value = existing
                            action = 'conflict'
                    if table == 'entity_dossiers':
                        merged = copy.deepcopy(existing)
                        known = {f['id'] for f in merged.get('facts', [])}
                        merged['facts'] = [*merged.get('facts', []), *(f for f in value.get('facts', []) if f['id'] not in known)]
                        merged['aliases'] = list(dict.fromkeys([*merged.get('aliases', []), *value.get('aliases', [])]))
                        existing_attributes = merged.get('attributes', [])
                        signatures = {digest(a) for a in existing_attributes}
                        merged['attributes'] = [*existing_attributes, *(a for a in value.get('attributes', []) if digest(a) not in signatures)]
                        if merged != existing:
                            value = merged
                            action = 'update'
                    if table == 'channels' and existing.get('sections', []) != channel_sections[row['id']]:
                        value = {**existing, 'sections': channel_sections[row['id']]}
                        action = 'update'
                    if action == 'keep':
                        result['keep'] += 1
                        continue
                result[action] += 1
                result['items'].append({'type': table, 'title': value.get('title', value.get('name', row.get('id', row.get('url', '')))), 'action': action})
                fields = {**keys, 'data': json.dumps(value, ensure_ascii=False)}
                if table == 'pages': fields['hash'] = row['hash']
                if table == 'runs': fields.update(status='completed' if row['status'] == 'completed' else 'interrupted', updated=0)
                writes.append((table, fields, old))
        for channel in affected:
            existing_count = sum(r['channel'] == channel for r in local['sources'])
            incoming_count = sum(t == 'sources' and f.get('channel') == channel and not old for t, f, old in writes)
            if existing_count + incoming_count > 12: raise ValueError('合并后频道信息源超过 12 个 / Too many sources after merge')
        if expected is None: return result
        # Fresh stores may not have initialized the entity owner repository yet.
        db.execute('CREATE TABLE IF NOT EXISTS entity_dossiers(owner TEXT NOT NULL,id TEXT NOT NULL,data TEXT NOT NULL,PRIMARY KEY(owner,id))')
        db.execute('CREATE TABLE IF NOT EXISTS entity_leads(owner TEXT NOT NULL,id TEXT NOT NULL,data TEXT NOT NULL,PRIMARY KEY(owner,id))')
        from .manual_import import asset_path
        for token, blob in blobs.items():
            path = asset_path(store, owner, token)
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                # Exclusive creation avoids replacing another import's immutable blob.
                try:
                    with path.open('xb') as stream:
                        written.append(path)
                        stream.write(blob)
                except FileExistsError: pass
            if hashlib.sha256(path.read_bytes()).hexdigest() != token: raise ValueError('Local attachment hash mismatch')
        for table, fields, old in writes:
            if old:
                db.execute(f'UPDATE {table} SET data=? WHERE owner=? AND id=?', (fields['data'], owner, fields['id']))
            else:
                columns = ','.join(fields)
                db.execute(f'INSERT INTO {table} ({columns}) VALUES ({",".join("?" for _ in fields)})', tuple(fields.values()))
        return result
