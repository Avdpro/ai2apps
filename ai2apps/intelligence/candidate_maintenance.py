"""Conservative, explicit maintenance of unreferenced learned candidates.

The caller owns the database transactions. No deletion or automatic startup
migration: histories remain readable, and every external reference retains its
draft, even if that reference is historical.
"""
import json
import re
import sqlite3
from collections import defaultdict


def archive_plan(platform, references=()):
    platform.row_factory = sqlite3.Row
    groups = defaultdict(list)
    for row in platform.execute("SELECT * FROM agent_drafts WHERE status!='archived'"):
        key = (json.loads(row['source_json']).get('provenance') or {}).get('intelligence_recipe_key')
        if key:
            groups[(row['owner_user_id'], key)].append(dict(row))
    candidates = [r for rows in groups.values() if len(rows) > 1 for r in rows]
    ids = {r['id']: r['id'] for r in candidates}
    protected = defaultdict(set)
    for row in platform.execute('SELECT id,draft_id,status FROM agent_compile_generations'):
        if row['draft_id'] in ids:
            ids[row['id']] = row['draft_id']
            if row['status'] == 'active':
                protected[row['draft_id']].add('active_generation')
    if not ids:
        return {'archive': [], 'retained': []}
    # Match the platform's identifiers once rather than trying every historical
    # version against large stored task payloads.
    pattern = re.compile(r'(?:adraft|agen)_[0-9a-f]{32}')
    for label, db in [('platform', platform), *references]:
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            cursor = db.execute('SELECT * FROM ' + quoted)
            columns = [d[0] for d in cursor.description]
            for row in cursor:
                record = dict(zip(columns, row))
                own = None
                if label == 'platform':
                    if table == 'agent_drafts': own = record.get('id')
                    elif table in ('agent_compile_generations', 'agent_step_evidence'):
                        own = record.get('draft_id')
                for column, value in record.items():
                    if not isinstance(value, str): continue
                    for token in pattern.findall(value):
                        if token not in ids: continue
                        target = ids[token]
                        # A draft's immutable versions and their evidence are
                        # retained by archival; they are not external callers.
                        if target != own:
                            protected[target].add(label + '.' + table + '.' + column)
    archive, retained = [], []
    for rows in groups.values():
        if len(rows) < 2: continue
        latest = max(rows, key=lambda r: (r['updated_at'], r['id']))['id']
        for row in rows:
            reasons = set(protected[row['id']])
            if row['active_generation_id'] or row['status'] == 'active': reasons.add('active_draft')
            if row['id'] == latest: reasons.add('latest_candidate')
            item = {k: row[k] for k in ('id', 'revision', 'status', 'updated_at')}
            if reasons: retained.append({**item, 'reasons': sorted(reasons)})
            else: archive.append(item)
    return {'archive': archive, 'retained': retained}


def apply_plan(platform, plan, timestamp):
    """Use only inside the same write transaction as the reference audit."""
    for row in plan['archive']:
        changed = platform.execute(
            """UPDATE agent_drafts SET status='archived',revision=revision+1,updated_at=?
               WHERE id=? AND revision=? AND status=? AND active_generation_id IS NULL
               AND NOT EXISTS (SELECT 1 FROM agent_compile_generations g
                               WHERE g.draft_id=agent_drafts.id AND g.status='active')""",
            (timestamp, row['id'], row['revision'], row['status']),
        )
        if changed.rowcount != 1:
            raise RuntimeError('Candidate changed during archival; roll back')
