"""Model-free multi-attachment Knowledge records and derived text aggregation."""
import hashlib
import json
import uuid
from ai2apps.core import utc_now_text
from .models import KnowledgeScope

GROUP_SCHEMA=("""CREATE TABLE IF NOT EXISTS knowledge_record_groups (
 parent_id TEXT PRIMARY KEY REFERENCES knowledge_items(id) ON DELETE CASCADE,
 job_id TEXT NOT NULL UNIQUE, signature TEXT, ready INTEGER NOT NULL DEFAULT 0)""",
"""CREATE TABLE IF NOT EXISTS knowledge_record_attachments (
 parent_id TEXT NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
 child_id TEXT NOT NULL UNIQUE REFERENCES knowledge_items(id) ON DELETE CASCADE,
 ordinal INTEGER NOT NULL, PRIMARY KEY(parent_id,ordinal))""")

def ensure_group(store,p,job):
    bucket=next(b for b in store.list_buckets(p) if b.id==job['bucket_id'])
    parent=store.create_text_item(p,scope=bucket.visibility,kind='document',
        title=job['record_title'] or '文件知识记录',text='附件正在导入和提取内容。',
        source_app_id=job['source_app_id'],bucket_id='auto' if job['auto_bucket'] else bucket.id,
        idempotency_key='file-group:'+job['id'],trusted_source_facets=(('content.group','attachments'),))
    with store.transaction(write=True) as c:
        c.execute('INSERT OR IGNORE INTO knowledge_record_groups(parent_id,job_id) VALUES (?,?)',(parent.id,job['id']))
        c.execute('UPDATE knowledge_import_jobs SET group_parent_id=? WHERE id=?',(parent.id,job['id']))
    return parent.id

def attach(store,p,parent_id,item,ordinal):
    with store.transaction(write=True) as c:
        parent=c.execute('SELECT * FROM knowledge_items WHERE id=? AND deleted_at IS NULL AND owner_user_id=? AND installation_id=?',(parent_id,p.actor_user_id,p.installation_id)).fetchone()
        if not parent:raise ValueError('Grouped record was deleted')
        c.execute('INSERT OR IGNORE INTO knowledge_record_attachments(parent_id,child_id,ordinal) VALUES (?,?,?)',(parent_id,item.id,ordinal))
        c.execute('DELETE FROM knowledge_bucket_items WHERE item_id=?',(item.id,))
        if item.kind not in {'audio','video'}:
            c.execute('DELETE FROM knowledge_bucket_routing WHERE item_id=?',(item.id,))
        if item.kind in {'audio','video'}:
            from .routing_store import enqueue_routing
            enqueue_routing(c,item.id,p,item.revision)


def attachments(store,p,parent_id):
    store.get_item(p,parent_id)
    with store.transaction() as c:
        rows=c.execute('''SELECT a.*,g.ordinal FROM knowledge_record_attachments g JOIN knowledge_assets a ON a.item_id=g.child_id JOIN knowledge_items i ON i.id=g.child_id WHERE g.parent_id=? AND i.deleted_at IS NULL ORDER BY g.ordinal''',(parent_id,)).fetchall()
    return [{'item_id':r['item_id'],'name':r['filename'],'media_type':r['media_type'],'size_bytes':r['size_bytes'],'ordinal':r['ordinal']} for r in rows]


