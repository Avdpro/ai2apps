"""Messager-owned, versioned Bot definitions; reserved types cannot be admitted."""
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StandardConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class FlashConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True)
    workflow_id: str = Field(min_length=1,max_length=100,pattern=r'^[a-z][a-z0-9_.-]*$')
    workflow_version: str = Field(min_length=1,max_length=32)
    plan: dict | None = None
    model: str | None = Field(default=None,max_length=300)
    review_id: str | None = Field(default=None,pattern=r'^[0-9a-f]{64}$')


class ShortcutConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True)
    state: dict


class BotDefinition(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True)
    schema_version: Literal[1] = 1
    execution_mode: Literal['agent', 'flash', 'app_shortcut'] = 'agent'
    audience: Literal['owner', 'outlet'] = 'owner'
    location: Literal['local', 'mirror'] = 'local'
    config: ShortcutConfig | FlashConfig | StandardConfig = Field(default_factory=StandardConfig)

    @model_validator(mode='after')
    def supported(self):
        if self.audience!='owner' or self.location!='local' or self.execution_mode not in ('agent','flash','app_shortcut'):

            raise ValueError('This Bot type is not available yet')
        expected={'agent':StandardConfig,'flash':FlashConfig,'app_shortcut':ShortcutConfig}[self.execution_mode]
        if not isinstance(self.config,expected):
            raise ValueError('Configuration does not match Bot execution mode')
        return self


# UI presets are conveniences over three orthogonal dimensions, not stored types.
PRESETS = (
    ('standard', 'agent', 'owner', 'local', True, 'conversation', 'chat'),
    ('flash', 'flash', 'owner', 'local', True, 'workflow_input', 'validated_input'),
    ('asc', 'app_shortcut', 'owner', 'local', True, 'app_shortcut', 'target_app'),
    ('outlet', 'agent', 'outlet', 'local', False, 'conversation', 'external_message'),
    ('mirror', 'agent', 'owner', 'mirror', False, 'remote_conversation', 'remote'),
)


def catalog():
    return [{'id':id, 'schema_version':1, 'execution_mode':mode, 'audience':audience,
             'location':location, 'available':available, 'click_behavior':click,
             'input_behavior':inputs, 'reason':None if available else 'not_implemented'}
            for id,mode,audience,location,available,click,inputs in PRESETS]


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS messager_bot_definitions(
        bot_id TEXT PRIMARY KEY, actor TEXT NOT NULL, revision INTEGER NOT NULL,
        definition_json TEXT NOT NULL)''')


def save(db, actor, bot_id, definition=None):
    value = BotDefinition.model_validate(definition or {}).model_dump()
    db.execute('INSERT INTO messager_bot_definitions VALUES(?,?,1,?)',
               (bot_id, actor, json.dumps(value)))
    return projection(json.dumps(value),1)


def projection(raw=None, revision=1):
    # Existing identities without a separate definition have always been standard.
    value = BotDefinition.model_validate(json.loads(raw) if raw else {}).model_dump()
    preset=next(p for p in catalog() if p['execution_mode']==value['execution_mode'] and p['audience']==value['audience'] and p['location']==value['location'])
    return {**value, 'revision':revision, 'preset':preset['id'],
            'available':preset['available'], 'click_behavior':preset['click_behavior'], 'input_behavior':preset['input_behavior']}
