"""Offline registrable-site boundaries, including private hosting suffixes.

Data: Mozilla Public Suffix List, vendored with its MPL-2.0 notice at
web/static/vendor/public_suffix_list.dat. No runtime network lookup.
"""
from functools import lru_cache
import ipaddress
from pathlib import Path


def _ascii(host):
    return host.rstrip('.').lower().encode('idna').decode('ascii')


@lru_cache(maxsize=1)
def _rules():
    exact, wildcard, exceptions = set(), set(), set()
    path = Path(__file__).resolve().parents[1] / 'web/static/vendor/public_suffix_list.dat'
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('//'):
            continue
        if line.startswith('!'):
            exceptions.add(_ascii(line[1:]))
        elif line.startswith('*.'):
            wildcard.add(_ascii(line[2:]))
        else:
            exact.add(_ascii(line))
    return exact, wildcard, exceptions


@lru_cache(maxsize=4096)
def registrable_site(host):
    """Return eTLD+1; IPs, unknown suffixes and suffix-only hosts fail closed."""
    try:
        host = _ascii(host)
        ipaddress.ip_address(host)
        return None
    except (UnicodeError, AttributeError):
        return None
    except ValueError:
        pass
    labels = host.split('.')
    if any(not label or len(label) > 63 or not all(c.isalnum() or c == '-' for c in label)
           or label.startswith('-') or label.endswith('-') for label in labels):
        return None
    exact, wildcard, exceptions = _rules()
    suffix_length = 0
    for index in range(len(labels)):
        suffix = '.'.join(labels[index:])
        if suffix in exceptions:
            suffix_length = len(labels) - index - 1
            break
        if suffix in exact:
            suffix_length = max(suffix_length, len(labels) - index)
        if index > 0 and suffix in wildcard:
            suffix_length = max(suffix_length, len(labels) - index + 1)
    if not suffix_length or len(labels) <= suffix_length:
        return None
    return '.'.join(labels[-suffix_length-1:])
