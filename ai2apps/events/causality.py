"""Host-owned cause envelopes. They are provenance, never execution authority."""
from contextvars import ContextVar
from contextlib import contextmanager

current_cause = ContextVar('business_event_cause', default=None)
current_delivery = ContextVar('hook_delivery', default=None)

@contextmanager
def cause_scope(cause, delivery=None):
    token=current_cause.set(cause);work=current_delivery.set(delivery)
    try:yield
    finally:
        current_delivery.reset(work);current_cause.reset(token)
