"""Local-owned browser SDK. Page scripts only inspect or edit the DOM.

Timing, native input, navigation, context ownership and result assembly all run
in Local, using the protocol-transparent native BiDi transport.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import random
import re
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

_ROOT = Path(__file__).resolve().parents[1]
_HELPERS = json.loads(Path(__file__).with_name('dom_helpers.json').read_text())


class BackgroundPage:
    def __init__(self, connection, context_id, *, interaction_mode=None):
        if not context_id:
            raise ValueError('An explicit browser context is required')
        self.connection = connection
        self.context_id = context_id
        self.created_contexts = {}
        self.interaction_mode = interaction_mode or (lambda url: 'natural')
        self.pointer = (0, 0)

    async def call_json(self, source, args=(), timeout=30):
        arguments = json.dumps(args, ensure_ascii=False).replace('<', '\\u003c')
        result = await self.connection.command('script.callFunction', {
            'functionDeclaration': f'async function(){{const fn=({source});return JSON.stringify(await fn(...{arguments}));}}',
            'target': {'context': self.context_id}, 'awaitPromise': True,
        }, timeout=timeout)
        if result.get('type') == 'exception':
            raise RuntimeError(result.get('exceptionDetails', {}).get('text', 'Page script failed'))
        remote = result.get('result', {})
        if remote.get('type') in ('undefined', 'null'):
            return None
        value = remote.get('value')
        if not isinstance(value, str):
            raise RuntimeError('Browser returned invalid page data')
        return json.loads(value)

    async def helper(self, name, *args):
        return await self.call_json(_HELPERS[name], args)

    async def snapshot(self, max_text=20000):
        source = (_ROOT / 'web/static/js/browser_snapshot.js').read_text()
        result = await self.call_json(source, [{'maxItems': 150, 'maxText': max_text,
                                              'maxHtml': 60000, 'htmlMode': 'visible'}])
        result.update(text_length=len(result['text']), text_sample=result['text'])
        result['fingerprint'] = '|'.join(map(str, [result['url'], len(result['items']), len(result['text']), len(result['html'])]))
        return result

    async def validate_context(self):
        tree = await self.connection.command('browsingContext.getTree', {'maxDepth': 0})
        if not any(item['context'] == self.context_id for item in tree.get('contexts', [])):
            raise RuntimeError('The bound browser context no longer exists')

    async def wait_stable(self, timeout=10, require_content=False):
        deadline = time.monotonic() + timeout
        previous, stable = None, 0
        while time.monotonic() < deadline:
            page = await self.snapshot()
            if page['fingerprint'] == previous and (not require_content or page['text'] or page['items']):
                stable += 1
                if stable >= 2:
                    return {'stable': True, 'page': page}
            else:
                stable = 0
            previous = page['fingerprint']
            await asyncio.sleep(.5)
        return {'stable': False, 'page': await self.snapshot()}

    async def navigate(self, url, delay_ms=3000):
        await self.connection.command('browsingContext.navigate', {
            'context': self.context_id, 'url': url, 'wait': 'complete'}, timeout=30)
        await asyncio.sleep(min(30000, max(0, float(delay_ms))) / 1000)
        readiness = await self.wait_stable(require_content=True)
        return {'url': url, 'delay_ms': delay_ms, 'stable': readiness['stable']}

    async def mode(self):
        return self.interaction_mode((await self.snapshot())['url'])

    async def pause(self, mode):
        if mode != 'fast':
            await asyncio.sleep(random.uniform(.35, .75))

    async def find_target(self, intent, operation=''):
        best = None
        query = re.sub('页面上的|按钮|输入框|the|button|field', '', str(intent).lower()).strip()
        for item in (await self.snapshot())['items']:
            if item.get('disabled') or (operation == 'input' and not item.get('editable') and item.get('role') != 'textbox'):
                continue
            name = item.get('text', '')
            low = name.lower()
            score = (120 if item.get('ref') == intent else 100 if query and low == query else
                     70 if query and query in low else 50 if query and low in query and len(low) > 1 else 0)
            if re.search('搜索|search', query) and (re.search('search|搜索', low) or item.get('type') == 'search'):
                score += 45
            if score and (best is None or score > best['score']):
                x, y, width, height = item['rect']
                best = {**item, 'name': name, 'score': score,
                        'sensitive': item.get('sensitive') or bool(re.search('password|one.?time|otp|验证码', name, re.I)),
                        'rect': dict(x=x, y=y, width=width, height=height)}
        return best

    async def pointer_to(self, target, *, click=True, hover_ms=0, seed=7):
        mode = await self.mode()
        await self.pause(mode)
        rect = target['rect']
        x = round(rect['x'] + rect['width'] * (.5 + ((seed * 17) % 21 - 10) / 100))
        y = round(rect['y'] + rect['height'] * (.5 + ((seed * 29) % 21 - 10) / 100))
        count = 1 if mode == 'fast' else 12
        actions = []
        for i in range(1, count + 1):
            t = i / count
            eased = t if mode == 'fast' else t * t * (3 - 2 * t)
            actions.append(dict(type='pointerMove', x=round(self.pointer[0] + (x-self.pointer[0])*eased),
                                y=round(self.pointer[1] + (y-self.pointer[1])*eased), duration=0 if mode == 'fast' else 35, origin='viewport'))
        actions.append({'type': 'pause', 'duration': max(0 if mode == 'fast' else 100, hover_ms)})
        if click:
            actions.extend([dict(type='pointerDown', button=0), dict(type='pause', duration=0 if mode == 'fast' else 70), dict(type='pointerUp', button=0)])
        await self.connection.command('input.performActions', {'context': self.context_id,
            'actions': [{'type': 'pointer', 'id': 'webagent-pointer', 'parameters': {'pointerType': 'mouse'}, 'actions': actions}]})
        self.pointer = x, y
        return {'x': x, 'y': y, 'profile': mode}

    async def type_text(self, value, *, replace=False, submit=False):
        value = str(value)
        mode = await self.mode()
        await self.pause(mode)

        async def keys(part, clear=False, enter=False):
            actions = []
            if clear:
                modifier = '\uE03D' if sys.platform == 'darwin' else '\uE009'
                actions.extend([dict(type='keyDown', value=modifier), dict(type='keyDown', value='a'),
                                dict(type='keyUp', value='a'), dict(type='keyUp', value=modifier),
                                dict(type='keyDown', value='\uE003'), dict(type='keyUp', value='\uE003')])
            for char in part:
                actions.append(dict(type='keyDown', value=char))
                if mode != 'fast':
                    actions.append(dict(type='pause', duration=random.randint(40, 110)))
                actions.append(dict(type='keyUp', value=char))
            if enter:
                actions.extend([dict(type='keyDown', value='\uE007'), dict(type='keyUp', value='\uE007')])
            if actions:
                await self.connection.command('input.performActions', {'context': self.context_id,
                    'actions': [{'type': 'key', 'id': 'webagent-keyboard', 'actions': actions}]}, timeout=30)

        if len(value) <= 500:
            for offset in range(0, max(1, len(value)), 150):
                await keys(value[offset:offset+150], replace and offset == 0, submit and offset+150 >= len(value))
            return
        token = uuid.uuid4().hex
        await self.helper('typeText:0', token, value, replace)
        try:
            prefix, suffix = (0, 0) if mode == 'fast' else (6, 4)
            await self.helper('insertTextChunk:0', token, '')
            await keys(value[:prefix], clear=replace)
            offset, typed = prefix, prefix+suffix
            while offset < len(value)-suffix:
                end = min(offset+8192, len(value)-suffix)
                await self.helper('insertTextChunk:0', token, value[offset:end])
                offset = end
                if mode != 'fast':
                    await asyncio.sleep(random.uniform(.12, .3))
                    if typed < 16 and offset < len(value)-suffix:
                        await self.helper('insertTextChunk:0', token, '')
                        await keys(value[offset]); offset += 1; typed += 1
            await self.helper('insertTextChunk:0', token, '')
            await keys(value[-suffix:] if suffix else '')
            await self.helper('typeText:1', token)
            if submit:
                await keys('', enter=True)
        finally:
            await self.helper('typeText:2', token)

    async def scroll(self, delta_y=620):
        mode = await self.mode()
        await self.pause(mode)
        await self.connection.command('input.performActions', {'context': self.context_id, 'actions': [
            {'type': 'wheel', 'id': 'webagent-wheel', 'actions': [dict(type='scroll', x=0, y=0,
                deltaX=0, deltaY=delta_y, duration=0 if mode == 'fast' else 360, origin='viewport')]}]})

    async def extract_list(self, step):
        args = step.get('arguments') or {}
        if args.get('search_provider') in ('google', 'bing'):
            from .search import SEARCH_RESULTS_SCRIPT
            return await self.call_json(SEARCH_RESULTS_SCRIPT, [args['search_provider'],
                min(50, max(1, int(args.get('limit', 10)))), args.get('query', '')])
        rule = step.get('arguments', {}).get('site_extraction')
        if rule:
            if rule.get('schema') != 'ai2apps.site-extraction/v1' or rule.get('kind') != 'list':
                raise ValueError('Invalid extraction rule')
            result = await self.helper('executeExtractionStep:0', rule)
            if not result or not result.get('items'):
                raise RuntimeError('site_rule_drift')
            return result
        result = await self.helper('extractArticleList:0', min(1000, max(1, int(step.get('arguments', {}).get('limit', 50)))))
        if step.get('arguments', {}).get('observe_regions'):
            result['observed_regions'] = await self.helper('observeExtractionRegions:0', 'list')
        return result

    async def handle_access(self):
        dismissed = False
        for attempt in range(3):
            candidate = await self.helper('handlePageAccess:0')
            if candidate['classification'] != 'safe_dismiss':
                return {**candidate, 'dismissed': dismissed}
            await self.pointer_to(candidate, seed=41+attempt)
            dismissed = True
            await self.wait_stable(timeout=5)
        remaining = await self.helper('handlePageAccess:0')
        return {'classification': 'needs_user', 'reason': 'cookie_consent', 'dismissed': False} if remaining['classification'] == 'safe_dismiss' else {**remaining, 'dismissed': dismissed}

    async def rendered_page(self, max_chars=20000):
        maximum = min(100000, max(100, int(max_chars or 20000)))
        source = (_ROOT / 'web/static/js/readability.js').read_text()
        warning = None
        try:
            result = await self.call_json('function(){' + source + '''
setReadablility(); const clone=document.cloneNode(true);
for(const node of clone.querySelectorAll('script,style,input,textarea,[hidden],[aria-hidden="true"]'))node.remove();
const article=new globalThis.__ai2appsReadability(clone).parse();
return article?{title:article.title,text:article.textContent,url:location.href}:null;}''')
            if result and len(result.get('text', '').strip()) >= 100:
                return {**result, 'text': result['text'].strip()[:maximum], 'extraction_method': 'readability'}
        except Exception as error:
            warning = str(error)[:160]
        snapshot = await self.snapshot(maximum)
        return {'url': snapshot['url'], 'title': snapshot['title'], 'text': snapshot['text'],
                'extraction_method': 'webdriver-bidi-cleaned-dom', 'fallback_reason': warning or 'readability_empty_or_short'}

    @staticmethod
    def public_url(url):
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('public_http_url_required')
        host = parsed.hostname
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if host == 'localhost' or host.endswith('.local'):
                raise ValueError('public_http_url_required')
        else:
            if not address.is_global:
                raise ValueError('public_http_url_required')
        return url

    async def social_search(self, query):
        target = await self.helper('submitSocialSearch:0')
        await self.pointer_to(target, click=True)
        await self.type_text(query, replace=True)
        if await self.helper('submitSocialSearch:1') != query:
            raise RuntimeError('weibo_search_text_mismatch')
        await self.pointer_to(await self.helper('submitSocialSearch:2'), click=True)
        from urllib.parse import parse_qs
        for _ in range(12):
            await asyncio.sleep(.7)
            url = urlsplit((await self.snapshot())['url'])
            if url.hostname == 's.weibo.com' and url.path == '/weibo' and parse_qs(url.query).get('q') == [query]:
                return
        raise RuntimeError('weibo_search_navigation_failed')

    async def weibo_page(self, options):
        from urllib.parse import parse_qs
        source_url = options.get('social_source_url') or options['url']
        source = urlsplit(source_url)
        if source.hostname not in ('weibo.com', 'www.weibo.com', 's.weibo.com'):
            raise ValueError('weibo_origin_required')
        if source.hostname == 's.weibo.com':
            await self.navigate('https://s.weibo.com/', 1800)
            access = await self.handle_access()
            if access['classification'] in ('needs_user', 'restricted'):
                return dict(outcome=access['classification'], reason=access.get('reason'))
            await self.social_search(parse_qs(source.query)['q'][0])
        elif source_url != options['url']:
            await self.navigate(source_url, 1800)
        items = {}
        for round in range(3):
            access = await self.handle_access()
            if access['classification'] in ('needs_user', 'restricted'):
                return dict(outcome=access['classification'], reason=access.get('reason'))
            found = await self.helper('extractWeiboPosts:0')
            items.update({item['url']: item for item in found.get('items', [])})
            if options.get('weibo') == 'detail' and options['url'] in items:
                break
            if len(items) >= 12 or round == 2:
                break
            await asyncio.sleep(3.5)
            await self.scroll(550)
            await asyncio.sleep(1.8)
        if options.get('weibo') != 'detail':
            return {**found, 'items': list(items.values()), 'text': '\n'.join(item['text'] for item in items.values())}
        wanted = options['url']
        target = None
        for _ in range(8):
            target = await self.helper('clickSocialPost:0', wanted)
            if target.get('ready'):
                break
            await self.scroll(target['delta'])
            await asyncio.sleep(.9)
        if not target or not target.get('ready'):
            raise RuntimeError('weibo_post_not_visible')
        original = self.context_id
        initial = (await self.connection.command('browsingContext.getTree', {'maxDepth': 0}))['contexts']
        bound = next(item for item in initial if item['context'] == original)
        before = {item['context'] for item in initial}
        await asyncio.sleep(5)
        await self.pointer_to(target, click=True)
        for _ in range(12):
            await asyncio.sleep(.5)
            tree = (await self.connection.command('browsingContext.getTree', {'maxDepth': 0}))['contexts']
            matches = [item for item in tree if (item['context'] == original or item['context'] not in before)
                and item.get('userContext') == bound.get('userContext')
                and (item['context'] == original or item.get('originalOpener') == original)
                and urlsplit(item.get('url', '')).hostname in ('weibo.com', 'www.weibo.com')
                and urlsplit(item.get('url', '')).path == urlsplit(wanted).path]
            if len(matches) > 1:
                raise RuntimeError('ambiguous_weibo_post_context')
            if matches:
                self.context_id = matches[0]['context']
                if self.context_id != original:self.created_contexts[self.context_id] = original
                break
        else:
            raise RuntimeError('weibo_post_click_failed')
        await asyncio.sleep(1.8)
        access = await self.handle_access()
        if access['classification'] in ('needs_user', 'restricted'):
            return dict(outcome=access['classification'], reason=access.get('reason'), context=self.context_id)
        result = await self.helper('extractWeiboDetail:0', wanted)
        if self.context_id != original:
            await self.connection.command('browsingContext.close', {'context': self.context_id})
        else:
            await self.connection.command('browsingContext.traverseHistory', {'context': original, 'delta': -1})
        self.context_id = original
        return result

    async def read_page(self, options):
        original = self.context_id
        opened = options.get('opened', {})
        temporary = None
        retained = False
        phase = options.get('phase')
        if phase in ('finish', 'close'):
            if opened.get('context') != self.context_id:
                raise ValueError('read_context_mismatch')
            temporary = self.context_id if opened.get('temporary') else None
            original = opened.get('original_context') or original
            if temporary and self.created_contexts.get(temporary) != original:
                raise ValueError('untracked_read_context')
        try:
            if phase not in ('finish', 'close'):
                self.public_url(options['url'])
                if options.get('new_tab') is not False:
                    temporary = (await self.connection.command('browsingContext.create', {
                        'type': 'tab', 'referenceContext': original, 'background': True}))['context']
                    self.context_id = temporary
                    self.created_contexts[temporary] = original
                await self.navigate(options.get('social_source_url') or options['url'], options.get('delay_ms', 0))
            self.public_url((await self.snapshot())['url'])
            if phase == 'open':
                retained = bool(temporary)
                return dict(outcome='success', context=self.context_id, original_context=original,
                            temporary=bool(temporary), url=(await self.snapshot())['url'])
            if phase == 'close':
                return dict(outcome='success', tab_closed=bool(temporary))
            access = await self.handle_access()
            if access['classification'] in ('needs_user', 'restricted'):
                retained = bool(temporary and access['classification'] == 'needs_user')
                return dict(outcome=access['classification'], reason=access.get('reason'), context=self.context_id)
            rule = options.get('site_extraction')
            result = await self.helper('executeExtractionStep:0', rule) if rule else None
            extraction_fallback = bool(rule and (not isinstance(result, dict) or
                not isinstance(result.get('text'), str) or len(result['text']) < 300))
            if extraction_fallback:
                result = None
            if options.get('weibo'):
                result = await self.weibo_page(options)
                if result.get('outcome') in ('needs_user', 'restricted'):
                    return result
            elif options.get('youtube') == 'feed':
                for attempt in range(4):
                    result = await self.helper('extractYouTubeFeed:0')
                    if result.get('items'):
                        break
                    if attempt < 3:
                        await asyncio.sleep(2.5)
            elif options.get('youtube') == 'video':
                await self.call_json("function(){document.querySelectorAll('video').forEach(video=>video.pause());return true;}")
                for kind in ('expand', 'transcript'):
                    target = await self.helper('extractYouTubeVideo:0', kind)
                    if target:
                        await self.pointer_to(target, click=True)
                        await asyncio.sleep(.5)
                result = await self.helper('extractYouTubeVideo:1')
            if not result:
                result = await self.rendered_page(options.get('max_chars'))
                if extraction_fallback:
                    result['extraction_fallback'] = True
            if options.get('include_cover') or options.get('include_images'):
                result['cover_image'] = await self.helper('extractLeadImage:0')
                if options.get('include_images'):
                    result['images'] = result['cover_image'].get('images', [])
            if options.get('observe_regions'):
                result['observed_regions'] = await self.helper('observeExtractionRegions:0', 'article')
            retained = bool(temporary and options.get('close_tab') is False)
            return {**result, 'outcome': 'success' if result.get('text', '').strip() else 'failed',
                    'context': self.context_id if retained else original, 'read_context': self.context_id,
                    'tab_closed': bool(temporary and not retained)}
        finally:
            if temporary and not retained:
                try:
                    await self.connection.command('browsingContext.close', {'context': temporary})
                finally:
                    self.created_contexts.pop(temporary, None)
            self.context_id = original

    async def read_results(self, items, limit=3, delay_ms=0):
        articles, failures, seen = [], [], set()
        original = self.context_id
        for item in (items if isinstance(items, list) else [])[:5]:
            url = item.get('url') if isinstance(item, dict) else None
            try:
                self.public_url(url)
            except (ValueError, TypeError, AttributeError):
                continue
            if url in seen:
                continue
            seen.add(url)
            result = await self.read_page({'url': url, 'new_tab': True, 'close_tab': True,
                                           'max_chars': 6000, 'delay_ms': delay_ms})
            self.context_id = original
            if result.get('outcome') in ('needs_user', 'restricted'):
                return {**result, 'articles': articles, 'failures': failures}
            if result.get('outcome') == 'success':
                articles.append({key: result.get(key, '') for key in ('url', 'title', 'text')})
            else:
                failures.append({'url': url, 'reason': result.get('reason', 'empty_page')})
            if len(articles) >= min(5, max(1, int(limit))):
                break
        return {'outcome': 'success' if articles else 'failed', 'articles': articles, 'failures': failures}

    async def related_windows(self):
        tree = (await self.connection.command('browsingContext.getTree', {'maxDepth': 0})).get('contexts', [])
        related = {self.context_id}
        related.update(child for child, parent in self.created_contexts.items() if parent == self.context_id)
        while True:
            additions = {item['context'] for item in tree if item.get('originalOpener') in related} - related
            if not additions:
                break
            related.update(additions)
        windows = []
        for item in [item for item in tree if item['context'] != self.context_id and item['context'] in related][:4]:
            reader = BackgroundPage(self.connection, item['context'], interaction_mode=self.interaction_mode)
            try:
                observation = await reader.observation()
                windows.append({**observation, 'context': item['context'], 'originalOpener': item.get('originalOpener')})
            except Exception:
                windows.append({**item, 'error': 'window_not_ready'})
        return windows

    async def observation(self):
        page = await self.snapshot()
        controls = [{**item, 'name': item.get('text', '')} for item in page['items']]
        return {**page, 'controls': controls, 'context': self.context_id,
                'control_count': len(controls), 'html_truncated': bool(page.get('htmlTruncated')),
                'link_count': sum(item.get('tag') == 'a' for item in controls),
                'button_count': sum(item.get('tag') == 'button' or item.get('role') == 'button' for item in controls)}

    async def upload(self, hint, paths):
        mode = await self.mode()
        if mode == 'natural':
            target = await self.find_target(hint)
            if not target:
                return None
            token = uuid.uuid4().hex
            await self.helper('chooseAttachmentFiles:0', token)
            try:
                await self.pointer_to(target)
                result = await self.connection.command('script.callFunction', {
                    'functionDeclaration': "async function(token){const deadline=Date.now()+4000;while(Date.now()<deadline){const state=window.__ai2appsFileChooser;if(state?.token!==token)return null;if(state.input)return state.input;await new Promise(r=>setTimeout(r,100));}return null;}",
                    'arguments': [{'type': 'string', 'value': token}], 'target': {'context': self.context_id},
                    'awaitPromise': True, 'resultOwnership': 'root'})
                shared_id = result.get('result', {}).get('sharedId')
                if not shared_id:
                    raise RuntimeError('Upload click did not open a file chooser; inspect before retrying')
                await self.connection.command('input.setFiles', {'context': self.context_id,
                    'element': {'sharedId': shared_id}, 'files': paths})
                return {'file_count': len(paths), 'target_ref': target['ref'], 'method': 'clicked-file-chooser'}
            finally:
                await self.helper('chooseAttachmentFiles:1', token)
        available = [item for item in (await self.snapshot()).get('file_inputs', []) if not item.get('disabled')]
        target = next((item for item in available if item.get('ref') == hint or item.get('text') == hint), None)
        target = target or (available[0] if len(available) == 1 else None)
        if not target:
            return None
        result = await self.connection.command('script.callFunction', {
            'functionDeclaration': "function(ref){const roots=[document];for(let i=0;i<roots.length;i++){for(const el of roots[i].querySelectorAll('*'))if(el.shadowRoot)roots.push(el.shadowRoot);for(const el of roots[i].querySelectorAll('input[type=file]'))if(el.getAttribute('data-ai2apps-ref')===ref)return el;}return null;}",
            'arguments': [{'type': 'string', 'value': target['ref']}], 'target': {'context': self.context_id},
            'awaitPromise': False, 'resultOwnership': 'root'})
        shared_id = result.get('result', {}).get('sharedId')
        if not shared_id:
            return None
        await self.connection.command('input.setFiles', {'context': self.context_id,
            'element': {'sharedId': shared_id}, 'files': paths})
        return {'file_count': len(paths), 'target_ref': target['ref'], 'method': 'native-bidi-setFiles'}
