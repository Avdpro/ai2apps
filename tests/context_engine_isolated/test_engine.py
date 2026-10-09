import asyncio
import json
import unittest
from dataclasses import replace

try:
    from context_engine import *
except ModuleNotFoundError:
    from ai2apps.context_engine import *


def surface(count=8, size=100):
    nodes = [Node.message("system", {"role": "system", "content": "keep system"})]
    nodes += [
        Node.message(f"n-{i}", {"role": "user", "content": str(i) + "x" * size})
        for i in range(count)
    ]
    return Surface("session", tuple(nodes))


class MeterFixture:
    unit = "tokens"

    def node(self, node, route):
        return len(node.body_json) // 4 + 1

    def envelope(self, surface, route):
        return 10  # Includes tool schema/request framing, separate from message nodes.


POLICY = Policy(headroom=20, summary_output=50, retain_units=50)
ROUTE = Route("provider", "model", 200, 10)
METER = MeterFixture()


class JournalStore:
    """Test adapter only: exercises the engine's durable lock/CAS contract."""

    def __init__(self, value=None):
        self.value = value or surface()
        self.target = ROUTE
        self.journal = []
        self.active = None

    def snapshot(self):
        return self.value

    def route(self):
        return self.target

    def begin(self, prepared):
        if self.active is not None:
            raise BusyError("active transaction")
        token = str(len(self.journal))
        self.active = token
        self.journal.append(
            {"type": "start", "id": token, "source": prepared.source_sha256}
        )
        return token

    def commit(self, token, prepared, summary, meter):
        if token != self.active:
            raise BusyError("not owner")
        if self.target != prepared.route:
            raise ChangedError("route changed")
        new = replacement(prepared, self.value, summary, meter)
        self.journal.append(
            {
                "type": "summary",
                "source": prepared.source_sha256,
                "body": summary.body_json,
            }
        )
        self.value = new
        self.journal.append({"type": "end", "id": token, "status": "committed"})
        self.active = None
        return new

    def fail(self, token, code):
        if token != self.active:
            raise BusyError("not owner")
        self.journal.append({"type": "end", "id": token, "status": code})
        self.active = None

    def dump(self):
        return json.dumps(
            {
                "nodes": [vars(n) for n in self.value.nodes],
                "journal": self.journal,
                "active": self.active,
            }
        )

    @classmethod
    def restore(cls, text):
        data = json.loads(text)
        store = cls(Surface("session", tuple(Node(**n) for n in data["nodes"])))
        store.journal, store.active = data["journal"], data["active"]
        return store

    def recover(self):
        if self.active is not None:
            self.fail(self.active, "interrupted")


def short_summary(selected, cap):
    async def answer():
        return Node.message(
            "summary:" + selected.source_sha256,
            {"role": "assistant", "content": "memory"},
        )

    return answer()


