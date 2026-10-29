"""Native browser workflow SDKs bound only by installed signed Mini-App exports."""
from dataclasses import replace
from ai2apps.packages.mini_app_exports import HostProtocol
from ai2apps.services import ToolProviderError
from ai2apps.services.aaat import principal_for
HOST='ai2apps.ai-browser'

async def travel(runtime,args,context,mini,spec):
    from .travel_aaat import TravelAdapters
    return await TravelAdapters(runtime).execute(spec['options']['operation'],args,context)

async def shopping(runtime,args,context,mini,spec):
    from .shopping_aaat import execute_operation
    providers=[p.id for p in runtime.app_capability_router.providers.values()
        if p.mini_app_id==mini['id'] and p.capability==spec['name']
        and runtime.package_mini_exports.is_placement(p,spec['host'],mini['id'])]
    if len(providers)!=1:raise ToolProviderError('Installed Mini-App binding is ambiguous; no operation submitted')
    provider=providers[0]
    return await execute_operation(runtime,args,context,spec['options']['operation'],mini_app_id=mini['id'],provider_id=provider)

async def search(runtime,args,context,mini,spec):
    from ai2apps.research.search_workflow import invoke
    return await invoke(runtime,args,context)

async def reader(runtime,args,context,mini,spec):
    from ai2apps.research.mini_apps import WebMiniAppAdapters
    return await WebMiniAppAdapters(runtime).fetch(args,context)

async def confirmed_search(runtime,args,context,mini,spec):
    if not args.get('confirmation_id'):return False
    from ai2apps.research.search_preparation import require_confirmation
    from ai2apps.services.aaat import InvocationPolicyError
    try:require_confirmation(runtime,principal_for(runtime,context),args,session_id=context.session_id,run_id=context.trace_id)
    except ToolProviderError as error:raise InvocationPolicyError('search_confirmation_changed',str(error)) from error
    return True

async def normalize_search(runtime,args,context,mini,spec):
    if not args.get('confirmation_id'):return args
    from ai2apps.research.search_preparation import require_confirmation
    values,_=require_confirmation(runtime,principal_for(runtime,context),args,session_id=context.session_id,run_id=context.trace_id)
    return {**values,'confirmation_id':args['confirmation_id']}

def citation_policy(runtime):
    from ai2apps.services.aaat import AgentResultPolicy
    from ai2apps.research.citations import citation_instruction,bind_final,report_preview,READ_TOOLS
    if 'citation_binding' not in runtime.app_capability_router.result_policies:
        runtime.app_capability_router.register_result_policy(AgentResultPolicy('citation_binding',citation_instruction,bind_final,report_preview,tuple(sorted(READ_TOOLS))))
def search_form(runtime,key,mini,spec):
    citation_policy(runtime)
    from ai2apps.agents.parameter_forms import FORMS
    from ai2apps.research.search_form import describe,complete
    FORMS[key]=replace(FORMS[key],describe=describe,complete=complete,related_capabilities=(),continuation=None)

def reader_form(runtime,key,mini,spec):
    citation_policy(runtime)

def shopping_form(runtime,key,mini,spec):
    from .shopping_aaat import install_result_policy
    install_result_policy(runtime)
    if spec['options']['operation']!='prepare_cart':return
    from ai2apps.agents.parameter_forms import FORMS
    from .shopping_aaat import cart_values,product_rows,FORM_LABELS
    from .mini_apps import WebAgentMiniAppBroker
    with runtime.database.transaction(write=True) as db:
        db.execute('CREATE TABLE IF NOT EXISTS shopping_cart_confirmations (interaction_id TEXT PRIMARY KEY,invocation_id TEXT NOT NULL)')
    async def describe(runtime,principal,form,values,item):
        from ai2apps.agents.provider_forms import describe as generic
        result=await generic(runtime,principal,form,values,item)
        run=runtime.agents.get_run(item.run_id)
        broker=WebAgentMiniAppBroker(runtime);mounted=broker.registered(mini['id'],principal,run.session_id)
        catalog={row['id']:row for task in values.get('source_tasks',[]) for row in product_rows(broker.task_declared(mounted,principal,task).get('result') or {})}
        for field in result['fields']:
            if field['key']=='selected':
                field.update(presentation='records',columns=[{'key':'id','label':{'zh':'商品','en':'Product'},'type':'select','options':[{'value':k,'label':str(row.get('title',k))} for k,row in catalog.items()]},{'key':'quantity','label':{'zh':'数量','en':'Quantity'},'type':'number','minimum':1,'maximum':10}])
                result['schema']['properties']['selected']['items']['properties']['id']['enum']=list(catalog)
        return result
    FORMS[key]=replace(FORMS[key],describe=describe,prepare_values=cart_values)

def shopping_discovery(runtime,context,mini,spec):
    from .shopping_aaat import discovery_context
    return discovery_context(runtime,context)

def install(binder):
    for key,execute,policy,form,effects in (
        ('browser.travel-research/v1',travel,None,None,('external_read','network')),
        ('browser.shopping-research/v1',shopping,None,shopping_form,('external_read','network')),
        ('browser.cart-preparation/v1',shopping,None,shopping_form,('external_read','network','external_write')),
        ('browser.search-report/v1',search,confirmed_search,search_form,('external_read','network')),
        ('browser.article-reader/v1',reader,None,reader_form,('external_read','network'))):
        binder.register_protocol(HostProtocol(key,(HOST,),execute,policy=policy,form_setup=form,effects=effects,capabilities=('network.outbound',),normalize=normalize_search if execute is search else None,discovery=shopping_discovery if execute is shopping else None))
