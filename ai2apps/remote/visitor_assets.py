"""Immutable, installation-scoped copies of explicitly selected public-space media."""
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

LIMITS = {'image':20*1024*1024, 'video':100*1024*1024, 'html':10*1024*1024}
HTML_CSP = "sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"

def content_gateway_ready():
    if 'AI2APPS_VISITOR_CONTENT_GATEWAY_READY' in os.environ:
        return os.environ['AI2APPS_VISITOR_CONTENT_GATEWAY_READY']=='1'
    descriptor=os.environ.get('AI2APPS_RUN_DESCRIPTOR_PATH','')
    if not descriptor or not Path(descriptor).is_absolute(): return False
    try:
        return json.loads((Path(descriptor).parent.parent/'config'/'visitor-content-gateway.json').read_text())=={'enabled':True,'protocol':'visitor-content-v1'}
    except (OSError,ValueError): return False

class VisitorAssets:
    def __init__(self, database, installation):
        scope=hashlib.sha256(installation.encode()).hexdigest()
        self.root=Path(database.path).parent/'visitor-space-assets'/scope

    def put(self, kind, data):
        if kind not in LIMITS or not data or len(data)>LIMITS[kind]:
            raise ValueError('素材为空或超过大小限制（图片 20 MB / 视频 100 MB / HTML 10 MB）')
        meta={'kind':kind}
        if kind=='image':
            from PIL import Image, ImageOps
            try:
                with Image.open(io.BytesIO(data)) as im:
                    if im.width*im.height>40_000_000: raise ValueError('图片像素过大')
                    im=ImageOps.exif_transpose(im).convert('RGBA');im.thumbnail((2560,2560))
                    buf=io.BytesIO();im.save(buf,format='PNG');data=buf.getvalue()
                    meta.update(mime='image/png',width=im.width,height=im.height)
            except (OSError, Image.DecompressionBombError) as exc:
                raise ValueError('无法读取图片') from exc
        elif kind=='html':
            try: data.decode('utf-8')
            except UnicodeDecodeError: raise ValueError('HTML 必须使用 UTF-8 编码') from None
            meta['mime']='text/html; charset=utf-8'
        else:
            if not (data[4:8]==b'ftyp' or data[:4]==b'\x1a\x45\xdf\xa3'):
                raise ValueError('仅支持独立 MP4/WebM 文件')
            probe=shutil.which('ffprobe')
            if not probe: raise ValueError('视频校验组件 ffprobe 不可用，暂不能导入视频')
            with tempfile.NamedTemporaryFile(suffix='.media') as f:
                f.write(data);f.flush()
                try:
                    result=subprocess.run([probe,'-v','error','-protocol_whitelist','file','-show_format','-show_streams','-of','json',f.name],capture_output=True,timeout=20,check=True)
                    info=json.loads(result.stdout);video=next(s for s in info['streams'] if s['codec_type']=='video')
                    duration=float(info['format']['duration']);w=int(video['width']);h=int(video['height'])
                    formats=info['format']['format_name'].split(',')
                    mime='video/mp4' if 'mp4' in formats else 'video/webm' if 'webm' in formats else None
                    if not mime or not 0<duration<=300 or min(w,h)>1080 or max(w,h)>1920 or min(w,h)<=0: raise ValueError()
                    if video['codec_name'] not in {'h264','vp8','vp9','av1'}: raise ValueError()
                    meta.update(mime=mime,width=w,height=h,duration=duration)
                except (ValueError,KeyError,StopIteration,subprocess.SubprocessError):
                    raise ValueError('视频须为 MP4/WebM，最长 5 分钟，最高 1080p，使用 H.264/VP8/VP9/AV1') from None
        asset=hashlib.sha256(kind.encode()+b'\0'+data).hexdigest()
        meta.update(id=asset,size=len(data),sha256=hashlib.sha256(data).hexdigest())
        self.root.mkdir(parents=True,exist_ok=True)
        for name,content in [(asset,data),(asset+'.json',json.dumps(meta).encode())]:
            with tempfile.NamedTemporaryFile(dir=self.root,delete=False) as f:
                f.write(content);temp=f.name
            os.replace(temp,self.root/name)
        return meta

    def get(self, asset):
        if not isinstance(asset,str) or not re.fullmatch(r'[a-f0-9]{64}',asset): raise ValueError('素材不存在')
        try:
            meta=json.loads((self.root/(asset+'.json')).read_text());path=self.root/asset
            if path.stat().st_size!=meta['size']: raise ValueError('素材已损坏')
            return meta,path
        except (OSError,KeyError,json.JSONDecodeError): raise ValueError('素材不存在，请重新选择') from None

def published_asset_ids(document):
    from .visitor_space import walk_cards
    return {c[k] for c in walk_cards((document or {}).get('cards',[])) for k in ('assetId','coverId') if c.get(k)}
