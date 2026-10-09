from unittest.mock import AsyncMock
import pytest
from ai2apps.codex import desktop_open

ID='01a0fff9-0f0a-7d81-82d3-1e7f4a0f0cf2'

@pytest.mark.asyncio
async def test_open_uses_fixed_protocol_and_argv(monkeypatch):
    process=AsyncMock();process.returncode=0;process.communicate.return_value=(b'',b'')
    spawn=AsyncMock(return_value=process)
    monkeypatch.setattr(desktop_open.sys,'platform','darwin')
    monkeypatch.setattr(desktop_open.asyncio,'create_subprocess_exec',spawn)
    assert (await desktop_open.open_conversation(ID))['opened']
    assert spawn.call_args.args==('/usr/bin/open','codex://threads/'+ID)
    with pytest.raises(ValueError):await desktop_open.open_conversation('https://example.com')
    assert spawn.call_count==1

@pytest.mark.asyncio
async def test_launch_error_is_reported(monkeypatch):
    process=AsyncMock();process.returncode=1;process.communicate.return_value=(b'',b'No handler')
    monkeypatch.setattr(desktop_open.sys,'platform','darwin')
    monkeypatch.setattr(desktop_open.asyncio,'create_subprocess_exec',AsyncMock(return_value=process))
    with pytest.raises(ValueError,match='No handler'):await desktop_open.open_conversation(ID)
