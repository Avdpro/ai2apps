import pytest
from ai2apps.messager.bots import BotDirectory
from test_app_interactions import runtime


def test_bot_order_persists_and_new_bots_append(runtime):
    directory=BotDirectory(runtime.database)
    a=directory.create('local','First','Help')
    b=directory.create('local','Second','Help')
    assert [x['id'] for x in directory.list('local')]==[a['id'],b['id']]
    directory.set_order('local',[b['id'],a['id']])
    restored=BotDirectory(runtime.database)
    assert [x['id'] for x in restored.list('local')]==[b['id'],a['id']]
    c=restored.create('local','New','Help')
    assert [x['id'] for x in restored.list('local')]==[b['id'],a['id'],c['id']]
    # A reorder captured before creation cannot drop the new Bot.
    restored.set_order('local',[a['id'],b['id']])
    assert [x['id'] for x in restored.list('local')]==[a['id'],b['id'],c['id']]


def test_bot_order_rejects_other_users_and_duplicates(runtime):
    directory=BotDirectory(runtime.database)
    a=directory.create('local','Owned','Help')
    other=directory.create('other','Other','Help')
    with pytest.raises(PermissionError):directory.set_order('local',[other['id']])
    with pytest.raises(ValueError):directory.set_order('local',[a['id'],a['id']])
    assert [x['id'] for x in directory.list('other')]==[other['id']]
