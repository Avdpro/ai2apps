"""Versioned Owner Mobile grant; authority comes only from a verified Cloud lease."""
import os

def ready():
    return os.environ.get('AI2APPS_OWNER_MOBILE_UNIFIED_READY', '1') == '1'


PROTOCOL = 'owner-mobile-unified-v1'
BINDINGS = ('mobile_access_protocol', 'mobile_client_id', 'mobile_client_epoch')


def validate_claims(claims):
    from uuid import UUID
    if not any(key in claims for key in BINDINGS):
        return
    if (claims.get('mobile_access_protocol') != PROTOCOL
            or str(UUID(claims.get('mobile_client_id', ''))) != claims.get('mobile_client_id')
            or type(claims.get('mobile_client_epoch')) is not int
            or claims['mobile_client_epoch'] < 1):
        raise ValueError('Invalid unified Mobile binding')


def authorized(claims):
    try:
        validate_claims(claims)
        return ready() and claims.get('mobile_access_protocol') == PROTOCOL
    except (ValueError, TypeError, AttributeError):
        return False

COMMIT_MODE = 'exchange-v1'


def negotiated(value):
    return ready() and value.get('mobileAccessProtocol') == PROTOCOL and value.get('commitMode') == COMMIT_MODE
