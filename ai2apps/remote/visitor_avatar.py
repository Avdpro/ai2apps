"""Minimal public identity projection; never changes signed visitor claims."""
import re
import time


def avatar_projection(payload):
    revision = payload.get('ownerAvatarRevision')
    if type(revision) is not int or revision < 0:
        return {'ownerAvatarUrl': None, 'ownerAvatarRevision': None}
    url = payload.get('ownerAvatarUrl')
    if not isinstance(url, str) or not re.fullmatch(
            r'https://coder\.ai2apps\.com/v1/public/avatars/[0-9a-fA-F-]{36}\.png', url):
        url = None
    return {'ownerAvatarUrl': url, 'ownerAvatarRevision': revision}


class VisitorAvatar:
    def __init__(self, manager):
        self.manager = manager
        self.cache = {}

    async def get(self, owner_id):
        # Caller has already validated its visitor lease and authoritative Owner.
        entry = self.cache.get(owner_id)
        now = time.monotonic()
        if entry and entry[0] > now:
            return entry[1]
        try:
            payload = await self.manager._request('GET', '/v1/public/spaces/' + owner_id)
            value = avatar_projection(payload)
        except Exception:
            value = entry[1] if entry else avatar_projection({})
        if len(self.cache) > 100:
            self.cache.clear()
        self.cache[owner_id] = (now + 60, value)
        return value
