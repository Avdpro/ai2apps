import logging
import pytest
from ai2apps.browser.shell_window import ShellBrowserWindowBroker


def queued(broker):
    return broker.enqueue(action='open',profile_key='a'*64,profile_name='Private name',is_default=True)


def test_handoff_records_phase_timings_without_profile_name(caplog):
    broker=ShellBrowserWindowBroker()
    with caplog.at_level(logging.INFO):
        key=queued(broker)
        broker.claim_next()
        broker.finish(key,status='launched',pid=42)
    assert 'queue_ms=' in caplog.text
    assert 'shell_ms=' in caplog.text
    assert 'total_ms=' in caplog.text
    assert 'Private name' not in caplog.text


def test_timeout_distinguishes_claimed_from_unclaimed():
    broker=ShellBrowserWindowBroker()
    key=queued(broker)
    with pytest.raises(TimeoutError,match='did not acknowledge'):
        broker.wait(key,timeout=0)
    key=queued(broker)
    broker.claim_next()
    with pytest.raises(TimeoutError,match='accepted.*did not finish'):
        broker.wait(key,timeout=0)
