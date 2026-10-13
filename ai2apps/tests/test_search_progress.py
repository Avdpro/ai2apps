from ai2apps.storage import PlatformDatabase
from ai2apps.browser.tasks import BrowserTaskRepository
from ai2apps.browser.search_progress import publish, read


def test_partial_results_are_durable_owner_scoped_and_status_events_stay_small(tmp_path):
    db=PlatformDatabase(tmp_path/'tasks.sqlite');db.initialize()
    tasks=BrowserTaskRepository(db)
    task=tasks.enqueue('owner','default','agent','list','','Search',{},session_id='session')
    first={'items':[{'url':'https://example.com/article','title':'Article'}]}
    publish(tasks,'owner',task['id'],first)
    assert read(db,'owner',task['id'])['partial']
    assert read(db,'another',task['id']) is None
    with db.transaction() as c:
        events=c.execute('SELECT payload_json FROM events ORDER BY sequence DESC LIMIT 1').fetchone()[0]
    assert 'Article' not in events
    publish(tasks,'owner',task['id'],{'items':[{**first['items'][0],'content':'Body'}]})
    assert read(db,'owner',task['id'])['items'][0]['content']=='Body'
    tasks.update('owner',task['id'],status='completed')
    publish(tasks,'owner',task['id'],first)
    assert read(db,'owner',task['id'])['items'][0]['content']=='Body'
