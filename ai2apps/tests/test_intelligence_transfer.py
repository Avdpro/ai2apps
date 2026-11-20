import copy
import hashlib
import io
import json
import zipfile
import pytest
from ai2apps.intelligence.store import IntelligenceStore
from ai2apps.intelligence.models import ChannelInput, SourceInput
from ai2apps.intelligence.article_content import image_id, validate_content
from ai2apps.intelligence.transfer import export_backup, merge_backup, parse_backup


def seed(root):
    store=IntelligenceStore(root)
    c=store.save_channel('alice',ChannelInput(name='Watches',interests='watches',interval_hours=2).model_dump())
    store.save_source('alice',c['id'],SourceInput(name='Source',url='https://example.org/news').model_dump())
    url='https://example.org/article';img='https://example.org/image.jpg';iid=image_id(url,img)
    a=store.import_article('alice',c['id'],{'title':'Watch','summary':'Summary','body':'Paragraph [1]','sources':[{'url':url,'title':'Source'}],'images':[{'id':iid,'url':img,'source_url':url}],'content_schema':'ai2apps.article-content/v1','content_blocks':[{'type':'paragraph','text':'Paragraph [1]'},{'type':'image','image_id':iid}]},url)
    return store,c,a


def commit(target,payload):
    p=merge_backup(target,'bob',payload)
    return merge_backup(target,'bob',payload,p['expected'])


def repack(payload,mutate):
    with zipfile.ZipFile(io.BytesIO(payload)) as z:files={n:z.read(n) for n in z.namelist()}
    data=json.loads(files['intelligence.json']);mutate(data);files['intelligence.json']=json.dumps(data).encode()
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        for n,b in files.items():z.writestr(n,b)
    return out.getvalue()


def test_roundtrip(tmp_path):
    s,c,a=seed(tmp_path/'s');t=IntelligenceStore(tmp_path/'t');p=export_backup(s,'alice')
    assert merge_backup(t,'bob',p)['create']==3
    assert not t.snapshot('bob')['channels']
    commit(t,p);snap=t.snapshot('bob');validate_content(snap['articles'][0])
    assert snap['articles'][0]['content_blocks']==a['content_blocks']
    assert snap['channels'][0]['interval_hours']==0
    assert not snap['sources'][0]['enabled']
    assert not snap['channels'][0]['knowledge_bucket_ids']
    assert merge_backup(t,'bob',p)['create']==0
    assert not t.snapshot('alice')['channels']


def test_single_scope(tmp_path):
    s,c,a=seed(tmp_path/'s');s.save_channel('alice',ChannelInput(name='Other',interests='other').model_dump())
    tables,_=parse_backup(export_backup(s,'alice',c['id']))
    assert [r['id'] for r in tables['channels']]==[c['id']]
    with pytest.raises(KeyError):export_backup(s,'bob',c['id'])


def test_conflicts(tmp_path):
    s,c,a=seed(tmp_path/'s');t=IntelligenceStore(tmp_path/'t');commit(t,export_backup(s,'alice'))
    with s.connect() as db:
        v=copy.deepcopy(a);v['body']='Changed [1]';v['content_blocks'][0]['text']=v['body'];db.execute('UPDATE articles SET data=? WHERE id=?',(json.dumps(v),a['id']))
    p=export_backup(s,'alice');assert commit(t,p)['conflict']==1
    actual=t.snapshot('bob')['articles'][0]
    assert actual['body']=='Paragraph [1]'
    assert actual['_transfer_conflicts'][0]['data']['body']=='Changed [1]'
    assert merge_backup(t,'bob',p)['conflict']==0


def test_stale_preview(tmp_path):
    s,c,a=seed(tmp_path/'s');t=IntelligenceStore(tmp_path/'t');p=export_backup(s,'alice');preview=merge_backup(t,'bob',p)
    t.save_channel('bob',ChannelInput(name='Watches',interests='changed').model_dump())
    with pytest.raises(ValueError):merge_backup(t,'bob',p,preview['expected'])
    preview=merge_backup(t,'bob',p)
    changed=repack(p,lambda d:d['tables']['articles'][0]['data'].update(title='New'))
    with pytest.raises(ValueError):merge_backup(t,'bob',changed,preview['expected'])


def test_unrelated_update(tmp_path):
    s,c,a=seed(tmp_path/'s');t=IntelligenceStore(tmp_path/'t');p=export_backup(s,'alice');preview=merge_backup(t,'bob',p)
    t.save_channel('bob',ChannelInput(name='Other',interests='other').model_dump())
    merge_backup(t,'bob',p,preview['expected'])


@pytest.mark.parametrize('kind',['format','dangling','duplicate','image'])
def test_invalid(tmp_path,kind):
    s,c,a=seed(tmp_path/'s');p=export_backup(s,'alice')
    def mutate(d):
        if kind=='format':d['format']='other'
        if kind=='dangling':d['tables']['articles'][0]['channel']='missing'
        if kind=='duplicate':d['tables']['articles']*=2
        if kind=='image':d['tables']['articles'][0]['data']['content_blocks'][1]['image_id']='invented'
    with pytest.raises(ValueError):parse_backup(repack(p,mutate))