class SelectionTests(unittest.TestCase):
    def test_budget_matches_upstream_formula(self):
        self.assertEqual(
            Policy(headroom=100, retain_ratio=0.16).budgets(Route("p", "m", 1000, 200)),
            (700, 128),
        )

    def test_explicit_retention(self):
        self.assertEqual(
            Policy(headroom=100, retain_units=70).budgets(Route("p", "m", 1000, 200)),
            (700, 70),
        )

    def test_invalid_budget(self):
        for policy, route in [
            (Policy(headroom=200), ROUTE),
            (Policy(headroom=0, retain_units=190), ROUTE),
        ]:
            with self.assertRaises(ValueError):
                policy.budgets(route)

    def test_unknown_units(self):
        with self.assertRaises(ValueError):
            costs(surface(), ROUTE, Utf8Meter())

    def test_below_pressure_noop(self):
        self.assertIsNone(prepare(surface(1, 1), ROUTE, METER, POLICY))

    def test_preserves_system_and_priced_tail(self):
        value = surface()
        selected = prepare(value, ROUTE, METER, POLICY)
        self.assertNotIn("system", [n.id for n in selected.source])
        tail = [n for n in value.nodes if n.id in selected.after]
        self.assertGreaterEqual(sum(METER.node(n, ROUTE) for n in tail), 50)

    def test_overflow_bypasses_invalid_pressure_budget(self):
        self.assertIsNotNone(
            prepare(surface(), ROUTE, METER, Policy(headroom=1000), "context-overflow")
        )

    def test_manual_keeps_newest_node(self):
        selected = prepare(surface(), ROUTE, METER, POLICY, "manual")
        self.assertEqual(selected.after, ("n-7",))

    def test_nonmonotonic_ids_are_positional(self):
        value = Surface(
            "session",
            tuple(
                Node.message(i, {"role": "user", "content": "x" * 100})
                for i in ["90", "1", "75", "3"]
            ),
        )
        selected = prepare(value, ROUTE, METER, POLICY, "manual")
        self.assertEqual([n.id for n in selected.source], ["90", "1", "75"])

    def test_pins_form_hard_boundary(self):
        value = surface()
        value = replace(
            value,
            nodes=value.nodes[:3]
            + (replace(value.nodes[3], pinned=True),)
            + value.nodes[4:],
        )
        selected = prepare(value, ROUTE, METER, POLICY, "manual")
        self.assertEqual([n.id for n in selected.source], ["n-0", "n-1"])

    def test_tool_pair_cannot_be_split(self):
        value = Surface(
            "session",
            (
                Node.message("u", {"role": "user", "content": "x" * 100}),
                Node.message("a", {"role": "assistant", "tool_calls": [{"id": "c"}]}),
                Node.message(
                    "t", {"role": "tool", "tool_call_id": "c", "content": "x" * 100}
                ),
            ),
        )
        selected = prepare(value, ROUTE, METER, POLICY, "manual")
        self.assertEqual([n.id for n in selected.source], ["u"])

    def test_orphan_tool_rejected(self):
        with self.assertRaises(ValueError):
            balanced_cuts(
                Surface(
                    "session",
                    (Node.message("t", {"role": "tool", "tool_call_id": "bad"}),),
                )
            )

    def test_duplicate_result_rejected(self):
        nodes = (
            Node.message("a", {"role": "assistant", "tool_calls": [{"id": "c"}]}),
            Node.message("t", {"role": "tool", "tool_call_id": "c"}),
            Node.message("t2", {"role": "tool", "tool_call_id": "c"}),
        )
        with self.assertRaises(ValueError):
            balanced_cuts(Surface("session", nodes))

    def test_detached_input(self):
        original = {"role": "user", "content": "unchanged"}
        node = Node.message("a", original)
        original["content"] = "changed"
        self.assertEqual(node.body["content"], "unchanged")

    def test_multimodal_source_is_preserved(self):
        image = {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": "data:image/example"}}
            ],
        }
        value = Surface(
            "session",
            (
                Node.message("image", image),
                Node.message("tail", {"role": "user", "content": "tail"}),
            ),
        )
        self.assertEqual(
            prepare(value, ROUTE, METER, POLICY, "manual").source[0].body, image
        )


class TransactionTests(unittest.IsolatedAsyncioTestCase):
    async def test_commit_has_source_journal(self):
        store = JournalStore()
        await compact(store, METER, short_summary, POLICY)
        self.assertIsNone(store.active)
        self.assertEqual(
            [x["type"] for x in store.journal], ["start", "summary", "end"]
        )

    async def test_summary_failure_keeps_original(self):
        store = JournalStore()
        before = store.value

        async def fail(*args):
            raise RuntimeError("provider error")

        with self.assertRaises(RuntimeError):
            await compact(store, METER, fail, POLICY)
        self.assertEqual(store.value, before)
        self.assertIsNone(store.active)

    async def test_large_summary_rejected(self):
        store = JournalStore()
        before = store.value

        async def large(*args):
            return Node.message("summary", {"role": "assistant", "content": "x" * 5000})

        with self.assertRaises(SummaryError):
            await compact(store, METER, large, POLICY)
        self.assertEqual(store.value, before)

    async def test_cancellation_closes_lock(self):
        store = JournalStore()
        started = asyncio.Event()

        async def wait(*args):
            started.set()
            await asyncio.Event().wait()

        task = asyncio.create_task(compact(store, METER, wait, POLICY))
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertIsNone(store.active)
        self.assertEqual(store.journal[-1]["status"], "cancelled")

    async def test_changed_source_rejected(self):
        store = JournalStore()

        async def change(selected, cap):
            store.value = replace(
                store.value,
                nodes=store.value.nodes[:1]
                + (Node.message("n-0", {"role": "user", "content": "changed"}),)
                + store.value.nodes[2:],
            )
            return await short_summary(selected, cap)

        with self.assertRaises(ChangedError):
            await compact(store, METER, change, POLICY)

    async def test_route_change_rejected(self):
        store = JournalStore()

        async def change(selected, cap):
            store.target = replace(ROUTE, model="new")
            return await short_summary(selected, cap)

        with self.assertRaises(ChangedError):
            await compact(store, METER, change, POLICY)

    async def test_unrelated_append_survives(self):
        store = JournalStore()

        async def append(selected, cap):
            store.value = replace(
                store.value,
                nodes=store.value.nodes
                + (Node.message("later", {"role": "user", "content": "later"}),),
            )
            return await short_summary(selected, cap)

        await compact(store, METER, append, POLICY)
        self.assertEqual(store.value.nodes[-1].id, "later")

    async def test_busy_lock(self):
        store = JournalStore()
        store.active = "other"
        with self.assertRaises(BusyError):
            await compact(store, METER, short_summary, POLICY)

    async def test_restart_recovers_uncommitted_start(self):
        store = JournalStore()
        store.begin(prepare(store.value, ROUTE, METER, POLICY))
        restarted = JournalStore.restore(store.dump())
        before = restarted.value
        restarted.recover()
        self.assertEqual(restarted.value, before)
        await compact(restarted, METER, short_summary, POLICY)

    async def test_overflow_only_after_progress(self):
        calls = []

        async def call():
            calls.append(1)
            if len(calls) == 1:
                raise ContextOverflowError()
            return "ok"

        async def progress():
            return True

        self.assertEqual(await with_overflow_recovery(call, progress), "ok")
        self.assertEqual(len(calls), 2)

    async def test_overflow_no_progress_stops(self):
        calls = []

        async def call():
            calls.append(1)
            raise ContextOverflowError()

        async def no():
            return False

        with self.assertRaises(ContextOverflowError):
            await with_overflow_recovery(call, no)
        self.assertEqual(len(calls), 1)

    async def test_ordinary_error_not_retried(self):
        async def call():
            raise ValueError("ordinary")

        async def no():
            self.fail("must not recover ordinary errors")

        with self.assertRaises(ValueError):
            await with_overflow_recovery(call, no)


