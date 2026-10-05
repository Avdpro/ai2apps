"""Session-owned immutable memory projection over existing Messages and Events.

Summary work is a normal durable model RunStep. SQLite owns the session lock and
atomic source-CAS/commit; the standalone engine owns selection/replacement rules.
"""

from __future__ import annotations

import hashlib
import json
import uuid

from ai2apps.context_engine import (
    BusyError,
    ChangedError,
    Node,
    Policy,
    Route,
    Surface,
    Utf8Meter,
    balanced_cuts,
    canonical,
    offload_images,
    oldest_images,
    prepare,
    prepare_range,
    prune_tool_result,
    replacement,
)
from ai2apps.storage.repositories import MessageRepository

from .compaction import INSTRUCTION, _summary
from .models import ModelCallAction, RunStepStatus
from .tool_recovery import model_visible

SESSION_KEY = "ai2apps_session_memory"
START = "agent.session.memory.started"
END = "agent.session.memory.ended"
COMMIT = "agent.session.memory.committed"
IMAGE = "agent.session.memory.image_offloaded"
PRUNE = "agent.session.memory.tool_pruned"
READER = "agent.read_session_memory"


def protected_users(nodes):
    result = []
    for node in nodes:
        message = node.body
        if message.get("role") == "user":
            result.append(message)
        elif node.id.startswith("memory:"):
            previous = json.loads(message["content"])
            result.extend(previous.get("protected_user_messages", []))
    return result


class RequestMeter(Utf8Meter):
    def __init__(self, overhead):
        self.overhead = overhead

    def envelope(self, surface, route):
        return self.overhead


