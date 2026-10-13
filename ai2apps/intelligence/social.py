"""Conservative social-source scheduling, independent of browser control."""
import re
from urllib.parse import urlsplit, parse_qs, urlencode, unquote, quote


def youtube_url(value):
    u=urlsplit(value)
    if (u.hostname or '').lower() not in ('youtube.com','www.youtube.com','m.youtube.com','youtu.be'):
        return None
    parts=u.path.strip('/').split('/')
    if parts[0]=='results':
        params=parse_qs(u.query)
        query=params.get('search_query',[''])[0].strip()
        if not query or len(query)>300:raise ValueError('YouTube 搜索关键词需为 1–300 个字符')
        values={'search_query':query}
        if params.get('sp'):values['sp']=params['sp'][0]  # Preserve user-selected YouTube filters.
        return 'https://www.youtube.com/results?'+urlencode(values)
    if parts[0]=='hashtag':
        tag=unquote(parts[1]).strip() if len(parts)==2 else ''
        if not tag or len(tag)>100 or any(c.isspace() or c in '/?#' for c in tag):raise ValueError('无效的 YouTube 话题标签')
        return 'https://www.youtube.com/hashtag/'+quote(tag,safe='')
    if u.hostname=='youtu.be':video=parts[0]
    elif parts[0]=='watch':video=parse_qs(u.query).get('v',[''])[0]
    elif parts[0] in ('shorts','live') and len(parts)>1:video=parts[1]
    else:video=None
    if video is not None:
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}',video):raise ValueError('无效的 YouTube 视频地址')
        return 'https://www.youtube.com/watch?v='+video
    if parts[0].startswith('@') and len(parts[0])>1:
        root='/'+parts[0]
        tab=parts[1] if len(parts)>1 else 'videos'
    elif parts[0] in ('channel','user','c') and len(parts)>1 and parts[1]:
        root='/'+parts[0]+'/'+parts[1]
        tab=parts[2] if len(parts)>2 else 'videos'
    else:raise ValueError('请添加 YouTube 频道、搜索结果、话题或具体视频地址')
    if tab not in ('videos','shorts','streams'):tab='videos'
    return 'https://www.youtube.com'+root+'/'+tab


def weibo_url(value):
    u=urlsplit(value);host=(u.hostname or '').lower();parts=u.path.strip('/').split('/')
    if host not in ('weibo.com','www.weibo.com','s.weibo.com'):return None
    if host=='s.weibo.com':
        query=parse_qs(u.query).get('q',[''])[0].strip()
        if parts[0]!='weibo' or not query or len(query)>100:
            raise ValueError('请填写微博话题搜索地址或话题名称')
        return 'https://s.weibo.com/weibo?'+urlencode({'q':query})
    if len(parts)==1 and re.fullmatch(r'[0-9]{5,20}',parts[0]):return 'https://weibo.com/u/'+parts[0]
    if len(parts)==2 and parts[0]=='u' and re.fullmatch(r'[0-9]{5,20}',parts[1]):return 'https://weibo.com/u/'+parts[1]
    raise ValueError('微博账号请使用含数字 UID 的主页地址，例如 https://weibo.com/u/1234567890')


def xiaohongshu_search_url(value):
    u=urlsplit(value)
    if (u.hostname or '').lower() not in ('xiaohongshu.com','www.xiaohongshu.com') or u.path.rstrip('/') != '/search_result':
        return None
    query=parse_qs(u.query).get('keyword',[''])[0].strip()
    if not query or len(query)>300:
        raise ValueError('Xiaohongshu search requires 1–300 characters')
    return 'https://www.xiaohongshu.com/search_result?'+urlencode({'keyword':query,'source':'web_explore_feed'})


def site_key(source):
    host=(urlsplit(source['url']).hostname or '').lower()
    if host in ('youtube.com','www.youtube.com','m.youtube.com','youtu.be'):return 'youtube.com'
    if host in ('weibo.com','www.weibo.com','s.weibo.com'):return 'weibo.com'
    if xiaohongshu_search_url(source['url']):return 'xiaohongshu.com'
    if source.get('kind')=='social':return host.removeprefix('www.').removeprefix('m.')
    return ''


def x_targets(mode, values, sort='latest'):
    if sort not in ('latest','top'):raise ValueError('Invalid X search order')
    """Normalize bounded account/search/list inputs; each target stays independent."""
    if mode not in ('accounts', 'search', 'lists') or not 1 <= len(values) <= 20:
        raise ValueError('X requires 1–20 accounts, search queries or list URLs')
    normalized=[]
    for value in values:
        value=value.strip()
        if mode=='accounts':
            if '://' in value:
                u=urlsplit(value)
                if u.scheme not in ('http','https') or u.hostname not in ('x.com','www.x.com','twitter.com','www.twitter.com') or u.query or u.fragment or u.username or u.password or u.port:
                    raise ValueError('Invalid X account URL')
                value=u.path.strip('/')
            value=value.lstrip('@')
            if not re.fullmatch(r'[A-Za-z0-9_]{1,15}',value) or value.lower() in ('home','search','explore','settings','i','messages','notifications'):
                raise ValueError('Invalid X account')
            value=value.lower()
        elif mode=='lists':
            u=urlsplit(value)
            match=re.fullmatch(r'/i/lists/([0-9]{1,20})/?',u.path)
            if u.scheme not in ('http','https') or u.hostname not in ('x.com','www.x.com','twitter.com','www.twitter.com') or u.username or u.password or u.port or not match:
                raise ValueError('Invalid X list URL; use https://x.com/i/lists/<ID>')
            value='https://x.com/i/lists/'+match.group(1)
        elif not value or len(value)>300 or '\n' in value or '\r' in value:
            raise ValueError('X search query must contain 1–300 characters')
        if value not in normalized:normalized.append(value)
    urls=['https://x.com/'+value if mode=='accounts' else value if mode=='lists' else 'https://x.com/search?'+urlencode({'q':value,**({'f':'live'} if sort=='latest' else {})}) for value in normalized]
    return normalized,urls