def refresh_groups(store):
    """Publish only changed aggregates; children stay internal to one visible record."""
    changed_count=0
    with store.transaction() as c:
        groups=c.execute('''SELECT g.*,j.status AS job_status,j.total_files,j.failed_files,j.detect_overlap FROM knowledge_record_groups g JOIN knowledge_import_jobs j ON j.id=g.job_id JOIN knowledge_items i ON i.id=g.parent_id WHERE i.deleted_at IS NULL''').fetchall()
    for group in groups:
        with store.transaction(write=True) as c:
            parent=c.execute('SELECT * FROM knowledge_items WHERE id=? AND deleted_at IS NULL',(group['parent_id'],)).fetchone()
            if not parent:continue
            rows=c.execute('''SELECT i.*,r.text,a.filename,a.parser,g.ordinal,o.status AS ocr_status FROM knowledge_record_attachments g JOIN knowledge_items i ON i.id=g.child_id JOIN knowledge_representations r ON r.item_id=i.id AND r.ordinal=0 JOIN knowledge_assets a ON a.item_id=i.id LEFT JOIN knowledge_image_ocr o ON o.item_id=i.id WHERE g.parent_id=? AND i.deleted_at IS NULL ORDER BY g.ordinal''',(parent['id'],)).fetchall()
            signature=hashlib.sha256(json.dumps(['overlap/v1',group['detect_overlap'],group['job_status'],group['failed_files'],[(r['id'],r['revision'],r['ocr_status'],r['parser']) for r in rows]]).encode()).hexdigest()
            if signature==group['signature']:continue
            ready=group['job_status'] in {'completed','partial','failed'}
            bodies=[]
            previous_image=None
            for row in rows:
                extracted=not row['text'].startswith(('Binary knowledge asset:','PDF knowledge asset:'))
                if row['kind'] in {'image','audio','video'}:
                    extracted=any(k in row['parser'] for k in ('ocr','asr','transcript'))
                    if not extracted:ready=False
                if not extracted:ready=False
                body=row['text'] if extracted else '内容尚未完成提取；原文件已保留。'
                evidence=None
                if extracted and row['kind']=='image':
                    if group['detect_overlap'] and previous_image is not None:
                        from .overlap import trim_overlap
                        body,evidence=trim_overlap(previous_image,body)
                    previous_image=row['text']
                else:previous_image=None
                row=dict(row)
                row['overlap']=evidence
                bodies.append((f"附件 {row['ordinal']+1} · {row['filename']}\n{body}",row))
            if group['failed_files']:bodies.append((f"有 {group['failed_files']} 个文件导入失败，请查看导入任务。",None))
            if not bodies:
                bodies=[('没有可用的附件内容。',None)];ready=False
            rep=c.execute('SELECT id FROM knowledge_representations WHERE item_id=? AND ordinal=0',(parent['id'],)).fetchone();now=utc_now_text()
            c.execute('DELETE FROM knowledge_chunks WHERE item_id=?',(parent['id'],))
            text='\n\n'.join(body for body,_ in bodies)[:2_000_000]
            c.execute("UPDATE knowledge_representations SET text=?,producer='knowledge.group/v1' WHERE id=?",(text,rep['id']))
            remaining=2_000_000
            for n,(body,row) in enumerate(bodies):
                body=body[:remaining];remaining-=len(body)
                if not body:break
                metadata={'data_trust':'untrusted','kind':'attachment','attachment_ordinal':n+1}
                if row:
                    metadata.update({'attachment_item_id':row['id'],'filename':row['filename']})
                    if row.get('overlap'):metadata['overlap']=row['overlap']
                c.execute('INSERT INTO knowledge_chunks(id,representation_id,item_id,space_id,ordinal,text,created_at,metadata_json) VALUES (?,?,?,?,?,?,?,?)',('kch_'+uuid.uuid4().hex,rep['id'],parent['id'],parent['space_id'],n,body,now,json.dumps(metadata)))
            c.execute('UPDATE knowledge_items SET revision=revision+1,updated_at=? WHERE id=?',(now,parent['id']))
            c.execute('UPDATE knowledge_record_groups SET signature=?,ready=? WHERE parent_id=?',(signature,int(ready),parent['id']))
            c.execute("INSERT INTO knowledge_change_log(operation,item_id,space_id,authoritative_revision,created_at) VALUES ('update',?,?,?,?)",(parent['id'],parent['space_id'],parent['revision']+1,now))
            changed_count+=1
    return changed_count

def group_content(store,p,item_id,download=False):
    item=store.get_item(p,item_id)
    with store.transaction() as c:
        if not c.execute('SELECT 1 FROM knowledge_record_groups WHERE parent_id=?',(item_id,)).fetchone():return None
    files=attachments(store,p,item_id)
    with store.transaction() as c:
        evidence=[json.loads(r['metadata_json']).get('overlap') for r in c.execute('SELECT metadata_json FROM knowledge_chunks WHERE item_id=? ORDER BY ordinal',(item_id,))]
    raw_text='\n\n'.join(f"附件 {f['ordinal']+1} · {f['name']}\n{store.get_item(p,f['item_id']).text}" for f in files)
    report=''.join('<li>附件 '+str(n+1)+'：与上一张重叠 '+str(e['removed_lines'])+' 行。<pre>'+__import__('html').escape(e['matched_text'])+'</pre></li>' for n,e in enumerate(evidence) if e)

    if download:
        import tempfile,zipfile,shutil
        from starlette.responses import StreamingResponse
        from starlette.background import BackgroundTask
        if sum(f['size_bytes'] for f in files)>128*1024**2:raise ValueError('附件总量超过128MB，请逐个下载')
        output=tempfile.SpooledTemporaryFile(max_size=8*1024**2)
        try:
            with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('knowledge.txt',item.text)
                archive.writestr('original-ocr.txt',raw_text)
                for file in files:
                    asset,path=store.asset_path(p,file['item_id'])
                    with path.open('rb') as source,archive.open(f"{file['ordinal']+1:03d}-{asset.filename}",'w') as target:shutil.copyfileobj(source,target)
            output.seek(0)
            return StreamingResponse(iter(lambda:output.read(65536),b''),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="knowledge-record.zip"','Cache-Control':'no-store'},background=BackgroundTask(output.close))
        except BaseException:output.close();raise
    import html
    from starlette.responses import HTMLResponse
    links=''.join(f'<li><a href="/v1/platform/knowledge/items/{html.escape(f["item_id"],quote=True)}/content?download=true">{html.escape(f["name"])}</a></li>' for f in files)
    return HTMLResponse('<!doctype html><meta charset="utf-8"><title>'+html.escape(item.title)+'</title><h1>'+html.escape(item.title)+'</h1><h2>原始附件</h2><ol>'+links+'</ol><h2>重叠检测</h2>'+('<ul>'+report+'</ul>' if report else '<p>没有检测到可确认的连续重叠内容，或未开启检测。</p>')+'<h2>去重后的提取内容</h2><pre>'+html.escape(item.text)+'</pre><details><summary>原始提取内容</summary><pre>'+html.escape(raw_text)+'</pre></details>',headers={'Cache-Control':'no-store','Content-Security-Policy':"default-src 'none'; base-uri 'none'; frame-ancestors 'self'; sandbox allow-same-origin allow-downloads allow-top-navigation-by-user-activation"})
