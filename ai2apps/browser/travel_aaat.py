"""Trip Planner's trusted AaAT owner adapters; execution stays in Browser Tasks."""
from copy import deepcopy
from dataclasses import replace
from datetime import date
import asyncio
import hashlib
import json
import logging
import time

from ai2apps.research.mini_apps import principal_for, wait_task
from ai2apps.services import ToolProviderError
from .mini_apps import WebAgentMiniAppBroker
from .travel import MINI, TRIP, COMMON, PROVIDERS, obj, text, query_source, validate_trip, research_identity, default_sources

APP = 'ai2apps.ai-browser'
KINDS = {'flights': ['ctrip_flights', 'google_flights', 'expedia_flights'],
         'hotels': ['ctrip_hotels', 'booking', 'expedia_hotels'], 'guide': ['sights']}
DECLARATION = {
    'schema': 'ai2apps.aaat-declaration/v1',
    'instructions': [
        'Trip Planner researches travel only: never reserve, select a fare/room, book or pay.',
        'When sources are omitted or auto, prefer Ctrip for flights wholly within China and hotels in China; explicit sources always win. For other destinations use Google Flights/Booking. Do not treat Chinese input language as proof of domestic travel.',
        'Use travel.flights for flight quotes, travel.hotels for lodging, travel.guide for sightseeing research and itinerary suggestions. Ask for missing dates/cities; never infer an airport code or exact location.',
        'Use explicit origin_airport, destination_airport and excluded_airports for airport restrictions. An excluded airport must not be inferred as a different requested airport; preserve user scope and verify actual candidate airport evidence.',
        'Flights default to outbound only. Do not assume a return journey or date; require return_date only for explicitly selected both/return directions. Outbound quotes can be round-trip references; independent return one-way quotes cannot be added to them as a paired total.',
        'Use travel.refine with recent same-Session source_tasks to filter observed offers or propose changed criteria. A requery proposal is not execution or authority: review changes with the user, then call the affected flight/hotel capability with the reviewed parameters.',
        'Hotel area, bed, transit and breakfast constraints require native evidence. Missing evidence is unknown, not satisfied. Cheapest means cheapest among loaded comparable offers, not the whole market.',
        'Keep actual source Task IDs and links, partial failures, quote basis/currency and verification status. Sightseeing snippets are leads, not verified opening hours/tickets. Normal/privacy/system privacy use the common Mini-App model mechanism.',
        'Browser waiting_input without requires_user is normal execution. Resume human assistance through the existing Task; never submit a replacement for uncertain work.'],
    'workflows': [
        {'intent': 'Compare flights and hotels, then plan sightseeing',
         'capabilities': ['travel.flights', 'travel.hotels', 'travel.guide']},
        {'intent': 'Refine observed offers and review changed search criteria',
         'capabilities': ['travel.refine', 'travel.flights', 'travel.hotels']}],
    'result_semantics': {'coverage': 'Only observed candidates; partial/empty/unverified are not successful live availability.',
                         'authority': 'Read-only research; no result or next action authorizes booking.'}}

NAMES = {'flights': ('查询航班', 'Find flights'), 'hotels': ('查询酒店', 'Find hotels'),
         'guide': ('旅行攻略', 'Travel guide'), 'refine': ('优化出行结果', 'Refine travel results')}
