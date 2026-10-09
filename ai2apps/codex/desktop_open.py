"""Open a Codex conversation through the local desktop's URL handler."""
import asyncio
import sys
import uuid


async def open_conversation(thread_id):
    try:
        canonical = str(uuid.UUID(thread_id))
    except (ValueError, TypeError, AttributeError) as error:
        raise ValueError('Invalid Codex conversation ID') from error
    if sys.platform != 'darwin':
        raise ValueError('Opening Codex Desktop is currently supported on macOS only')
    process = await asyncio.create_subprocess_exec(
        '/usr/bin/open', f'codex://threads/{canonical}',
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
    except (TimeoutError, asyncio.CancelledError):
        if process.returncode is None:
            process.kill()
        await process.communicate()
        raise
    if process.returncode:
        raise ValueError('Unable to open Codex Desktop: ' + stderr.decode(errors='replace')[-1000:])
    return {'opened': True, 'thread_id': canonical}