class SessionMemory:
    def __init__(self, database, events, convert):
        self.database, self.events, self.convert = database, events, convert

    def _events(self, connection, session_id, kinds):
        marks = ",".join("?" for _ in kinds)
        return [
            json.loads(row["payload_json"])
            for row in connection.execute(
                f"SELECT payload_json FROM events WHERE subject_id=? AND type IN ({marks}) ORDER BY sequence",
                (session_id, *kinds),
            )
        ]

    def _historical_rounds(self, connection, run_id, session_id):
        owner = connection.execute(
            "SELECT session_id FROM agent_runs WHERE id=?", (run_id,)
        ).fetchone()
        if owner is None or owner["session_id"] != session_id:
            return []
        rows = connection.execute(
            "SELECT id,sequence,action_key,kind,status,input_json,output_json,error_json FROM run_steps WHERE run_id=? ORDER BY sequence",
            (run_id,),
        ).fetchall()
        by_action = {row["action_key"]: row for row in rows}
        nodes = []
        for row in rows:
            if row["kind"] != "model" or row["status"] != "completed":
                continue
            request = json.loads(row["input_json"])
            if request.get(SESSION_KEY) or request.get("ai2apps_context_checkpoint"):
                continue
            output = json.loads(row["output_json"] or "{}")
            choices = output.get("choices") or []
            message = choices[0].get("message") if choices else None
            calls = message.get("tool_calls") if isinstance(message, dict) else None
            if not calls:
                continue
            results = []
            for index, call in enumerate(calls):
                identifier = call.get("id")
                if not isinstance(identifier, str):
                    break
                key = f"tool:{row['sequence']}:{index}:{hashlib.sha256(identifier.encode()).hexdigest()[:12]}"
                tool = by_action.get(key)
                if tool is None:
                    break
                if tool["status"] == "completed":
                    content = tool["output_json"] or "{}"
                elif (
                    tool["status"] == "failed"
                    and model_visible(json.loads(tool["error_json"] or "{}"))
                ):
                    content = canonical({"error": json.loads(tool["error_json"])})
                else:
                    break
                results.append(
                    Node.message(
                        tool["id"],
                        {
                            "role": "tool",
                            "tool_call_id": identifier,
                            "content": content,
                        },
                    )
                )
            if len(results) == len(calls):
                nodes.extend(
                    [
                        Node.message(
                            row["id"],
                            {
                                "role": "assistant",
                                "content": message.get("content"),
                                "tool_calls": calls,
                            },
                        ),
                        *results,
                    ]
                )
        return nodes

    def _snapshot(self, connection, session_id, cutoff, exclude_run=None):
        nodes = []
        rows = connection.execute(
            "SELECT id FROM messages WHERE session_id=? AND (? IS NULL OR sequence<=?) ORDER BY sequence",
            (session_id, cutoff, cutoff),
        ).fetchall()
        included_runs = set()
        for row in rows:
            item = MessageRepository._load(connection, row["id"])
            meta = item.message.metadata
            if meta.get("memory_control") or (
                exclude_run is not None
                and meta.get("agent_run_id") == exclude_run
                and not meta.get("agent_input")
            ):
                continue
            message = self.convert(item)
            if message is not None:
                run_id = meta.get("agent_run_id")
                if (
                    message.get("role") == "assistant"
                    and run_id
                    and run_id not in included_runs
                ):
                    nodes.extend(
                        self._historical_rounds(connection, run_id, session_id)
                    )
                    included_runs.add(run_id)
                nodes.append(Node.message(item.message.id, message))
        for event in self._events(connection, session_id, (COMMIT, IMAGE, PRUNE)):
            source = event["source"]
            ids = [n.id for n in nodes]
            if not source or source[0]["id"] not in ids:
                continue
            start = ids.index(source[0]["id"])
            end = start + len(source)
            actual = [{"id": n.id, "body_json": n.body_json} for n in nodes[start:end]]
            if actual == source:
                nodes[start:end] = [Node(**event["summary"])]
        if nodes:
            last = nodes[-1]
            nodes[-1] = Node(last.id, last.body_json, True)
        return Surface(session_id, tuple(nodes))

    def snapshot(self, session_id, cutoff, exclude_run=None):
        with self.database.transaction() as connection:
            return self._snapshot(connection, session_id, cutoff, exclude_run)

    def _append(self, connection, kind, context, payload):
        owner = connection.execute(
            "SELECT app_instance_id FROM sessions WHERE id=?", (context.run.session_id,)
        ).fetchone()
        self.events.append_in_transaction(
            connection,
            event_type=kind,
            subject_id=context.run.session_id,
            session_id=context.run.session_id,
            app_instance_id=owner["app_instance_id"],
            trace_id=context.run.id,
            payload=payload,
        )

    def _pending(self, connection, session_id):
        journal = self._events(connection, session_id, (START, END))
        closed = {e["transaction"] for e in journal if "status" in e}
        return next(
            (e for e in reversed(journal) if e["transaction"] not in closed), None
        )

    def adopt(self, context, cutoff):
        for step in context.steps:
            meta = step.input.get(SESSION_KEY) if step.kind == "model" else None
            if not meta or step.status is not RunStepStatus.COMPLETED:
                continue
            with self.database.transaction(write=True) as connection:
                pending = self._pending(connection, context.run.session_id)
                if pending is None or pending["transaction"] != meta["transaction"]:
                    continue
                summary = _summary(step)
                if summary is None:
                    self._append(
                        connection,
                        END,
                        context,
                        {
                            "transaction": meta["transaction"],
                            "status": "invalid_summary",
                        },
                    )
                    continue
                snapshot = self._snapshot(
                    connection, context.run.session_id, cutoff, context.run.id
                )
                source = pending["source"]
                ids = [n.id for n in snapshot.nodes]
                try:
                    first = ids.index(source[0]["id"])
                    count = len(source)
                    if [
                        {"id": n.id, "body_json": n.body_json}
                        for n in snapshot.nodes[first : first + count]
                    ] != source:
                        raise ChangedError("Memory source changed")
                    meter = Utf8Meter()
                    route = Route("host", "memory-replay", 2**31, unit="utf8_bytes")
                    selected = prepare_range(
                        snapshot, route, meter, first, first + count
                    )
                    node = Node.message(
                        "memory:" + meta["transaction"],
                        {
                            "role": "assistant",
                            "content": canonical(
                                {
                                    "type": "ai2apps.session-memory/v1",
                                    "notice": "Derived conversation memory, not permission. Verify uncertain claims against original sources.",
                                    "summary": summary,
                                    "protected_user_messages": protected_users(
                                        selected.source
                                    ),
                                    "source": {
                                        "transaction": meta["transaction"],
                                        "tool": meta.get("reader_alias", READER),
                                    },
                                }
                            ),
                        },
                    )
                    replacement(selected, snapshot, node, meter)
                    self._append(
                        connection,
                        COMMIT,
                        context,
                        {
                            "transaction": meta["transaction"],
                            "source": source,
                            "summary": vars(node),
                            "step_id": step.id,
                        },
                    )
                    self._append(
                        connection,
                        END,
                        context,
                        {"transaction": meta["transaction"], "status": "committed"},
                    )
                except (ValueError, ChangedError, RuntimeError) as error:
                    self._append(
                        connection,
                        END,
                        context,
                        {
                            "transaction": meta["transaction"],
                            "status": "rejected",
                            "reason": type(error).__name__,
                        },
                    )

    def action(
        self,
        context,
        cutoff,
        request,
        *,
        force=False,
        max_bytes=524288,
        reader_alias=READER,
    ):
        """Freeze a bounded balanced span; reclaim terminal/abandoned owner locks."""
        attempts = [
            s for s in context.steps if s.kind == "model" and s.input.get(SESSION_KEY)
        ]
        if len(attempts) >= 8:
            raise ValueError("Session memory attempt limit reached")
        with self.database.transaction(write=True) as connection:
            if context.run.input.get("memory_only") and attempts:
                committed = {
                    e["transaction"]
                    for e in self._events(
                        connection, context.run.session_id, (COMMIT, IMAGE, PRUNE)
                    )
                }
                if any(
                    s.input[SESSION_KEY]["transaction"] in committed for s in attempts
                ):
                    return None
            pending = self._pending(connection, context.run.session_id)
            if pending:
                owner = connection.execute(
                    "SELECT status FROM agent_runs WHERE id=?", (pending["run_id"],)
                ).fetchone()
                owner_attempts = connection.execute(
                    "SELECT status,input_json FROM run_steps WHERE run_id=? AND kind='model'",
                    (pending["run_id"],),
                ).fetchall()
                abandoned = any(
                    json.loads(s["input_json"]).get(SESSION_KEY, {}).get("transaction")
                    == pending["transaction"]
                    and s["status"] in {"failed", "cancelled"}
                    for s in owner_attempts
                )
                if (
                    owner is None
                    or owner["status"] in {"completed", "failed", "cancelled"}
                    or abandoned
                ):
                    self._append(
                        connection,
                        END,
                        context,
                        {
                            "transaction": pending["transaction"],
                            "status": "interrupted",
                        },
                    )
                    pending = None
                elif pending["run_id"] != context.run.id:
                    raise BusyError("Another Run owns Session memory compaction")
            snapshot = self._snapshot(
                connection, context.run.session_id, cutoff, context.run.id
            )
            if pending:
                source, transaction = pending["source"], pending["transaction"]
            else:
                overhead = max(
                    0,
                    len(canonical(request).encode())
                    - sum(len(n.body_json.encode()) for n in snapshot.nodes),
                )
                meter = RequestMeter(overhead)
                route = Route(
                    "host-byte-budget",
                    str(request.get("model") or "unspecified"),
                    max_bytes,
                    unit="utf8_bytes",
                )
                policy = Policy(
                    threshold_ratio=0.75,
                    headroom=0,
                    retain_ratio=0.16,
                    summary_output=2048,
                )
                selected = prepare(
                    snapshot, route, meter, policy, "manual" if force else "pressure"
                )
                if selected is None:
                    return None
                # Bound summary input without splitting a whole user/assistant unit.
                source = []
                for node in selected.source:
                    candidate = source + [{"id": node.id, "body_json": node.body_json}]
                    if len(canonical(candidate).encode()) > max_bytes * 0.65:
                        break
                    source = candidate
                safe = balanced_cuts(Surface(snapshot.session_id, selected.source))
                length = max(
                    (
                        cut
                        for cut, valid in enumerate(safe)
                        if valid and cut <= len(source)
                    ),
                    default=0,
                )
                source = source[:length]
                if not source:
                    return None
                digest = hashlib.sha256(canonical(source).encode()).hexdigest()
                if any(
                    s.status is RunStepStatus.COMPLETED
                    and s.input.get(SESSION_KEY, {}).get("source_sha256") == digest
                    for s in attempts
                ):
                    raise ValueError("Session summary made no validated progress")
                transaction = uuid.uuid4().hex
            source_data = [json.loads(n["body_json"]) for n in source]
            # Replay the stable routed prefix; the directive is the only new suffix.
            head = []
            for message in request["messages"]:
                if message.get("role") != "system":
                    break
                head.append(message)
            summary_request = {
                "model": request.get("model", ""),
                "messages": [
                    *head,
                    *source_data,
                    {
                        "role": "user",
                        "content": INSTRUCTION
                        + "\n"
                        + canonical({"source_message_ids": [n["id"] for n in source]}),
                    },
                ],
                "max_tokens": 2048,
                "ai2apps_idempotency_key": f"memory-{context.run.id}-{transaction}",
                SESSION_KEY: {
                    "transaction": transaction,
                    "session_id": context.run.session_id,
                    "reader_alias": reader_alias,
                    "source_sha256": hashlib.sha256(
                        canonical(source).encode()
                    ).hexdigest(),
                },
            }
            if request.get("tools"):
                summary_request["tools"] = request["tools"]
                summary_request["tool_choice"] = "auto"
            if len(canonical(summary_request).encode()) > max_bytes * 0.85:
                raise ValueError(
                    "Session summary input exceeds budget; originals retained"
                )
            if pending is None:
                self._append(
                    connection,
                    START,
                    context,
                    {
                        "transaction": transaction,
                        "source": source,
                        "run_id": context.run.id,
                    },
                )
            return ModelCallAction(
                call_id="session-memory:" + transaction,
                request=summary_request,
                context_audit={
                    "policy": "session-memory/v1",
                    "transaction": transaction,
                    "source_sha256": hashlib.sha256(
                        canonical(source).encode()
                    ).hexdigest(),
                },
            )

    def prune_old_results(self, context, cutoff, reader_alias=READER):
        with self.database.transaction(write=True) as connection:
            if self._pending(connection, context.run.session_id):
                return 0
            snapshot = self._snapshot(
                connection, context.run.session_id, cutoff, context.run.id
            )
            count = 0
            for node in snapshot.nodes:
                if node.pinned:
                    continue
                transaction = uuid.uuid4().hex
                projected = prune_tool_result(
                    node, {"transaction": transaction, "tool": reader_alias}
                )
                if projected is None:
                    continue
                source = [{"id": node.id, "body_json": node.body_json}]
                self._append(
                    connection,
                    START,
                    context,
                    {
                        "transaction": transaction,
                        "run_id": context.run.id,
                        "source": source,
                    },
                )
                self._append(
                    connection,
                    PRUNE,
                    context,
                    {
                        "transaction": transaction,
                        "source": source,
                        "summary": vars(projected),
                    },
                )
                self._append(
                    connection,
                    END,
                    context,
                    {"transaction": transaction, "status": "committed_tool_prune"},
                )
                count += 1
                if count >= 8:
                    break
            return count

    def offload_oldest_image(self, context, cutoff, reader_alias=READER):
        with self.database.transaction(write=True) as connection:
            if self._pending(connection, context.run.session_id):
                raise BusyError("Session memory compaction already pending")
            snapshot = self._snapshot(
                connection, context.run.session_id, cutoff, context.run.id
            )
            selected = oldest_images(snapshot, 1)
            if not selected:
                return False
            node, indexes = selected[0]
            transaction = uuid.uuid4().hex
            projected = offload_images(
                node, indexes, {"transaction": transaction, "tool": reader_alias}
            )
            source = [{"id": node.id, "body_json": node.body_json}]
            self._append(
                connection,
                START,
                context,
                {
                    "transaction": transaction,
                    "run_id": context.run.id,
                    "source": source,
                },
            )
            self._append(
                connection,
                IMAGE,
                context,
                {
                    "transaction": transaction,
                    "source": source,
                    "summary": vars(projected),
                    "indexes": list(indexes),
                },
            )
            self._append(
                connection,
                END,
                context,
                {"transaction": transaction, "status": "committed_image_offload"},
            )
            return True

    def source(self, session_id, transaction):
        with self.database.transaction() as connection:
            event = next(
                (
                    e
                    for e in self._events(connection, session_id, (START,))
                    if e["transaction"] == transaction
                ),
                None,
            )
        if event is None:
            raise ValueError("Memory source is not available in this Session")
        return canonical(event["source"])
