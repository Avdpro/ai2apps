"""Execute durable WebAgent browser interactions in Local, independent of HTML."""
from __future__ import annotations

import asyncio
import fnmatch
import hashlib
import json
import logging
import re
import time
from pathlib import Path
from urllib.parse import urlsplit, urlencode

from .background_planner import BackgroundPlanner
from .background_page import NativeInputNotDispatched
from .site_boundary import registrable_site

logging.getLogger(__name__).info(
    'WebAgent same-site scope policy loaded from %s', __file__)


def scope_allows(url, scopes):
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password:
            return False
    except ValueError:
        return False
    for scope in scopes:
        if fnmatch.fnmatchcase(url, scope):
            return True
        try:
            allowed = urlsplit(scope)
            # An exact source host authorizes the same registrable site, while
            # explicit wildcard scopes retain their existing glob semantics.
            if not allowed.hostname or '*' in allowed.netloc or allowed.username or allowed.password:
                continue
            if parsed.scheme != allowed.scheme or (parsed.port or (443 if parsed.scheme == 'https' else 80)) != (allowed.port or (443 if allowed.scheme == 'https' else 80)):
                continue
            site = registrable_site(allowed.hostname)
            if not site or site != registrable_site(parsed.hostname):
                continue
            # Substitute only the host. Keep the declared path/query glob so
            # same-site aliases do not broaden a path-restricted capability.
            alias = parsed._replace(netloc=allowed.netloc).geturl()
            if fnmatch.fnmatchcase(alias, scope):
                return True
        except (ValueError, UnicodeError):
            continue
    return False


def intent(step):
    target = step.get('target') or {}
    return target.get('accessible_name') or target.get('intent') or target.get('ref') or step.get('description', '')


def recovery_assistance(step, evidence, error=''):
    """Plain, bounded guidance from trusted step metadata, not model/page advice."""
    args=step.get('arguments') or {}
    label=str(args.get('assistance_label') or step.get('description') or step.get('id') or '定位页面控件').strip()[:160]
    visual=any(item.get('phase') in ('select','review') for item in evidence)
    no_vision='no declared image-input' in str(error).lower()
    if str(args.get('locale','zh')).lower().startswith('zh'):
        tried='已自动重新观察页面并尝试文字定位'+('和视觉复核' if visual else '')+'。'
        hint=('当前任务模型不支持图片识别，无法执行视觉恢复；请配置支持图片的任务模型后继续。' if no_vision else
              '若页面仍在加载，请等加载完成；若弹窗遮挡操作区，请关闭弹窗，再点“已处理，继续”让 AI 重试。也可以取消任务。')
        return f'自动处理暂停在：{label}。{tried}尚未执行无法确认的动作。{hint}'
    tried='Fresh page observation and text targeting'+(' and visual review' if visual else '')+' were attempted.'
    hint=('The task model has no image-input capability; configure a vision-capable task model to continue.' if no_vision else
          'Wait for loading to finish or dismiss a popup covering this area, then choose Continue to let AI retry. You may also cancel.')
    return f'Automatic processing paused at: {label}. {tried} The uncertain action was not executed. {hint}'


def requests_submission(step):
    description=str(step.get('description',''))
    # Constraints in model descriptions are not affirmative input instructions.
    # Actual submit targets remain blocked independently by target/effect guards.
    description=re.sub(r"\b(?:do not|don't|never)\s+(?:(?:press|hit)\s+(?:the\s+)?enter|submit)\b|(?:不要|不得|不能|勿)\s*(?:按下?|敲击)?\s*(?:回车|提交)", '', description, flags=re.I)
    return bool(re.search(r'\b(?:press|hit)\s+(?:the\s+)?enter\b|\bsubmit\b|回车|提交', description, re.I))


def native_input_assistance(step):
    args=step.get('arguments') or {}
    label=str(args.get('assistance_label') or step.get('description') or step.get('id') or '').strip()[:160]
    if str(args.get('locale','zh')).lower().startswith('zh'):
        return f'自动处理暂停在：{label}。浏览器窗口尚未就绪，已尝试恢复窗口，本次没有发送点击或输入。继续时将重新检查窗口状态。'
    return f'Automatic processing paused at: {label}. Window restoration did not make the page ready. No click or input was sent; continuing will check the window again.'


def interaction_policy(step, target=None):
    text = ' '.join(str(value or '') for value in [step.get('description'), intent(step),
                    (target or {}).get('name'), (target or {}).get('role')])
    if re.search('captcha|verify you are human|验证码|机器人验证', text, re.I):
        return {'outcome': 'needs_user', 'reason': 'captcha'}
    if re.search('paywall|checkout|purchase|buy now|subscribe to continue|付款|支付|购买|付费墙|订阅后继续', text, re.I):
        return {'outcome': 'restricted', 'reason': 'payment_or_paywall'}
    if re.search('terms of service|privacy terms|legal agreement|服务条款|法律条款|隐私条款', text, re.I) and re.search('accept|agree|同意|接受', text, re.I):
        return {'outcome': 'needs_user', 'reason': 'legal_consent'}
    return None