LABELS = {k: {'zh': zh, 'en': en} for k, zh, en in [
    ('origin','出发城市 / 已确认机场','Origin city / confirmed airport'),
    ('destination','目的地','Destination'), ('departure','出发日期','Departure date'),
    ('return_date','返回日期','Return date'), ('hotel_checkin','入住日期','Check-in'),
    ('hotel_checkout','退房日期','Check-out'), ('adults','成人数','Adults'),
    ('purpose','出行目的','Trip purpose'), ('preferences','预算与其他偏好','Budget and preferences'),
    ('hotel_area','住宿区域 / 地标','Hotel area / landmark'), ('flight_cabin','舱位','Cabin'),
    ('origin_airport','指定出发机场','Origin airport'),('destination_airport','指定到达机场','Destination airport'),('excluded_airports','排除机场','Excluded airports'),
    ('nonstop_only','只看直飞','Nonstop only'), ('airline_preference','航空公司偏好','Airline preference'),
    ('hotel_bed','床型','Bed preference'), ('hotel_breakfast','早餐','Breakfast'),
    ('hotel_near_transit','靠近地铁','Near metro'), ('sources','查询网站','Sources'),
    ('direction','航程方向','Flight directions'), ('profile','浏览器分身','Browser Profile'),
    ('locale','结果语言','Result language'), ('model_profile','模型配置','Model profile'),
    ('source_tasks','已有结果引用','Existing result references'), ('request','优化要求','Refinement request'),
    ('previous_refinement','上次优化引用','Previous refinement reference'), ('retain_pages','保留查询页面','Keep search pages')]}
OPTIONS = {key: {value: {'zh': zh, 'en': en} for value, zh, en in values} for key, values in {
    'direction': [('both','去程和返程','Outbound and return'),('outbound','仅去程','Outbound only'),('return','仅返程','Return only')],
    'flight_cabin': [('economy','经济舱','Economy'),('premium_economy','超级经济舱','Premium economy'),('business','商务舱','Business'),('first','头等舱','First')],
    'hotel_bed': [('any','不限','Any'),('large_double','大床','Large double'),('twin','双床','Twin')],
    'hotel_breakfast': [('any','不限','Any'),('included','含早餐','Included'),('not_required','不要求早餐','Not required')],
    'purpose': [('leisure','旅游','Leisure'),('business','商务','Business'),('mixed','商务与旅游','Mixed')],
    'model_profile': [('normal','普通配置','Normal'),('privacy','隐私配置','Privacy')],
    'sources': [('auto','自动（境内优先携程）','Auto (Ctrip for China)'),('ctrip_flights','携程机票','Ctrip flights'),('ctrip_hotels','携程酒店','Ctrip hotels'),('google_flights','Google Flights','Google Flights'),('expedia_flights','Expedia 机票','Expedia flights'),('booking','Booking 酒店','Booking hotels'),('expedia_hotels','Expedia 酒店','Expedia hotels')]
}.items()}


def schema(operation):
    properties = {**deepcopy(COMMON), 'profile': {**text(100), 'default':'default'},
                  'retain_pages': {'type':'boolean','default':False}}
    properties['locale']['default'] = 'zh'
    properties['model_profile']['default'] = 'normal'
    if operation == 'refine':
        properties.update(request={**text(3000),'minLength':1}, source_tasks={
            'type':'array','items':{**text(100),'minLength':1},'minItems':1,'maxItems':10,'uniqueItems':True},
            previous_refinement=text(100))
        return obj(properties, ['request','source_tasks'])
    keys = ['destination','adults','purpose','preferences']
    keys += (['origin','departure','return_date','flight_cabin','nonstop_only','airline_preference','origin_airport','destination_airport','excluded_airports'] if operation=='flights'
             else ['hotel_checkin','hotel_checkout','hotel_area','hotel_bed','hotel_breakfast','hotel_near_transit'] if operation=='hotels'
             else ['departure','return_date'])
    properties.update({key:deepcopy(TRIP['properties'][key]) for key in keys})
    for key, value in {'adults':1,'purpose':'leisure','preferences':'','flight_cabin':'economy',
        'nonstop_only':False,'airline_preference':'','origin_airport':'','destination_airport':'','excluded_airports':[],'hotel_area':'','hotel_bed':'any',
        'hotel_breakfast':'any','hotel_near_transit':False}.items():
        if key in properties:properties[key]['default']=value
    required = ['destination'] + (['hotel_checkin','hotel_checkout'] if operation=='hotels' else ['departure'] if operation=='flights' else ['departure','return_date'])
    if operation=='flights':
        required.append('origin')
        properties['direction']={'type':'string','enum':['both','outbound','return'],'default':'outbound'}
    if operation in ('flights','hotels'):
        properties['sources']={'type':'array','items':{'type':'string','enum':['auto',*KINDS[operation]]},
                              'minItems':1,'maxItems':3,'uniqueItems':True,'default':['auto']}
    result = obj(properties,required)
    if operation=='flights':
        result['allOf']=[{'if':{'properties':{'direction':{'enum':['both','return']}},'required':['direction']},
                          'then':{'required':['return_date'],'properties':{'return_date':{'minLength':10}}}}]
    return result


