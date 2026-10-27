"""Shopping Pro owns its AaAT workflow, calendar facts and cart consent."""

FORM_LABELS = {'profile': {'zh': '浏览器分身', 'en': 'Browser profile'}, 'pages': {'zh': '订单页数', 'en': 'Order pages'}, 'locale': {'zh': '输出语言', 'en': 'Output language'}, 'previous_task': {'zh': '之前的任务', 'en': 'Previous task'}, 'history_mode': {'zh': '购物历史', 'en': 'Purchase history'}, 'source_tasks': {'zh': '历史记录来源', 'en': 'Observed history tasks'}, 'selected': {'zh': '商品与目标数量', 'en': 'Products and target quantities'}, 'message': {'zh': '补充要求', 'en': 'Additional instructions'}, 'query': {'zh': '搜索内容', 'en': 'Search query'}, 'recipient': {'zh': '收礼人', 'en': 'Recipient'}, 'occasion': {'zh': '送礼场合', 'en': 'Occasion'}, 'preferences': {'zh': '偏好', 'en': 'Preferences'}, 'budget_minor': {'zh': '预算（最小货币单位）', 'en': 'Budget (minor currency units)'}, 'currency': {'zh': '货币', 'en': 'Currency'}, 'model_profile': {'zh': '模型配置', 'en': 'Model profile'}, 'conversation': {'zh': '对话上下文', 'en': 'Conversation context'}}
from copy import deepcopy
import json
import time
from ai2apps.services import ToolProviderError
from ai2apps.services.aaat import principal_for, AgentResultPolicy
from .mini_apps import WebAgentMiniAppBroker
from .shopping import product_rows, replenishment_date

APP='ai2apps.ai-browser'
MINI='ai2apps.shopping-pro'
DECLARATION={'schema':'ai2apps.aaat-declaration/v1','instructions':[
    'Shopping Pro prepares replenishment lists and Amazon carts from observed purchases. For a replenishment request use shopping.refresh_list (incremental history and recommendations), or shopping.recommend with existing cached source tasks. AaAT history_mode is incremental by default, or cache for no network history read. Full history reload is available ONLY inside Shopping Pro, never through AaAT. Saved history is selected by this owner automatically; do not request task IDs from the user. Reading history alone does not produce recommendations. Do not substitute your own ranking or a PDF for the Shopping Pro recommendation.',
    'shopping.prepare_cart arguments are source_tasks (observed browser_task_id strings), selected (an array of {id, quantity}), and profile. Example: {"source_tasks":["observed-task-id"],"selected":[{"id":"B000000001","quantity":2}],"profile":"default"}. Use selected, not report.items. Resolve first/next references against the displayed report order, preserving user quantities.',
    'Use returned browser_task_id as source_tasks for shopping.recommend and shopping.prepare_cart. Use the same browser profile. Products must come from observed history, never invented IDs or URLs.',
    'When a task needs assistance, relay its owner-provided message and observed quantities. Unverified cart quantities are not proof of authentication failure; never guess that login or captcha is required. Do not retry uncertain cart changes or claim success before the actual cart is verified.',
    'Present the owner report with its exact due_date, days_until_due and due_bucket. overdue<0, due_today=0, next_3_days=1..3, later>3, unknown=no repeat cycle. Do not reclassify four days away as within three days. Historical cycles are estimates, not stock measurements.',
    'For a list-first request, finish this turn by showing the replenishment report; do not open a cart form until the user subsequently asks to prepare the cart. After showing the replenishment list, offer shopping.prepare_cart. Open its confirmation form with observed source_tasks and selected IDs/quantities. Let the user review products and quantities before any cart changes. Cancellation is not permission. Only the actual verified cart result proves preparation; never checkout, pay or subscribe.'
], 'workflows':[{'intent':'刷新购买记录并生成补货单','capabilities':['shopping.refresh_list','shopping.history','shopping.recommend']},
 {'intent':'确认商品与数量后准备购物车','capabilities':['shopping.prepare_cart']}],
 'result_semantics':{'report':'Backend calendar facts and selected quantities are authoritative. Unknown prices remain null; monetary values are integer minor units. source_task is the observed-history task, not the recommendation task.',
 'history':'Incremental sync skips known order details; cache mode does not browse history. Recomputing a date-based recommendation does not require rereading purchases.',
 'cart':'Explicit out-of-stock products are skipped; partial results list skipped products and reasons. Unknown action outcomes still pause and prohibit automatic replay. prepare_cart verifies observed target quantities in the actual cart; existing equal/higher quantities may already satisfy the target. Failure or assistance is not success.'}}