def test_local_blob(tmp_path):
    from ai2apps.intelligence.manual_import import asset_path
    s,c,a=seed(tmp_path/'s');blob=b'original';token=hashlib.sha256(blob).hexdigest();path=asset_path(s,'alice',token);path.parent.mkdir(parents=True);path.write_bytes(blob)
    with s.connect() as db:
        v=copy.deepcopy(a);v['original_content']={'url':'/v1/platform/intelligence/imports/'+token+'/doc.txt'};db.execute('UPDATE articles SET data=? WHERE id=?',(json.dumps(v),a['id']))
    p=export_backup(s,'alice');t=IntelligenceStore(tmp_path/'t');merge_backup(t,'bob',p);assert not asset_path(t,'bob',token).exists()
    commit(t,p);assert asset_path(t,'bob',token).read_bytes()==blob
    assert not asset_path(t,'alice',token).exists()


def test_running_target(tmp_path):
    s,c,a=seed(tmp_path/'s');t=IntelligenceStore(tmp_path/'t');p=export_backup(s,'alice');commit(t,p);channel=t.snapshot('bob')['channels'][0]
    with t.connect() as db:db.execute('INSERT INTO runs(id,owner,channel,status,updated,data) VALUES(?,?,?,?,?,?)',('run','bob',channel['id'],'running',0,'{}'))
    with pytest.raises(ValueError,match='updating'):merge_backup(t,'bob',p)


def test_reexport(tmp_path):
    s,c,a=seed(tmp_path/'s');t=IntelligenceStore(tmp_path/'t');commit(t,export_backup(s,'alice'));u=IntelligenceStore(tmp_path/'u');commit(u,export_backup(t,'bob'))
    assert merge_backup(u,'bob',export_backup(s,'alice'))['create']==0


def test_original_source_recognizes_reexport(tmp_path):
    s,c,a=seed(tmp_path/'s');t=IntelligenceStore(tmp_path/'t');commit(t,export_backup(s,'alice'))
    p=export_backup(t,'bob');preview=merge_backup(s,'alice',p)
    assert preview['create']==0


def test_sections_merge_and_remap(tmp_path):
    s,c,a=seed(tmp_path/'s')
    with s.connect() as db:
        channel=s.unpack(db.execute('SELECT * FROM channels WHERE id=?',(c['id'],)).fetchone())
        channel['sections']=[{'id':'incoming','name':'Release','description':'New products'},{'id':'new','name':'Reviews','description':'Reviews'}]
        db.execute('UPDATE channels SET data=? WHERE id=?',(json.dumps(channel),c['id']))
        a['section_id']='incoming';db.execute('UPDATE articles SET data=? WHERE id=?',(json.dumps(a),a['id']))
    t=IntelligenceStore(tmp_path/'t')
    local=t.save_channel('bob',ChannelInput(name='Watches',interests='local',sections=[{'id':'local','name':'Release','description':'Existing'}]).model_dump())
    p=export_backup(s,'alice');result=commit(t,p)
    assert result['update']==1
    assert t.snapshot('bob')['articles'][0]['section_id']=='local'
    current=t.get('channels','bob',local['id'])
    assert current['interests']=='local'
    assert [v['name'] for v in current['sections']]==['Release','Reviews']
    assert merge_backup(t,'bob',p)['update']==0


def test_entities_merge_evidence_and_scope(tmp_path):
    from ai2apps.intelligence.entities import Repository
    s,c,a=seed(tmp_path/'s');Repository(s)
    with s.connect() as db:
        db.execute('INSERT INTO entity_dossiers VALUES(?,?,?)',('alice','entity',json.dumps({'id':'entity','name':'Brand','kind':'brand','aliases':[],'facts':[{'id':'fact','article_id':a['id'],'quote':'Paragraph'}],'attributes':[]})))
        db.execute('INSERT INTO entity_dossiers VALUES(?,?,?)',('alice','watched',json.dumps({'id':'watched','name':'Watched','kind':'brand','watched':True,'aliases':[],'facts':[]})))
    tables,_=parse_backup(export_backup(s,'alice',c['id']))
    assert len(tables['entity_dossiers'])==1
    t=IntelligenceStore(tmp_path/'t');Repository(t)
    with t.connect() as db:db.execute('INSERT INTO entity_dossiers VALUES(?,?,?)',('bob','local-brand',json.dumps({'id':'local-brand','name':'Brand','kind':'brand','aliases':['Local alias'],'facts':[]})))
    p=export_backup(s,'alice');commit(t,p)
    with t.connect() as db:
        data=json.loads(db.execute('SELECT data FROM entity_dossiers WHERE owner=? AND id=?',('bob','local-brand')).fetchone()[0])
        assert len(data['facts'])==1
        assert db.execute('SELECT 1 FROM articles WHERE owner=? AND id=?',('bob',data['facts'][0]['article_id'])).fetchone()
        assert 'Local alias' in data['aliases']
    assert merge_backup(t,'bob',p)['update']==0


def test_failed_transaction_rolls_back_records_and_new_blob(tmp_path):
    import sqlite3
    from ai2apps.intelligence.manual_import import asset_path
    s,c,a=seed(tmp_path/'s');blob=b'rollback';token=hashlib.sha256(blob).hexdigest();path=asset_path(s,'alice',token);path.parent.mkdir(parents=True);path.write_bytes(blob)
    with s.connect() as db:
        a['original_content']={'url':'/v1/platform/intelligence/imports/'+token+'/file.txt'};db.execute('UPDATE articles SET data=? WHERE id=?',(json.dumps(a),a['id']))
    t=IntelligenceStore(tmp_path/'t');p=export_backup(s,'alice');preview=merge_backup(t,'bob',p)
    with t.connect() as db:db.execute("CREATE TRIGGER refuse_article BEFORE INSERT ON articles BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
    with pytest.raises(sqlite3.IntegrityError):merge_backup(t,'bob',p,preview['expected'])
    assert not t.snapshot('bob')['channels']
    assert not asset_path(t,'bob',token).exists()
