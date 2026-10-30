"""Model-free automatic bucket job schema and enqueue."""
from ai2apps.core import utc_now_text
ROUTING_SCHEMA = """CREATE TABLE IF NOT EXISTS knowledge_bucket_routing (
 item_id TEXT PRIMARY KEY REFERENCES knowledge_items(id), actor_user_id TEXT NOT NULL,
 installation_id TEXT NOT NULL, item_revision INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending', model_id TEXT, fingerprint TEXT,
 token TEXT, approved TEXT, run_token TEXT, error TEXT, updated_at TEXT NOT NULL
)"""

def enqueue_routing(c,item_id,principal,revision):
    c.execute(ROUTING_SCHEMA)
    c.execute('INSERT OR IGNORE INTO knowledge_bucket_routing(item_id,actor_user_id,installation_id,item_revision,updated_at) VALUES (?,?,?,?,?)',
              (item_id,principal.actor_user_id,principal.installation_id,revision,utc_now_text()))

