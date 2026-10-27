"""Task-local target-rule repair over fresh Probe evidence; never a new operation."""
from __future__ import annotations
import math
import logging
logging.getLogger(__name__).info('WebAgent control recovery loaded from %s', __file__)
from ai2apps.agent_builder.compiler import compile_source
from ai2apps.agent_builder.probe_contract import coverage
from ai2apps.task_llm import resolve_task_model


class ControlRuleRecovery:
    def __init__(self, visual):
        self.visual=visual

    async def resolve(self,page,goal,*,step=None,lookup=None,allowed_refs=None):
        from .execution_budget import recovery_scope
        async with recovery_scope(page):
            return await self._resolve(page,goal,step=step,lookup=lookup,allowed_refs=allowed_refs)

    async def _resolve(self,page,goal,*,step,lookup,allowed_refs):
        from .visual_recovery import VisualRecoveryUnavailable, binding
        from .background_executor import scope_allows
        visual=self.visual;operation=(step or {}).get('operation','click')
        if operation not in ('click','delete','input','hover'):raise VisualRecoveryUnavailable('Target repair cannot change this operation')
        if hasattr(page,'wait_stable'):await page.wait_stable(timeout=3,require_content=False)
        snapshot,viewport=await visual.observe(page)
        visual.evidence.append({'phase':'reobserve','probe_coverage':coverage(snapshot),'context':page.context_id})
        candidates=[{k:c.get(k) for k in ('ref','text','tag','role','type','href','rect','structure')} for c in snapshot['items']
            if (allowed_refs is None or c['ref'] in allowed_refs) and not c.get('disabled') and not c.get('sensitive')
            and isinstance(c.get('rect'),list) and len(c['rect'])==4 and c['rect'][2]>0 and c['rect'][3]>0]
        candidates=[c for c in candidates if not c.get('href') or scope_allows(c['href'],visual.scopes)]
        if operation=='input':candidates=[c for c in candidates if c.get('tag') in ('input','textarea','select') or c.get('role')=='textbox']
        if not candidates:raise VisualRecoveryUnavailable('Fresh Probe has no permitted visible controls')
        def matched(value):
            if not value or value.get('ambiguous'):return None
            if value.get('ref'):return next((c for c in candidates if c['ref']==value['ref']),None)
            rect=value.get('rect')
            if not isinstance(rect,dict):return None
            rounded=[math.floor(rect[k]*10+.5)/10 for k in ('x','y','width','height')]
            rows=[c for c in candidates if c['rect']==rounded]
            return rows[0] if len(rows)==1 else None
        from .repair_cache import RepairCache
        cache=RepairCache.for_step(visual,page,step,goal,snapshot['url'])
        cached,cache_status=cache.lookup(snapshot,candidates) if cache else (None,'unavailable')
        if cache:visual.evidence.append({'phase':'repair_cache','status':cache_status})
        target=await lookup() if cached is None and lookup else None
        chosen=cached or matched(target)
        generated=False
        if chosen is None:
            params=visual.run.input['parameters']
            model=resolve_task_model(visual.runtime,visual.tier,params.get('model_profile','normal'),pinned_routes=params.get('ai_model_routes'))
            if not model:raise VisualRecoveryUnavailable('No current task model for rule repair')
            selected=await visual.decide(model,'repair',goal,{'url':snapshot['url'],'controls':candidates,'probe_coverage':coverage(snapshot),'operation':operation},None)
            chosen=next((c for c in candidates if c['ref']==selected),None)
            if chosen is None:
                if not visual.policy['visual_locating']:raise VisualRecoveryUnavailable('DOM repair did not select a unique observed target')
                located=await visual._locate(page,goal,allowed_refs={c['ref'] for c in candidates})
                # Visual selection is still only a candidate: compile and bind it
                # against fresh Probe evidence just like a text-selected ref.
                snapshot,viewport=await visual.observe(page)
                candidates=visual.candidates(snapshot,viewport,allowed_refs)
                chosen=next((c for c in candidates if c['ref']==located['ref']),None)
                if chosen is None:raise VisualRecoveryUnavailable('Visual target disappeared before rule validation')
            generated=True
        # A fresh Probe may know an offscreen control even when a label-based
        # locator failed. Scroll to its observed geometry, then rebind by meaning.
        if chosen not in visual.candidates(snapshot,viewport,allowed_refs):
            expected={k:chosen.get(k) for k in ('ref','text','tag','role','href')}
            for _ in range(2):
                await page.scroll(round(chosen['rect'][1]+chosen['rect'][3]/2-viewport['height']/2))
                await page.pause('natural')
                snapshot,viewport=await visual.observe(page)
                latest=next((c for c in snapshot['items'] if c['ref']==expected['ref']),None)
                if latest is None or any(latest.get(k)!=v for k,v in expected.items()):
                    raise VisualRecoveryUnavailable('Target identity changed while scrolling')
                chosen={k:latest.get(k) for k in ('ref','text','tag','role','type','href','rect','structure')}
                if chosen in visual.candidates(snapshot,viewport,allowed_refs):break
            else:raise VisualRecoveryUnavailable('Observed target remains outside viewport')
            visual.evidence.append({'phase':'scroll_reobserve','target_ref':chosen['ref']})
        # Compile only an immutable operation + observed-ref rule. Model output
        # never supplies executable code, selectors, arguments or new scopes.
        source={'agent_type':'web','site_scope':visual.scopes,'steps':[{'name':'repair','operation':operation,
            'target':{'ref':chosen['ref']},'arguments':dict((step or {}).get('arguments') or {}),
            'execution':{'mode':'compiled'},'on':{'success':'done','failed':'failed'}}]}
        checked=compile_source(source,probe=snapshot)
        if not checked.valid:raise VisualRecoveryUnavailable('Repaired target failed Probe/compiler validation')
        fresh,fresh_view=await visual.observe(page)
        latest=next((c for c in visual.candidates(fresh,fresh_view,allowed_refs) if c['ref']==chosen['ref']),None)
        if latest is None or binding(snapshot,viewport,chosen)!=binding(fresh,fresh_view,latest):
            raise VisualRecoveryUnavailable('Probe changed during rule validation; no input dispatched')
        box=dict(zip(('x','y','width','height'),latest['rect']))
        target={**latest,'name':latest['text'],'rect':box}
        visual.evidence.append({'phase':'rule_validated','generated':generated,'operation':operation,
            'target_ref':latest['ref'],'target_tag':latest.get('tag'),'rule_digest':checked.source_digest,'probe_coverage':coverage(fresh)})
        if visual.policy['visual_review']!='off':
            try:target=await visual.review_target(page,target,goal)
            except VisualRecoveryUnavailable:
                if cache and cached:
                    cache.invalidate()
                    visual.evidence.append({'phase':'repair_cache','status':'invalidated_review'})
                raise
        else:target['_dom_binding']=binding(fresh,fresh_view,latest)
        if cache and (generated or cached):
            # Save only after post-action verification, never at model selection.
            ticket=cache.ticket(fresh,candidates,latest)
            if ticket:target['_repair_cache']=ticket
        return target
