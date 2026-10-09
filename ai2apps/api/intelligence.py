"""Owner-scoped Intelligence Center API; browser actions stay in the BiDi SDK."""
from typing import Literal
from threading import RLock
from starlette.concurrency import run_in_threadpool
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from ai2apps.api.identity import require_app_capability
from ai2apps.intelligence.models import ChannelInput, SourceInput, Page, Candidate, ChannelQuestion, ArticleCover, ArticleImages, public_url
from ai2apps.intelligence.store import IntelligenceStore, stamp
from ai2apps.intelligence import entity_categories, entities, post_filter, service, site_agents, knowledge_sync, topics, writing, feedback as article_feedback
from ai2apps.browser.profiles import BrowserProfileRepository


class SocialResult(BaseModel):
    token: str = Field(max_length=64)
    outcome: Literal['success','failed','needs_user','restricted','not_started']


class ManualPage(BaseModel):
    page: Page
    profile_key: str = Field(default='default', max_length=160)


class SectionOrder(BaseModel):
    ids: list[str] = Field(max_length=32)


class Claim(BaseModel):
    scheduled: bool = False


class Progress(BaseModel):
    message: str = Field(max_length=500)
    status: Literal['running', 'failed', 'cancelled'] = 'running'


class SourceLog(BaseModel):
    source_id: str = Field(max_length=64)
    name: str = Field(max_length=160)
    status: Literal['success', 'failed', 'needs_user', 'restricted', 'deferred']
    message: str = Field(default='', max_length=500)
    pages: int = Field(default=0, ge=0, le=6)
    skipped: int = Field(default=0, ge=0, le=40)
    agent_stats: dict[str, int] = Field(default_factory=dict, max_length=10)


class Finish(BaseModel):
    pages: list[Page] = Field(max_length=36)
    logs: list[SourceLog] = Field(max_length=12)


class NewEntity(BaseModel):
    name: str = Field(min_length=1,max_length=160)
    kind: Literal['company','brand','product','model','person','organization','event','industry']

class EntityQuestion(BaseModel):
    question: str = Field(min_length=1,max_length=3000)

class EntityMove(BaseModel):
    target_id: str = Field(min_length=1,max_length=64)
    fact_ids: list[str] = Field(min_length=1,max_length=500)

class LeadStatus(BaseModel):
    status: Literal['read','ignored','new']
    reason: str = Field(default='',max_length=1000)

class Candidates(BaseModel):
    candidates: list[Candidate] = Field(max_length=40)


class CandidateCheck(Candidates):
    seen_urls: list[str] = Field(default_factory=list, max_length=72)

    @field_validator('seen_urls')
    @classmethod
    def canonical_seen_urls(cls, values):
        return [public_url(value) for value in values]


class Feedback(BaseModel):
    feedback: Literal['', 'more', 'less'] | None = None
    read: bool | None = None
    reasons: list[str] = Field(default_factory=list, max_length=6)
    reason_signature: str | None = Field(default=None, max_length=64)


