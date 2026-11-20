"""Gallery-owned character authoring and finalized appearance handoff for AaAT."""
from copy import deepcopy
from uuid import uuid4
from ai2apps.gallery.characters import Characters,CharacterInput,Appearance
from ai2apps.gallery.repository import GalleryError
from ai2apps.services.aaat import principal_for
from ai2apps.workspace.materials import MaterialFile,import_materials


def editable(value):
    return CharacterInput.model_validate({k:v for k,v in value.items() if k in CharacterInput.model_fields and k!='appearances'} | {
        'appearances':[{k:v for k,v in a.items() if k in Appearance.model_fields} for a in value['appearances']]})


def public(value):
    return {k:deepcopy(v) for k,v in value.items() if k in {'id','name','description','aliases','revision','default_appearance_id','appearances'}} | {
        'appearances':[{k:deepcopy(v) for k,v in a.items() if k in {*Appearance.model_fields,'revision'}} for a in value['appearances']]}


def install(runtime,register,repository):
    def store(context):return Characters(repository(runtime),principal_for(runtime,context).actor_user_id)
    def checked(args,context):
        owner=store(context);value=owner.get(args['character_id'])
        if value['revision']!=args['revision']:raise GalleryError('character_revision_conflict','Character changed. Read it again before editing or using it.')
        return owner,value,editable(value)
    async def listing(args,context):
        owner=store(context);items=[public(v) for v in owner.list()]
        if args.get('finalized_only',False):
            aliases={c['id']:c.get('aliases',[]) for c in items}
            items=[c|{'aliases':aliases.get(c['id'],[])} for c in owner.definitions()]
        query=args.get('query','').casefold()
        if query:items=[v for v in items if query in ' '.join([v['name'],*v.get('aliases',[]),*(a['name'] for a in v['appearances'])]).casefold()]
        return {'items':[{k:v for k,v in c.items() if k in {'id','name','aliases','revision','default_appearance_id'}} | {'appearances':[{k:v for k,v in a.items() if k in {'id','name','revision','approved','definition_image_id'}} for a in c['appearances']]} for c in items[:args.get('limit',50)]]}
    async def get(args,context):return {'character':public(store(context).get(args['character_id']))}
    async def create(args,context):return {'character':public(store(context).save(CharacterInput(**args))),'status':'completed'}
    async def update(args,context):
        owner,value,body=checked(args,context)
        patch=args['changes'];updated=body.model_copy(update=patch)
        return {'character':public(owner.save(CharacterInput.model_validate(updated.model_dump()),value['id'])),'status':'completed'}
    async def appearance_create(args,context):
        owner,value,body=checked(args,context);a=Appearance(id=uuid4().hex,**args['appearance'])
        body.appearances.append(a)
        if not body.default_appearance_id:body.default_appearance_id=a.id
        saved=owner.save(body,value['id'])
        return {'character':public(saved),'appearance_id':a.id,'status':'completed'}
    async def appearance_update(args,context):
        owner,value,body=checked(args,context);a=next((a for a in body.appearances if a.id==args['appearance_id']),None)
        if not a:raise GalleryError('character_appearance_missing','Appearance unavailable.')
        patched=Appearance.model_validate(a.model_dump()|args['changes'])
        body.appearances=[patched if item.id==a.id else item for item in body.appearances]
        return {'character':public(owner.save(body,value['id'])),'status':'completed'}
    async def use(args,context):
        owner,value,_=checked(args,context)
        a=next((a for c in owner.definitions() if c['id']==value['id'] for a in c['appearances'] if a['id']==args['appearance_id']),None)
        if not a:raise GalleryError('character_not_finalized','Choose a finalized appearance with a definition image and guide.')
        asset,path=owner.gallery.asset_path(owner.owner,a['definition_image_id'])
        async def resolve(identifier):return MaterialFile(asset['name'],asset['media_type'],path) if identifier==asset['id'] else 'unavailable'
        result=await import_materials(runtime.workspace,context.session_id,[asset['id']],resolve)
        return {**result,'character_id':value['id'],'appearance_id':a['id'],'character_revision':value['revision'],
            'appearance_revision':a['revision'],'summary':a['summary'],'definition_image_id':asset['id']}
    string=lambda maximum:{'type':'string','minLength':1,'maxLength':maximum}
    revision={'type':'integer','minimum':1}
    ident={'character_id':string(100)}
    version={**ident,'revision':revision}
    # Pydantic supplies precisely the same appearance fields/limits as the UI API.
    fields=Appearance.model_json_schema()['properties'];fields={k:v for k,v in fields.items() if k!='id'}
    appearance={'type':'object','properties':fields,'required':['name'],'additionalProperties':False}
    patch={'type':'object','properties':fields,'minProperties':1,'additionalProperties':False}
    def schema(props,required=()):return {'type':'object','properties':props,'required':list(required),'additionalProperties':False}
    identity_fields={k:CharacterInput.model_json_schema()['properties'][k] for k in ['name','description','aliases']}
    common=' Owned characters only. Authoring never starts image generation. Use existing image generation/editing capabilities, save their actual image artifact to Gallery, then set definition_image_id. Finalization requires a definition image and nonempty summary; a changed saved appearance becomes unconfirmed and must be reviewed before finalizing again. Never guess IDs; list/read first and use the returned revision. '
    specs=[
        ('character.list','列出角色形象 / List characters and appearances','Find characters by name, alias or appearance name; includes drafts unless finalized_only=true.',schema({'query':{'type':'string','maxLength':200},'finalized_only':{'type':'boolean','default':False},'limit':{'type':'integer','minimum':1,'maximum':100,'default':50}}),listing,False),
        ('character.get','读取角色设定 / Read character settings','Read editable settings, source references, selected definition image and exact revision. No generated history.',schema(ident,['character_id']),get,False),
        ('character.create','创建角色 / Create character','Create one named identity without generating images. Then create named appearances with character.appearance.create.',schema(identity_fields,['name']),create,True),
        ('character.update','修改角色 / Update character','Patch identity name, description or aliases; omitted fields are preserved.',schema({**version,'changes':schema(identity_fields)|{'minProperties':1}},['character_id','revision','changes']),update,True),
        ('character.appearance.create','创建形象 / Create appearance','Add one independent named appearance to an existing identity. reference_ids are generation inputs; definition_image_id is the single reusable output image; summary is the reusable prose.',schema({**version,'appearance':appearance},['character_id','revision','appearance']),appearance_create,True),
        ('character.appearance.update','修改形象 / Update appearance','Patch only supplied appearance fields, including definition_image_id and summary; preserves other appearances and generated history. approved=true requests finalization; returned approved is authoritative.',schema({**version,'appearance_id':string(80),'changes':patch},['character_id','revision','appearance_id','changes']),appearance_update,True),
        ('character.use','使用角色形象 / Use character appearance','Import exactly one finalized definition image into this Session and return its summary. Pass the returned image artifact plus summary to the drawing capability. Does not generate or modify an image.',schema({**version,'appearance_id':string(80)},['character_id','revision','appearance_id']),use,False),
    ]
    labels={'character_id':{'zh':'角色 ID','en':'Character ID'},'appearance_id':{'zh':'形象 ID','en':'Appearance ID'},'revision':{'zh':'角色版本','en':'Character revision'},'query':{'zh':'搜索','en':'Search'},'finalized_only':{'zh':'仅已定稿','en':'Finalized only'},'limit':{'zh':'数量上限','en':'Limit'},'name':{'zh':'角色名称','en':'Character name'},'description':{'zh':'身份说明','en':'Identity description'},'aliases':{'zh':'别名','en':'Aliases'},'changes':{'zh':'修改字段','en':'Changes'},'appearance':{'zh':'形象设定','en':'Appearance settings'}}
    summaries_zh={'character.list':'按名称、别名或形象名称查询自有角色，可筛选已定稿形象。','character.get':'读取角色与形象的编辑设定和当前版本。','character.create':'创建角色身份，不生成图片。','character.update':'按版本修改角色名称、身份说明或别名。','character.appearance.create':'为角色新增独立形象，分别保存输入参考图、定义图和说明。','character.appearance.update':'按版本修改形象；定稿需要定义图与说明，修改后需重新确认。','character.use':'导入已定稿形象的一张定义图并返回说明，供其它绘图能力使用，不自动生成。'}
    for name,title,summary,shape,handler,write in specs:
        register(name,'ai2apps.gallery',title,summary+common,shape,handler,effects=('artifact.create',) if name=='character.use' else ('write',) if write else ('read',),provider_version='1',field_labels=labels,form_summary={'zh':summaries_zh[name],'en':summary})