def report(plan,catalog):
    observed={r['id']:r for r in catalog};items=[]
    for suggestion in plan.get('items',[]):
        if suggestion['id'] not in observed:continue
        item=observed[suggestion['id']]
        items.append({**suggestion,**replenishment_date(item),
            'title':item.get('title',suggestion['id']),'unit_price_minor':item.get('last_unit_price_minor'),
            'currency':item.get('last_price_currency'),'channel':item.get('preferred_channel','unknown')})
    totals={}
    for row in items:
        price=row['unit_price_minor'];currency=row['currency']
        row['line_total_minor']=price*row['quantity'] if type(price) is int and price>=0 and currency else None
        if row.get('selected') and row['line_total_minor'] is not None:totals[currency]=totals.get(currency,0)+row['line_total_minor']
    buckets={key:sum(r['due_bucket']==key for r in items) for key in ['overdue','due_today','next_3_days','later','unknown']}
    return {'items':items,'bucket_counts':buckets,'selected_count':sum(bool(r.get('selected')) for r in items),
            'selected_totals_minor':totals,'unknown_selected_prices':sum(bool(r.get('selected')) and r['line_total_minor'] is None for r in items),
            'basis':'local_calendar_day_and_observed_distinct_purchase_dates','message':plan.get('message','')}


def report_markdown(value):
    labels={'overdue':'已逾期','due_today':'今日到期','next_3_days':'未来3天内','later':'3天以后','unknown':'周期未知'}
    def text(value):return str(value).replace('|',r'\|').replace('\n',' ')[:240]
    lines=['Shopping Pro 补货单（历史周期估计，请核对实际库存）。',
        '| 商品 | 数量 | 预计补货日 | 日期分档 | 默认选择 |','| --- | ---: | --- | --- | --- |']
    for row in value['items']:
        lines.append('| '+text(row['title'])+' | '+str(row['quantity'])+' | '+str(row['due_date'] or '未知')+' | '+labels[row['due_bucket']]+' | '+('是' if row.get('selected') else '否')+' |')
    lines.append('')
    totals='，'.join(currency+' '+format(amount/100,'.2f') for currency,amount in value['selected_totals_minor'].items())
    if totals:lines.append('默认所选历史价格合计：'+totals+'（不含税费；当前价格以购物网站为准）。')
    if value['unknown_selected_prices']:lines.append('另有 '+str(value['unknown_selected_prices'])+' 件所选商品价格未知，未计入合计。')
    lines.append('加入购物车前需要确认商品和目标数量；此补货单尚未改变购物车。')
    return '\n'.join(lines)



