"""Strict recognition of HF Static's additive head metadata, not HTML cleanup.

The complete original byte sequence must survive unchanged. Only one known
platform insertion is permitted; arbitrary scripts or edits remain mismatches.
"""
from html.parser import HTMLParser
import json
import re

MARKER=b'<script>window.huggingface={variables:'


def matches_static_html(original,public):
    if public==original:return True,False
    extra_size=len(public)-len(original)
    if not 0<extra_size<=16384:return False,False
    head=re.search(br'<head\b[^>]*>',original,re.I)
    if head is None:
        # HTML permits an implicit head. HF prepends its metadata to such
        # files; still require an exact unchanged original byte suffix.
        at=0
    else:
        end=original.lower().find(b'</head>',head.end())
        if end<0:return False,False
        at=public.find(MARKER,head.end(),end+extra_size)
        if at<0 or at>end:return False,False
    if not public[at:].startswith(MARKER) or public[:at]!=original[:at] or public[at+extra_size:]!=original[at:]:return False,False
    try:extra=public[at:at+extra_size].decode('utf-8')
    except UnicodeDecodeError:return False,False
    class PlatformHead(HTMLParser):
        def __init__(self):super().__init__(convert_charrefs=True);self.script=False;self.scripts=0;self.metas=0;self.data=[]
        def handle_starttag(self,tag,attrs):
            attrs=dict(attrs)
            if tag=='script' and not attrs and not self.script and not self.scripts:
                self.script=True;self.scripts+=1;return
            if tag=='meta' and not self.script and set(attrs) in ({'property','content'},{'name','content'}):
                key=attrs.get('property') or attrs.get('name')
                if key not in ('og:title','og:description','og:image','twitter:card','twitter:image'):raise ValueError()
                if attrs.get('content') is None:raise ValueError()
                self.metas+=1;return
            raise ValueError()
        def handle_endtag(self,tag):
            if tag!='script' or not self.script:raise ValueError()
            self.script=False
        def handle_data(self,data):
            if self.script:self.data.append(data)
            elif data.strip():raise ValueError()
        def handle_comment(self,data):raise ValueError()
        def handle_decl(self,decl):raise ValueError()
        def handle_pi(self,data):raise ValueError()
    try:
        parsed=PlatformHead();parsed.feed(extra);parsed.close()
        script=''.join(parsed.data)
        match=re.fullmatch(r'window\.huggingface=\{variables:(\{.*\})\};',script,re.S)
        if parsed.script or parsed.scripts!=1 or parsed.metas>8 or not match:return False,False
        def invalid_constant(_):raise ValueError()
        variables=json.loads(match[1],parse_constant=invalid_constant)
        if not isinstance(variables,dict) or not all(re.fullmatch(r'[A-Z][A-Z0-9_]{0,127}',key) and isinstance(value,(str,int,float,bool,type(None))) for key,value in variables.items()):return False,False
    except (ValueError,TypeError):return False,False
    return True,True


def is_static_cdn_url(url):
    """HF Static's official CDN, never arbitrary redirects or URL credentials."""
    from urllib.parse import urlsplit
    try:
        value=urlsplit(url)
        return (value.scheme=='https' and value.hostname is not None
                and value.hostname.endswith('.cdn.hf.co')
                and value.username is None and value.password is None
                and value.port in (None,443))
    except ValueError:return False
