"""Contract 1.3 custom notification normalization; no network or credential access."""
from __future__ import annotations
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit, unquote, parse_qsl

CUSTOM_LIMITS = dict(request_bytes=32768, title_code_points=160, body_code_points=4000,
                    group_key_code_points=160, app_id_characters=160, route_characters=80,
                    resource_id_code_points=256, url_characters=2048, apns_bytes=4096)


def opaque(value, maximum):
    if (not isinstance(value, str) or not value.strip() or len(value) > maximum
            or any(unicodedata.category(c) in ('Cc', 'Cf', 'Cs') for c in value)):
        raise ValueError('Invalid notification reference')
    return value


def plain(value, maximum, paragraphs=False):
    if not isinstance(value, str) or any(unicodedata.category(c) == 'Cs' for c in value):
        raise ValueError('Invalid notification text')
    value = value.replace('\r\n', '\n').replace('\r', '\n')
    value = ''.join(c if c in '\u200c\u200d' or unicodedata.category(c) not in ('Cc','Cf')
                    else '\n' if paragraphs and c == '\n' else ' ' for c in value)
    value = '\n'.join(' '.join(line.split()) for line in value.split('\n'))
    value = re.sub(r'\n{3,}', '\n\n', value).strip()
    if not value.replace('\u200c','').replace('\u200d','').strip() or len(value) > maximum:
        raise ValueError('Invalid notification text length')
    return value


def https_url(value):
    opaque(value, 2048)
    try:
        if re.search(r'\s|\\|%(?![0-9a-fA-F]{2})', value):
            raise ValueError('Invalid notification URL')
        decoded = unquote(value, errors='strict')
        if any(unicodedata.category(c) in ('Cc','Cf','Cs') for c in decoded):
            raise ValueError('Invalid notification URL')
        u = urlsplit(value)
        if u.scheme.lower() != 'https' or not value.lower().startswith('https://') or not u.hostname or u.username or u.password:
            raise ValueError('Invalid notification URL')
        _ = u.port
        sensitive = {'access_token','refresh_token','token','handoff','code','password','secret','authorization','device_credential'}
        if any(k.lower() in sensitive for k, _ in parse_qsl(u.query) + parse_qsl(u.fragment)):
            raise ValueError('Sensitive notification URL')
        host = u.hostname.lower()
        path = re.sub('/+', '/', unquote(u.path, errors='strict'))
        if (host.startswith('device-') and host.endswith('.ai2apps.com')) or (host in ('coder.ai2apps.com','home.ai2apps.com') and re.match(r'^/(v1|api|admin)(/|$)', path, re.I)):
            raise ValueError('Protected notification URL')
        return urlunsplit(('https',u.netloc,u.path or '/',u.query,u.fragment))
    except (UnicodeError, ValueError) as error:
        raise ValueError('Invalid notification URL') from error


def target(value):
    if not isinstance(value, dict):
        raise ValueError('Invalid notification target')
    app = value.get('app_id')
    if not isinstance(app, str) or len(app)>160 or '..' in app or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)?',app):
        raise ValueError('Invalid notification App')
    if value.get('type') == 'https_url' and set(value) == {'type','app_id','url'}:
        return {**value, 'url': https_url(value['url'])}
    if value.get('type') != 'app_route' or set(value) != {'type','app_id','route','id'}:
        raise ValueError('Unsupported notification target')
    route = value['route']
    if not isinstance(route,str) or '..' in route or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,79}',route):
        raise ValueError('Invalid notification route')
    id = opaque(value['id'],256)
    if re.search(r'[\s/\\]',id) or id in ('.','..') or re.match(r'^(https?|javascript|data|file|vbscript|blob):',id,re.I):
        raise ValueError('Invalid notification resource')
    return dict(value)


def fields(content, destination, group_key=None, metadata=None):
    if not isinstance(content,dict) or set(content)-{'title','body','locale'}:
        raise ValueError('Invalid notification content')
    result = {'content': {'title':plain(content.get('title'),160), 'body':plain(content.get('body'),4000,True)},
              'target':target(destination), 'metadata':{}}
    if 'locale' in content:
        # BCP47 canonicalization is final on Cloud; reject malformed syntax locally.
        locale = content['locale']
        if not isinstance(locale,str) or len(locale)>35 or not re.fullmatch(r'[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*',locale):
            raise ValueError('Invalid notification locale')
        result['content']['locale'] = locale
    if group_key is not None:
        result['group_key'] = opaque(group_key,160)
    if metadata is not None:
        if not isinstance(metadata,dict) or set(metadata)-{'run_id','system_task_id'}:
            raise ValueError('Invalid notification metadata')
        result['metadata'] = {k:opaque(v,160 if k=='run_id' else 256) for k,v in metadata.items()}
    return result


def supports(capability, target_type):
    return (isinstance(capability,dict) and isinstance(capability.get('limits'),dict)
            and isinstance(capability.get('target_types'),list) and isinstance(capability.get('content_fields'),list)
            and capability.get('kind')=='app.custom'
            and type(capability.get('version')) is int and capability['version']==1
            and type(capability.get('content_schema_version')) is int and capability['content_schema_version']==1
            and capability.get('privacy_policy')=='system_preview_v1'
            and capability.get('app_authorization')=='trusted_host_v1'
            and capability.get('grouping') is True
            and target_type in capability.get('target_types',[])
            and {'title','body','locale'}.issubset(capability.get('content_fields',[]))
            and all(type(capability.get('limits',{}).get(k)) is int and capability['limits'][k]>=v for k,v in CUSTOM_LIMITS.items()))
