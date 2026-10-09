"""UI locale and persisted channel output language resolution."""
import sys

LANGUAGES = {'zh':'Simplified Chinese', 'zh-TW':'Traditional Chinese', 'en':'English', 'ja':'Japanese', 'ko':'Korean', 'fr':'French', 'de':'German', 'es':'Spanish', 'pt-BR':'Brazilian Portuguese', 'ru':'Russian'}


def normalize(value):
    value = str(value or '').split(',')[0].split(';')[0].strip().replace('_','-')
    if value.lower() in ('zh-tw','zh-hk','zh-hant'):
        return 'zh-TW'
    if value.lower().startswith('pt'):
        return 'pt-BR'
    if value in LANGUAGES:
        return value
    base = value.split('-')[0].lower()
    return base if base in LANGUAGES else None


def output_language(runtime, request, principal, channel_id, data):
    channel = data.get('channel', {}) if isinstance(data, dict) else {}
    selected = normalize(channel.get('output_language')) if isinstance(channel, dict) else None
    if selected:
        return LANGUAGES[selected]
    if runtime and principal and not channel_id.startswith('entity-'):
        try:
            from .store import IntelligenceStore
            saved = IntelligenceStore(runtime.config.paths.artifacts_path / 'intelligence').get('channels', principal.actor_user_id, channel_id)
            selected = normalize(saved.get('output_language'))
        except (AttributeError, KeyError):
            pass
    if not selected and request is not None:
        selected = normalize(request.headers.get('x-intelligence-language'))
    if not selected:
        routes = sys.modules.get('omlx.admin.routes')
        getter = getattr(routes, '_current_ui_language', None)
        selected = normalize(getter()) if getter else None
    return LANGUAGES[selected or 'en']