def table_view(catalog, rows, *, cart=False):
    from .product_images import allowed
    observed={row['id']:row for row in catalog}
    labels={'overdue':'已逾期','due_today':'今日到期','next_3_days':'未来3天内','later':'3天以后','unknown':'周期未知'}
    columns=[{'key':'quantity','label':'数量'},{'key':'price','label':'历史单价'},{'key':'subtotal','label':'历史小计'},{'key':'channel','label':'渠道'}]
    columns+=([{'key':'status','label':'结果'}] if cart else [{'key':'due','label':'预计补货日'},{'key':'bucket','label':'日期分档'},{'key':'selected','label':'默认选择'}])
    items=[]
    for row in rows[:30]:
        source=observed.get(row['id'])
        if not source:continue
        fields={'quantity':str(row.get('quantity','未知')),'channel':{'fresh':'Amazon Fresh','whole_foods':'Whole Foods','amazon':'Amazon'}.get(source.get('preferred_channel'),'未知')}
        price=source.get('last_unit_price_minor');currency=source.get('last_price_currency')
        known=type(price) is int and price>=0 and bool(currency)
        quantity=row.get('quantity')
        fields['price']=currency+' '+format(price/100,'.2f') if known else '未知'
        fields['subtotal']=currency+' '+format(price*quantity/100,'.2f') if known and type(quantity) is int else '未知'
        if cart:fields['status']='已回读核实' if row.get('verified') else '未核实'
        else:fields.update(due=row.get('due_date') or '未知',bucket=labels.get(row.get('due_bucket'),'周期未知'),selected='是' if row.get('selected') else '否')
        item={'id':row['id'],'title':str(source.get('title',row['id']))[:500],'fields':fields}
        if source.get('url'):item['url']=source['url']
        if allowed(source.get('image_url','')):
            from urllib.parse import quote
            image_url=('/v1/platform/studios/ai2apps.ai-browser/shopping/tasks/'+quote(source['_source_task'],safe='')+'/products/'+quote(row['id'],safe='')+'/image') if source.get('_source_task') else source['image_url']
            item['image']={'url':image_url,'alt':item['title']}
        items.append(item)
    return {'schema':'ai2apps.aaat-view/v1','id':'cart' if cart else 'replenishment','layout':'table',
        'title':'已核实购物车商品' if cart else 'Shopping Pro 补货清单','columns':columns,'items':items,
        'summary':'仅显示实际回读的商品；未下单、未付款。' if cart else '历史周期估计，请核对库存；未改变购物车。缺少图片时保留占位。'}

def cart_values(runtime,principal,form,values,item):
    """Migrate the report-shaped draft before review; never authorize execution."""
    if 'items' not in values:return values
    alias=values['items']
    if 'selected' in values and values['selected']!=alias:
        raise ValueError('商品列表存在冲突，请核对 selected 与 items')
    values['selected']=alias
    del values['items']
    return values


def cart_receipt(runtime,args,context):
    if not context.invocation_id or not context.trace_id:raise ToolProviderError('Cart requires a durable confirmed invocation')
    run=runtime.agents.get_run(context.trace_id)
    if run.session_id!=context.session_id:raise ToolProviderError('Cart Session mismatch')
    provider=APP+'.shopping.prepare_cart'
    expected={k:v for k,v in args.items() if k!='provider'}
    for item in reversed(runtime.agents.list_interactions(run.id)):
        if item.ui_hints.get('provider')!=provider:continue
        from ai2apps.agents.form_continuation import selected_form
        from ai2apps.core import ResourceConflictError
        try:form=selected_form(runtime.database,item)
        except ResourceConflictError:break
        if form.key!=provider:break
        result=(item.response or {}).get('result') or {}
        if (item.status.value!='submitted' or (item.response or {}).get('status')!='completed'
            or item.ui_hints.get('provider_version')!=runtime.app_capability_router.providers[provider].version
            or result.get('capability')!='shopping.prepare_cart' or result.get('provider')!=provider
            or result.get('user_confirmed') is not True or result.get('configure_only') is not True or result.get('executed_in_app')
            or {k:v for k,v in result.get('arguments',{}).items() if k!='provider'}!=expected):break
        with runtime.database.transaction(write=True) as db:
            db.execute('INSERT OR IGNORE INTO shopping_cart_confirmations VALUES (?,?)',(item.id,context.invocation_id))
            if db.execute('SELECT invocation_id FROM shopping_cart_confirmations WHERE interaction_id=?',(item.id,)).fetchone()['invocation_id']!=context.invocation_id:break
        return
    raise ToolProviderError('Confirm the exact Shopping Pro products, quantities and profile in this Run before preparing the cart')


