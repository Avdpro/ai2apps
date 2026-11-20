"""Download a public PDF without browser credentials, cookies or a proxy."""
import http.client
import ipaddress
import socket
import time
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from .repository import MAX_ATTACHMENT_BYTES


def _destination(url):
    if len(url) > 2048 or any(ord(c) < 33 or ord(c) == 127 for c in url) or '\\' in url:
        raise ValueError('Invalid PDF URL')
    parts = urlsplit(url)
    port = {'https': 443, 'http': 80}.get(parts.scheme)
    if (not port or parts.port not in (None, port) or not parts.hostname
            or parts.username is not None or parts.password is not None):
        raise ValueError('Use a public HTTP(S) URL without credentials or a custom port')
    host = parts.hostname.encode('idna').decode('ascii')
    authority = f'[{host}]' if ':' in host else host
    path = quote(parts.path or '/', safe="/%:@!$&'()*+,;=-._~")
    query = quote(parts.query, safe="/%?:@!$&'()*+,;=-._~")
    return urlunsplit((parts.scheme, authority, path, query, '')), host, port, path + ('?' + query if query else '')


def public_url(url):
    return _destination(url)[0]


def _pinned_connection(host, port, deadline):
    peers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not peers:
        raise ValueError('PDF host could not be resolved')
    for _, _, _, _, address in peers:
        ip = ipaddress.ip_address(address[0])
        ip = getattr(ip, 'ipv4_mapped', None) or ip
        if not ip.is_global or ip.is_multicast or ip.is_reserved:
            raise ValueError('PDF URL points to a non-public network address')

    def connect(_host_port, timeout=None, source_address=None):
        error = None
        for family, kind, proto, _, address in peers:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('PDF download timed out')
            peer = socket.socket(family, kind, proto)
            try:
                peer.settimeout(min(remaining, 5))
                peer.connect(address)  # Use the checked address; never resolve again.
                peer.settimeout(min(deadline - time.monotonic(), 8))
                return peer
            except (OSError, ValueError) as exc:
                peer.close()
                error = exc
        raise OSError('Could not connect to the public PDF host') from error

    factory = http.client.HTTPSConnection if port == 443 else http.client.HTTPConnection
    connection = factory(host, port, timeout=8)
    # HTTPSConnection retains the original hostname for certificate verification and SNI.
    connection._create_connection = connect
    return connection


def download(url):
    deadline = time.monotonic() + 25
    for hop in range(5):
        url, host, port, target = _destination(url)
        connection = _pinned_connection(host, port, deadline)
        try:
            connection.request('GET', target, headers={
                'Accept': 'application/pdf, application/octet-stream;q=0.5',
                'Accept-Encoding': 'identity',
                'User-Agent': 'AI2Apps-PublicPDF/1.0',
            })
            with connection.getresponse() as response:
                if response.status in (301, 302, 303, 307, 308):
                    location = response.getheader('Location')
                    if not location or hop == 4:
                        raise ValueError('PDF redirect limit exceeded')
                    next_url = urljoin(url, location)
                    if port == 443 and not next_url.lower().startswith('https://'):
                        raise ValueError('PDF redirect downgraded HTTPS')
                    url = next_url
                    continue
                if response.status != 200:
                    raise ValueError(f'Public PDF returned HTTP {response.status}')
                media = response.getheader('Content-Type', '').split(';', 1)[0].strip().lower()
                if media not in ('application/pdf', 'application/octet-stream'):
                    raise ValueError('The URL did not return a PDF; use a public full-text PDF link')
                size = response.getheader('Content-Length', '')
                if size.isdecimal() and int(size) > MAX_ATTACHMENT_BYTES:
                    raise ValueError('PDF exceeds the 25 MiB limit')
                data = bytearray()
                while True:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('PDF download timed out')
                    chunk = response.read1(65536)
                    if not chunk:
                        break
                    data.extend(chunk)
                    if len(data) > MAX_ATTACHMENT_BYTES:
                        raise ValueError('PDF exceeds the 25 MiB limit')
                if size.isdecimal() and len(data) != int(size):
                    raise ValueError('PDF download was incomplete')
                if b'%PDF-' not in data[:1024]:
                    raise ValueError('Downloaded content is not a PDF')
                return url, bytes(data)
        finally:
            connection.close()
    raise ValueError('PDF redirect limit exceeded')
