"""B0 definitions preserve owner identity and reject unimplemented execution modes."""
import json
import pytest
from pydantic import ValidationError
from ai2apps.messager.bot_types import BotDefinition, catalog
from ai2apps.messager.creation import create, options
from test_app_interactions import runtime
from test_bot_capability_discovery import setup
from test_bot_creation import draft


def test_reserved_presets_are_not_execution_authority():
    entries=catalog()
    assert [v['id'] for v in entries]==['standard','flash','asc','outlet','mirror']
    assert [v['id'] for v in entries if v['available']]==['standard','flash','asc']
    for entry in entries[1:]:
        with pytest.raises(ValidationError):
            BotDefinition.model_validate({k:entry[k] for k in ('execution_mode','audience','location')})
    for value in ({'schema_version':2},{'config':{'script':'arbitrary code'}},{'unexpected':True}):
        with pytest.raises(ValidationError):BotDefinition.model_validate(value)
    assert catalog()[0]['available']  # Mutating a returned catalog cannot enable a type.
    entries[3]['available']=True
    assert not catalog()[3]['available']


def test_every_creation_path_has_a_versioned_definition(runtime):
    setup(runtime);directory=runtime.messager_bots
    configured=create(runtime,'local',draft(runtime))
    direct=directory.create('local','Direct','Fixture')
    default=directory.ensure_default('local')
    listed={b['id']:b for b in directory.list('local')}
    for ref in (configured['id'],direct['id'],default):
        definition=listed[ref]['definition']
        assert definition==configured['definition']==direct['definition']
        assert definition['schema_version']==definition['revision']==1
        assert definition['click_behavior']=='conversation' and definition['config']=={}
    assert options(runtime)['bot_types']==catalog()
    assert create(runtime,'local',draft(runtime))==configured
    assert directory.list('foreign')==[]
    # Names, duties and avatars do not choose or alter execution mode.
    directory.update('local',direct['id'],'Flash-Bot','Run arbitrary fixed workflows')
    assert next(b for b in directory.list('local') if b['id']==direct['id'])['definition']['preset']=='standard'
    with runtime.database.transaction() as db:
        row=db.execute('SELECT definition_json FROM messager_bot_definitions WHERE bot_id=? AND actor=?',(configured['id'],'local')).fetchone()
    assert json.loads(row[0])==BotDefinition().model_dump()


def test_existing_standard_identity_projection_does_not_rewrite_user_state(runtime):
    setup(runtime);directory=runtime.messager_bots
    bot=directory.create('local','Existing','Keep my role')
    with runtime.database.transaction(write=True) as db:
        db.execute('DELETE FROM messager_bot_definitions WHERE bot_id=?',(bot['id'],))
    item=next(b for b in directory.list('local') if b['id']==bot['id'])
    assert item['definition']['preset']=='standard' and item['duty']=='Keep my role'
    with runtime.database.transaction() as db:
        assert db.execute('SELECT count(*) FROM messager_bot_definitions WHERE bot_id=?',(bot['id'],)).fetchone()[0]==0
