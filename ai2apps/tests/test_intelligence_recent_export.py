import json
import pytest
from ai2apps.tests.test_intelligence_transfer import seed, commit
from ai2apps.intelligence.store import IntelligenceStore
from ai2apps.intelligence.transfer import export_backup, parse_backup, selected_rows


def dated(store,a,created,updated,**extra):
    with store.connect() as db:
        a={**a,'created_at':created,'updated_at':updated,**extra}
        db.execute('UPDATE articles SET data=? WHERE id=?',(json.dumps(a),a['id']))
    return a


def test_recent_created_vs_updated_complete_dependencies(tmp_path):
    s,c,a=seed(tmp_path/'s')
    dated(s,a,'2026-10-01T00:00:00Z','2026-10-31T10:00:00Z')
    kwargs={'since':'2026-10-31T00:00:00Z','until':'2026-11-01T00:00:00Z'}
    updated=export_backup(s,'alice',c['id'],**kwargs)
    tables,_=parse_backup(updated)
    assert len(tables['articles'])==1 and len(tables['channels'])==1
    assert tables['articles'][0]['data']['content_blocks']==a['content_blocks']
    assert not tables['conversations'] and not tables['runs']
    created,_=parse_backup(export_backup(s,'alice',changes='created',**kwargs))
    assert not created['articles']
    target=IntelligenceStore(tmp_path/'t');commit(target,updated)
    assert len(target.snapshot('bob')['articles'])==1


def test_half_open_range_and_timezone(tmp_path):
    s,c,a=seed(tmp_path/'s');dated(s,a,'2026-10-31T08:00:00+08:00','2026-10-31T08:00:00+08:00')
    assert len(selected_rows(s,'alice',since='2026-10-31T00:00:00Z')['articles'])==1
    assert not selected_rows(s,'alice',until='2026-10-31T00:00:00Z')['articles']
    with pytest.raises(ValueError):selected_rows(s,'alice',since='2026-10-31T00:00:00')
    with pytest.raises(ValueError):selected_rows(s,'alice',since='2026-11-01T00:00:00Z',until='2026-10-31T00:00:00Z')


def test_read_favorite_excluded_but_image_content_update_included(tmp_path):
    s,c,a=seed(tmp_path/'s');dated(s,a,'2026-10-01T00:00:00Z','2026-10-01T00:00:00Z')
    s.feedback('alice',a['id'],favorite=True,read=True)
    assert not selected_rows(s,'alice',since='2026-10-31T00:00:00Z')['articles']
    s.save_cover('alice',a['id'],'https://example.org/article','https://example.org/new.jpg')
    assert len(selected_rows(s,'alice',since='2026-10-31T00:00:00Z')['articles'])==1


def test_cached_pages_and_preferences_scoped(tmp_path):
    s,c,a=seed(tmp_path/'s');dated(s,a,'2026-10-31T10:00:00Z','2026-10-31T10:00:00Z')
    with s.connect() as db:
        for url in ('https://example.org/article','https://example.org/unrelated'):
            db.execute('INSERT INTO pages VALUES(?,?,?,?,?)',('alice',c['id'],url,'hash',json.dumps({'url':url,'text':'Original'})))
    selected=selected_rows(s,'alice',since='2026-10-31T00:00:00Z')
    assert [r['url'] for r in selected['pages']]==['https://example.org/article']