def reviewed_trip(args, operation):
    start=args['hotel_checkin'] if operation=='hotels' else args['departure']
    end=args['hotel_checkout'] if operation=='hotels' else args.get('return_date','')
    if operation=='flights' and args.get('direction','outbound') in ('both','return') and not end:
        raise ValueError('请选择返回日期 / Choose a return date')
    trip = {'origin':'','destination':args['destination'],'departure':start,'return_date':end,
            'hotel_checkin':start,'hotel_checkout':end,'nights':(date.fromisoformat(end)-date.fromisoformat(start)).days if end else 1,
            'adults':1,'purpose':'leisure','preferences':''}
    trip.update({k:deepcopy(v) for k,v in args.items() if k in TRIP['properties']})
    validate_trip(trip,flights=operation=='flights',hotels=operation=='hotels')
    return trip


def combined_trip(tasks):
    """Compose independent flight/hotel observations without losing their scope."""
    groups={}
    for task in tasks:
        parameters=task['input'];provider=parameters.get('provider')
        if provider not in PROVIDERS:raise ToolProviderError('Unknown travel source')
        kind=PROVIDERS[provider][0];trip=parameters['trip']
        if kind in groups and research_identity(groups[kind],provider)!=research_identity(trip,provider):
            raise ToolProviderError('Choose results from one reviewed trip per research kind')
        groups.setdefault(kind,trip)
    anchor=groups.get('flight') or groups.get('hotel') or next(iter(groups.values()))
    for trip in groups.values():
        if (trip['destination'],trip['adults'])!=(anchor['destination'],anchor['adults']):
            raise ToolProviderError('Travel results have different destinations or occupancy')
    result=deepcopy(anchor)
    if 'hotel' in groups:
        hotel=groups['hotel']
        for key in ('hotel_checkin','hotel_checkout','hotel_area','hotel_bed','hotel_breakfast','hotel_near_transit'):
            if key in hotel:result[key]=deepcopy(hotel[key])
    result['preferences']='; '.join(dict.fromkeys(t.get('preferences','') for t in groups.values() if t.get('preferences')))[:2000]
    return result


