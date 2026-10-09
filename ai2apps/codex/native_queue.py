"""Native Desktop delivery. Never resume or interrupt Desktop-owned sessions."""
import asyncio
import re
from .transport import CodexDesktop


class DeliveryRejected(ValueError):
    """The CLI rejected delivery; no successful enqueue was reported."""


async def enqueue(thread_id, message, model=''):
    binary = CodexDesktop.executable()
    if not binary: raise DeliveryRejected('Codex is not installed')
    # macOS imposes an argv limit; fail before starting a potentially ambiguous send.
    if len(message.encode()) > 100000:
        raise DeliveryRejected('Desktop task prompt exceeds 100 KB; move long content into an attachment')
    args = [binary, 'queue', '--thread', thread_id, '--message', message]
    if model: args += ['--model', model]
    proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, env=CodexDesktop.environment())
    try:
        out, err = await asyncio.wait_for(proc.communicate(), 30)
    except BaseException:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
        raise
    if proc.returncode:
        raise DeliveryRejected(err.decode(errors='replace')[-2000:] or 'Codex queue failed')
    match = re.search(r'Queued message ([\w-]+) for thread', out.decode(errors='replace'))
    return match.group(1) if match else None


async def find_turn(client, thread_id, marker, turn_id=None):
    cursor = None
    while True:
        params = {'threadId':thread_id, 'limit':5, 'itemsView':'full'}
        if cursor: params['cursor'] = cursor
        page = await client.call('thread/turns/list', params)
        for turn in page.get('data', []):
            if turn_id and turn.get('id') == turn_id: return turn
            for item in turn.get('items', []):
                if item.get('type') != 'userMessage': continue
                if any(marker in part.get('text','') for part in item.get('content', []) if isinstance(part, dict)):
                    return turn
        cursor = page.get('nextCursor')
        if not cursor: return None


def progress(turn):
    """Persisted status alone can say interrupted while a Desktop turn is active."""
    items = turn.get('items', [])
    output = '\n'.join(i.get('text','') for i in items if i.get('type') == 'agentMessage')[-100000:]
    step = next((str(i.get('command') or i.get('type'))[:2000] for i in reversed(items)
                 if i.get('type') not in ('userMessage','reasoning')), 'Codex Desktop is executing')
    terminal = turn.get('completedAt') is not None
    status = turn.get('status')
    if not terminal: return 'running', output, step
    return {'completed':'ended','interrupted':'cancelled','failed':'failed'}.get(status,'running'), output, step
