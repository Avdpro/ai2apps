"""User-initiated package export through the authenticated native Shell picker.

Only server-authorized sources enter this queue. Web content cannot supply a
destination: it is returned by the Shell's native Save As dialog.
"""
import threading
import time
from pathlib import Path
from uuid import uuid4

from ai2apps.studio.live_photo_pair import pvt_bundle


class NativeExportBroker:
    def __init__(self):
        self.lock = threading.Lock()
        self.requests = {}
        self.last_poll = 0.0

    def claim_next(self):
        with self.lock:
            self.last_poll = time.monotonic()
            for identifier, item in self.requests.items():
                if not item['claimed']:
                    item['claimed'] = True
                    return {'id': identifier, 'name': 'LivePhoto.pvt', 'extension': 'pvt'}
        return None

    def enqueue(self, source):
        with self.lock:
            if time.monotonic() - self.last_poll > 5:
                raise ValueError('Restart the updated Desktop Shell to use Save As')
            if len(self.requests) >= 8:
                raise ValueError('Too many pending Save As dialogs')
            identifier = uuid4().hex
            self.requests[identifier] = dict(source=Path(source), claimed=False,
                event=threading.Event(), result=None)
            return identifier

    def wait(self, identifier, timeout=600):
        with self.lock:
            item = self.requests[identifier]
        try:
            if not item['event'].wait(timeout):
                raise ValueError('Save As timed out; please try again')
            if item['result'].get('error'):
                raise ValueError(item['result']['error'])
            return item['result']
        finally:
            with self.lock:
                self.requests.pop(identifier, None)

    def finish(self, identifier, *, path=None, error=None):
        # Hold the lock through export: timeout/removal cannot race a late picker
        # response into writing a file after the originating request has expired.
        with self.lock:
            item = self.requests.get(identifier)
            if not item or not item['claimed'] or item['result'] is not None:
                raise ValueError('Save As request is no longer active')
            result = {'cancelled': True}
            if error:
                result = {'error': str(error)[:500]}
            elif path:
                destination = Path(path)
                if not destination.is_absolute() or destination.suffix.lower() != '.pvt':
                    raise ValueError('Native Save As must select an absolute .pvt destination')
                try:
                    pvt_bundle(item['source'], destination)
                    result = {'cancelled': False, 'name': destination.name, 'path': str(destination)}
                except Exception as exc:
                    result = {'error': str(exc)[:500]}
            item['result'] = result
            item['event'].set()
            return result


native_export_broker = NativeExportBroker()