def create_intelligence_router(runtime_provider, principal_provider):
    router = APIRouter(prefix='/intelligence', tags=['intelligence'], dependencies=[
        Depends(require_app_capability(principal_provider, 'app.use'))])
    dep = Depends(principal_provider)
    store_cache = {}
    finishing = set()
    planning = set()
    chatting = set()
    topic_planning = set()
    reason_planning = set()
    drafting = set()
    knowledge_lock = RLock()

    def sync(principal, channel=None, retry=False):
        with knowledge_lock:
            return knowledge_sync.sync_pending(store(), getattr(runtime_provider(), 'knowledge', None), principal, channel, retry)

    @router.get('/knowledge/buckets')
    def knowledge_buckets(principal=dep):
        knowledge = getattr(runtime_provider(), 'knowledge', None)
        return {'items': knowledge_sync.available_buckets(knowledge, principal) if knowledge else []}

    @router.post('/knowledge-sync')
    def pump_knowledge(principal=dep):
        return sync(principal)

    @router.post('/channels/{id}/knowledge-sync')
    def retry_knowledge(id: str, principal=dep):
        checked(store().get, 'channels', principal.actor_user_id, id)
        return sync(principal, id, True)


    def store():
        root = runtime_provider().config.paths.artifacts_path / 'intelligence'
        if str(root) not in store_cache:
            store_cache[str(root)] = IntelligenceStore(root)
        return store_cache[str(root)]

    def checked(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except KeyError as error:
            raise HTTPException(404, str(error)) from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    def check_profile(owner, key):
        if key != 'default':
            checked(BrowserProfileRepository(runtime_provider().database).require, owner, key)

    @router.get('')
    def snapshot(principal=dep):
        return store().snapshot(principal.actor_user_id)

    @router.post('/channels')
    async def add_channel(body: ChannelInput, request: Request, principal=dep):
        data = body.model_dump()
        checked(knowledge_sync.validate_buckets, getattr(runtime_provider(), 'knowledge', None), principal, body.knowledge_bucket_ids)
        try:
            data['sections'] = await service.plan_sections(runtime_provider(), request, principal, data)
            data['entity_taxonomy'] = await entity_categories.plan(runtime_provider(), request, principal, data)
        except TimeoutError as error:
            raise HTTPException(504, 'AI 创建栏目超时，频道尚未创建，请重试') from error
        result = checked(store().save_channel, principal.actor_user_id, data)
        if body.interval_hours:
            from ai2apps.api.agent_platform import _session
            with runtime_provider().intelligence_collector.store.connect() as db:
                db.execute('INSERT INTO collection_schedules VALUES(?,?) ON CONFLICT(owner) DO UPDATE SET session_id=excluded.session_id', (principal.actor_user_id,_session(runtime_provider(),principal,None)))
        return result

    @router.put('/channels/{id}')
    def edit_channel(id: str, body: ChannelInput, principal=dep):
        with knowledge_lock:
            checked(store().get, 'channels', principal.actor_user_id, id)
            checked(knowledge_sync.validate_buckets, getattr(runtime_provider(), 'knowledge', None), principal, body.knowledge_bucket_ids)
            result = checked(store().save_channel, principal.actor_user_id, body.model_dump(), id)
            from ai2apps.api.agent_platform import _session
            collector = runtime_provider().intelligence_collector
            with collector.store.connect() as db:
                db.execute('INSERT INTO collection_schedules VALUES(?,?) ON CONFLICT(owner) DO UPDATE SET session_id=excluded.session_id', (principal.actor_user_id,_session(runtime_provider(),principal,None)))
            sync(principal, id)
            return result

    @router.get('/channels/{id}/drafts')
    def list_drafts(id: str, principal=dep):
        return {'items':checked(store().drafts,principal.actor_user_id,id)}

    @router.get('/drafts/{id}')
    def get_draft(id: str, principal=dep):
        return checked(store().draft,principal.actor_user_id,id)

    @router.post('/channels/{id}/drafts')
    async def create_draft(id: str, body: writing.CreateDraft, request: Request, principal=dep):
        owner=principal.actor_user_id
        channel=checked(store().get,'channels',owner,id)
        try:previous=store().draft(owner,body.request_id)
        except KeyError:previous=None
        if previous:
            if previous['channel_id']!=id or previous['create_input']!=body.model_dump():
                raise HTTPException(409,'请求编号已使用，请重新创建稿件')
            return previous
        token=(owner,body.request_id)
        if token in drafting:raise HTTPException(409,'此稿件正在生成，请稍后重试')
        scope=checked(writing.select_evidence,channel,store().snapshot(owner)['articles'],body)
        draft={'id':body.request_id,'channel_id':id,'kind':body.kind,'guidance':body.guidance,
            'scope':body.scope,'scope_id':body.scope_id,'scope_label':scope['label'],
            'evidence':scope['evidence'],'total_articles':scope['total_articles'],'create_input':body.model_dump(),
            'turns':[],'revision':1,'created_at':stamp()}
        drafting.add(token)
        try:
            result=await writing.compose(runtime_provider(),request,principal,id,draft,body.guidance)
            draft.update(title=result['title'],current=result,updated_at=stamp())
            draft['turns']=[{'request_id':body.request_id,'revision':1,'guidance':body.guidance,'note':result['note'],'created_at':draft['updated_at']}]
            return checked(store().save_draft,owner,draft)
        except TimeoutError as error:
            raise HTTPException(504,'稿件生成超时，可重试；不会重复创建') from error
        finally:drafting.discard(token)

    @router.post('/drafts/{id}/revise')
    async def revise_draft(id: str, body: writing.ReviseDraft, request: Request, principal=dep):
        owner=principal.actor_user_id
        draft=checked(store().draft,owner,id)
        previous=next((t for t in draft['turns'] if t['request_id']==body.request_id),None)
        if previous:
            if previous['guidance']!=body.guidance or previous['revision']!=body.revision+1:
                raise HTTPException(409,'请求编号已使用，请重新提交修改')
            return draft
        if draft['revision']!=body.revision:raise HTTPException(409,'稿件已更新，请重新打开后修改')
        token=(owner,id)
        if token in drafting:raise HTTPException(409,'此稿件正在修改，请稍后重试')
        drafting.add(token)
        try:
            result=await writing.compose(runtime_provider(),request,principal,draft['channel_id'],draft,body.guidance)
            draft.update(title=result['title'],current=result,revision=body.revision+1,updated_at=stamp())
            draft['turns'].append({'request_id':body.request_id,'revision':draft['revision'],'guidance':body.guidance,'note':result['note'],'created_at':draft['updated_at']})
            return checked(store().save_draft,owner,draft,body.revision)
        except TimeoutError as error:
            raise HTTPException(504,'修改超时，原稿保留，可重试') from error
        finally:drafting.discard(token)

    entity_jobs = set()

    def entity_repo():
        return entities.Repository(store())

    @router.post('/entities')
    def new_entity(body: NewEntity,principal=dep):
        return checked(entity_repo().create,principal.actor_user_id,body.name,body.kind)

    @router.get('/entities')
    def entity_snapshot(principal=dep):
        return entity_repo().snapshot(principal.actor_user_id)

    @router.post('/channels/{id}/entity-categories')
    async def plan_entity_categories(id: str, request: Request, principal=dep):
        owner=principal.actor_user_id
        checked(store().get,'channels',owner,id)
        if owner in entity_jobs:raise HTTPException(409,'正在整理实体，请稍后')
        entity_jobs.add(owner)
        try:
            await entity_categories.organize(runtime_provider(),request,principal,store(),id,replan=True)
            return entity_repo().snapshot(owner)
        except ValueError as error:
            raise HTTPException(409,str(error)) from error
        except TimeoutError as error:
            raise HTTPException(504,'AI 规划实体分类超时，原分类保留，请重试') from error
        finally:entity_jobs.discard(owner)

    @router.post('/channels/{id}/entities')
    async def build_entities(id: str, request: Request, principal=dep):
        owner=principal.actor_user_id
        checked(store().get,'channels',owner,id)
        if owner in entity_jobs: raise HTTPException(409,'正在整理实体，请稍后')
        entity_jobs.add(owner)
        try:
            repo=entity_repo()
            articles=[a for a in store().snapshot(owner)['articles'] if a['channel_id']==id]
            pending=repo.pending(owner,articles)
            # Bounded request, checkpoints after every article; next call resumes.
            for article in pending[:8]:
                plan=await entities.extract_or_review(runtime_provider(),request,principal,article,repo)
                checked(repo.ingest,owner,article,plan)
            await entity_categories.organize(runtime_provider(),request,principal,store(),id)
            return {'processed':min(8,len(pending)),'remaining':max(0,len(pending)-8),**repo.snapshot(owner)}
        except TimeoutError as error:
            raise HTTPException(504,'实体整理超时，已完成部分保留，可继续整理') from error
        finally: entity_jobs.discard(owner)

    @router.post('/entities/{id}/images')
    def entity_images(id: str, body: entities.EntityImageSettings, principal=dep):
        return checked(entity_repo().image_settings,principal.actor_user_id,id,body)

    @router.post('/entities/{id}/dismiss')
    def dismiss_entity(id: str, principal=dep):
        return checked(entity_repo().dismiss,principal.actor_user_id,id,True)

    @router.post('/entities/{id}/restore')
    def restore_entity(id: str, principal=dep):
        return checked(entity_repo().dismiss,principal.actor_user_id,id,False)

    @router.put('/entities/{id}')
    def entity_settings(id: str, body: entities.EntitySettings, principal=dep):
        return checked(entity_repo().settings,principal.actor_user_id,id,body)

    @router.post('/entities/{id}/move-facts')
    def entity_move(id: str,body: EntityMove,principal=dep):
        return checked(entity_repo().move,principal.actor_user_id,id,body.target_id,body.fact_ids)

    @router.post('/entities/{id}/question')
    async def entity_question(id: str,body: EntityQuestion,request: Request,principal=dep):
        repo=entity_repo();checked(repo.get,principal.actor_user_id,id)
        e=next((e for e in repo.snapshot(principal.actor_user_id)['entities'] if e['id']==id),None)
        if not e: raise HTTPException(404,'没有可访问的实体证据')
        return await entities.answer(runtime_provider(),request,principal,e,body.question)

    @router.post('/entities/opportunities/evaluate')
    async def evaluate_entities(request: Request,principal=dep):
        owner=principal.actor_user_id
        if owner in entity_jobs: raise HTTPException(409,'正在整理实体，请稍后')
        entity_jobs.add(owner)
        try:
            repo=entity_repo();snapshot=repo.snapshot(owner);count=0
            for entity in snapshot['entities']:
                if not entity['watched'] or not entity['rule'].strip(): continue
                digest=entities.signature([entity['rule'],[(f['id'],f['historical']) for f in entity['facts']]])
                if entity.get('evaluated_signature')==digest: continue
                lead=await entities.opportunity(runtime_provider(),request,principal,entity,[l for l in snapshot['opportunities'] if l['entity_id']==entity['id']])
                checked(repo.save_lead,owner,entity,digest,lead);count+=1
                if count>=5: break
            return {'evaluated':count,**repo.snapshot(owner)}
        except TimeoutError as error:
            raise HTTPException(504,'机会分析超时，已完成部分保留') from error
        finally: entity_jobs.discard(owner)

    @router.patch('/entities/opportunities/{id}')
    def opportunity_status(id: str,body: LeadStatus,principal=dep):
        return checked(entity_repo().lead_status,principal.actor_user_id,id,body.status,body.reason)

    @router.post('/channels/{id}/topics')
    async def channel_topics(id: str, request: Request, principal=dep):
        owner = principal.actor_user_id
        channel = checked(store().get, 'channels', owner, id)
        articles = topics.recent([a for a in store().snapshot(owner)['articles'] if a['channel_id']==id])
        digest = topics.signature(articles)
        if channel.get('hot_topics',{}).get('signature') == digest:
            return channel['hot_topics']
        if (owner,id) in topic_planning:
            raise HTTPException(409, '此频道正在整理热点，请稍后刷新')
        topic_planning.add((owner,id))
        try:
            result = await topics.summarize(runtime_provider(),request,principal,channel,articles)
            return checked(store().save_topics,owner,id,digest,result)
        except TimeoutError as error:
            raise HTTPException(504, '热点整理超时，已有热点保留，请重试') from error
        finally:
            topic_planning.discard((owner,id))

    @router.get('/channels/{id}/conversation')
    def conversation(id: str, principal=dep):
        return {'turns': checked(store().conversation, principal.actor_user_id, id)}

    @router.post('/channels/{id}/conversation')
    async def ask_channel(id: str, body: ChannelQuestion, request: Request, principal=dep):
        owner = principal.actor_user_id
        channel = checked(store().get, 'channels', owner, id)
        previous = checked(store().conversation_turn, owner, id, body.request_id)
        if previous:
            if previous['question'] != body.question or previous.get('article_id') != body.article_id:
                raise HTTPException(409, '请求编号已被使用，请重新提问')
            return previous
        if (owner,id) in chatting:
            raise HTTPException(409, '此频道正在回答，请稍后重试')
        if body.article_id:
            selected = checked(store().get, 'articles', owner, body.article_id)
            if selected['channel_id'] != id:
                raise HTTPException(422, '所选文章不属于当前频道')
        chatting.add((owner,id))
        try:
            articles = [a for a in store().snapshot(owner)['articles'] if a['channel_id']==id]
            history = store().conversation(owner,id)
            answer = await service.converse(runtime_provider(),request,principal,channel,body.question,articles,history,body.article_id)
            return checked(store().save_conversation, owner,id,
                {'id':body.request_id,'question':body.question,'article_id':body.article_id,'created_at':stamp(),**answer})
        except TimeoutError as error:
            raise HTTPException(504, '回答超时，请重试；问题不会重复保存') from error
        finally:
            chatting.discard((owner,id))

    async def save_manual(id, article, identity, request, principal):
        channel = checked(store().get, 'channels', principal.actor_user_id, id)
        if channel.get('sections'):
            assignments = await service.classify_articles(runtime_provider(), request, principal, channel, channel['sections'], [{**article, 'id': 'manual'}])
            article['section_id'] = assignments['manual']
        result = checked(store().import_article, principal.actor_user_id, id, article, identity)
        await run_in_threadpool(sync, principal, id)
        return result

    @router.post('/channels/{id}/import-url')
    async def import_url(id: str, body: ManualPage, request: Request, principal=dep):
        checked(store().get, 'channels', principal.actor_user_id, id)
        p = body.page
        source = dict(url=p.url, title=p.title, source_name='手动收录', source_id='', profile_key=body.profile_key, retrieved_at=stamp(), content_type='webpage')
        images = [dict(url=i.url, alt=i.alt, source_url=p.url) for i in p.images if i.url]
        article = dict(title=p.title or p.url, summary=p.text[:500], body=p.text, sources=[source], images=images)
        if p.image_url:
            article['cover_image'] = dict(url=p.image_url, source_url=p.url)
        return await save_manual(id, article, p.url, request, principal)

    @router.post('/channels/{id}/import-file')
    async def import_file(id: str, request: Request, file: UploadFile = File(...), title: str = Form(''), summarize_image: bool = Form(False), principal=dep):
        import hashlib
        import tempfile
        from pathlib import Path
        from ai2apps.intelligence import manual_import
        checked(store().get, 'channels', principal.actor_user_id, id)
        name = Path(file.filename or '文件').name[:200]
        suffix = Path(name).suffix.lower()
        if suffix not in manual_import.EXTENSIONS:
            raise HTTPException(422, '不支持此文件格式')
        data = await file.read(manual_import.LIMIT + 1)
        await file.close()
        if not data or len(data) > manual_import.LIMIT:
            raise HTTPException(422, '请选择不超过 20MB 的非空文件')
        with tempfile.TemporaryDirectory(prefix='intel-import-') as temp:
            path = Path(temp) / ('document' + suffix)
            path.write_bytes(data)
            try:
                text, kind = await run_in_threadpool(manual_import.parse_file, path, name)
            except Exception as error:
                raise HTTPException(422, '文件读取失败：' + str(error)[:200]) from error
        generated = None
        if kind == 'image' and summarize_image:
            channel = checked(store().get, 'channels', principal.actor_user_id, id)
            generated = await manual_import.summarize_image(runtime_provider(), request, principal, channel, data)
        token = hashlib.sha256(data).hexdigest()
        target = manual_import.asset_path(store(), principal.actor_user_id, token)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        url = '/v1/platform/intelligence/imports/' + token + '/' + __import__('urllib.parse', fromlist=['quote']).quote(name, safe='')
        source = dict(url=url, title=name, source_name='本地文件 · ' + name, retrieved_at=stamp(), content_type=kind)
        article = dict(title=(title.strip() or Path(name).stem)[:200], summary=text[:500], body=text, sources=[source], images=[])
        if generated:
            article.update(generated, image_ai_summary=True)
            if title.strip():
                article['title'] = title.strip()[:200]
        if kind == 'image':
            article['cover_image'] = dict(url=url, source_url=url)
            article['images'] = [dict(url=url, source_url=url, alt=article['title'])]
        return await save_manual(id, article, 'file:' + token, request, principal)

    @router.get('/imports/{token}/{name}')
    def import_asset(token: str, name: str, principal=dep):
        from ai2apps.intelligence import manual_import
        path = checked(manual_import.asset_path, store(), principal.actor_user_id, token)
        if not path.is_file():
            raise HTTPException(404, '附件不存在')
        media = 'application/octet-stream'
        try:
            from PIL import Image
            with Image.open(path) as image:
                media = Image.MIME.get(image.format, media)
        except Exception:
            with path.open('rb') as stream:
                if stream.read(5) == b'%PDF-':
                    media = 'application/pdf'
        return FileResponse(path, media_type=media, filename=name, content_disposition_type='inline' if media.startswith('image/') or media == 'application/pdf' else 'attachment', headers={'X-Content-Type-Options': 'nosniff'})

    @router.put('/channels/{id}/sections/order')
    def reorder_sections(id: str, body: SectionOrder, principal=dep):
        return checked(store().reorder_sections, principal.actor_user_id, id, body.ids)

    @router.post('/channels/{id}/sections')
    async def initialize_sections(id: str, request: Request, principal=dep):
        owner = principal.actor_user_id
        channel = checked(store().get, 'channels', owner, id)
        if channel.get('sections') or (owner, id) in planning:
            raise HTTPException(409, '栏目已存在或正在创建，请刷新频道')
        planning.add((owner, id))
        try:
            sections = await service.plan_sections(runtime_provider(), request, principal, channel)
            articles = [a for a in store().snapshot(owner)['articles'] if a['channel_id'] == id]
            assignments = await service.classify_articles(runtime_provider(), request, principal, channel, sections, articles)
            return checked(store().initialize_sections, owner, id, sections, assignments, articles)
        except TimeoutError as error:
            raise HTTPException(504, 'AI 栏目整理超时，内容未修改，请重试') from error
        finally:
            planning.discard((owner, id))

    @router.delete('/channels/{id}')
    def delete_channel(id: str, principal=dep):
        with knowledge_lock:
            checked(store().delete, 'channels', principal.actor_user_id, id)
        return {'ok': True}

    @router.get('/source-agents')
    def source_agents(principal=dep):
        from ai2apps.agent_builder.repository import AgentBuilderRepository
        runtime = runtime_provider()
        result = []
        for draft in AgentBuilderRepository(runtime.database).list_drafts(principal.actor_user_id):
            if not draft.active_generation_id:
                continue
            try:
                record = site_agents.selected_agent(runtime, principal.actor_user_id, draft.active_generation_id)
            except ValueError:
                continue
            result.append({**record, 'name': draft.name})
        return {'agents': result}

    def check_source_agents(owner, body):
        for generation_id in (body.list_agent_generation_id, body.article_agent_generation_id):
            if generation_id:
                checked(site_agents.selected_agent, runtime_provider(), owner, generation_id)

    @router.post('/channels/{id}/sources')
    def add_source(id: str, body: SourceInput, principal=dep):
        check_profile(principal.actor_user_id, body.profile_key)
        check_source_agents(principal.actor_user_id, body)
        return checked(store().save_source, principal.actor_user_id, id, body.model_dump())

    @router.put('/sources/{id}')
    def edit_source(id: str, body: SourceInput, principal=dep):
        source = checked(store().get, 'sources', principal.actor_user_id, id)
        check_profile(principal.actor_user_id, body.profile_key)
        check_source_agents(principal.actor_user_id, body)
        return checked(store().save_source, principal.actor_user_id, source['channel_id'], body.model_dump(), id)

    @router.delete('/sources/{id}')
    def delete_source(id: str, principal=dep):
        checked(store().delete, 'sources', principal.actor_user_id, id)
        return {'ok': True}

    @router.post('/sources/{id}/social-claim')
    def claim_social(id: str, principal=dep):
        return checked(store().claim_social,principal.actor_user_id,id)

    @router.post('/sources/{id}/social-finish')
    def finish_social(id: str, body: SocialResult, principal=dep):
        return checked(store().finish_social,principal.actor_user_id,id,body.token,body.outcome)

    @router.post('/sources/{id}/social-resume')
    def resume_social(id: str, principal=dep):
        return checked(store().resume_social,principal.actor_user_id,id)

    @router.get('/sources/{id}/site-agent/{kind}')
    def get_site_agent(id: str, kind: Literal['list', 'article'], principal=dep):
        source = checked(store().get, 'sources', principal.actor_user_id, id)
        record = store().site_recipe(principal.actor_user_id, site_agents.recipe_key(source, kind))
        if record and record.get('healthy', True):
            from ai2apps.agent_builder.repository import AgentBuilderRepository
            from ai2apps.agent_builder.compiler import COMPILER_VERSION
            from ai2apps.core import RepositoryError
            try:
                generation = AgentBuilderRepository(runtime_provider().database).get_generation(record['generation_id'], principal.actor_user_id)
                if generation.status.value == 'active' and generation.compiler_version == COMPILER_VERSION:
                    return {'recipe': record}
            except RepositoryError:
                pass
        return {'recipe': None}

    @router.post('/sources/{id}/site-agent/learn')
    async def learn_site_agent(id: str, body: site_agents.LearnRequest, request: Request, principal=dep):
        source = checked(store().get, 'sources', principal.actor_user_id, id)
        try:
            candidate = await site_agents.learn(runtime_provider(), request, principal, source, body,
                store().site_recipe(principal.actor_user_id, site_agents.recipe_key(source, body.kind)))
            store().save_site_recipe(principal.actor_user_id, site_agents.recipe_key(source, body.kind), {**candidate, 'healthy': False})
            return candidate
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except TimeoutError as error:
            raise HTTPException(504, '网站规则学习超时，使用通用采集') from error

    @router.post('/sources/{id}/site-agent/invalidate')
    def invalidate_site_agent(id: str, body: dict, principal=dep):
        owner = principal.actor_user_id
        source = checked(store().get, 'sources', owner, id)
        if body.get('kind') not in ('list', 'article'):
            raise HTTPException(422, '无效规则类型')
        key = site_agents.recipe_key(source, body['kind'])
        store().invalidate_site_recipe(owner, key, body.get('generation_id'))
        return {'ok': True}

    @router.post('/sources/{id}/site-agent/activate')
    def activate_site_agent(id: str, body: site_agents.Activation, principal=dep):
        owner = principal.actor_user_id
        source = checked(store().get, 'sources', owner, id)
        from ai2apps.agent_builder.repository import AgentBuilderRepository
        repository = AgentBuilderRepository(runtime_provider().database)
        try:
            generation = repository.get_generation(body.generation_id, owner)
            draft = repository.get_draft(generation.draft_id, owner)
            rule = generation.ir['steps'][0]['arguments']['site_extraction']
            if (rule['origin'] != site_agents.scope_url(source['url']) or rule['kind'] not in ('list', 'article')
                or draft.source.get('provenance', {}).get('intelligence_recipe_key') != site_agents.recipe_key(source, rule['kind'])):
                raise ValueError('网站规则与信息源不匹配')
            if body.matched > body.samples or body.matched / body.samples < .6 or body.matched < min(2, body.samples):
                raise ValueError('运行时比对未通过')
            from ai2apps.agent_builder.models import StepOutcome
            repository.add_evidence(draft_id=draft.id, owner_user_id=owner, step_name='extract', generation_id=generation.id,
                outcome=StepOutcome.SUCCESS, evidence={'kind': rule['kind'], 'samples': body.samples, 'matched': body.matched, 'validation': 'generic-extraction-comparison'})
            repository.activate_generation(draft.id, generation.id, owner)
        except Exception as error:
            from ai2apps.core import RepositoryError
            if isinstance(error, RepositoryError):
                raise HTTPException(404, '网站采集版本不存在或不属于当前用户') from error
            if isinstance(error, (KeyError, ValueError)):
                raise HTTPException(422, '无效的网站采集版本') from error
            raise
        record = {'draft_id': draft.id, 'generation_id': generation.id, 'ir': generation.ir, 'rule': rule}
        store().save_site_recipe(owner, site_agents.recipe_key(source, rule['kind']), record)
        return record

    @router.post('/channels/{id}/runs')
    def claim(id: str, body: Claim, principal=dep):
        from ai2apps.api.agent_platform import _session
        runtime = runtime_provider()
        return checked(runtime.intelligence_collector.submit, principal, id,
                       _session(runtime, principal, None), body.scheduled)

    @router.patch('/runs/{id}')
    def progress(id: str, body: Progress, principal=dep):
        current = checked(store().get, 'runs', principal.actor_user_id, id)
        if current.get('execution_owner') == 'local' and body.status != 'cancelled':
            raise HTTPException(409, '本轮更新由 Local 后台执行，前台不能覆盖进度')
        checked(store().progress, principal.actor_user_id, id, body.message, body.status)
        runtime_provider().notifications.notify()
        return {'ok': True}

    @router.post('/channels/{id}/pending-pages')
    def pending_pages(id: str, body: CandidateCheck, principal=dep):
        return checked(store().pending_candidates, principal.actor_user_id, id,
                       [item.model_dump() for item in body.candidates], body.seen_urls)

    @router.get('/channels/{id}/filtered-posts')
    def filtered_posts(id: str, principal=dep):
        return {'items': checked(store().filtered_posts, principal.actor_user_id, id)}

    @router.post('/channels/{id}/filtered-posts/{item_id}/restore')
    def restore_post(id: str, item_id: str, principal=dep):
        return checked(store().restore_filtered_post, principal.actor_user_id, id, item_id)

    @router.post('/channels/{id}/post-candidates/{source_id}')
    async def post_candidates(id: str, source_id: str, body: Candidates, request: Request, principal=dep):
        owner = principal.actor_user_id
        channel = checked(store().get, 'channels', owner, id)
        source = checked(store().get, 'sources', owner, source_id)
        if source['channel_id'] != id:
            raise HTTPException(404, '信息源不属于此频道')
        history = {r['page']['url']: r for r in store().filtered_posts(owner,id)}
        candidates = [c.model_dump() for c in body.candidates]
        pending = [p for p in candidates if p['url'] not in history]
        decisions = await post_filter.review(runtime_provider(),request,principal,channel,pending,
                                            store().preferences(owner,id), 'list')
        rejected = set()
        for p,d in zip(pending,decisions):
            if d.reject:
                store().save_filtered_post(owner,id,{**p,'source_id':source_id},d.reason,'list')
                rejected.add(p['url'])
        kept = [p for p in candidates if p['url'] not in rejected and history.get(p['url'],{}).get('status') != 'filtered']
        return {'candidates': kept, 'filtered': len(candidates)-len(kept)}

    @router.post('/channels/{id}/recommend')
    async def recommend(id: str, body: Candidates, request: Request, principal=dep):
        channel = checked(store().get, 'channels', principal.actor_user_id, id)
        return await service.recommend(runtime_provider(), request, principal, channel, [c.model_dump() for c in body.candidates])

    @router.post('/runs/{id}/finish')
    async def finish(id: str, body: Finish, request: Request, principal=dep):
        owner = principal.actor_user_id
        run = checked(store().get, 'runs', owner, id)
        if run.get('execution_owner') == 'local':
            raise HTTPException(409, '本轮更新由 Local 后台提交结果')
        if run['status'] != 'running' or id in finishing:
            raise HTTPException(409, '此更新已结束或正在生成文章')
        finishing.add(id)
        validated_logs = None
        try:
            channel = checked(store().get, 'channels', owner, run['channel_id'])
            for log in body.logs:
                source = checked(store().get, 'sources', owner, log.source_id)
                if source['channel_id'] != channel['id']:
                    raise HTTPException(422, '更新记录包含其他频道的信息源')
            validated_logs = [log.model_dump() for log in body.logs]
            history = store().filtered_posts(owner, channel['id'])
            restored = [r['page'] for r in history if r['status']=='restored' and r['stage']=='detail']
            enabled = {s['id'] for s in store().snapshot(owner)['sources'] if s['channel_id']==channel['id'] and s['enabled']}
            restored = [p for p in restored if p['source_id'] in enabled]
            pages = checked(store().new_pages, owner, channel['id'], restored + [p.model_dump() for p in body.pages])
            # Keep evidence within a predictable context budget. Unprocessed pages are retried next time.
            budget, limited = 0, []
            for page in pages:
                if budget + len(page['text']) > 120000:
                    break
                limited.append(page)
                budget += len(page['text'])
            previous = [a for a in store().snapshot(owner)['articles'] if a['channel_id'] == channel['id']][:40]
            approved = {r['page']['url'] for r in history if r['status']=='restored'}
            posts = [p for p in limited if post_filter.is_post(p) and p['url'] not in approved]
            decisions = await post_filter.review(runtime_provider(),request,principal,channel,posts,store().preferences(owner,channel['id']))
            rejected = set()
            for p,d in zip(posts,decisions):
                if d.reject:
                    store().save_filtered_post(owner,channel['id'],p,d.reason,'detail')
                    rejected.add(p['url'])
            limited = [p for p in limited if p['url'] not in rejected]
            articles = await service.digest(runtime_provider(), request, principal, channel, limited, previous)
            checked(store().finish, owner, id, limited, articles, [log.model_dump() for log in body.logs])
            await run_in_threadpool(sync, principal, channel['id'])
            return checked(store().get, 'runs', owner, id)
        except (HTTPException, TimeoutError) as error:
            try:
                reason = '模型超时，请重试' if isinstance(error, TimeoutError) else str(error.detail)[:400]
                store().progress(owner, id, '生成失败：' + reason + '；内容未标为已处理', 'failed', logs=validated_logs)
            except ValueError:
                pass
            if isinstance(error, TimeoutError):
                raise HTTPException(504, '模型超时，请重试') from error
            raise
        finally:
            finishing.discard(id)

    @router.get('/articles/{id}/image')
    async def article_image(id: str, url: str, principal=dep):
        from fastapi.responses import Response
        from ai2apps.intelligence.images import load_public_image
        article = checked(store().get, 'articles', principal.actor_user_id, id)
        images = article.get('images', []) + ([article['cover_image']] if article.get('cover_image') else [])
        if url not in {i.get('url') for i in images}:
            raise HTTPException(404, '图片不属于此文章')
        data,mime = await load_public_image(url)
        return Response(data,media_type=mime,headers={'Cache-Control':'private, max-age=3600','X-Content-Type-Options':'nosniff'})

    @router.put('/articles/{id}/images')
    def save_images(id: str, body: ArticleImages, principal=dep):
        return checked(store().save_images, principal.actor_user_id, id, body.source_url,
            [i.model_dump() for i in body.images], body.image_url)

    @router.put('/articles/{id}/cover')
    def save_cover(id: str, body: ArticleCover, principal=dep):
        return checked(store().save_cover, principal.actor_user_id, id, body.source_url, body.image_url)

    @router.get('/channels/{id}/preferences')
    def preferences(id: str, principal=dep):
        return {'items': checked(store().preferences, principal.actor_user_id, id)}

    @router.post('/articles/{id}/feedback-reasons')
    async def feedback_reasons(id: str, request: Request, principal=dep):
        owner = principal.actor_user_id
        article = checked(store().get, 'articles', owner, id)
        channel = checked(store().get, 'channels', owner, article['channel_id'])
        digest = article_feedback.signature(channel, article)
        if article.get('feedback_options', {}).get('signature') == digest:
            return article['feedback_options']
        if (owner,id) in reason_planning:
            raise HTTPException(409, '正在生成理由，请稍后重试')
        reason_planning.add((owner,id))
        try:
            reasons = await article_feedback.generate(runtime_provider(), request, principal, channel, article)
            return checked(store().save_feedback_options, owner, id, digest, reasons)
        except TimeoutError as error:
            raise HTTPException(504, 'AI 生成理由超时，尚未记录踩反馈，请重试') from error
        finally:
            reason_planning.discard((owner,id))

    @router.patch('/articles/{id}')
    def feedback(id: str, body: Feedback, principal=dep):
        return checked(store().feedback, principal.actor_user_id, id, body.feedback, body.read, body.reasons, body.reason_signature)

    return router
