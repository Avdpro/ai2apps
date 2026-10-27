"""Owner-authored public snapshots. No conversion of visitor identity to Local authority."""
import copy
import json
import os
from pathlib import PurePosixPath, Path
from urllib.parse import urlsplit

from ai2apps.core import utc_now_text

DEFAULT = {'title': '我的访客空间', 'description': '', 'theme': 'violet', 'cards': []}


def app_gateway_ready():
    if 'AI2APPS_VISITOR_APP_GATEWAY_READY' in os.environ:
        return os.environ['AI2APPS_VISITOR_APP_GATEWAY_READY'] == '1'
    descriptor = os.environ.get('AI2APPS_RUN_DESCRIPTOR_PATH', '')
    if not descriptor or not Path(descriptor).is_absolute():
        return False
    try:
        config = Path(descriptor).parent.parent / 'config' / 'visitor-space-gateway.json'
        return json.loads(config.read_text()) == {'enabled': True, 'protocol': 'personal-space-anonymous-v1'}
    except (OSError, ValueError):
        return False


def validate_document(value):
    if not isinstance(value, dict) or set(value) - {'title', 'description', 'theme', 'cards'}:
        raise ValueError('空间内容格式不正确')
    result = {}
    for key, limit in [('title', 80), ('description', 1000)]:
        text = value.get(key, '')
        if not isinstance(text, str) or len(text) > limit or (key == 'title' and not text.strip()):
            raise ValueError('名称或简介长度不正确')
        result[key] = text.strip()
    result['theme'] = value.get('theme', 'violet')
    if result['theme'] not in {'violet', 'ocean', 'sand'}:
        raise ValueError('未知主题')
    cards = value.get('cards', [])
    if not isinstance(cards, list) or len(cards) > 30:
        raise ValueError('最多添加 30 张卡片')
    result['cards'] = [validate_card(card) for card in cards]
    return result


CARD_FIELDS = {
    'text': set(), 'link': {'url', 'coverId'}, 'app': {'appKey'},
    'image': {'assetId', 'fit'}, 'video': {'assetId', 'coverId'},
    'html': {'assetId', 'height', 'coverId', 'autoload'}, 'article': {'body', 'coverId'},
    'carousel': {'cards', 'autoplay', 'interval'},
}

def validate_card(card, nested=False):
    import re
    if not isinstance(card, dict) or card.get('kind') not in CARD_FIELDS:
        raise ValueError('未知卡片类型')
    kind = card['kind']
    if set(card) - ({'kind', 'title', 'text', 'hidden'} | CARD_FIELDS[kind]):
        raise ValueError('卡片格式不正确')
    out = {'kind': kind, 'hidden': card.get('hidden', False)}
    if type(out['hidden']) is not bool:
        raise ValueError('卡片显示设置不正确')
    for key, limit in [('title',100), ('text',2000)]:
        value = card.get(key, '')
        if not isinstance(value,str) or len(value)>limit:
            raise ValueError('卡片文字过长')
        out[key] = value
    for key in ('assetId', 'coverId'):
        if key in CARD_FIELDS[kind]:
            value = card.get(key, '')
            if not isinstance(value,str) or (value and not re.fullmatch(r'[a-f0-9]{64}',value)):
                raise ValueError('素材标识不正确')
            out[key] = value
    if kind == 'link':
        url = card.get('url','')
        if not isinstance(url,str) or len(url)>2048:
            raise ValueError('链接格式不正确')
        parsed=urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('链接必须是无凭据的 HTTPS 地址')
        out['url']=url
    if kind == 'app':
        key=card.get('appKey')
        if not isinstance(key,str) or not key or len(key)>200:
            raise ValueError('请选择开放应用')
        out['appKey']=key
    if kind == 'image':
        out['fit']=card.get('fit','contain')
        if out['fit'] not in {'contain','cover'}:
            raise ValueError('图片显示方式不正确')
    if kind == 'html':
        out['autoload']=card.get('autoload',False)
        if type(out['autoload']) is not bool: raise ValueError('自动加载设置不正确')
        out['height']=card.get('height',360)
        if type(out['height']) is not int or not 160<=out['height']<=800:
            raise ValueError('HTML 高度须为 160–800 像素')
    if kind == 'article':
        body=card.get('body','')
        if not isinstance(body,str) or len(body.encode('utf-8'))>1024*1024:
            raise ValueError('稿件不能超过 1 MB')
        out['body']=body
    if kind == 'carousel':
        children=card.get('cards',[])
        if nested or not isinstance(children,list) or len(children)>8:
            raise ValueError('轮播最多 8 张卡片，不能嵌套轮播')
        out['cards']=[validate_card(c,True) for c in children]
        out['autoplay']=card.get('autoplay',False)
        out['interval']=card.get('interval',5)
        if type(out['autoplay']) is not bool or type(out['interval']) is not int or not 3<=out['interval']<=30:
            raise ValueError('轮播间隔须为 3–30 秒')
    return out

def walk_cards(cards):
    for card in cards:
        yield card
        if card['kind']=='carousel':
            yield from walk_cards(card.get('cards',[]))


