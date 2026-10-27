"""Owner-scoped X evidence archive and explicit, idempotent promotion."""
import hashlib,json

def post_id(url):return hashlib.sha256(url.encode()).hexdigest()[:32]

def list_posts(store,owner,channel,offset=0):
    store.get('channels',owner,channel)
    with store.connect() as db:
        rows=db.execute("SELECT data FROM pages WHERE owner=? AND channel=? AND json_extract(data,'$.platform')='x' ORDER BY rowid DESC LIMIT 21 OFFSET ?",(owner,channel,offset)).fetchall()
        articles=[store.unpack(row) for row in db.execute('SELECT * FROM articles WHERE owner=? AND channel=?',(owner,channel))]
    items=[]
    for row in rows[:20]:
        page=json.loads(row['data']);page['id']=post_id(page['url'])
        page['briefings']=[{'id':a['id'],'title':a['title']} for a in articles if any(s.get('url')==page['url'] for s in [*a.get('sources',[]),*a.get('post_evidence',[])])]
        page['role']='event_evidence' if page['briefings'] else 'supplementary'
        items.append(page)
    return {'items':items,'next_offset':offset+20 if len(rows)>20 else None}

def promote(store,owner,channel,id):
    store.get('channels',owner,channel)
    with store.connect() as db:
        rows=db.execute("SELECT data FROM pages WHERE owner=? AND channel=? AND json_extract(data,'$.platform')='x'",(owner,channel)).fetchall()
    page=next((json.loads(row['data']) for row in rows if post_id(json.loads(row['data'])['url'])==id),None)
    if page is None:raise KeyError('Post not found')
    text=page.get('text','')
    if not text.strip():raise ValueError('Post has no readable content')
    ref={k:page.get(k,'') for k in ('url','title','source_name','source_id','retrieved_at','platform','post_id','author','published_at')}
    article={'title':page.get('title') or text[:120],'summary':text[:180],'body':text,'section_id':None,
             'sources':[ref],'post_evidence':[{**page,'role':'primary'}],'presentation':'important_post',
             'importance_reason':'Manually promoted by the user','manual_post_promotion':True,'images':[{**image,'source_url':page['url']} for image in page.get('images',[])],
             'primary_source_url':page['url'],'original_content':{'title':page.get('title',''),'body':text}}
    if page.get('image_url'):article['cover_image']={'url':page['image_url'],'source_url':page['url']}
    elif article['images']:article['cover_image']={'url':article['images'][0]['url'],'source_url':page['url']}
    return store.import_article(owner,channel,article,'x-post:'+page['url'])
