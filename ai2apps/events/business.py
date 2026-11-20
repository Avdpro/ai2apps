"""Versioned business facts over the existing EventStore; trusted owners register types."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Callable
from uuid import uuid4

from jsonschema import Draft202012Validator
from ai2apps.storage.records import canonical_json
from ai2apps.core import utc_now_text


@dataclass(frozen=True)
class EventType:
    name: str
    producer: str
    title: str
    subject_kind: str
    schema: dict
    filters: tuple[str, ...]
    coverage: str
    authorize: Callable[[str, str], bool]
    version: int = 1
    authorize_collection: Callable[[str], bool] | None = None
    details: tuple[str,str,str] | None = None


class BusinessEvents:
    def __init__(self, events):
        self.events, self.database, self.types = events, events.database, {}

    def register(self, definition: EventType):
        if definition.name in self.types:
            raise ValueError('Duplicate business event type')
        if definition.version != 1 or not re.fullmatch(r'[a-z][a-z0-9_]*(?:[.][a-z][a-z0-9_]*)+', definition.name) or not definition.producer:
            raise ValueError('Invalid business event namespace/version')
        Draft202012Validator.check_schema(definition.schema)
        definition = replace(definition, schema=json.loads(canonical_json(definition.schema)))
        self.types[definition.name] = definition
        return Publisher(self, definition)

    @staticmethod
    def revision(definition):
        return hashlib.sha256(canonical_json({'name':definition.name,'schema':definition.schema,
            'filters':definition.filters,'coverage':definition.coverage,'producer':definition.producer,
            'subject_kind':definition.subject_kind,'version':definition.version,
            'owned_collection':definition.authorize_collection is not None,'details':definition.details}).encode()).hexdigest()

    def catalog(self):
        return [dict(type=d.name, version=d.version, revision=self.revision(d), producer=d.producer, title=d.title, subject_kind=d.subject_kind,
                     data_schema=json.loads(canonical_json(d.schema)), filter_fields=list(d.filters),
                     coverage=d.coverage, subscription_scopes=['subjects']+(['owned_collection'] if d.authorize_collection else []), details_binding=d.details) for d in self.types.values()]

    def read(self, actor, event_id):
        with self.database.transaction() as db:
            row = db.execute('SELECT * FROM business_event_facts WHERE event_id=? AND owner=?', (event_id, actor)).fetchone()
        if row is None:
            raise KeyError('Business event unavailable')
        d = self.types.get(row['type'])
        if d is None or not d.authorize(actor, row['subject_id']):
            raise PermissionError('Business event scope unavailable')
        event = self.events.get(event_id)
        # Only business projections pass this boundary, never arbitrary raw events.
        return dict(id=event.id, sequence=event.sequence, type=row['type'], schema_version=event.schema_version,
                    subject={'kind': d.subject_kind, 'id': row['subject_id']}, occurred_at=event.occurred_at.isoformat(),
                    data=json.loads(row['data_json']), recorded_at=row['recorded_at'], declaration_revision=row['declaration_revision'], cause_root_id=row['cause_root_id'], cause=json.loads(row['cause_json']) if row['cause_json'] else None, causality='known' if row['cause_json'] and not json.loads(row['cause_json']).get('unknown') else 'unknown')

    def list(self, actor, *, after=0, limit=50, event_type=None):
        if after < 0 or not 1 <= limit <= 100:
            raise ValueError('Invalid business event cursor/limit')
        if event_type and event_type not in self.types:
            raise ValueError('Business event type unavailable')
        with self.database.transaction() as db:
            rows = db.execute('''SELECT event_id,sequence FROM business_event_facts
                WHERE owner=? AND sequence>? AND (? IS NULL OR type=?) ORDER BY sequence LIMIT ?''',
                (actor, after, event_type, event_type, limit)).fetchall()
        items = []
        for row in rows:
            try:
                items.append(self.read(actor, row['event_id']))
            except (KeyError, PermissionError):
                pass
        return {'items': items, 'next_cursor': rows[-1]['sequence'] if rows else after}


class Publisher:
    """Capability object retained by the trusted registering owner, never exposed over HTTP."""
    def __init__(self, service, definition):
        self.service, self.definition = service, definition

    def publish(self, db, *, owner, subject_id, occurrence_key, data, occurred_at=None, existing_event_id=None):
        service, d = self.service, self.definition
        if not owner or not subject_id or not occurrence_key or len(occurrence_key) > 300:
            raise ValueError('Business fact identity required')
        Draft202012Validator(d.schema).validate(data)
        if occurred_at:
            moment = datetime.fromisoformat(occurred_at.replace('Z','+00:00'))
            if moment.tzinfo is None:
                raise ValueError('Business event time requires timezone')
            occurred_at = moment.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        body = canonical_json(data)
        if len(body.encode()) > 16384:
            raise ValueError('Business event payload too large')
        signature = hashlib.sha256(canonical_json({'subject':subject_id,'data':data}).encode()).hexdigest()
        row = db.execute('''SELECT event_id,signature FROM business_event_facts
            WHERE owner=? AND producer=? AND type=? AND occurrence_key=?''',
            (owner,d.producer,d.name,occurrence_key)).fetchone()
        if row:
            if row['signature'] != signature:
                raise ValueError('Business occurrence content conflict')
            return row['event_id']
        if existing_event_id:
            event = db.execute('SELECT * FROM events WHERE id=?', (existing_event_id,)).fetchone()
            if event is None or event['type'] != d.name or event['subject_id'] != subject_id:
                raise ValueError('Existing event mismatch')
            event_id, sequence = event['id'], event['sequence']
        else:
            event = service.events.append_in_transaction(db,event_type=d.name,subject_id=subject_id,
                payload=data,schema_version=d.version,occurred_at=occurred_at)
            event_id, sequence = event.id,event.sequence
        from .causality import current_cause
        cause=current_cause.get() or {'owner':owner,'root_id':uuid4().hex,'depth':0,'ancestry':[]}
        if cause['owner']!=owner:raise PermissionError('Event cause owner mismatch')
        db.execute('''INSERT INTO business_event_facts
            (event_id,sequence,owner,producer,type,subject_id,occurrence_key,signature,data_json,cause_root_id,recorded_at,declaration_revision,cause_json)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (event_id,sequence,owner,d.producer,d.name,subject_id,occurrence_key,signature,body,cause['root_id'],utc_now_text(),service.revision(d),canonical_json(cause)))
        return event_id