class TravelAdapters:
    def __init__(self,runtime):self.runtime=runtime;self.broker=WebAgentMiniAppBroker(runtime)

    def resolve(self,context):
        principal=principal_for(self.runtime,context)
        return principal,self.broker.registered(MINI,principal,context.session_id)

    def discovery_mount(self,context):
        """Discovery reads existing authorized instances; it never launches one."""
        from ai2apps.api.ownership import authorize_session
        from ai2apps.core.errors import RepositoryError
        from ai2apps.studio.capability_broker import MountedMiniApp
        principal=principal_for(self.runtime,context)
        authorize_session(self.runtime,principal,context.session_id)
        definition,declaration=self.runtime.extension_manager._studio_mini_app_definition(APP,MINI,principal)
        with self.runtime.database.transaction() as db:
            rows=db.execute("SELECT i.id FROM app_instances i JOIN app_definitions d ON d.id=i.app_definition_id WHERE d.package_id=? AND i.status='active' ORDER BY i.updated_at DESC",
                            (definition['package_id'],)).fetchall()
        for row in rows:
            try:self.runtime.extension_manager.require_instance_access(row['id'],principal)
            except (RepositoryError,RuntimeError):continue
            return principal,MountedMiniApp(mount={'app_instance_id':row['id'],'app_key':definition['package_id'],
                'effective_digest':definition['effective_digest'],'interaction_session_id':context.session_id},
                declaration=declaration,capabilities=frozenset())
        return principal,None

    def observed(self,mounted,principal,task_id,context,profile):
        task=self.broker.task_declared(mounted,principal,task_id)
        if task.get('session_id')!=context.session_id or task['profile_key']!=profile:
            raise ToolProviderError('Travel result must belong to this Session and Profile')
        if task['status']!='completed' or task['capability'] not in ('query','refine'):
            raise ToolProviderError('Travel result is not a completed research/refinement Task')
        return task

    async def execute(self,operation,args,context):
        from jsonschema import Draft202012Validator
        args=deepcopy(args);spec=schema(operation)
        for key,field in spec['properties'].items():
            if key not in args and 'default' in field:args[key]=deepcopy(field['default'])
        Draft202012Validator(spec).validate(args)
        if not context.invocation_id:raise ToolProviderError('Travel requires a durable Tool invocation')
        trip=reviewed_trip(args,operation) if operation!='refine' else None
        principal,mounted=self.resolve(context)
        profile=args['profile'];common={k:args[k] for k in COMMON}
        batch='aaat-travel-'+hashlib.sha256(context.invocation_id.encode()).hexdigest()[:32]
        deadline=time.monotonic()+850
        async def run(capability,parameters,key,report_context=context):
            task=self.broker.submit_declared(mounted,principal,capability=capability,parameters=parameters,
                profile=profile,request_id=batch+'-'+key,retain_pages=args['retain_pages'])
            return await wait_task(self.runtime,self.broker,mounted,principal,task,report_context,deadline)
        if operation=='refine':
            sources=[self.observed(mounted,principal,key,context,profile) for key in args['source_tasks']]
            if any(t['capability']!='query' for t in sources):raise ToolProviderError('Refinement needs query Tasks')
            parameters={**common,'trip':combined_trip(sources),'request':args['request'],'source_tasks':args['source_tasks']}
            if args.get('previous_refinement'):
                old=self.observed(mounted,principal,args['previous_refinement'],context,profile)
                if old['capability']!='refine':raise ToolProviderError('Expected a refinement Task')
                parameters['previous_refinement']=old['id']
            observed=await run('refine',parameters,'refine')
            result=self.result([observed],[],profile)
            proposal=observed.get('result') or {}
            result.update(proposal=proposal,requires_review=proposal.get('action') in ('requery','clarify'))
            result['aaat_context']['status']=('ambiguous' if proposal.get('action')=='clarify' else
                'resolved' if proposal.get('action')=='requery' else 'complete' if proposal.get('selection') else 'partial')
            return result
        sources=args.get('sources',['auto'])
        if 'auto' in sources:
            if len(sources)!=1:raise ToolProviderError('Choose auto or explicit sources, not both')
            sources=default_sources(trip, {'flights':'flight','hotels':'hotel'}.get(operation,operation))
        jobs=[(provider,leg) for provider in sources
              for leg in (['outbound','return'] if args.get('direction')=='both' else [args.get('direction','outbound')])]
        # Validate every source before any Task, including confirmed IATA scope.
        for provider,leg in jobs:query_source({**common,'trip':trip,'provider':provider,'leg':leg})
        completed=[];failures=[]
        async def one(provider,leg):
            async def progress(update):
                await context.report_progress(update.get('text','Travel research'),phase=update.get('phase','tool'),
                    content={**update.get('content',{}),'completed_sources':[t['id'] for t in completed]})
            try:
                task=await run('query',{**common,'trip':trip,'provider':provider,'leg':leg},provider+'-'+leg,
                               replace(context,progress_reporter=progress))
                completed.append(task)
                await context.report_progress('来源结果已就绪 / Source results ready',phase='travel',
                    content={'browser_task_id':task['id'],'travel_sources':self.result(completed,failures,profile)['sources']})
            except (ToolProviderError,TimeoutError) as error:
                failures.append({'provider':provider,'leg':leg,'message':str(error)[:700],
                                 **getattr(error,'details',{})})
        async with asyncio.TaskGroup() as group:
            for job in jobs:group.create_task(one(*job))
        result=self.result(completed,failures,profile)
        if operation=='guide' and completed:
            try:
                summary=await run('summarize',{**common,'trip':trip,'source_tasks':[t['id'] for t in completed]},'summary')
                result['itinerary']=summary.get('result') or {}
                result['summary_task_id']=summary['id']
            except (ToolProviderError,TimeoutError) as error:
                result['failures'].append({'phase':'summary','message':str(error)[:700],**getattr(error,'details',{})})
                result['aaat_context']['status']='partial'
        return result

    @staticmethod
    def result(tasks,failures,profile):
        sources=[{'browser_task_id':t['id'],'parameters':t['input'],'result':t.get('result') or {}} for t in tasks]
        complete=bool(sources) and not failures and all(s['result'].get('status') not in ('partial','empty') for s in sources)
        return {'source_tasks':[t['id'] for t in tasks],'sources':sources,'failures':deepcopy(failures),
            'untrusted':True,'aaat_context':{'schema':'ai2apps.aaat-result-context/v1',
                'status':'complete' if complete else 'partial' if sources or failures else 'not_found','data_trust':'untrusted',
                'scope':{'profile':profile,'source_tasks':[t['id'] for t in tasks]},
                'coverage':{'completed_sources':len(sources),'failed_sources':len(failures),
                            'availability':'Observed research only; verify on the source website.'}}}