class BackgroundExecutor:
    async def recover_observation(self,request,run):
        """Read an owner-persisted remote request; never resubmit an action."""
        step=request.get('step',{});args=step.get('arguments') or {}
        if step.get('operation')!='search.api' or args.get('provider')!='deepseek' or not args.get('receipt_id'):
            return None
        from .search_api import search
        parameters=run.input['parameters']
        try:
            result=await search(self.runtime,parameters['owner_user_id'],args['query'],args.get('limit',10),
                scopes=request.get('site_scope') or [],provider='deepseek',model_profile=parameters.get('model_profile','normal'),
                receipt_id=args['receipt_id'],task_id=parameters.get('browser_task_id',run.id),recover=True)
            return {'outcome':'success','evidence':{'operation':'search.api','result':result}} if result is not None else None
        except ValueError as error:return {'outcome':'failed','evidence':{'reason':'search_api_failed','message':str(error)}}

    def __init__(self, runtime):
        self.runtime = runtime
        self.planner = BackgroundPlanner(runtime)

    async def owner_read(self,page,step,run,inputs=None):
        """Dispatch only a registered trusted owner's read adapter, never model code."""
        parameters=run.input.get('parameters',{})
        key=(parameters.get('caller_app_id'),step['arguments']['owner_action'])
        handler=getattr(self.runtime,'browser_owner_readers',{}).get(key)
        if step.get('operation')!='inspect' or handler is None:
            return {'outcome':'restricted','evidence':{'reason':'owner_reader_not_registered'}}
        from .tasks import BrowserTaskRepository
        owner=parameters.get('owner_user_id');task_id=parameters.get('browser_task_id')
        if not owner or not task_id:
            return {'outcome':'restricted','evidence':{'reason':'owner_reader_task_required'}}
        tasks=BrowserTaskRepository(self.runtime.database,self.runtime.events)
        task=tasks.get(owner,task_id);_,registered_caller=tasks.program(owner,task_id)
        if task.get('run_id')!=run.id or registered_caller!=key[0]:
            return {'outcome':'restricted','evidence':{'reason':'owner_reader_task_mismatch'}}
        return await handler(page,step,inputs or {},run)

    async def execute(self, page, request, run):
        from .execution_budget import TaskExecutionBudget, RecoveryBudgetExceeded
        prior_budget=getattr(page,'execution_budget',None) if page else None
        if page is not None and prior_budget is None:
            page.execution_budget=TaskExecutionBudget(request.get('execution_policy'))
        try:
            result=await self._execute(page,request,run)
        except RecoveryBudgetExceeded as error:
            result={'outcome':'failed','evidence':{'reason':'browser_recovery_budget_exhausted','message':str(error),
                'action_outcome_unknown':error.uncertain,'automatic_replay_allowed':False}}
        finally:
            if page is not None and prior_budget is None:
                page.execution_budget=None
        from ai2apps.agent_builder.execution_policy import resolve_policy
        if result.get('outcome')=='needs_user' and not resolve_policy(request.get('execution_policy'))['allow_user_intervention']:
            return {'outcome':'failed','evidence':{**result.get('evidence',{}),
                'reason':'browser_user_intervention_disabled','requires_user':False}}
        return result

    async def _execute(self, page, request, run):
        step = request['step']
        if step['operation'] == 'search.api':
            from .search_api import search
            args=step.get('arguments') or {}
            try:
                result=await search(self.runtime,run.input['parameters']['owner_user_id'],args['query'],args.get('limit',10),scopes=request.get('site_scope') or [],provider=args.get('provider'),model_profile=run.input['parameters'].get('model_profile','normal'),receipt_id=args.get('receipt_id',''),task_id=run.input['parameters'].get('browser_task_id',run.id))
                return {'outcome':'success','evidence':{'operation':'search.api','result':result}}
            except ValueError as error:
                return {'outcome':'failed','evidence':{'reason':'search_api_failed','message':str(error)}}
        page.allowed_assets = self.asset_ids(request.get('invocation_input', {}))
        scopes = request.get('site_scope') or []
        preview = bool(request.get('preview'))
        original = page.context_id
        from .visual_recovery import VisualControlRecovery
        prior_recovery = getattr(page, 'visual_recovery', None)
        page.visual_recovery = VisualControlRecovery(self.runtime, run, scopes, step.get('ai', {}).get('tier', 'standard'), policy=request.get('execution_policy'))
        try:
            selected = step.get('browser_context')
            if selected and selected != original:
                if selected not in {item['context'] for item in await page.related_windows()}:
                    return dict(outcome='failed', evidence={'reason': 'unrelated_or_closed_window'})
                page.context_id = selected
            await page.validate_context()
            if (step.get('arguments') or {}).get('owner_action'):
                return await self.owner_read(page,step,run,request.get('invocation_input',{}))
            if (step.get('arguments') or {}).get('shopping_action'):
                parameters = run.input.get('parameters', {})
                profile=parameters.get('model_profile')
                gift_normal=False
                if profile=='normal' and (step['arguments']['shopping_action'] in {'gift_search','screen_gifts','cart_item','cart_report'}):
                    from .tasks import BrowserTaskRepository
                    task=BrowserTaskRepository(self.runtime.database).get(parameters['owner_user_id'],parameters['browser_task_id'])
                    gift_normal=(task['capability'] in {'gift_recommend','gift_revise','gift_prepare_cart'}
                        and task['browser_context'].get('model_profile')=='normal')
                if (not str(parameters.get('caller_app_id', '')).endswith(':ai2apps.shopping-pro')
                        or (profile!='privacy' and not gift_normal)):
                    return dict(outcome='restricted', evidence={'reason':'shopping_scope_denied'})
                from .shopping import execute
                return await execute(page, step['arguments'])
            mode = step.get('mode', 'adaptive')
            if mode == 'interpreted' and not preview:
                return await self.adaptive(page, request, run)
            if not preview and step['operation'] == 'extract_list' and step.get('arguments', {}).get('custom_search'):
                return await self.recover_list(page, request, run,
                    {'outcome': 'not_found', 'evidence': {'reason': 'custom_search_results_unavailable'}})
            result = await self.compiled(page, step, scopes, preview)
            if (not preview and step['operation'] == 'extract_list'
                    and step.get('arguments', {}).get('mini_app_list_recovery')
                    and result['outcome'] == 'not_found'
                    and result.get('evidence', {}).get('reason') in (
                        'site_rule_drift', 'search_markup_unavailable', 'search_page_not_loaded')):
                return await self.recover_list(page, request, run, result)
            if not preview and mode == 'adaptive' and result['outcome'] in ('not_found', 'retryable_error', 'failed'):
                # Exceptions are not caught here: an interrupted native command
                # has an unknown result and must never enter adaptive replay.
                return await self.adaptive(page, request, run, result)
            return result
        finally:
            page.context_id = original
            page.visual_recovery = prior_recovery

    @staticmethod
    def asset_ids(value):
        if isinstance(value, dict):
            return ({value['asset_id']} if isinstance(value.get('asset_id'), str) else set()) | set().union(*(BackgroundExecutor.asset_ids(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(BackgroundExecutor.asset_ids(item) for item in value))
        return set()

    async def recover_list(self, page, request, run, failure):
        from .execution_budget import recovery_scope
        async with recovery_scope(page):
            return await self._recover_list(page,request,run,failure)

    async def _recover_list(self, page, request, run, failure):
        from .list_recovery import CANDIDATES_SCRIPT, eligible, selected_result
        args = request['step'].get('arguments') or {}
        observed = await page.call_json(CANDIDATES_SCRIPT, [args.get('exclude_ads', True)])
        if not scope_allows(observed.get('page_url', ''), request.get('site_scope') or []):
            return dict(outcome='restricted', evidence={'reason': 'site_scope'})
        observed['items'] = [c for c in observed.get('items', [])
                             if eligible(c, args.get('search_provider'))
                             and not (args.get('exclude_ads', True) and c.get('is_ad'))]
        if not observed['items']:
            return failure
        try:
            ids = await asyncio.wait_for(self.planner.select_list(run, request['step'], observed), timeout=45)
            result = selected_result(observed, ids, args)
        except Exception:
            # No unverified success or model/configuration error can strand the queue.
            # This catches only read-only model selection, never native commands.
            return dict(outcome='not_found', evidence={**failure['evidence'],
                        'recovery': 'failed', 'recovery_reason': 'list_recovery_unavailable'})
        return dict(outcome='success', evidence={'operation': 'extract_list', 'result': result,
                    'recovery': 'observed_links_ai', 'original_failure': failure['evidence'].get('reason')})

    async def access_blocker(self, page, step, scopes, *, dispatched=False):
        """Read only scoped owned windows; never retry input or dismiss a gate."""
        if not callable(getattr(page, 'inspect_access', None)):
            return None
        original = page.context_id
        try:
            current = await page.snapshot()
            windows = [{'context':original, 'url':current.get('url','')}]
            if callable(getattr(page, 'related_windows', None)):
                windows += await page.related_windows()
            for window in windows:
                if not scope_allows(window.get('url',''), scopes):
                    continue
                page.context_id = window['context']
                access = await page.inspect_access()
                kind = access.get('assistance_kind') or access.get('reason')
                if access.get('classification') != 'needs_user' or kind not in ('authentication','captcha'):
                    continue
                host = urlsplit(window['url']).hostname
                zh = str((step.get('arguments') or {}).get('locale','zh')).startswith('zh')
                message = (f'网站 {host} 要求'+('登录' if kind=='authentication' else '完成访问验证')+
                    '。请在当前任务页面完成后点击“已处理，继续”；查询条件已保留，不会重复提交。') if zh else (
                    f'{host} requires '+('sign-in' if kind=='authentication' else 'access verification')+
                    '. Complete it in the task page, then continue. Query settings are retained; no automatic resubmission.')
                return dict(outcome='needs_user', evidence={'reason':kind,'assistance_kind':kind,
                    'assistance_message':message,'automatic_replay_allowed':False,
                    'action_outcome_unknown':bool(dispatched),
                    'result':{'context':window['context'],'url':window['url'],'access':access}})
        except Exception:
            # A failed read never changes uncertain-input handling or scope.
            return None
        finally:
            page.context_id = original
        return None

    async def compiled(self, page, step, scopes, preview=False):
        operation = step['operation']
        args = step.get('arguments') or {}
        before = await page.snapshot()
        url = args.get('url')
        if operation == 'open' and args.get('github_repository_search') and url == 'https://github.com/search':
            url += '?' + urlencode({'q': str(args.get('query', '')), 'type': 'repositories'})
        rule = args.get('site_extraction') or {}
        rule_url = None
        if rule.get('schema') == 'ai2apps.site-extraction/v1' and rule.get('origin'):
            origin = urlsplit(rule['origin'])
            path = rule.get('path') or '/'
            if origin.scheme in ('http', 'https') and origin.netloc and path.startswith('/') and not path.startswith('//'):
                rule_url = origin._replace(path=path, query='', fragment='').geturl()
        if operation == 'read_page' and not url and rule_url:
            url = rule_url
            args = {**args, 'url': url}
        # Intelligence rules describe their own starting document. A fresh task
        # has a blank tab; initialize it before enforcing the extraction scope.
        if operation == 'extract_list' and rule_url:
            if not scope_allows(rule_url, scopes):
                return dict(outcome='restricted', evidence={'reason': 'navigation_outside_scope', 'url': rule_url, 'before': before})
            current = urlsplit(before['url'])
            destination = urlsplit(rule_url)
            if (current.scheme, current.netloc, current.path) != (destination.scheme, destination.netloc, destination.path):
                if preview:
                    return dict(outcome='success', evidence={'preview': True, 'operation': operation, 'url': rule_url, 'before': before})
                await page.navigate(rule_url, args.get('delay_ms', 3000))
                before = await page.snapshot()
        if operation == 'open' and not url:
            match = re.search(r'https?://[^\s，。]+', step.get('description', ''))
            url = match.group(0) if match else None
        if operation in ('open', 'read_page'):
            if not url or not scope_allows(url, scopes):
                return dict(outcome='restricted', evidence={'reason': 'navigation_outside_scope', 'url': url, 'before': before})
        elif operation != 'read_results' and not scope_allows(before['url'], scopes):
            return dict(outcome='restricted', evidence={'reason': 'site_scope', 'before': before})
        target = None
        assets = args.get('asset_ids') if operation == 'input' else None
        if assets and any(asset_id not in getattr(page, 'allowed_assets', set()) for asset_id in [item.get('asset_id') if isinstance(item, dict) else item for item in assets]):
            return dict(outcome='failed', evidence={'reason': 'attachment_not_supplied'})
        if operation in ('click', 'delete', 'input', 'hover'):
            policy = interaction_policy(step)
            if policy:
                return {'outcome': policy['outcome'], 'evidence': {**policy, 'before': before}}
            goal=f'{operation}: {intent(step)}. Only this step: '+str(step.get('description',''))
            cached=False
            if not preview and not assets and getattr(page,'visual_recovery',None):
                from .repair_cache import RepairCache
                cache=RepairCache.for_step(page.visual_recovery,page,step,goal,before['url'])
                cached=bool(cache and cache.exists())
            target = ({'name': intent(step)} if assets else None if cached else
                      await page.find_target(intent(step), 'input' if operation == 'input' else operation))
            if (not target or target.get('ambiguous')) and not preview and not assets and getattr(page,'visual_recovery',None):
                from .visual_recovery import VisualRecoveryUnavailable
                from .control_recovery import ControlRuleRecovery
                try:
                    target=await ControlRuleRecovery(page.visual_recovery).resolve(page,
                        goal,
                        step=step,lookup=lambda:page.find_target(intent(step),'input' if operation=='input' else operation))
                except VisualRecoveryUnavailable as error:
                    return dict(outcome='needs_user',evidence={'reason':'control_rule_unresolved',
                        'action_outcome_unknown':False,'automatic_replay_allowed':False,
                        'control_recovery':list(page.visual_recovery.evidence),
                        'assistance_kind':'unsupported_interaction',
                        'assistance_message':recovery_assistance(step,page.visual_recovery.evidence,error),
                        'diagnostic':str(error)[:250]})
            if not target or target.get('ambiguous'):
                return dict(outcome='not_found', evidence={'reason': 'target_not_found', 'before': before})
            if operation=='input' and target.get('_visual') and target.get('tag') not in ('input','textarea') and target.get('role')!='textbox':
                return dict(outcome='needs_user',evidence={'reason':'visual_input_target_invalid',
                    'assistance_message':'视觉选中的控件不是可编辑输入框，本次未输入。请核对任务页面或取消。'})
            policy = interaction_policy(step, target)
            if policy:
                return {'outcome': policy['outcome'], 'evidence': {**policy, 'target': target, 'before': before}}
            if operation == 'input' and target.get('sensitive'):
                return dict(outcome='needs_user', evidence={'reason': 'sensitive_input', 'before': before})
        if preview:
            return dict(outcome='success', evidence={'preview': True, 'operation': operation, 'target': target, 'before': before})
        if operation == 'open':
            try:
                if args.get('search_provider') == 'xiaohongshu':
                    url = await page.select_xhs_site(url)
                    if not scope_allows(url, scopes):
                        return dict(outcome='restricted', evidence={'reason':'navigation_outside_scope','url':url})
                result = (await page.preload(url) if args.get('preload') else
                          {'url':url,'page_reused':True} if args.get('reuse_current_page') and before['url']==url
                          else await page.navigate(url, args.get('delay_ms', 3000)))
            except (TimeoutError, RuntimeError) as error:
                # Search GET navigation is safe to abandon for the alternate engine.
                # Never apply this recovery to clicks, inputs or submissions.
                if args.get('search_provider') not in ('google', 'bing', 'duckduckgo', 'brave'):
                    raise
                return dict(outcome='failed', evidence={'reason':'search_network_protocol_error' if 'NS_ERROR_NET_HTTP3_PROTOCOL_ERROR' in str(error) else 'search_navigation_failed',
                    'provider':args['search_provider'], 'detail':str(error)[:300]})
        elif operation == 'extract_list':
            try:
                result = await page.extract_list(step)
            except RuntimeError as error:
                if str(error).startswith('xiaohongshu_sort_'):
                    return dict(outcome='not_found', evidence={'reason':str(error).split(':')[0], 'before':before})
                if str(error) != 'site_rule_drift':
                    raise
                return dict(outcome='not_found', evidence={'reason': 'site_rule_drift', 'before': before})
            if result.get('classification') in ('needs_user', 'restricted'):
                return dict(outcome=result['classification'], evidence={'reason':result['reason'],
                    'assistance_kind':result.get('assistance_kind'), 'result':result, 'before':before})
            if args.get('search_provider') and not result.get('items') and not result.get('empty'):
                return dict(outcome='not_found', evidence={'reason':result.get('reason','search_results_unavailable'),
                    'provider':args['search_provider'], 'result':result, 'before':before})
        elif operation == 'read_page':
            result = await page.read_page(args)
            if result.get('outcome') != 'success':
                return dict(outcome=result.get('outcome', 'failed'), evidence={'operation': operation, 'reason': result.get('reason') or ('article_extraction_failed' if result.get('fallback_reason') else 'article_read_failed'), 'assistance_kind': result.get('assistance_kind'), 'result': result, 'before': before})
        elif operation == 'read_results':
            items = args.get('items') or []
            if any(not scope_allows(item.get('url', ''), scopes) for item in items if isinstance(item, dict)):
                return dict(outcome='restricted', evidence={'reason': 'navigation_outside_scope'})
            result = await page.read_results(items, args.get('limit', 3), args.get('delay_ms', 0), **({'skip_restricted':True} if args.get('skip_restricted') else {}))
            if result['outcome'] != 'success':
                return dict(outcome=result['outcome'], evidence={'operation': operation, 'result': result})
        elif operation == 'page_access':
            if url:
                return dict(outcome='failed', evidence={'reason': 'page_access_does_not_navigate_use_open'})
            result = await page.handle_access()
        elif operation == 'wait_state':
            deadline = time.monotonic() + min(30, max(.5, args.get('timeout_ms', 10000) / 1000))
            ready = False
            while time.monotonic() < deadline:
                found = await page.find_target(str(args.get('target', '')))
                if bool(found) == (args.get('present') is not False):
                    ready = True; break
                await asyncio.sleep(.5)
            result = {'ready': ready, 'context': page.context_id}
            if not ready:
                return dict(outcome='failed', evidence={'operation': operation, 'result': result})
        elif operation == 'inspect':
            result = {'page': before, 'context': page.context_id, 'windows': await page.related_windows()}
            if intent(step):
                result['target'] = await page.find_target(intent(step))
        elif operation in ('click', 'delete', 'input', 'hover'):
            if args.get('custom_search') and operation in ('click', 'delete') and re.search(
                    r'\b(post|reply|comment|like|repost|follow|send|publish|delete|buy|pay|checkout)\b|发帖|发布|发送|评论|点赞|转发|关注|删除|购买|支付', target.get('name') or '', re.I):
                return dict(outcome='restricted', evidence={'reason': 'custom_search_consequential_target'})
            if args.get('foundation_read_only') or args.get('foundation_preparation_only'):
                if operation in ('click', 'delete') and re.search('buy|purchase|checkout|subscribe|upgrade|pay|order|send|publish|delete|submit|购买|支付|付款|订阅|升级|下单|发送|发布|删除|提交', target['name'], re.I):
                    return dict(outcome='restricted', evidence={'reason': 'foundation_consequential_target'})
                if operation == 'input' and args.get('foundation_read_only') and not (re.search('搜索|查询|search|find', args.get('foundation_search_goal', ''), re.I) and re.search('search|搜索|查询|检索|buscar|recherch|suche|検索|검색|pesquis|поиск', (target.get('name') or '') + (target.get('role') or '') + (target.get('type') or ''), re.I)):
                    return dict(outcome='restricted', evidence={'reason': 'foundation_input_not_search'})
                if args.get('foundation_preparation_only') and requests_submission(step):
                    return dict(outcome='restricted', evidence={'reason': 'foundation_submission_disallowed'})
            if operation == 'input' and assets:
                ids = [asset['asset_id'] if isinstance(asset, dict) else asset for asset in assets]
                from ai2apps.gallery import GalleryRepository
                repository = GalleryRepository(self.runtime.database, self.runtime.config.paths.artifacts_path / 'gallery', self.runtime.events)
                # asset_path enforces current run actor ownership; never accept a
                # model-supplied filesystem path or URL as an upload source.
                owner = getattr(page, 'owner', None)
                if not owner:
                    raise ValueError('Upload actor missing')
                paths = [str(repository.asset_path(owner, asset_id)[1]) for asset_id in ids]
                result = await page.upload(intent(step), paths)
                if not result:
                    return dict(outcome='not_found', evidence={'reason': 'file_input_not_found'})
            else:
                if operation == 'input':
                    value = next((args[key] for key in ('value', 'text', 'content') if args.get(key) is not None), None)
                    if value is None:
                        match = re.search('[“\"\']([^”\"\']+)[”\"\']', step.get('description', ''))
                        value = match.group(1) if match else ''
                    submit = bool(re.search('搜索|查询|search|find', step.get('description', '') + step.get('working_goal', ''), re.I) and requests_submission(step))
                    if not value and not submit:
                        return dict(outcome='failed', evidence={'reason': 'input_value_required'})
                async def interact(chosen):
                    nonlocal result
                    if operation=='input':
                        result=await page.pointer_to(chosen,click=True)
                        await page.type_text(value,replace=bool(value),submit=submit)
                    else:
                        result=await page.pointer_to(chosen,click=operation!='hover',hover_ms=650 if operation=='hover' else 0)
                unlabeled_icon=target.get('tag') in ('i','svg') and not str(target.get('text') or target.get('name') or '').strip()
                if getattr(page,'visual_recovery',None) and (page.visual_recovery.policy['visual_review']=='always' or unlabeled_icon) and not target.get('_visual'):
                    from .visual_recovery import VisualRecoveryUnavailable
                    try:
                        target=await page.visual_recovery.review_target(page, target, goal)
                    except VisualRecoveryUnavailable:
                        return dict(outcome='needs_user',evidence={'reason':'visual_review_unavailable','assistance_message':'未能完成任务要求的视觉复核，本次未执行；请检查页面或取消。'})
                if target.get('_visual'):
                    from .visual_recovery import VisualRecoveryUnavailable, VisualActionUncertain
                    try:
                        recovery=await page.visual_recovery.click(page,target['_visual']['goal'],target=target,action=interact,readback=page.snapshot)
                    except NativeInputNotDispatched:
                        return dict(outcome='needs_user',evidence={'reason':'native_input_not_dispatched',
                            'action_outcome_unknown':False,'automatic_replay_allowed':False,
                            'assistance_kind':'unsupported_interaction','assistance_message':native_input_assistance(step)})
                    except VisualActionUncertain as error:
                        blocker = await self.access_blocker(page, step, scopes, dispatched=True)
                        if blocker:
                            return blocker
                        return dict(outcome='needs_user',evidence={'reason':'action_outcome_unknown',**error.evidence,
                            'assistance_kind':'unsupported_interaction','assistance_message':'操作可能已经生效，已回读页面；请核对结果，不要重复操作。'})
                    except VisualRecoveryUnavailable as error:
                        return dict(outcome='needs_user',evidence={'reason':'visual_target_changed','assistance_kind':'unsupported_interaction',
                            'assistance_message':'页面在控件复核后发生变化，本次未执行。请检查页面后继续或取消。'})
                    if recovery['visually_verified'] is False:
                        blocker = await self.access_blocker(page, step, scopes, dispatched=True)
                        if blocker:
                            return blocker
                        return dict(outcome='needs_user',evidence={'reason':'visual_action_unverified','action_outcome_unknown':True,
                            'assistance_kind':'unsupported_interaction','visual_recovery':recovery['evidence'],
                            'assistance_message':'操作已执行一次，但回读与视觉复核未能确认结果。请核对实际页面；不要重复执行该操作。'})
                    result={**result,'visual_recovery':recovery['evidence']}
                else:
                    try:
                        await interact(target)
                    except NativeInputNotDispatched:
                        return dict(outcome='needs_user',evidence={'reason':'native_input_not_dispatched',
                            'action_outcome_unknown':False,'automatic_replay_allowed':False,
                            'assistance_kind':'unsupported_interaction',
                            'assistance_message':native_input_assistance(step)})
                    except Exception as error:
                        # Preserve the failing protocol stage in Local diagnostics.
                        # Do not print page contents, input values or credentials.
                        logging.getLogger(__name__).exception('Native browser input failed at step %s', step.get('id'))
                        try:
                            observed=await page.snapshot()
                            observation_error=None
                        except Exception as read_error:
                            observed=None;observation_error=type(read_error).__name__
                        return dict(outcome='needs_user',evidence={'reason':'action_outcome_unknown',
                            'action_outcome_unknown':True,'automatic_replay_allowed':False,
                            'readback':observed,'readback_error':observation_error,'dispatch_error':type(error).__name__,
                            'assistance_kind':'unsupported_interaction','assistance_message':'操作可能已经生效，已尝试回读；请核对结果，不要重复操作。'})
                result = {**result, 'target': target, 'windows': await page.related_windows(),**({'control_recovery':list(page.visual_recovery.evidence)} if getattr(page,'visual_recovery',None) and any(e.get('phase')=='reobserve' for e in page.visual_recovery.evidence) else {})}
                blocker = await self.access_blocker(page, step, scopes, dispatched=True)
                if blocker:
                    return blocker
        elif operation == 'scroll':
            await page.scroll(int(args.get('delta_y', 620)))
            result = {'delta_y': int(args.get('delta_y', 620))}
        elif operation == 'complete':
            result = {'complete': True}
        else:
            return dict(outcome='failed', evidence={'reason': 'unsupported_operation', 'operation': operation})
        after = await page.snapshot()
        if hasattr(page,'input_diagnostics') and page.input_diagnostics.attempted:
            page.input_diagnostics.readback='observed'
        # Readers may close their temporary tab and restore an about:blank
        # caller. Validate the document actually read, not that restored tab.
        destinations = ([result.get('url') or url] if operation == 'read_page' else
            [item.get('url') for item in result.get('articles', [])] if operation == 'read_results' else
            [after['url']])
        if any(not scope_allows(destination, scopes) for destination in destinations):
            return dict(outcome='restricted', evidence={'reason': 'navigation_outside_scope',
                'operation': operation, 'result': result, 'before': before, 'after': after})
        outcome = result.get('classification', 'success')
        if outcome not in ('needs_user', 'restricted'):
            outcome = 'success'
        return dict(outcome=outcome, evidence={'operation': operation, 'result': result, 'before': before, 'after': after})

    async def adaptive(self, page, request, run, failure=None):
        step, scopes = request['step'], request.get('site_scope') or []
        attempts = [{'source_step': step, **failure}] if failure else []
        for _ in range(8):
            blocker = await self.access_blocker(page, step, scopes)
            if blocker:
                return blocker
            from .execution_budget import recovery_scope
            async with recovery_scope(page, enabled=failure is not None):
                observation = await page.observation()
                observation['windows'] = await page.related_windows()
                # An interpreted inspect step already performed a real SDK read.
                # Let an already-satisfied precondition finish from that evidence,
                # rather than requiring an invented extra action just for a receipt.
                if not attempts and (step.get('authored_operation') or step['operation'])=='inspect' and scope_allows(observation.get('url',''),scopes):
                    attempts.append({'source_step':{'operation':'inspect','name':'initial_observation'},
                        'outcome':'success','evidence':{'operation':'inspect','result':observation,
                            'before':observation,'after':observation}})
                planning = self.planner.next(run=run, step=step, observation=observation, attempts=attempts, scopes=scopes)
                if (step.get('arguments') or {}).get('custom_search'):
                    try:
                        decision = await asyncio.wait_for(planning, timeout=45)
                    except TimeoutError:
                        return dict(outcome='failed', evidence={'reason': 'custom_search_planner_timeout', 'attempts': attempts})
                    except (ValueError, TypeError, KeyError):
                        return dict(outcome='failed', evidence={'reason': 'custom_search_planner_invalid_action', 'attempts': attempts})
                else:
                    from .background_planner import PlannerDecisionUnavailable
                    try:
                        decision = await planning
                    except PlannerDecisionUnavailable:
                        return dict(outcome='failed',evidence={'reason':'browser_planner_invalid_decision',
                            'action_outcome_unknown':False,'automatic_replay_allowed':False,
                            'message':'AI未能生成可靠的下一步操作，已停止；没有派发该步骤的新点击或输入。'})
                if decision['decision'] == 'needs_user':
                    return dict(outcome='needs_user', evidence={'reason': decision.get('reason'), 'assistance_kind': decision['assistance_kind'], 'attempts': attempts})
                if decision['decision'] == 'complete':
                    results = [item['evidence']['result'] for item in attempts if item.get('outcome') == 'success' and 'result' in item.get('evidence', {})]
                    if (step.get('authored_operation') or step['operation']) == 'extract_list':
                        result = next((item for item in reversed(results) if isinstance(item, dict) and isinstance(item.get('items'), list)), None)
                        if result is None:
                            result = await page.extract_list(step)
                    else:
                        result = results[-1] if results else {'context': page.context_id, 'url': observation['url']}
                    return dict(outcome='success', evidence={'operation': step['operation'], 'result': result, 'attempts': attempts})
                action = decision['compiled_step']
                args = step.get('arguments') or {}
                if args.get('custom_search'):
                    if action['browser_context'] != page.context_id:
                        return dict(outcome='restricted', evidence={'reason': 'custom_search_unrelated_context'})
                    if action['operation'] == 'input':
                        action['arguments'] = {**action.get('arguments', {}), 'value': args['query']}
                    action['arguments'] = {**action.get('arguments', {}), 'custom_search': True}
                if args.get('read_only') or args.get('preparation_only'):
                    from .step_policy import allowed_primitives
                    permitted = allowed_primitives(step)
                    if action['operation'] not in permitted:
                        return dict(outcome='restricted', evidence={'reason': 'foundation_action_outside_contract'})
                    action['arguments'] = {**action.get('arguments', {}), 'foundation_read_only': bool(args.get('read_only')), 'foundation_preparation_only': bool(args.get('preparation_only')), 'foundation_search_goal': args.get('goal', '')}
                target_name = intent(action)
                goal = str(step.get('working_goal', '')) + ' ' + str(step.get('description', ''))
                risky = action['operation'] == 'click' and (
                    re.search('购买|支付|授权|同意|接受|purchase|pay|checkout|authorize|agree|accept', target_name, re.I) or
                    (re.fullmatch('发布|发送|提交|publish|send|submit|post', target_name.strip(), re.I) and
                     not re.search('发布|发送|提交|发微博|publish|send|submit|post', goal, re.I)))
                if risky:
                    digest = hashlib.sha256(json.dumps({key: action.get(key) for key in
                        ('operation', 'target', 'arguments', 'browser_context')}, sort_keys=True).encode()).hexdigest()
                    if digest not in request.get('approved_browser_actions', []):
                        return dict(outcome='needs_user', evidence={'reason': action.get('description') or target_name,
                            'confirmation_required': True, 'action_hash': digest, 'attempts': attempts})
                original = page.context_id
                try:
                    page.context_id = action['browser_context']
                    result = await self.compiled(page, action, scopes)
                finally:
                    page.context_id = original
                attempts.append({'source_step': decision['step'], **result})
                if result['outcome'] in ('needs_user', 'restricted'):
                    if result.get('evidence',{}).get('reason') in ('control_rule_unresolved','native_input_not_dispatched'):
                        evidence=result['evidence']
                        message=native_input_assistance(step) if evidence['reason']=='native_input_not_dispatched' else recovery_assistance(step,evidence.get('control_recovery',[]),evidence.get('diagnostic',''))
                        evidence.update(assistance_message=message,
                            failed_operation=action['operation'],failed_target=str(intent(action))[:200],owner_step=step.get('id'))
                    return result
        return dict(outcome='failed', evidence={'reason': 'ai_step_action_limit', 'attempts': attempts})
