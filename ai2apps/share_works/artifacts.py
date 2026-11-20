"""Private, immutable static snapshots. No network access while preparing."""
import base64
import hashlib
import io
import json
import re
import stat
import zipfile
from pathlib import PurePosixPath
from PIL import Image
from .cli import PublishError

MAX_INPUT=128*1024*1024
MAX_EXPANDED=256*1024*1024
MAX_FILES=2000
ALLOWED={'.html','.css','.js','.json','.png','.jpg','.jpeg','.webp','.gif','.ico','.woff','.woff2','.ttf','.txt','.mp3','.mp4','.webm','.pdf'}
DATA_IMAGE=re.compile(r'data:image/(png|jpeg|webp|gif);base64,([a-zA-Z0-9+/=\r\n]+)',re.I)


def normalize(data, filename, nonce, *, public_base=None):
    if not data or len(data)>MAX_INPUT:raise PublishError('artifact_size_limit')
    files={}
    if filename.lower().endswith('.zip'):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                total=0
                for item in archive.infolist():
                    path=PurePosixPath(item.filename)
                    if (not item.filename or '\\' in item.filename or path.is_absolute()
                        or '..' in path.parts or ':' in item.filename or item.flag_bits&1
                        or stat.S_ISLNK(item.external_attr>>16)):
                        raise PublishError('unsafe_zip')
                    if item.is_dir(): continue
                    if (path.suffix.lower() not in ALLOWED or any(p.startswith('.') for p in path.parts)
                        or path.name.lower() in ('_worker.js','_headers','_redirects')
                        or any(p.lower() in ('functions','node_modules') for p in path.parts)):
                        raise PublishError('unsupported_site_file')
                    name=str(path)
                    if name in files or len(files)>=MAX_FILES:raise PublishError('unsafe_zip')
                    total+=item.file_size
                    if total>MAX_EXPANDED:raise PublishError('expanded_size_limit')
                    files[name]=archive.read(item)
        except (zipfile.BadZipFile,RuntimeError,NotImplementedError) as e:raise PublishError('unsafe_zip') from e
    elif filename.lower().endswith(('.html','.htm')):files['index.html']=data
    else:raise PublishError('html_or_zip_required')
    if 'index.html' not in files:raise PublishError('missing_index_html')
    try:text=files['index.html'].decode('utf-8')
    except UnicodeDecodeError:raise PublishError('utf8_required')
    def validate_image(match):
        try:
            raw=base64.b64decode(re.sub(r'\s','',match[2]),validate=True)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in ('PNG','JPEG','WEBP','GIF') or image.width*image.height>40_000_000:raise ValueError()
                image.verify()
        except Exception as e:raise PublishError('invalid_embedded_image') from e
    # Validate supported embedded images without changing their data URI or
    # generating any resource files. Publication preserves every source byte.
    for match in DATA_IMAGE.finditer(text):validate_image(match)
    # Network-dependent images are not a complete offline snapshot. Never fetch
    # arbitrary URLs or silently omit them as part of publishing.
    from html.parser import HTMLParser
    class Check(HTMLParser):
        def handle_starttag(self, tag, attrs):
            attrs=dict(attrs)
            if tag in ('img','script','iframe','video','audio','source','link'):
                for field in ('src','href','poster','srcset'):
                    value=attrs.get(field,'').strip()
                    if not value:continue
                    if field=='srcset':raise PublishError('unsupported_srcset')
                    if value.startswith(('http:','https:','//','file:','/','blob:')):raise PublishError('external_resource')
                    if value.startswith('data:'):
                        if ((tag=='img' and field=='src') or (tag=='video' and field=='poster')) and DATA_IMAGE.fullmatch(value):
                            continue
                        raise PublishError('unsupported_embedded_resource')
                    from urllib.parse import unquote
                    target=PurePosixPath(unquote(value).split('#')[0].split('?')[0])
                    if '..' in target.parts or str(target) not in files:raise PublishError('missing_resource')
    from urllib.parse import unquote
    def local_reference(value):
        value=unquote(value.strip())
        if not value or value.startswith('#'):return
        if value.startswith(('http:','https:','//','file:','/','blob:','data:')):raise PublishError('external_resource')
        name=PurePosixPath(value.split('#')[0].split('?')[0])
        if '..' in name.parts or str(name) not in files:raise PublishError('missing_resource')
    Check().feed(text)
    for name,body in list(files.items()):
        if name.lower().endswith('.html') and name!='index.html':
            # Relative nested paths need rewriting before publication; refuse
            # rather than silently publishing a broken entry.
            if '/' in name:raise PublishError('nested_html_not_supported')
            Check().feed(body.decode('utf-8'))
        if name.lower().endswith('.css'):
            css=body.decode('utf-8')
            if re.search(r'@import',css,re.I):raise PublishError('external_resource')
            for value in re.findall(r'url\(\s*["\']?([^"\')]+)',css,re.I):
                value=value.strip()
                if value.startswith('data:image/'):continue
                prefix=str(PurePosixPath(name).parent)
                local_reference(value if prefix=='.' else prefix+'/'+value)
    if public_base:
        # Only social image metadata is materialized; ordinary page images and
        # all non-metadata HTML bytes stay unchanged in the reviewed snapshot.
        def social_image(match):
            from html import unescape,escape
            tag=match[0]
            props=dict((key.lower(),unescape(value)) for key,quote,value in re.findall(r"([\w:-]+)\s*=\s*([\"'])(.*?)\2",tag,re.S))
            if (props.get('property') or props.get('name')) not in ('og:image','twitter:image'):return tag
            value=props.get('content','')
            encoded=DATA_IMAGE.fullmatch(value)
            if not encoded:return tag
            raw=base64.b64decode(re.sub(r'\s','',encoded[2]),validate=True)
            with Image.open(io.BytesIO(raw)) as image:
                image.thumbnail((600,600));image=image.convert('RGBA')
                background=Image.new('RGB',image.size,'white');background.paste(image,mask=image.getchannel('A'))
                out=io.BytesIO();background.save(out,format='JPEG',quality=82,optimize=True);body=out.getvalue()
            name='share-cover-'+hashlib.sha256(body).hexdigest()[:24]+'.jpg'
            if name in files and files[name]!=body:raise PublishError('share_cover_conflict')
            files[name]=body
            address=public_base.rstrip('/')+'/shares/'+nonce+'/'+name
            return re.sub(r"(\bcontent\s*=\s*)([\"'])(.*?)\2",lambda field:field[1]+field[2]+escape(address,quote=True)+field[2],tag,flags=re.I|re.S)
        text=re.sub(r'<meta\b[^>]*>',social_image,text,flags=re.I)
        files['index.html']=text.encode('utf-8')
    # Apart from optional social metadata above, preserve original HTML bytes.
    # The immutable snapshot directory already carries its nonce.
    if len(files)>MAX_FILES or sum(map(len,files.values()))>MAX_EXPANDED:raise PublishError('expanded_size_limit')
    manifest={name:hashlib.sha256(value).hexdigest() for name,value in sorted(files.items())}
    digest=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
    return files,manifest,digest


def preview(text):
    # The API additionally applies sandbox CSP: the preview is never an App.
    return text