class VisitorSpaceStore:
    def __init__(self, database):
        self.database = database

    def get(self, installation):
        with self.database.transaction() as c:
            row = c.execute('SELECT * FROM visitor_spaces WHERE installation_id=?', (installation,)).fetchone()
        if row is None:
            return {'enabled': False, 'version': 0, 'revision': 0, 'epoch': 0,
                    'draft': copy.deepcopy(DEFAULT), 'published': None}
        return {'enabled': bool(row['enabled']), 'version': row['version'], 'revision': row['revision'],
                'epoch': row['epoch'], 'draft': json.loads(row['draft']),
                'published': json.loads(row['published']) if row['published'] else None}

    def update(self, installation, expected, *, draft=None, enabled=None, published=None):
        with self.database.transaction(write=True) as c:
            row = c.execute('SELECT * FROM visitor_spaces WHERE installation_id=?', (installation,)).fetchone()
            version = row['version'] if row else 0
            if type(expected) is not int or expected != version:
                raise ValueError('页面已被其他窗口修改，请刷新后重试')
            current_draft = json.loads(row['draft']) if row else copy.deepcopy(DEFAULT)
            current_pub = json.loads(row['published']) if row and row['published'] else None
            was_enabled = bool(row['enabled']) if row else False
            now_enabled = was_enabled if enabled is None else enabled
            if type(now_enabled) is not bool:
                raise ValueError('开关格式不正确')
            if now_enabled and not (published or current_pub):
                raise ValueError('请先发布空间内容')
            revision = (row['revision'] if row else 0) + int(published is not None)
            epoch = (row['epoch'] if row else 0) + int(now_enabled != was_enabled)
            c.execute('''INSERT INTO visitor_spaces VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(installation_id) DO UPDATE SET enabled=excluded.enabled,
                version=excluded.version,revision=excluded.revision,epoch=excluded.epoch,
                draft=excluded.draft,published=excluded.published,updated_at=excluded.updated_at''',
                (installation, int(now_enabled), version+1, revision, epoch,
                 json.dumps(validate_document(draft) if draft is not None else current_draft),
                 json.dumps(published or current_pub) if (published or current_pub) else None, utc_now_text()))
        return self.get(installation)


def eligible_apps(manager, principal):
    from ai2apps.extensions.models import UnitKind
    result = []
    for app in manager.list_apps(principal=principal):
        if app.get('source') != 'installed':
            continue
        effective = manager.repository.effective(UnitKind.APP, app['app_key'])
        if not effective:
            continue
        package = manager.repository.package(effective.upstream_digest)
        entry = package.manifest.get('open_entry')
        if (not isinstance(entry, dict) or entry.get('kind') != 'sandbox'
                or entry.get('capabilities', []) != [] or effective.resources):
            continue
        resource = entry.get('resource')
        if not isinstance(resource, str) or resource.startswith('/') or '\\' in resource:
            continue
        if not any(item.get('path') == resource for item in package.file_index):
            continue
        root = str(PurePosixPath(resource).parent)
        if root in {'.', '/'} or '..' in PurePosixPath(root).parts:
            continue
        result.append({'appKey': app['app_key'], 'title': app.get('display_name', app['app_key']),
                       'digest': effective.effective_digest, 'entry': entry['resource'], 'root': root})
    return result


def build_snapshot(document, apps, assets=None):
    result = validate_document(document)
    result['cards'] = [card for card in result['cards'] if not card['hidden']]
    by_key = {app['appKey']: app for app in apps}
    for card in result['cards']:
        if card['kind']=='carousel':
            card['cards']=[c for c in card['cards'] if not c['hidden']]
            if not card['cards']: raise ValueError('轮播至少需要一张可见卡片')
    for card in walk_cards(result['cards']):
        if card['kind'] in {'image','video','html'} and not card.get('assetId'):
            raise ValueError('请先选择卡片素材')
        for key in ('assetId','coverId'):
            if card.get(key):
                if assets is None: raise ValueError('素材服务不可用')
                metadata, _ = assets.get(card[key])
                expected = 'image' if key=='coverId' else card['kind']
                if metadata['kind'] != expected: raise ValueError('素材类型与卡片不一致')
        if card['kind'] == 'app':
            app = by_key.get(card['appKey'])
            if app is None:
                raise ValueError('应用没有可发布的零权限 Sandbox Open-Entry')
            if not app_gateway_ready():
                raise ValueError('访客应用通道尚未部署，暂时只能发布文字和链接')
            card['binding'] = {k: app[k] for k in ('digest', 'entry', 'root')}
    return result


def resolve_resource(manager, card, resource):
    from ai2apps.extensions.models import UnitKind
    safe = PurePosixPath(resource)
    binding = card['binding']
    if (not resource or resource.startswith('/') or '\\' in resource or '..' in safe.parts
            or not resource.startswith(binding['root'] + '/')):
        raise ValueError('Resource is outside the Open-Entry')
    with manager.database.transaction() as c:
        enabled = c.execute("SELECT 1 FROM app_definitions WHERE package_id=? AND effective_digest=? AND status='enabled' AND source='installed'",
                            (card['appKey'], binding['digest'])).fetchone()
    if enabled is None:
        raise ValueError('Published App is disabled or removed')
    effective = manager.repository.effective(UnitKind.APP, card['appKey'])
    if not effective or effective.effective_digest != binding['digest'] or effective.resources:
        raise ValueError('Published App changed; republish required')
    package = manager.repository.package(effective.upstream_digest)
    indexed = next((x for x in package.file_index if x.get('path') == resource), None)
    if indexed is None:
        raise ValueError('Resource not published')
    return manager._verified_stored_resource(Path(package.store_path), resource, indexed)