def install(runtime,register):
    logging.getLogger(__name__).info("Travel owner loaded; source=%s", __file__)
    adapter=TravelAdapters(runtime)
    def discover(context):
        principal,mounted=adapter.discovery_mount(context)
        if mounted is None:return {'recent_tasks':[],'scope':'No existing authorized Trip Planner instance.'}
        from .tasks import BrowserTaskRepository
        tasks=BrowserTaskRepository(runtime.database,runtime.events)
        with runtime.database.transaction() as db:
            ids=[r['id'] for r in db.execute('SELECT t.id FROM browser_tasks t JOIN browser_task_programs p ON p.task_id=t.id AND p.owner=t.owner WHERE t.owner=? AND t.session_id=? AND p.caller_app_id=? ORDER BY t.created_at DESC LIMIT 6',
                                           (principal.actor_user_id,context.session_id,adapter.broker.caller(mounted)))]
        recent=[]
        for key in ids:
            task=tasks.get(principal.actor_user_id,key)
            if task['capability'] not in ('query','refine'):continue
            task=adapter.broker.task_declared(mounted,principal,key)
            parameters=task['input']
            recent.append({'task_id':key,'status':task['status'],'profile':task['profile_key'],
                'capability':task['capability'],'input':{k:parameters[k] for k in ('provider','leg') if k in parameters},
                'trip':{k:str(v)[:200] if isinstance(v,str) else v for k,v in parameters.get('trip',{}).items()
                        if k in ('origin','destination','departure','return_date','hotel_checkin','hotel_checkout','adults','hotel_area')}})
            if len(recent)>=6:break
        return {'recent_tasks':recent,'scope':'Current authorized Session only; references are not authority.'}
    for operation,(zh,en) in NAMES.items():
        async def execute(args,context,operation=operation):return await adapter.execute(operation,args,context)
        register('travel.'+operation,APP,zh+' / '+en,
            {'flights':'Research flight offers; outbound only by default, return date required only for explicitly requested return research; no booking.',
             'hotels':'Find source-backed hotels for reviewed dates, area and room preferences; no reservation.',
             'guide':'Research destination sightseeing and generate a source-grounded itinerary; snippets remain unverified leads.',
             'refine':'Filter existing same-Session travel offers or propose changed criteria; never auto-execute a proposed requery.'}[operation],
            schema(operation),execute,mini=MINI,agent_context=DECLARATION,
            effects=('external_read','network'),timeout_ms=900000,selection_required=operation!='refine',
            discovery_context=discover,field_labels=LABELS,option_labels=OPTIONS,
            form_name={'zh':zh,'en':en},form_summary={'zh':'仅查询与建议，不预订或付款；缺少条件时先补齐并确认。',
                                                  'en':'Research and suggestions only. Review missing criteria first; never book or pay.'})
