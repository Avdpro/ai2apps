"""Owner-only Bot draft admission: one atomic create with its initial settings."""
import json
from uuid import uuid4
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator
from .app_access import digest
from . import bot_types
from .templates import RESEARCH, research_template

class CreationAvatar(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kind:Literal['preset']='preset'
    preset:Literal['spark','robot','orbit','flower','sun','moon','cat','owl','leaf','rocket','compass','heart']='spark'
    color:str=Field(default='#6366f1',pattern=r'^#[0-9a-fA-F]{6}$')

class CreationAccess(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    app_id:str=Field(min_length=1,max_length=256)
    enabled:bool

class BotCreateDraft(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:str=Field(min_length=8,max_length=128)
    bot_type:Literal['standard','flash','asc']='standard'
    template_id:Literal['research']|None=None
    definition:bot_types.BotDefinition=Field(default_factory=bot_types.BotDefinition)
    group_id:str|None=Field(default=None,min_length=1,max_length=128)
    name:str=Field(min_length=1,max_length=64)
    duty:str=Field(min_length=1,max_length=600)
    avatar:CreationAvatar=Field(default_factory=CreationAvatar)
    model_id:str|None=Field(default=None,min_length=1,max_length=300)
    apps:list[CreationAccess]=Field(default_factory=list,max_length=256)
    access_review_hash:str=Field(pattern=r'^[0-9a-f]{64}$')

    @model_validator(mode='after')
    def matching_type(self):
        if {'standard':'agent','flash':'flash','asc':'app_shortcut'}[self.bot_type]!=self.definition.execution_mode:raise ValueError('Bot preset and definition do not match')
        if self.template_id and self.bot_type != 'standard':raise ValueError('This template requires a Standard Bot')
        return self


def options(runtime):
    from .flash_workflows import REGISTRY
    access=runtime.messager_bot_app_access.creation_catalog()
    return {'flash_workflows':REGISTRY.catalog(),'bot_types':bot_types.catalog(),'definition_schema_version':1,'default_duty':runtime.messager_bots.default_duty,
            'access':access,'templates':[research_template(access)]}


def ensure_research(runtime, actor, language='en'):
    """Seed once per owner; archived or customized Bots are never overwritten."""
    with runtime.app_chat.lock:
        with runtime.database.transaction() as db:
            if db.execute('SELECT 1 FROM messager_bot_templates WHERE actor=? AND template_id=? AND builtin=1',(actor,RESEARCH)).fetchone():
                return
        catalog=runtime.messager_bot_app_access.creation_catalog()
        template=research_template(catalog)
        locale='zh' if language.lower().startswith('zh') else 'en'
        body=BotCreateDraft(
            request_id='system:'+uuid4().hex,template_id=RESEARCH,
            name=template['name'][locale],duty=template['role'][locale],avatar=template['avatar'],
            apps=[{'app_id':app_id,'enabled':True} for app_id in template['app_ids']],
            access_review_hash=catalog['review_hash'],
        )
        create(runtime,actor,body,builtin=True)


def create(runtime,actor,body:BotCreateDraft,*,source_principal=None,source_instance_id=None,builtin=False):
    from .flash_workflows import REGISTRY
    if {'standard':'agent','flash':'flash','asc':'app_shortcut'}[body.bot_type]!=body.definition.execution_mode:raise ValueError('Bot preset and definition do not match')
    if body.bot_type=='asc':
        if source_principal is None or source_principal.actor_user_id!=actor or not source_instance_id:raise PermissionError('Capture App-State in the owning App to create an ASC-Bot')
        if body.apps or body.model_id:raise ValueError('ASC-Bots do not grant App access or use an Agent model')
        from ai2apps.apps.state_setup import get_app_state
        get_app_state(runtime).validate(source_principal,source_instance_id,body.definition.config.state)
    if body.bot_type=='flash':
        config=body.definition.config.model_dump()
        if config.get('plan') is not None:
            from .flash_plans import reviewed
            approved=reviewed(runtime,actor,config.get('review_id'),body.duty,body.model_id,[a.model_dump() for a in body.apps])
            if config!=approved:raise ValueError('Reviewed workflow was changed')
        else:
            REGISTRY.get(config)
            if body.apps or body.model_id:raise ValueError('This fixed workflow does not use App access or an AI model')
    name,duty=body.name.strip(),body.duty.strip()
    if not name or not duty:raise ValueError('Bot name and role are required')
    if body.model_id and (body.model_id!=body.model_id.strip() or any(ord(c)<32 for c in body.model_id)):raise ValueError('Invalid conversation model')
    excluded = {'request_id', 'access_review_hash'} if body.bot_type == 'asc' else {'request_id'}
    if body.group_id is None:
        excluded.add('group_id')  # Keep existing request signatures valid.
    if body.template_id is None:
        excluded.add('template_id')
    signature = digest(body.model_dump(exclude=excluded))
    with runtime.app_chat.lock:
        with runtime.database.transaction() as db:
            old=db.execute('SELECT signature,result_json FROM messager_bot_creations WHERE actor=? AND request_id=?',(actor,body.request_id)).fetchone()
        if old:
            if old['signature']!=signature:raise ValueError('Creation request changed; retry the original request')
            return json.loads(old['result_json'])
        access=runtime.messager_bot_app_access
        catalog=access.creation_catalog()
        if body.bot_type!='asc' and catalog['review_hash']!=body.access_review_hash:raise ValueError('App access catalog changed; review your choices again')
        grants=access.prepare_grants(catalog,[a.model_dump() for a in body.apps])
        ref=uuid4().hex;avatar=body.avatar.model_dump()
        result={'id':ref,'name':name,'duty':duty,'avatar':avatar}
        with runtime.database.transaction(write=True) as db:
            db.execute('INSERT INTO messager_bots VALUES(?,?,?,?)',(ref,actor,name,duty))
            if body.group_id is not None:
                runtime.messager_bots.groups.move(actor, ref, body.group_id, connection=db)
                result['group_id'] = body.group_id
            result['definition']=bot_types.save(db,actor,ref,body.definition.model_dump())
            if body.template_id:
                db.execute('INSERT INTO messager_bot_templates VALUES(?,?,?,?)',(actor,ref,body.template_id,int(builtin)))
                result['template_id']=body.template_id
            db.execute('INSERT INTO messager_bot_permissions VALUES(?,?,1,?)',(ref,actor,'{}'))
            db.execute('INSERT INTO messager_bot_app_access VALUES(?,?,1,?)',(ref,actor,json.dumps(grants)))
            db.execute('INSERT INTO messager_bot_avatars VALUES(?,?,?)',(ref,actor,json.dumps(avatar)))
            if body.model_id:db.execute('INSERT INTO messager_bot_conversation_models(actor,bot_id,model_id,revision) VALUES(?,?,?,1)',(actor,ref,body.model_id))
            db.execute('INSERT INTO messager_bot_creations VALUES(?,?,?,?,?)',(actor,body.request_id,signature,ref,json.dumps(result)))
        return result