def install(runtime,register):
    from ai2apps.research.mini_apps import wait_task
    from ai2apps.agents.parameter_forms import FORMS, schema_fields, present_fields
    from dataclasses import replace
    with runtime.database.transaction(write=True) as db:
        db.execute('CREATE TABLE IF NOT EXISTS shopping_cart_confirmations (interaction_id TEXT PRIMARY KEY,invocation_id TEXT NOT NULL)')
    def discover(context):
        from .shopping_cache import latest_history, recent_tasks, discovery_mount
        principal=principal_for(runtime,context)
        broker=WebAgentMiniAppBroker(runtime);mounted=discovery_mount(broker,principal,context.session_id)
        if mounted is None:return {'history':{'available':False,'source_tasks':[]},'recent_tasks':[]}
        history=latest_history(broker,mounted,principal,'default')
        tasks=recent_tasks(broker,mounted,principal,session_id=context.session_id,limit=4)
        return {'history':{'source_tasks':[history['id']] if history else [],'profile':'default',
            'available':history is not None},'recent_tasks':[{
                'task_id':t['id'],'capability':'shopping.'+t['capability'],'profile':t['profile_key'],
                'state':t['status'],'message':str(t.get('message') or '')[:300],
                'failure':{k:str(v)[:300] for k,v in (t.get('failure') or {}).items() if k in ('code','message')},
                'arguments':{k:v[:20 if k=='selected' else 4] for k,v in t['input'].items() if k in ('selected','source_tasks') and isinstance(v,list)}} for t in tasks]}
    for operation in ('history','refresh_list','recommend','revise','prepare_cart','gift_recommend'):
        async def describe(principal,model=None,operation=operation):
            _,declaration=runtime.extension_manager._studio_mini_app_definition(APP,MINI,principal)
            entry=next(c for c in declaration['web_agent']['capabilities'] if c['id']==operation)
            schema=deepcopy(entry['source']['inputs'])
            schema['properties']['profile']={'type':'string','default':'default','title':'浏览器分身 / Browser Profile'}
            for key,title,default in [('pages','订单页数 / Pages',1),('locale','语言 / Language','zh'),('previous_task','先前历史任务 / Previous history','')]:
                if key in schema['properties']:schema['properties'][key].update(title=title,default=default)
            if operation in ('history','refresh_list'):
                schema['properties'].pop('previous_task',None)
                schema['required']=[key for key in schema.get('required',[]) if key!='previous_task']
                schema['properties']['history_mode']={'type':'string','enum':['incremental','cache'],'default':'incremental','title':'历史记录 / History','description':'增量检查新订单，或只使用本地缓存。全量重读仅可在 Shopping Pro 内操作。'}
            if 'source_tasks' in schema['properties']:schema['properties']['source_tasks']['title']='观察记录任务 / Observed history tasks'
            if 'selected' in schema['properties']:schema['properties']['selected']['title']='确认商品与目标数量 / Confirm products and target quantities'
            return {'effective_schema':schema,'fields':present_fields(schema_fields(schema),FORM_LABELS,{'history_mode':{'incremental':{'zh':'增量刷新','en':'Incremental refresh'},'cache':{'zh':'仅用本地缓存','en':'Local cache only'}},'locale':{'zh':{'zh':'中文','en':'Chinese'},'en':{'zh':'英文','en':'English'}}}),'selection_required':operation in ('history','refresh_list','prepare_cart','gift_recommend')}
        async def execute(args,context,operation=operation):
            if not context.invocation_id:raise ToolProviderError('Shopping requires a durable Tool invocation')
            principal=principal_for(runtime,context)
            if operation=='prepare_cart':cart_receipt(runtime,args,context)
            broker=WebAgentMiniAppBroker(runtime);mounted=broker.registered(MINI,principal,context.session_id)
            parameters={k:v for k,v in args.items() if k not in ('profile','history_mode')}
            mode=args.get('history_mode','incremental')
            if mode not in ('incremental','cache'):raise ToolProviderError('AaAT supports incremental or cached history only')
            history_operation=operation in ('history','refresh_list')
            if history_operation and args.get('previous_task'):
                raise ToolProviderError('AaAT resolves history references automatically; previous_task is not an input')
            if operation=='refresh_list':parameters['previous_task']=''
            if operation=='history' and mode=='cache':
                from .shopping_cache import latest_history
                observed=latest_history(broker,mounted,principal,args.get('profile','default'))
                if not observed:raise ToolProviderError('没有本地购物历史，请选择增量刷新。')
            else:
                task=broker.submit_declared(mounted,principal,capability=operation,
                    parameters=parameters,profile=args.get('profile','default'),
                    request_id='aaat-'+context.invocation_id,
                    **({'_shopping_history_mode':mode} if history_operation else {}))
                observed=await wait_task(runtime,broker,mounted,principal,task,context,time.monotonic()+850)
            raw=observed.get('result') or {};result={'browser_task_id':observed['id'],'result':raw,'untrusted':True}
            source_tasks=[observed['id']] if operation in ('history','refresh_list') else args.get('source_tasks',[])
            if operation in ('recommend','revise','refresh_list'):
                catalog=[{**row,'_source_task':observed['id']} for row in product_rows(raw)] if operation=='refresh_list' else [{**row,'_source_task':key} for key in source_tasks for row in product_rows(broker.task_declared(mounted,principal,key).get('result') or {})]
                plan=(raw.get('assigned') or {}).get('shopping_report',{}).get('plan',{}) if operation=='refresh_list' else raw
                result['report']=report(plan,catalog)
                result['aaat_view']=table_view(catalog,result['report']['items'])
            elif operation=='prepare_cart':
                catalog=[{**row,'_source_task':key} for key in source_tasks for row in product_rows(broker.task_declared(mounted,principal,key).get('result') or {})]
                result['aaat_view']=table_view(catalog,raw.get('items',[]),cart=True)
            result['aaat_context']={'schema':'ai2apps.aaat-result-context/v1','status':'partial' if raw.get('status')=='partial' else 'complete','data_trust':'untrusted',
                'scope':{'profile':args.get('profile','default'),'source_tasks':source_tasks},'coverage':{'task_status':observed['status']}}
            return result
        capability='shopping.'+operation
        register(capability,APP,'Shopping Pro: '+operation,
            {'refresh_list':'Refresh purchase history AND generate the replenishment list using Shopping Pro business rules.',
             'recommend':'Generate an authoritative replenishment list from observed history tasks, with exact calendar buckets.',
             'prepare_cart':'After user confirmation of products and quantities, prepare and verify the Amazon cart. Never checkout or pay.'}.get(operation,'Shopping Pro '+operation+' using observed purchases.'),
            {'type':'object','properties':{'profile':{'type':'string','default':'default'}},'additionalProperties':False},
            execute,mini=MINI,descriptor=describe,agent_context=DECLARATION,
            effects=('network','external_read','external_write') if operation=='prepare_cart' else ('network','external_read'),
            timeout_ms=900000,open_parameters=True,discovery_context=discover,form_summary={'zh':'依据购物历史生成建议；准备购物车需确认商品和数量，不下单或付款。','en':'Use observed purchases for recommendations; cart preparation requires product and quantity confirmation and never checks out or pays.'},form_name={'zh':{'history':'购物历史','refresh_list':'生成补货清单','recommend':'补货建议','revise':'调整补货清单','prepare_cart':'准备购物车','gift_recommend':'礼物推荐'}[operation],'en':{'history':'Purchase history','refresh_list':'Replenishment list','recommend':'Replenishment recommendations','revise':'Revise replenishment list','prepare_cart':'Prepare cart','gift_recommend':'Gift recommendations'}[operation]})
        if operation=='prepare_cart':
            async def cart_form(runtime,principal,form,values,item):
                definition=await describe_cart(principal)
                schema=definition['effective_schema'];fields=present_fields(schema_fields(schema),FORM_LABELS)
                run=runtime.agents.get_run(item.run_id)
                broker=WebAgentMiniAppBroker(runtime);mounted=broker.registered(MINI,principal,run.session_id)
                catalog={row['id']:row for key in values.get('source_tasks',[]) for row in product_rows(broker.task_declared(mounted,principal,key).get('result') or {})}
                selected=values.get('selected') or []
                selected=[row for row in selected if isinstance(row,dict)] if isinstance(selected,list) else []
                labels=[str(catalog.get(r.get('id'),{}).get('title',r.get('id','')))+' × '+str(r.get('quantity','')) for r in selected]
                for field in fields:
                    if field['key']=='selected':
                        field.update(label={'zh':'确认商品及目标数量（不下单、不付款）','en':'Confirm products and quantities (no checkout or payment)'},presentation='records',
                            columns=[{'key':'id','label':{'zh':'商品','en':'Product'},'type':'select','options':[{'value':key,'label':str(row.get('title',key))} for key,row in catalog.items()]},
                                     {'key':'quantity','label':{'zh':'目标数量','en':'Target quantity'},'type':'number','minimum':1,'maximum':10}],minItems=1,maxItems=20)
                        schema['properties']['selected']['items']['properties']['id']['enum']=list(catalog)

                return {'schema':schema,'fields':fields,'description':{'zh':'确认后将准备购物车（不下单、不付款）：\n'+'\n'.join(labels),'en':'Confirm to prepare the cart without checkout or payment:\n'+'\n'.join(labels)},'submit_label':{'zh':'确认加入购物车','en':'Confirm cart'}}
            describe_cart=describe
            key=APP+'.'+capability
            FORMS[key]=replace(FORMS[key],describe=cart_form,prepare_values=cart_values,prompt={'zh':'确认购物车商品和数量','en':'Confirm cart products'})
    def preview(step):
        out=step.output or {}
        return {k:out[k] for k in ('browser_task_id','report','aaat_context') if k in out}
    def finalize(content,steps):
        relevant=[step for step in steps if step.kind=='tool' and step.tool_name in ('shopping.refresh_list','shopping.recommend','shopping.revise','shopping.prepare_cart')]
        if relevant and relevant[-1].tool_name=='shopping.prepare_cart' and relevant[-1].status.value=='completed':
            raw=(relevant[-1].output or {}).get('result') or {}
            if raw.get('status') in ('partial','complete'):
                skipped=raw.get('skipped',[])
                text=str(raw.get('message') or '购物车已核实，未下单、未付款。')
                if skipped:text+='\n缺货未添加：'+'；'.join(str(r.get('title',r['id']))+' × '+str(r['quantity']) for r in skipped)
                return text,{'shopping_cart_task':relevant[-1].output['browser_task_id']}
        if relevant and relevant[-1].status.value=='completed' and isinstance(relevant[-1].output,dict) and relevant[-1].output.get('report'):
            return (('补货清单已生成，请核对下方商品、日期和选择；确认商品及数量后才能准备购物车。' if relevant[-1].output.get('aaat_view') else report_markdown(relevant[-1].output['report']))),{'shopping_report_task':relevant[-1].output['browser_task_id']}
        return content,None
    runtime.app_capability_router.register_result_policy(AgentResultPolicy('shopping-owner-report',
        lambda steps:{'role':'system','content':'Shopping Pro report fields are authoritative. Preserve calendar buckets and unknown values; a history read alone is not a recommendation. Show the actual cart outcome, never infer success from submission.'},
        finalize,preview,('shopping.refresh_list','shopping.recommend','shopping.revise','shopping.prepare_cart')))


async def owned_product_image(runtime,principal,task_id,product_id):
    from .tasks import BrowserTaskRepository
    from .product_images import product_images
    from ai2apps.api.ownership import authorize_session
    from ai2apps.api.agent_platform import _run_result
    tasks=BrowserTaskRepository(runtime.database,runtime.events)
    task=tasks.get(principal.actor_user_id,task_id)
    _,caller=tasks.program(principal.actor_user_id,task_id)
    if not caller.endswith(':'+MINI) or task['status']!='completed' or task['capability'] not in ('history','refresh_list','search_products'):
        raise ToolProviderError('Product image requires an owned completed Shopping observation')
    if task.get('session_id'):authorize_session(runtime,principal,task['session_id'])
    result=_run_result(runtime.agents.get_run(task['run_id'])) if task.get('run_id') else {}
    observed=next((row for row in product_rows(result) if row['id']==product_id),None)
    images=await product_images([observed]) if observed else []
    if not images:raise ToolProviderError('Observed product image is unavailable')
    return images[0]['image_data_url']
