"""Device-owned Mobile exposure policy, independent of Cloud App IDs."""
from ai2apps.core import utc_now_text

LEGACY_APPS = frozenset({'ai2apps.general-chat', 'ai2apps.todo', 'ai2apps.knowledge',
    'ai2apps.gallery', 'ai2apps.imagine-studio', 'ai2apps.video-studio', 'ai2apps.readaloud'})

class MobileAppPolicy:
    def __init__(self, database):
        self.database = database

    def enabled(self, installation_id, app_key):
        with self.database.transaction() as connection:
            row = connection.execute('SELECT enabled FROM mobile_app_access WHERE installation_id=? AND app_key=?',
                                     (installation_id, app_key)).fetchone()
        return bool(row['enabled']) if row is not None else app_key in LEGACY_APPS

    def set_enabled(self, installation_id, app_key, enabled):
        with self.database.transaction(write=True) as connection:
            connection.execute('''INSERT INTO mobile_app_access(installation_id,app_key,enabled,updated_at)
                VALUES (?,?,?,?) ON CONFLICT(installation_id,app_key) DO UPDATE SET
                enabled=excluded.enabled,updated_at=excluded.updated_at''',
                (installation_id, app_key, int(enabled), utc_now_text()))


def app_enabled(runtime, principal, app_key):
    return MobileAppPolicy(runtime.database).enabled(principal.installation_id, app_key)


def require_mobile_path(runtime, principal, path):
    """Guard direct native Mobile URLs as well as catalog/open requests."""
    from fastapi import HTTPException
    app = None
    for suffix, key in [('chat','ai2apps.general-chat'), ('todo','ai2apps.todo'),
                        ('knowledge','ai2apps.knowledge'), ('gallery','ai2apps.gallery')]:
        if any(path == prefix or path.startswith(prefix + '/')
               for prefix in ('/mobile/' + suffix, '/v1/mobile/' + suffix)):
            app = key
            break
    if app and not app_enabled(runtime, principal, app):
        raise HTTPException(403, 'This App is disabled for Mobile')


def package_gateway_ready():
    import os
    if 'AI2APPS_MOBILE_PACKAGE_GATEWAY_READY' in os.environ:
        return os.environ['AI2APPS_MOBILE_PACKAGE_GATEWAY_READY'] == '1'
    # Helper launches have an allowlisted environment. Read only the matching
    # instance's operator-owned configuration, never a path from an HTTP request.
    import json
    from pathlib import Path
    descriptor = os.environ.get('AI2APPS_RUN_DESCRIPTOR_PATH', '')
    if not descriptor or not Path(descriptor).is_absolute():
        return False
    try:
        path = Path(descriptor).parent.parent / 'config' / 'mobile-package-gateway.json'
        value = json.loads(path.read_text())
        return value == {'enabled': True, 'protocol': 'mobile-app-access-gateway-v1'}
    except (OSError, ValueError):
        return False
