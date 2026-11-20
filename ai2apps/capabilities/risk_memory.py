"""Durable classification and user preferences for legacy unknown effects."""

import hashlib
import json

from .effects import can_remember_unknown_risk


def risk_binding(db, tool_name, provider=None):
    if provider and any(item[2] == "confirm" for item in provider[2]):
        return None
    row = db.execute(
        """SELECT t.id, t.revision, t.effects_json, s.id, s.package_version,
                  s.active_package_digest, s.revision, i.provider_key
           FROM tool_descriptors t JOIN service_descriptors s ON s.id=t.service_id
           JOIN service_instances i ON i.service_id=s.id
           WHERE t.qualified_name=? AND t.enabled=1 AND s.status='enabled'
             AND i.status IN ('running','degraded')
           ORDER BY CASE i.status WHEN 'running' THEN 0 ELSE 1 END,
                    i.updated_at DESC, i.created_at DESC LIMIT 1""",
        (tool_name,),
    ).fetchone()
    if row is None or not can_remember_unknown_risk(json.loads(row["effects_json"])):
        return None
    return hashlib.sha256(json.dumps(["v1", *row, provider]).encode()).hexdigest()


def risk_scope(db, run_id):
    row = db.execute(
        """SELECT s.app_instance_id, r.agent_definition_id, a.owner_user_id
           FROM agent_runs r JOIN sessions s ON s.id=r.session_id
           JOIN app_instances a ON a.id=s.app_instance_id WHERE r.id=?
             AND COALESCE(json_extract(r.input_json, '$.execution_origin'), 'user') = 'user'""",
        (run_id,),
    ).fetchone()
    if row is None:
        return None
    return row["app_instance_id"], row["agent_definition_id"], row["owner_user_id"] or "local"


def saved_risk(db, run_id, binding):
    scope = risk_scope(db, run_id)
    if scope is None or not binding:
        return None
    row = db.execute(
        """SELECT risk FROM tool_risk_preferences WHERE app_instance_id=?
           AND agent_definition_id=? AND actor=? AND binding=?""",
        (*scope, binding),
    ).fetchone()
    return row["risk"] if row else None


def remember_risk(db, run_id, binding, risk, interaction_id):
    scope = risk_scope(db, run_id)
    if scope is None:
        raise ValueError("This execution cannot save a tool risk preference")
    db.execute(
        """INSERT INTO tool_risk_preferences VALUES (?,?,?,?,?,?)
           ON CONFLICT(app_instance_id, agent_definition_id, actor, binding)
           DO UPDATE SET risk=excluded.risk, interaction_id=excluded.interaction_id""",
        (*scope, binding, risk, interaction_id),
    )


class ToolRiskMemory:
    def __init__(self, database):
        self.database = database

    def lookup(self, run_id, tool_name, provider):
        with self.database.transaction() as db:
            binding = risk_binding(db, tool_name, provider)
            if not binding:
                return None, None, None
            row = db.execute(
                "SELECT risk, reason FROM tool_risk_classifications WHERE binding=?",
                (binding,),
            ).fetchone()
            return binding, saved_risk(db, run_id, binding), dict(row) if row else None

    def store_classification(self, binding, risk, reason):
        with self.database.transaction(write=True) as db:
            db.execute("INSERT OR IGNORE INTO tool_risk_classifications VALUES (?,?,?)",
                       (binding, risk, reason))
