"""Local-owned browser SDK. Page scripts only inspect or edit the DOM.

Timing, native input, navigation, context ownership and result assembly all run
in Local, using the protocol-transparent native BiDi transport.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import math
import random
import re
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

from .processing_pool import serialized_input
from .rendering_leases import native_rendered
from contextlib import asynccontextmanager
from .dom_visibility import page_function

_ROOT = Path(__file__).resolve().parents[1]
_HELPERS = json.loads(Path(__file__).with_name('dom_helpers.json').read_text())
logging.getLogger(__name__).info('Browser access preflight loaded from %s', __file__)
logging.getLogger(__name__).info('WebAgent native input policy=visible-directed-dispatch-v2 loaded from %s', __file__)
logging.getLogger(__name__).info('Browser read-scoped CAPTCHA policy loaded from %s', __file__)


class NativeInputNotDispatched(RuntimeError):
    """Window preparation failed before any content input was dispatched."""
    input_dispatched=False


class BackgroundPage:
    def __init__(self, connection, context_id, *, interaction_mode=None):
        if not context_id:
            raise ValueError('An explicit browser context is required')
        self.connection = connection
        self.context_id = context_id
        self.created_contexts = {}
        self.interaction_mode = interaction_mode or (lambda url: 'natural')
        self.pointer = (0, 0)
        self.reset_input_diagnostics()

    @asynccontextmanager
    async def rendering_lease(self, purpose):
        leases = getattr(self.connection, 'rendering_leases', None)
        if leases is None:
            yield
        else:
            entered = False
            try:
                async with leases.hold(self, purpose):
                    entered = True
                    yield
            except Exception as error:
                if not entered and purpose == 'input' and not self.input_diagnostics.attempted:
                    raise NativeInputNotDispatched('Native rendering preparation failed before input') from error
                raise

    async def capture_screenshot(self, params, *, timeout=15):
        from .rendering_leases import capture_screenshot
        return await capture_screenshot(self, params, timeout=timeout)

    def reset_input_diagnostics(self):
        from .input_dispatch import InputDiagnostics
        self.input_diagnostics=InputDiagnostics()

    @serialized_input
    @native_rendered("input")
    async def dispatch_input(self, actions, *, context_id=None, timeout=30):
        """One native command, never retried; aggregate partial operation state."""
        trace=self.input_diagnostics
        kinds=sorted({item.get('type','unknown') for item in actions})
        entry=trace.begin('+'.join(kinds),context_id or self.context_id)
        try:
            result=await self.connection.command('input.performActions',{
                'context':context_id or self.context_id,'actions':actions},**({'timeout':timeout} if timeout!=30 else {}))
        except BaseException as error:
            not_sent=getattr(error,'command_dispatched',None) is False
            trace.finish(entry,not_sent=not_sent)
            if not_sent and not trace.attempted and isinstance(error,Exception):
                raise NativeInputNotDispatched('Native input transport unavailable before dispatch') from error
            raise
        trace.finish(entry,acknowledged=True)
        return result

    @serialized_input
    @native_rendered("input")
    async def dispatch_editor(self, name, *args):
        # Bulk insertion is an existing SDK edit, not a native key command.
        # Its partial effects must still prevent replay of the whole input.
        entry=self.input_diagnostics.begin('editor',self.context_id)
        try:
            result=await self.helper(name,*args)
        except BaseException:
            self.input_diagnostics.finish(entry)
            raise
        self.input_diagnostics.finish(entry,acknowledged=True)
        return result

    async def prepare_native_input(self):
        try:
            await self.activate_for_input()
        except Exception as error:
            if self.input_diagnostics.attempted:
                raise  # Earlier commands may already have affected this action.
            # Only runtime conditions are retried, before any content input.
            # Re-observe the same bound page and retain the owner's budget.
            from .execution_budget import recovery_scope
            try:
                async with recovery_scope(self):
                    await self.activate_for_input()
                return
            except Exception as recovery_error:
                raise NativeInputNotDispatched('Native window unavailable: not visible/ready; no input dispatched') from recovery_error

    async def call_json(self, source, args=(), timeout=30, *, context_id=None):
        arguments = json.dumps(args, ensure_ascii=False).replace('<', '\\u003c')
        result = await self.connection.command('script.callFunction', {
            'functionDeclaration': page_function(source, arguments),
            'target': {'context': context_id or self.context_id}, 'awaitPromise': True,
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

    async def snapshot(self, max_text=20000, *, max_items=150):
        source = (_ROOT / 'web/static/js/browser_snapshot.js').read_text()
        result = await self.call_json(source, [{'maxItems': min(600,max_items), 'maxText': max_text,
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

    async def navigate(self, url, delay_ms=3000, *, wait_ready=True):
        from .background_bidi import BrowserTransportError
        recovered=False
        for attempt in range(2):
            try:
                await self.connection.command('browsingContext.navigate', {
                    'context':self.context_id,'url':url,'wait':'none'},timeout=30)
                break
            except RuntimeError as error:
                if 'NS_ERROR_NET_HTTP3_PROTOCOL_ERROR' not in str(error) or attempt:
                    raise
                # Explicit network-protocol rejection of a GET is definitive;
                # retry only the same URL/context once, never an input action.
                await asyncio.sleep(.6)
            except (TimeoutError,BrowserTransportError) as error:
                if attempt:
                    error.navigation_attempts=2
                    raise
                reconnect=getattr(self.connection,'reconnect',None)
                if reconnect:await reconnect()
                # Inspect the same recorded context; never adopt another tab by
                # URL/focus or launch a replacement browser after a timeout.
                tree=await self.connection.command('browsingContext.getTree',{'maxDepth':0},timeout=5)
                current=next((c for c in tree.get('contexts',[]) if c['context']==self.context_id),None)
                if current is None:raise RuntimeError('Navigation recovery: original browser context no longer exists') from error
                expected=getattr(self,'user_context',None)
                if expected and current.get('userContext')!=expected:
                    raise RuntimeError('Navigation recovery: Profile mismatch') from error
                if current.get('url','').split('#')[0]==url.split('#')[0]:
                    recovered=True
                    break
                # Opening a URL is an explicit GET navigation. Retry once only
                # after observing that it did not reach the requested location.
        await asyncio.sleep(min(30000, max(0, float(delay_ms))) / 1000)
        if not wait_ready:
            self.prefetched_url = url
            return {'url':url,'preloaded':True,'navigation_attempts':attempt+1}
        readiness = await self.wait_stable(require_content=True)
        return {'url': url, 'delay_ms': delay_ms, 'stable': readiness['stable'], 'navigation_recovered':recovered, 'navigation_attempts':attempt+1}

    @serialized_input
    async def preload(self, url):
        # Pace tab openings under the shared Profile input lock, but release it
        # before waiting for page load. Other admitted readers can load too.
        self.public_url(url)
        if self.interaction_mode(url) == 'natural':
            await asyncio.sleep(random.uniform(.45, .85))
        return await self.navigate(url, delay_ms=0, wait_ready=False)

    async def mode(self):
        return self.interaction_mode((await self.snapshot())['url'])

    async def select_xhs_site(self, search_url):
        """Inspect both public sites in the same Profile, without reading cookies."""
        from .search import XHS_LOGIN_STATE_SCRIPT
        from urllib.parse import urlunsplit
        domains = ('www.xiaohongshu.com', 'www.rednote.com')
        previous = None
        database = getattr(self, 'database', None)
        if database:
            with database.transaction(write=True) as c:
                c.execute('CREATE TABLE IF NOT EXISTS browser_search_site_preferences (owner TEXT NOT NULL, profile TEXT NOT NULL, provider TEXT NOT NULL, domain TEXT NOT NULL, PRIMARY KEY(owner,profile,provider))')
                row = c.execute("SELECT domain FROM browser_search_site_preferences WHERE owner=? AND profile=? AND provider='xiaohongshu'", (self.owner,self.profile_key)).fetchone()
                previous = row['domain'] if row else None
        original = self.context_id
        states = {}
        for domain in domains:
            temporary = None
            try:
                options = {'type':'tab', 'background':True}
                if getattr(self,'user_context',None): options['userContext'] = self.user_context
                created = await self.connection.command('browsingContext.create', options)
                temporary = created['context']
                self.context_id = temporary
                await self.navigate('https://' + domain + '/explore', 1500)
                for attempt in range(3):
                    state = await self.call_json(XHS_LOGIN_STATE_SCRIPT)
                    if state.get('state') != 'unknown': break
                    await asyncio.sleep(.5)
                states[domain] = state.get('state', 'unknown')
            except (RuntimeError, TimeoutError):
                states[domain] = 'unavailable'
            finally:
                self.context_id = original
                if temporary:
                    try: await self.connection.command('browsingContext.close', {'context':temporary})
                    except (RuntimeError, TimeoutError): pass
        logged = [domain for domain in domains if states.get(domain) == 'logged_in']
        chosen = previous if previous in logged else next(iter(logged), None)
        # Unknown is not a login claim. Prefer a page without an explicit login
        # gate; the actual result extractor still enforces login and CAPTCHA.
        chosen = chosen or (previous if previous in domains and states.get(previous) == 'unknown' else None)
        chosen = chosen or next((d for d in domains if states.get(d) == 'unknown'), domains[0])
        if logged and database:
            with database.transaction(write=True) as c:
                c.execute("INSERT INTO browser_search_site_preferences VALUES (?,?,'xiaohongshu',?) ON CONFLICT(owner,profile,provider) DO UPDATE SET domain=excluded.domain", (self.owner,self.profile_key,chosen))
        self.xhs_site_selection = {'domain':chosen, 'login_states':states, 'verified_login':chosen in logged}
        parsed = urlsplit(search_url)
        return urlunsplit(('https',chosen,parsed.path,parsed.query,parsed.fragment))

    async def pause(self, mode):
        if mode != 'fast':
            await asyncio.sleep(random.uniform(.35, .75))

    async def find_target(self, intent, operation=''):
        best = None
        refs = set(re.findall(r'\b(e\d+)\b', str(intent)))
        if len(refs) > 1:
            return None
        requested_ref = next(iter(refs), None)
        query = re.sub('页面上的|按钮|输入框|the|button|field', '', str(intent).lower()).strip()
        for item in (await self.snapshot(max_items=600 if requested_ref else 150))['items']:
            if item.get('disabled') or (operation == 'input' and not item.get('editable') and item.get('role') != 'textbox'):
                continue
            if requested_ref and item.get('ref') != requested_ref:
                continue
            name = item.get('text', '')
            low = name.lower()
            score = (120 if item.get('ref') == (requested_ref or intent) else 100 if query and low == query else
                     70 if query and query in low else 0)
            if re.fullmatch('搜索|search', query) and (re.search('search|搜索', low) or item.get('type') == 'search'):
                score += 45
            if score and (best is None or score > best['score']):
                x, y, width, height = item['rect']
                best = {**item, 'name': name, 'score': score,
                        'sensitive': item.get('sensitive') or bool(re.search('password|one.?time|otp|验证码', name, re.I)),
                        'rect': dict(x=x, y=y, width=width, height=height)}
            elif score and best is not None and score==best['score'] and item.get('ref')!=best.get('ref'):
                best['ambiguous']=True
        return best

    async def activate_for_input(self):
        """Render the owned tab before native input; hidden CSS animations freeze.

        Read-only loading stays in background. This runs under the Profile input
        lock and never adopts another tab or changes page styles/visibility rules.
        Native hosts can hide a Profile window independently of tab selection;
        restore that window explicitly rather than relying on OS focus events.
        """
        async def observed():
            value=await self.call_json("function(){return {visible:document.visibilityState === 'visible',document_focus:document.hasFocus()};}")
            return value if isinstance(value,dict) else {'visible':value is True,'document_focus':None}
        state=await observed()
        self.input_diagnostics.focus.update(visible_before=state['visible'],document_focus_before=state['document_focus'])
        if state['visible']:
            return
        if not state['visible']:
            self.input_diagnostics.focus['unhide_requests']+=1
            await self.connection.command('browsingContext.unhideBrowserWindow', {'context': self.context_id})
        self.input_diagnostics.focus['activate_requests']+=1
        await self.connection.command('browsingContext.activate', {'context': self.context_id})
        for _ in range(20):
            state=await observed()
            if state['visible']:
                self.input_diagnostics.focus.update(visible_after=True,document_focus_after=state['document_focus'])
                return
            await asyncio.sleep(.1)
        raise RuntimeError('The bound browser page is not visible for native input')

    @serialized_input
    @native_rendered("input")
    async def pointer_to(self, target, *, click=True, hover_ms=0, seed=7):
        await self.prepare_native_input()
        mode = await self.mode()
        await self.pause(mode)
        input_context = target.get('input_context') or self.context_id
        prior = self.pointer if input_context == self.context_id else (0, 0)
        rect = target['rect']
        x = round(rect['x'] + rect['width'] * (.5 if target.get('_visual') else .5 + ((seed * 17) % 21 - 10) / 100))
        y = round(rect['y'] + rect['height'] * (.5 if target.get('_visual') else .5 + ((seed * 29) % 21 - 10) / 100))
        count = 1 if mode == 'fast' else 12
        actions = []
        for i in range(1, count + 1):
            t = i / count
            eased = t if mode == 'fast' else t * t * (3 - 2 * t)
            actions.append(dict(type='pointerMove', x=round(prior[0] + (x-prior[0])*eased),
                                y=round(prior[1] + (y-prior[1])*eased), duration=0 if mode == 'fast' else 35, origin='viewport'))
        actions.append({'type': 'pause', 'duration': max(0 if mode == 'fast' else 100, hover_ms)})
        if click:
            actions.extend([dict(type='pointerDown', button=0), dict(type='pause', duration=0 if mode == 'fast' else 70), dict(type='pointerUp', button=0)])
        if target.get('_visual') or target.get('_dom_binding'):
            from .visual_recovery import VALIDATE_TARGET, VisualRecoveryUnavailable
            expected=(target.get('_dom_binding') or target['_visual']['binding'])['viewport']
            checked=await self.call_json(VALIDATE_TARGET,[target['ref'],rect,expected['document_token']])
            if not checked or checked.get('valid') is not True:
                raise VisualRecoveryUnavailable('Reviewed target changed or is covered before native input')
        await self.dispatch_input([{'type': 'pointer', 'id': 'webagent-pointer', 'parameters': {'pointerType': 'mouse'}, 'actions': actions}],context_id=input_context)
        if input_context == self.context_id:
            self.pointer = x, y
        return {'x': x, 'y': y, 'profile': mode}

    @serialized_input
    @native_rendered("input")
    async def type_text(self, value, *, replace=False, submit=False):
        await self.prepare_native_input()
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
                await self.dispatch_input([{'type': 'key', 'id': 'webagent-keyboard', 'actions': actions}])

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
                await self.dispatch_editor('insertTextChunk:0', token, value[offset:end])
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

    @serialized_input
    @native_rendered("input")
    async def scroll(self, delta_y=620):
        await self.prepare_native_input()
        mode = await self.mode()
        await self.pause(mode)
        point = await self.call_json('function(){return {x:Math.floor(innerWidth/2),y:Math.floor(innerHeight/2)};}')
        # Firefox/APZ may acknowledge a timed wheel before its queued layout
        # updates reach scripts in a background context. Send one native wheel,
        # then observe its actual scroll state rather than stacking stale deltas.
        state_script='''() => {let n=document.elementFromPoint(innerWidth/2,innerHeight/2),s=[[scrollX,scrollY]];while(n){if(n.scrollHeight>n.clientHeight||n.scrollWidth>n.clientWidth)s.push([n.scrollLeft,n.scrollTop]);n=n.parentElement||n.getRootNode()?.host;}return s;}'''
        before=await self.call_json(state_script)
        await self.dispatch_input([
            {'type': 'wheel', 'id': 'webagent-wheel', 'actions': [dict(type='scroll', x=point['x'], y=point['y'],
                deltaX=0, deltaY=delta_y, duration=0, origin='viewport')]}])
        previous=before;changed=False;stable=0
        for _ in range(20):
            await asyncio.sleep(.1)
            current=await self.call_json(state_script)
            self.input_diagnostics.readback='observed'
            changed=changed or current!=before
            stable=stable+1 if current==previous else 0
            if changed and stable>=2:return {'settled':True,'changed':True}
            previous=current
        return {'settled':stable>=2,'changed':changed}

    async def ensure_xhs_sort(self, order):
        """Apply observed sort controls using native input; require selected-state evidence."""
        from .search import XHS_SORT_STATE_SCRIPT
        if order not in ('latest', 'general', 'likes'):
            raise ValueError('Invalid Xiaohongshu search order')
        state = {}
        for _ in range(6):
            state = await self.call_json(XHS_SORT_STATE_SCRIPT, [order])
            if state.get('invalid'):
                raise RuntimeError('xiaohongshu_sort_wrong_page')
            if state.get('verified'):
                if state.get('filter'):await self.pointer_to(state['filter'])
                await self.wait_stable(require_content=True)
                return
            if state.get('option') or state.get('filter'):
                break
            await asyncio.sleep(1)
        if not state.get('option') and state.get('filter'):
            await self.pointer_to(state['filter'], click=False, hover_ms=650)
            state = await self.call_json(XHS_SORT_STATE_SCRIPT, [order])
            if not state.get('option'):
                await self.pointer_to(state['filter'])
                await asyncio.sleep(.5)
                state = await self.call_json(XHS_SORT_STATE_SCRIPT, [order])
        if not state.get('verified') and state.get('option'):
            await self.pointer_to(state['option'])
        for _ in range(6):
            await asyncio.sleep(.5)
            state = await self.call_json(XHS_SORT_STATE_SCRIPT, [order])
            if state.get('verified'):
                if state.get('filter'):await self.pointer_to(state['filter'])
                await self.wait_stable(require_content=True)
                return
        raise RuntimeError('xiaohongshu_sort_not_verified: ' + order)

    async def extract_list(self, step):
        args = step.get('arguments') or {}
        if args.get('news_scan'):
            return await self.extract_news_list(step)
        access = await self.visual_access(await self.handle_access(read_only=True))
        if access['classification'] in ('needs_user', 'restricted'):
            return {**access, 'items': [], 'page_url': (await self.snapshot())['url']}
        sort_warning = None
        if args.get('xiaohongshu_sort'):
            try:
                await self.ensure_xhs_sort(args['xiaohongshu_sort'])
            except RuntimeError as error:
                if not str(error).startswith('xiaohongshu_sort_not_verified:'):
                    raise
                # Sorting is optional; readable results must not be discarded.
                sort_warning = 'xiaohongshu_sort_not_verified'
                if args['xiaohongshu_sort'] != 'general':
                    try:
                        await self.ensure_xhs_sort('general')
                    except RuntimeError as fallback_error:
                        if not str(fallback_error).startswith('xiaohongshu_sort_not_verified:'):
                            raise
        if args.get('x_sort'):
            await self.ensure_x_search_sort((await self.snapshot())['url'], args['x_sort'])
        if args.get('search_provider') in ('google', 'bing', 'duckduckgo', 'brave'):
            from .search import SEARCH_RESULTS_SCRIPT
            result = await self.call_json(SEARCH_RESULTS_SCRIPT, [args['search_provider'],
                min(50, max(1, int(args.get('limit', 10)))), args.get('query', ''), args.get('exclude_ads', True)])
            await self.emit_search_progress(result)
            return result
        if args.get('search_provider') in ('wikipedia', 'x', 'weibo', 'xiaohongshu', 'youtube', 'bilibili'):
            from .search import SITE_SEARCH_RESULTS_SCRIPT
            call_args = [args['search_provider'], min(50, max(1, int(args.get('limit', 10)))), args.get('query', ''), args.get('exclude_ads', True)]
            result = await self.call_json(SITE_SEARCH_RESULTS_SCRIPT, call_args)
            # SPA video pages may appear stable while their search content is still loading.
            # Read-only retries are bounded and never dismiss login/verification controls.
            if args['search_provider'] in ('youtube', 'bilibili', 'x', 'xiaohongshu'):
                for _ in range(6):
                    if result.get('reason') not in ('search_page_not_loaded', 'search_markup_unavailable'):
                        break
                    await asyncio.sleep(1)
                    result = await self.call_json(SITE_SEARCH_RESULTS_SCRIPT, call_args)
            if sort_warning:
                result.update(sort_warning=sort_warning, requested_sort=args['xiaohongshu_sort'], sort_verified=False)
            if args['search_provider']=='xiaohongshu' and getattr(self,'xhs_site_selection',None):
                result['site_selection'] = self.xhs_site_selection
            await self.emit_search_progress(result)
            if args['search_provider'] == 'xiaohongshu' and result.get('items'):
                await self.enrich_xhs_notes(result)
            if args['search_provider'] in ('youtube', 'bilibili') and result.get('items'):
                await self.enrich_video_covers(result)
            if args['search_provider'] == 'x' and result.get('items'):
                # X virtualizes its timeline: accumulate results before each scroll.
                collected = {item['url']: item for item in result['items']}
                stalled = 0
                stop = 'scroll_limit'
                for _ in range(12):
                    if len(collected) >= call_args[1]:
                        stop = 'limit_reached'
                        break
                    await self.scroll(700)
                    await asyncio.sleep(.8)
                    page = await self.call_json(SITE_SEARCH_RESULTS_SCRIPT, call_args)
                    before = len(collected)
                    for item in page.get('items', []):
                        collected.setdefault(item['url'], item)
                    await self.emit_search_progress({**result,'items':list(collected.values())[:call_args[1]]})
                    stalled = stalled + 1 if len(collected) == before else 0
                    if page.get('classification') == 'needs_user' or page.get('reason') == 'provider_unavailable':
                        stop = page.get('reason')
                        break
                    if stalled >= 3:
                        stop = 'no_more_results'
                        break
                result.update(items=list(collected.values())[:call_args[1]],
                              count=min(len(collected), call_args[1]), scan_stop_reason=stop)
            return result
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

    async def emit_search_progress(self, result):
        callback=getattr(self,'search_progress',None)
        if callback and result.get('items'):
            await callback(result)

    async def enrich_video_covers(self, result):
        """Keep observed video thumbnails portable across desktop and Mobile."""
        from .search import VIDEO_COVER_TARGET_SCRIPT
        budget = 2_000_000
        for item in result['items'][:20]:
            if not item.get('url'):
                continue
            for _ in range(3):
                target = await self.call_json(VIDEO_COVER_TARGET_SCRIPT, [item['url']])
                if target and 'scroll' in target:
                    await self.scroll(target['scroll'])
                    await asyncio.sleep(.4)
                    continue
                if target and target.get('rect'):
                    cover = await self.xhs_cover(target['rect'], budget)
                    if cover:
                        item['image_data_url'] = cover
                        budget -= len(cover)
                        await self.emit_search_progress(result)
                    break
                await asyncio.sleep(.4)
            if budget <= 0:
                break

    async def enrich_xhs_notes(self, result):
        """Read observed notes sequentially through native clicks and history.

        Never synthesize detail URLs, replay uncertain input, or bypass access
        gates. A missed detail keeps its list metadata with an explicit status.
        """
        from .search import XHS_NOTE_TARGET_SCRIPT, XHS_NOTE_DETAIL_SCRIPT
        original = (await self.snapshot())['url']
        for item in result['items']:
            item.update(content='', summary='', content_status='list_only')
        await self.emit_search_progress(result)
        cover_budget = 2_000_000
        for item in result['items'][:20]:
            target = None
            for _ in range(6):
                target = await self.call_json(XHS_NOTE_TARGET_SCRIPT, [item['url']])
                if target:
                    break
                await asyncio.sleep(.5)
            if not target:
                item['content'] = ''
                item['content_status'] = 'detail_unavailable'
                continue
            if target.get('url'):
                item['url'] = target['url']
            cover = await self.xhs_cover(target.get('cover_rect'), cover_budget)
            if cover:
                item['image_data_url'] = cover
                cover_budget -= len(cover)
            await self.pointer_to(target)
            detail = {}
            for _ in range(10):
                await asyncio.sleep(.8)
                detail = await self.call_json(XHS_NOTE_DETAIL_SCRIPT, [item['url']])
                if detail.get('ready'):
                    break
                access = await self.handle_access(read_only=True)
                if access.get('classification') in ('needs_user', 'restricted'):
                    result.update(classification=access['classification'], reason=access.get('reason'),
                                  assistance_kind=access.get('assistance_kind', 'authentication'))
                    return
            if detail.get('ready'):
                for key in ('content', 'author', 'published_at', 'like_count', 'collect_count', 'comment_count'):
                    if detail.get(key) is not None:
                        item[key] = detail[key]
                item['content_status'] = 'detail_read'
            else:
                item['content'] = ''
                item['content_status'] = 'detail_unavailable'
            await self.emit_search_progress(result)
            # The note click creates a native history entry; return through the
            # browser's Back action rather than a focus-dependent Escape key.
            try:
                await self.connection.command('browsingContext.traverseHistory',
                                              {'context': self.context_id, 'delta': -1})
            except RuntimeError as error:
                if 'no such history entry' not in str(error).lower():
                    raise
                # Rednote may replace history when opening the note overlay.
                # Close an observed overlay control; otherwise restore only the
                # original search GET, never replay the note click.
                close_target = await self.call_json(r'''function(){
                    const node=[...document.querySelectorAll('.close-circle,.close-mask,.note-container .close,#noteContainer .close,[aria-label="Close"]')].find(ai2appsDOMVisible);
                    return node?{rect:node.getBoundingClientRect().toJSON()}:null;
                }''')
                if close_target:
                    await self.pointer_to(close_target)
                    await asyncio.sleep(.4)
                if (await self.snapshot())['url'] != original:
                    try:
                        await self.navigate(original, 800)
                    except (RuntimeError, TimeoutError):
                        result['detail_stop_reason'] = 'search_page_not_restored'
                        break
            await self.pause(await self.mode())
            restored = False
            for _ in range(6):
                if (await self.snapshot())['url'] == original:
                    restored = True
                    break
                await asyncio.sleep(.4)
            if not restored:
                result['detail_stop_reason'] = 'search_page_not_restored'
                break

    async def xhs_cover(self, rect, budget):
        """Copy only the observed cover pixels through native BiDi, without CDN requests."""
        if not isinstance(rect, dict) or budget <= 0:
            return None
        try:
            box = {key: float(rect[key]) for key in ('x', 'y', 'width', 'height')}
            if not (all(math.isfinite(value) for value in box.values()) and 0 <= box['x'] and 0 <= box['y'] and
                    0 < box['width'] <= 1200 and 0 < box['height'] <= 1200):
                return None
            captured = await self.capture_screenshot({
                'context': self.context_id, 'origin': 'viewport',
                'clip': {'type': 'box', **box},
                'format': {'type': 'image/jpeg', 'quality': .75},
            }, timeout=10)
            data = captured.get('data', '')
            if not isinstance(data, str) or not data.startswith('/9j/'):
                return None
            value = 'data:image/jpeg;base64,' + data
            return value if len(value) <= min(400_000, budget) else None
        except (TimeoutError, RuntimeError, ValueError, KeyError):
            # A missing preview does not invalidate an otherwise readable note.
            return None

    async def extract_news_list(self, step):
        """Bounded read-only discovery on the native SDK, across news regions/pages."""
        args = dict(step.get('arguments') or {})
        args.pop('news_scan', None)
        limit = min(100, max(1, int(args.get('limit', 40))))
        initial = (await self.snapshot())['url']
        origin = urlsplit(initial)
        seen, visited, regions = {}, set(), []
        stop_reason = 'page_limit'
        rounds = 0
        load_clicks = 0
        last_load_count = -1
        for page_number in range(3):
            current = (await self.snapshot())['url']
            if current in visited:
                stop_reason = 'repeated_page'
                break
            visited.add(current)
            stalled = 0
            for scroll_round in range(8):
                before_count = len(seen)
                result = await self.extract_list({**step, 'arguments': {**args, 'limit': limit}})
                if result.get('classification') in ('needs_user', 'restricted'):
                    return {**result, 'items': list(seen.values()), 'discovery': {'rounds': rounds, 'stop_reason': 'page_blocked'}}
                for item in result.get('items', []):
                    seen.setdefault(item.get('url') or item.get('href'), item)
                if not regions and result.get('observed_regions'):
                    regions = result['observed_regions']
                rounds += 1
                stalled = stalled + 1 if len(seen) == before_count else 0
                # Region observation is expensive and only needs one sample.
                if regions:
                    args['observe_regions'] = False
                if stalled >= 2:
                    stop_reason = 'no_new_links'
                    break
                if len(seen) >= limit:
                    stop_reason = 'item_limit'
                    break
                position = await self.call_json(r'''function(){
                    const button=[...document.querySelectorAll('main button,[role=main] button')].find(b=>{
                        const r=b.getBoundingClientRect();
                        return !b.disabled&&!b.closest('form,[role=dialog]')&&
                            /^(load more(?: (?:news|articles|stories))?|show more (?:news|articles|stories)|加载更多|更多新闻)$/i.test(b.textContent.trim())&&
                            r.width>2&&r.height>2&&r.top>=0&&r.bottom<=innerHeight;
                    });
                    return {y:scrollY,height:innerHeight,total:document.documentElement.scrollHeight,
                        more:button?{rect:button.getBoundingClientRect().toJSON()}:null};
                }''')
                if position.get('more') and load_clicks < 2 and len(seen) != last_load_count:
                    last_load_count = len(seen)
                    await self.pointer_to(position['more'])
                    load_clicks += 1
                    await asyncio.sleep(.7)
                    continue
                if position['y'] + position['height'] >= position['total'] - 8:
                    stop_reason = 'end_of_page'
                    break
                await self.scroll(max(400, int(position['height'] * .85)))
                await asyncio.sleep(.35)
            else:
                stop_reason = 'scroll_limit'
            if len(seen) >= limit:
                break
            # Only explicit same-origin news/next links. No guessed URLs, form
            # submissions or generic "continue" clicks that could have effects.
            navigation = await self.call_json(r'''function(){
                const links=[...document.querySelectorAll('a[href]')];
                const valid=a=>a.origin===location.origin&&a.pathname!==location.pathname;
                const next=links.find(a=>valid(a)&&(a.rel==='next'||/^(next|next page|下一页)$/i.test(a.textContent.trim())));
                const news=location.pathname==='/'?links.find(a=>valid(a)&&/^(news(?:\s*news)*|latest news|新闻|最新新闻)$/i.test(a.textContent.trim())&&/\/(news|latest|articles)(\/|$)/i.test(a.pathname)):null;
                return {next:(news||next)?.href||''};
            }''')
            url = navigation.get('next')
            if not url or url in visited:
                break
            if page_number == 2:
                stop_reason = 'page_limit'
                break
            self.public_url(url)
            target = urlsplit(url)
            if (target.scheme, target.netloc) != (origin.scheme, origin.netloc):
                break
            # The learned region belongs to the initial document only. Later
            # observed news/pagination URLs use generic multi-region discovery.
            args.pop('site_extraction', None)
            args['observe_regions'] = False
            await self.navigate(url, delay_ms=300)
        items = list(seen.values())
        detail = [i for i in items if re.search(r'/(?:article|articles|story|stories)/[^/]+', urlsplit(i.get('url','')).path)]
        if len(detail) >= 3:
            # Prefer clear article detail URLs, but retain unfamiliar URL schemes
            # rather than silently treating them as non-articles.
            other = [i for i in items if i not in detail and not re.search(
                r'/(?:video|videos|drivers|teams|results|standings|tags?|category|categories)(?:/|$)', urlsplit(i.get('url','')).path)]
            items = detail + other
        return {'url': initial, 'page_url': initial, 'items': items[:limit],
                'observed_regions': regions, 'discovery': {'pages': sorted(visited),
                    'rounds': rounds, 'load_more_clicks': load_clicks, 'stop_reason': stop_reason,
                    'unique_links': len(items), 'candidate_links': len(seen)}}

    async def inspect_access(self, *, read_only=False):
        context_id = self.context_id
        candidate = await self.helper('handlePageAccess:0', *([False, True] if read_only else []))
        transforms = []
        for _ in range(3):
            if not (candidate.get('frame') and candidate.get('reason') == 'cookie_consent'
                    and isinstance(candidate.get('frame_index'), int)):
                break
            frame = candidate
            remote = await self.connection.command('script.callFunction', {
                'functionDeclaration': 'function(i){return document.querySelectorAll("iframe")[i]?.contentWindow;}',
                'arguments': [{'type': 'number', 'value': frame['frame_index']}],
                'target': {'context': context_id}, 'awaitPromise': False})
            value = remote.get('result', {})
            child = value.get('value', {}).get('context') if value.get('type') == 'window' else None
            if not child:
                return frame
            transforms.append({**frame['frame_viewport'], 'context': context_id, 'index': frame['frame_index'], 'blocker': frame})
            context_id = child
            candidate = await self.call_json(_HELPERS['handlePageAccess:0'], ([True, True] if read_only else [True]), context_id=context_id)
            if candidate['classification'] == 'none':
                return {**frame, 'frame_unresolved': True}
        if candidate['classification'] == 'safe_dismiss' and transforms:
            native_rect = dict(candidate['rect'])
            rect = dict(native_rect)
            for t in reversed(transforms):
                rect = {'x': t['x'] + rect['x'] * t['scale_x'],
                        'y': t['y'] + rect['y'] * t['scale_y'],
                        'width': rect['width'] * t['scale_x'], 'height': rect['height'] * t['scale_y']}
                hit = await self.call_json('function(i,x,y){const f=document.querySelectorAll("iframe")[i];return !!f&&document.elementFromPoint(x,y)===f;}',
                    [t['index'], rect['x']+rect['width']/2, rect['y']+rect['height']/2], context_id=t['context'])
                if not hit:
                    return {**t['blocker'], 'frame_obscured': True}
            # Keep the actual native click at the point just hit-tested in every ancestor.
            native_rect = {**native_rect, 'x': native_rect['x']+native_rect['width']/2-1, 'y': native_rect['y']+native_rect['height']/2-1, 'width': 2, 'height': 2}
            candidate = {**candidate, 'rect': native_rect, 'input_context': context_id, 'frame': True}
        return candidate

    async def handle_access(self, *, read_only=False):
        dismissed = False
        for attempt in range(3):
            candidate = await self.inspect_access(**({'read_only':True} if read_only else {}))
            if candidate['classification'] != 'safe_dismiss':
                return {**candidate, 'dismissed': dismissed}
            await self.pointer_to(candidate, seed=41+attempt)
            dismissed = True
            await self.wait_stable(timeout=5)
        remaining = await self.inspect_access(**({'read_only':True} if read_only else {}))
        return {**remaining, 'classification': 'needs_user', 'reason': remaining.get('reason', 'blocking_prompt'), 'dismissed': False} if remaining['classification'] == 'safe_dismiss' else {**remaining, 'dismissed': dismissed}

    async def rendered_page(self, max_chars=20000):
        maximum = min(100000, max(100, int(max_chars or 20000)))
        current = urlsplit((await self.snapshot(100))['url'])
        if current.hostname in ('www.bilibili.com', 'm.bilibili.com') and re.match(r'^/video/(BV\w+|av\d+)', current.path, re.I):
            source = Path(__file__).with_name('bilibili_content.js').read_text()
            result = await self.call_json(source, [maximum])
            if result is not None:
                if result.get('content_kind') not in ('subtitles','transcript'):
                    # Use native input on the page's own subtitle menu; the page
                    # performs its normal authenticated loading. No API/cookie
                    # discovery or alternate browser transport is involved.
                    controls = r'''function(stage){
const selectors=stage==='hover'?'.bpx-player-video-wrap, .bpx-player-container':stage==='open'?'.bpx-player-ctrl-subtitle':'.bpx-player-ctrl-subtitle-language-item, .bpx-player-ctrl-subtitle-language [data-lan], .bpx-player-ctrl-subtitle-item';
for(const node of document.querySelectorAll(selectors)){
 if(!ai2appsDOMVisible(node))continue;
 const name=(node.innerText||node.getAttribute('aria-label')||'').trim();
 if(stage==='language'&&!/^(?:中文|简体|AI中字|Chinese)/i.test(name))continue;
 if(/登录|会员|开通/.test(name))continue;
 const r=node.getBoundingClientRect();if(r.width&&r.height&&r.top>=0&&r.bottom<=innerHeight)return {name,rect:{x:r.x,y:r.y,width:r.width,height:r.height}};
}return null;}'''
                    try:
                        target = await self.call_json(controls, ['open'])
                        if not target or not isinstance(target.get('rect'),dict):
                            hover = await self.call_json(controls, ['hover'])
                            if hover and isinstance(hover.get('rect'),dict):
                                await self.pointer_to(hover, click=False)
                                target = await self.call_json(controls, ['open'])
                        if target and isinstance(target.get('rect'),dict):
                            await self.pointer_to(target, click=True)
                            target = await self.call_json(controls, ['language'])
                            if target and isinstance(target.get('rect'),dict):
                                await self.pointer_to(target, click=True)
                                await self.wait_stable(timeout=3)
                                result = await self.call_json(source, [maximum])
                    except Exception as error:
                        result.setdefault('content_warnings',[]).append('subtitle_menu: '+str(error)[:160])
                return result
        source = (_ROOT / 'web/static/js/readability.js').read_text()
        warning = None
        try:
            result = await self.call_json('function(maxChars){' + source + '''
setReadablility(); const clone=document.cloneNode(true);
for(const node of clone.querySelectorAll('script,style,input,textarea,[hidden],[aria-hidden="true"]'))node.remove();
const article=new globalThis.__ai2appsReadability(clone).parse();
return article?{title:article.title,text:article.textContent,source_blocks:ai2appsArticleDocument(article,maxChars),url:location.href}:null;}''',[maximum])
            if result and len(result.get('text', '').strip()) >= 100:
                return {**result, 'text': result['text'].strip()[:maximum], 'extraction_method': 'readability',
                        'extracted_chars':len(result['text'].strip()), 'returned_chars':min(len(result['text'].strip()),maximum),
                        'truncated':len(result['text'].strip())>maximum, 'extraction_limit':maximum}
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

    async def ensure_x_search_sort(self, url, order=None):
        from .search import X_SEARCH_SORT_SCRIPT
        params=parse_qs(urlsplit(url).query)
        order=order or ('latest' if params.get('f',[''])[0]=='live' else 'top')
        if order not in ('latest','top'):raise ValueError('Invalid X search order')
        query=params.get('q',[''])[0]
        clicked=False
        for _ in range(10):
            state=await self.call_json(X_SEARCH_SORT_SCRIPT,[order,query])
            if state.get('invalid'):raise RuntimeError('x_search_wrong_page')
            if state.get('verified'):
                await self.wait_stable(require_content=True)
                return
            if state.get('option') and not clicked:
                await self.pointer_to(state['option'])
                clicked=True
            await asyncio.sleep(.5)
        raise RuntimeError('x_search_sort_not_verified: '+order)

    async def x_page(self, options):
        if options['x']=='feed' and urlsplit(options['url']).path=='/search':
            await self.ensure_x_search_sort(options['url'])
        script = (_ROOT / 'web/static/js/x_post_snapshot.js').read_text()
        items = {}
        observed = None
        rule_valid = bool(options.get('x_extraction'))
        rule_compared = rule_valid
        wanted = re.search(r'/status/(\d+)', options['url'])
        stale = 0
        attempts = 20 if options['x'] == 'feed' else 3
        for attempt in range(attempts):
            access = await self.handle_access()
            if access['classification'] in ('needs_user', 'restricted'):
                return dict(outcome=access['classification'], reason=access.get('reason'))
            snapshot = await self.call_json(script, [options.get('x_extraction')])
            observed = snapshot.get('x_observed') or observed
            # An empty/loading snapshot contributes no article evidence. Any
            # nonempty invalid snapshot still invalidates the accumulated result.
            if snapshot.get('items'):
                rule_valid = rule_valid and snapshot.get('x_rule_valid', False)
                rule_compared = rule_compared and snapshot.get('x_rule_compared', False)
            before = len(items)
            for item in snapshot['items']:items[item['post_id']] = item
            if options['x'] == 'detail':
                post = items.get(wanted.group(1)) if wanted else None
                if post:
                    return {**post, 'x_observed':observed, 'x_rule_valid':rule_valid, 'x_rule_compared':rule_compared, 'platform':'x', 'content_type':'post', 'cover_image':{'url':post['images'][0]['url'] if post['images'] else ''},
                        'text':'Author: '+post['author']+'\nPublished: '+post['published_at']+'\nVisible post only; replies not included.\n'+post['text']}
            stale = stale + 1 if len(items) == before else 0
            if attempt == attempts - 1 or (options['x'] == 'feed' and (stale >= 3 or len(items) >= 200)):break
            if options['x'] == 'feed':await self.scroll(650)
            await asyncio.sleep(random.uniform(1.2, 2.0))
        if options['x'] == 'detail':return {'outcome':'failed','reason':'x_post_body_not_visible','url':options['url']}
        if not items:return {'outcome':'failed','reason':'x_feed_empty_or_not_loaded','url':options['url']}
        return {'url':options['url'], 'items':list(items.values())[:200], 'x_observed':observed, 'x_rule_valid':rule_valid, 'x_rule_compared':rule_compared, 'text':'\n'.join(item['title'] for item in items.values())[:10000], 'extraction_method':'x-visible-posts-v1'}

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
            return dict(outcome=access['classification'], reason=access.get('reason'), assistance_kind=access.get('assistance_kind'), access=access, context=self.context_id)
        result = await self.helper('extractWeiboDetail:0', wanted)
        if self.context_id != original:
            await self.connection.command('browsingContext.close', {'context': self.context_id})
        else:
            await self.connection.command('browsingContext.traverseHistory', {'context': original, 'delta': -1})
        self.context_id = original
        return result

    async def read_page(self, options):
        # Plain article reading must never turn into an unbounded interaction.
        # Specialised media workflows retain their own declared budgets.
        if any(options.get(k) for k in ('x', 'weibo', 'youtube')) or options.get('phase'):
            return await self._read_page(options)
        try:
            async with asyncio.timeout(10):
                return await self._read_page(options)
        except TimeoutError:
            return {'outcome': 'failed', 'reason': 'article_read_timeout', 'timeout_seconds': 10}

    async def article_access(self, options):
        try:
            async with asyncio.timeout(2):
                access = await self.handle_access(read_only=True)
        except TimeoutError:
            # A native dismissal may already have happened. Read-only fallback
            # is safe; do not dispatch another click on an uncertain outcome.
            access = {'classification': 'needs_user', 'reason': 'access_check_timeout', 'input_uncertain': True}
        if access['classification'] not in ('needs_user', 'restricted'):
            return access, None
        if access['classification']=='restricted' or access.get('reason') in {'authentication','login_required','login','captcha','paywall','rate_limited'}:
            return access, None
        # This only reads loaded, rendered article paragraphs; it neither
        # removes gates nor uses hidden scripts/metadata or a new HTTP request.
        from .article_access import VISIBLE_ARTICLE, classify
        observed = await self.call_json(VISIBLE_ARTICLE)
        gate=classify(observed.get('access_hint','')) or classify(observed.get('notice',''))
        if gate in {'login_required','paywall','access_verification_pending'}:
            reason='authentication' if gate=='login_required' else 'captcha' if gate=='access_verification_pending' else 'paywall'
            return {'classification':'restricted' if reason=='paywall' else 'needs_user','reason':reason,'assistance_kind':reason},None
        if not classify(observed.get('access_hint','')) and not classify(observed.get('notice','')):
            paragraphs = [v.strip() for v in observed.get('paragraphs',[]) if len(v.strip()) >= 35]
            body = '\n\n'.join(paragraphs)
            if len(body) >= 160:
                return access, {'outcome':'success', 'url':observed['url'], 'title':observed.get('title',''),
                    'text':body[:min(100000,int(options.get('max_chars') or 20000))],
                    'extraction_method':'loaded-dom-under-overlay', 'content_warnings':['optional_overlay_retained']}
        return await self.visual_access(access), None

    async def visual_access(self, access):
        recovery = getattr(self, 'visual_recovery', None)
        if (access.get('classification')=='needs_user' and access.get('reason') in {'blocking_prompt','dismissible_prompt'} and not access.get('input_uncertain')
                and recovery and recovery.policy['visual_locating']):
            from .visual_recovery import VisualRecoveryUnavailable, VisualActionUncertain
            try:
                recovery_seconds=recovery.policy.get('recovery_timeout_seconds')
                async with asyncio.timeout(4 if recovery_seconds is None else recovery_seconds):
                    await self.snapshot(max_items=600)
                    refs = await self.call_json("function(){return [...document.querySelectorAll('[role=dialog],[aria-modal=true],dialog[open],[class*=newsletter i]')].filter(n=>ai2appsDOMVisible(n,{viewport:true})).flatMap(n=>[...n.querySelectorAll('button,[role=button]')]).filter(n=>ai2appsDOMVisible(n,{viewport:true})&&!n.disabled&&n.type!=='submit'&&!n.closest('form')&&/^(?:|close|dismiss|cancel|not now|×|✕|关闭|取消)$/i.test((n.getAttribute('aria-label')||n.innerText||'').trim())).map(n=>n.getAttribute('data-ai2apps-ref')).filter(Boolean);} ")
                    if refs:
                        async def dismissed():
                            value=await self.inspect_access()
                            return {**value,'verified':value['classification']=='none'}
                        result=await recovery.click(self, 'Close only the optional promotional overlay. Never follow, subscribe, accept consent, sign in, submit or navigate.',
                            allowed_refs=refs, readback=dismissed)
                        if not result.get('state_verified'):return access
                        access = await self.inspect_access()
                        if access['classification'] not in ('needs_user','restricted'):
                            return access
            except (TimeoutError, VisualRecoveryUnavailable, VisualActionUncertain):
                pass  # No second visual action; the read deadline still applies.
        return access

    async def _read_page(self, options):
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
                destination=options.get('social_source_url') or options['url']
                if getattr(self,'prefetched_url',None) == destination and not temporary:
                    await self.wait_stable(require_content=True)
                    self.prefetched_url = None
                elif not options.get('x') or (await self.snapshot())['url'] != destination:
                    await self.navigate(destination, options.get('delay_ms', 0))
            self.public_url((await self.snapshot())['url'])
            if phase == 'open':
                retained = bool(temporary)
                return dict(outcome='success', context=self.context_id, original_context=original,
                            temporary=bool(temporary), url=(await self.snapshot())['url'])
            if phase == 'close':
                return dict(outcome='success', tab_closed=bool(temporary))
            from .article_access import VISIBLE_ARTICLE, classify, preview, LABELS
            observed = await self.call_json(VISIBLE_ARTICLE) if options.get('allow_preview') else {}
            access, loaded = ((await self.handle_access(), None) if any(options.get(k) for k in ('x','weibo','youtube'))
                              else await self.article_access(options))
            if loaded is not None:
                return {**loaded, 'read_context':self.context_id}
            access_reason = classify(observed.get('access_hint', '')) or classify(observed.get('notice', ''), access.get('reason', ''))
            if access_reason:
                partial = preview(observed, access_reason) if options.get('allow_preview') else None
                if partial:
                    return {**partial, 'outcome': 'success'}
                return dict(outcome='failed', reason=LABELS[access_reason], access_reason=access_reason)
            if access['classification'] in ('needs_user', 'restricted'):
                if access.get('reason') not in {'authentication','login_required','login','captcha','cookie_consent','legal_consent','paywall'}:
                    return dict(outcome='failed',reason='article_blocker_unresolved',access=access)
                retained = bool(temporary and access['classification'] == 'needs_user')
                return dict(outcome=access['classification'], reason=access.get('reason'), assistance_kind=access.get('assistance_kind'), access=access, context=self.context_id)
            observed_url = urlsplit((await self.snapshot(100))['url'])
            bilibili_video = observed_url.hostname in ('www.bilibili.com', 'm.bilibili.com') and re.match(r'^/video/(BV\w+|av\d+)', observed_url.path, re.I)
            rule = None if bilibili_video else options.get('site_extraction')
            result = await self.helper('executeExtractionStep:0', rule, options.get('max_chars')) if rule else None
            extraction_fallback = bool(rule and (not isinstance(result, dict) or
                not isinstance(result.get('text'), str) or len(result['text']) < 300))
            if extraction_fallback:
                result = None
            if options.get('x'):
                result = await self.x_page(options)
                if result.get('outcome') in ('needs_user', 'restricted', 'failed'):return result
            elif options.get('weibo'):
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
            if not options.get('x') and (options.get('include_cover') or options.get('include_images')):
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

    async def read_results(self, items, limit=3, delay_ms=0, *, skip_restricted=False):
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
            if result.get('outcome') == 'restricted' and skip_restricted:
                failures.append({'url':url,'reason':result.get('reason','restricted')})
                continue
            if result.get('outcome') in ('needs_user', 'restricted'):
                return {**result, 'articles': articles, 'failures': failures}
            if result.get('outcome') == 'success':
                articles.append({**{key: result.get(key, '') for key in ('url', 'title', 'text')}, **({'source_id':item['source_id'], 'requested_url':url} if item.get('source_id') else {})})
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
        page = await self.snapshot(max_items=600)
        controls = [{**item, 'name': item.get('text', '')} for item in page['items']]
        return {**page, 'controls': controls, 'context': self.context_id,
                'control_count': len(controls), 'html_truncated': bool(page.get('htmlTruncated')),
                'link_count': sum(item.get('tag') == 'a' for item in controls),
                'button_count': sum(item.get('tag') == 'button' or item.get('role') == 'button' for item in controls)}

    @serialized_input
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
