"""Imagine owns the requirement to finish image work with an actual result.

Only final settlement is checked. Repaired calls can continue normally; neither
this hook nor a model response authorizes retries or clears unknown outcomes.
"""
from ai2apps.services.aaat import AgentResultPolicy

from .capabilities import IMAGE_RESULT_CAPABILITIES, COMIC_TRANSLATION_CAPABILITY

CAPABILITIES = IMAGE_RESULT_CAPABILITIES


def _last_attempt_failed(steps, capabilities):
    attempts=[s for s in steps if s.kind=='tool' and s.tool_name in capabilities
              and (getattr(s,'error',None) or {}).get('code')!='tool_declaration_required']
    return bool(attempts and attempts[-1].status.value in ('failed','uncertain'))


def completion_check(steps, artifacts):
    if not _last_attempt_failed(steps, CAPABILITIES):return None
    return {'code':'image_result_unavailable',
            'message':'The requested image operation did not finish successfully. Existing verified results are retained; no image completion is claimed.'}


def comic_completion_check(steps, artifacts):
    if not _last_attempt_failed(steps, (COMIC_TRANSLATION_CAPABILITY,)):return None
    return {'code':'comic_result_unavailable',
            'message':'The requested comic translation did not finish successfully. Existing verified results are retained; no translated deliverable is claimed.'}


def install(router):
    router.register_result_policy(AgentResultPolicy('imagine-delivery',
        lambda steps:{'role':'system','content':'Finish image work with a verified image result. After a preflight material rejection, inspect current Session materials and correct references. If image work remains unsuccessful, explain what is available and what is missing; finishing the report does not complete image generation.'},
        lambda content,steps:(content,None),capabilities=CAPABILITIES,completion_check=completion_check))

    router.register_result_policy(AgentResultPolicy('comic-delivery',
        lambda steps:{'role':'system','content':'Finish comic translation with a verified deliverable. Retain completed pages and original errors; an unsuccessful or unknown translation is not a completed comic. This check never authorizes replay or switching models.'},
        lambda content,steps:(content,None),capabilities=(COMIC_TRANSLATION_CAPABILITY,),completion_check=comic_completion_check))