class ExtensionTests(unittest.TestCase):
    def test_exact_route_policy(self):
        special = Policy(headroom=10)
        mapping = Policies(overrides=(("provider", "model", special),))
        self.assertEqual(mapping.resolve(ROUTE), special)
        self.assertEqual(
            mapping.resolve(replace(ROUTE, model="other")), mapping.default
        )

    def test_duplicate_override_rejected(self):
        with self.assertRaises(ValueError):
            Policies(overrides=(("p", "m", POLICY), ("p", "m", POLICY)))

    def test_explicit_range(self):
        value = surface()
        selected = prepare_range(value, ROUTE, METER, 1, 3)
        result = replacement(
            selected,
            value,
            Node.message("s", {"role": "assistant", "content": "short"}),
            METER,
        )
        self.assertEqual([n.id for n in result.nodes[:3]], ["system", "s", "n-2"])

    def test_system_range_rejected(self):
        with self.assertRaises(ValueError):
            prepare_range(surface(), ROUTE, METER, 0, 2)
class ImageProjectionTests(unittest.TestCase):
    def test_explicit_image_reference_preserves_source(self):
        source = Node.message('image', {'role':'user','content':[{'type':'text','text':'keep instruction'},{'type':'image_url','image_url':{'url':'data:image/png;base64,ABC'}}]})
        result = offload_images(source, (1,), {'transaction':'transaction','tool':'reader'})
        self.assertEqual(source.body['content'][1]['type'], 'image_url')
        self.assertEqual(result.body['content'][0], source.body['content'][0])
        self.assertIn('omitted',result.body['content'][1]['text'])
        with self.assertRaises(ValueError): offload_images(result,(1,), {})
        with self.assertRaises(ValueError): offload_images(source,(1,1), {})

    def test_only_old_input_images_are_selected(self):
        image={'type':'image_url','image_url':{'url':'https://example.test/image.png'}}
        nodes=tuple(Node.message(str(i),{'role':role,'content':[image]},pinned=i==2) for i,role in enumerate(('assistant','user','user')))
        self.assertEqual(oldest_images(Surface('s',nodes)), ((nodes[1],(0,)),))

class PruningTests(unittest.TestCase):
    def test_tool_pair_and_original_evidence_preserved(self):
        tool = Node.message('tool', {'role':'tool','tool_call_id':'call','content':'evidence'+'x'*40000})
        projected = prune_tool_result(tool, {'transaction':'source','tool':'reader'})
        self.assertIsNotNone(projected)
        self.assertEqual(projected.body['tool_call_id'],'call')
        self.assertEqual(tool.body['content'],'evidence'+'x'*40000)
        self.assertLess(len(projected.body_json),len(tool.body_json))
        self.assertIn('Partial original',projected.body['content'])
        self.assertIsNone(prune_tool_result(projected,{},threshold=1))

    def test_user_and_small_results_do_not_prune(self):
        self.assertIsNone(prune_tool_result(Node.message('user',{'role':'user','content':'x'*40000}),{}))
        self.assertIsNone(prune_tool_result(Node.message('tool',{'role':'tool','tool_call_id':'call','content':'short'}),{}))
