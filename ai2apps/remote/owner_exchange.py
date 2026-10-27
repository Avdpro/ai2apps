"""Instance-private IDs for bounded, idempotent unified handoff exchanges.

Only a hash of the handoff is persisted; the bearer stays in request memory.
Storage errors fail closed before contacting Cloud. Caller holds logout lock.
"""
import hashlib
import json
import time
from uuid import UUID, uuid4
from .security import RemoteTokenError

KEY = 'owner-mobile-exchange-requests-v1'


class ExchangeRequests:
    def __init__(self, manager):
        self.manager = manager

    def request_id(self, device, connection, handoff):
        try:
            try:
                entries = json.loads(self.manager.secret_backend.load(KEY))
            except KeyError:
                entries = {}
            if not isinstance(entries, dict):raise ValueError()
            now = time.time()
            for value in entries.values():
                if str(UUID(value['requestId'])) != value['requestId'] or type(value['created']) not in (int,float):raise ValueError()
            # Keep longer than Cloud's 60-second committed recovery window;
            # never turn an expired same-handoff attempt into a fresh operation.
            entries = {k:v for k,v in entries.items() if now-v['created'] < 86400}
            key = hashlib.sha256((device+'\n'+(connection or '')+'\n'+handoff).encode()).hexdigest()
            if key not in entries:
                if len(entries)>=256:raise ValueError()
                entries[key] = {'requestId':str(uuid4()),'created':now}
            self.manager.secret_backend.store(KEY, json.dumps(entries))
            return entries[key]['requestId']
        except Exception:
            raise RemoteTokenError('Unified Mobile exchange recovery storage unavailable') from None
