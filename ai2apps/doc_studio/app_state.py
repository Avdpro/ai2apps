"""Portable writing defaults for Doc Studio ASC-Bots."""
from ai2apps.apps.app_state import StateContract

from .models import APP_ID, WritingOptions
from .translation import MINI_ID as TRANSLATE, Options

PORTABLE = ('style', 'target', 'language')


def register(service):
    fields = WritingOptions.model_json_schema()['properties']
    properties = {key: {**fields[key], 'x-app-state': 'portable'} for key in PORTABLE}
    service.register(StateContract(
        APP_ID, None, 1, 'Doc Studio writing defaults',
        {'type': 'object', 'properties': properties, 'required': list(PORTABLE),
         'additionalProperties': False},
        clients=('desktop',),
        excluded_fields=('project_id', 'base_version_id', 'guidance', 'title', 'content',
                         'materials', 'outputs', 'chat', 'permissions'),
    ))
    settings = {
        TRANSLATE: ('Translate document settings', {
            'language': Options.model_json_schema()['properties']['language'],
            'output_format': {'enum': ['layout', 'markdown']},
            'markdown': {'type': 'boolean'},
        }),
        'ai2apps.imagine.article-cards': ('Article Cards settings', {
            'ratio': {'enum': ['3:4', '9:16']}, 'theme': {'enum': ['paper', 'sage', 'ink']},
        }),
    }
    for mini, (name, fields) in settings.items():
        service.register(StateContract(APP_ID, mini, 1, name, {
            'type': 'object', 'properties': {key: {**value, 'x-app-state': 'portable'} for key, value in fields.items()},
            'required': list(fields), 'additionalProperties': False,
        }, clients=('desktop',), excluded_fields=('text', 'file_id', 'profile_id', 'article', 'assets', 'outputs')))
