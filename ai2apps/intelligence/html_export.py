"""Self-contained reading HTML. No live HTML, credentials or remote assets embedded."""
import asyncio
import base64
import hashlib
import html
import io
import re
from pathlib import Path
from datetime import datetime
from .models import public_url
from .transfer import MAX_BYTES

MAX_IMAGES = 1200
COMPACT_THRESHOLD = 12 * 1024 * 1024
AI2APPS_LOGO = (Path(__file__).resolve().parents[1] / "web/static/logo-dark.svg").read_text(encoding="utf-8")
CSS = """*{box-sizing:border-box}body{margin:auto;max-width:1100px;padding:24px;background:#e9edf3;color:#172033;font:17px/1.8 system-ui,sans-serif}header,article{background:white;padding:28px;border-radius:16px;margin:20px 0}h1,h2{line-height:1.4}h1{font-size:30px}.export-date{font-size:19px;font-weight:600;color:#4b5563;margin:20px 0 8px}.export-heading{display:flex;align-items:center;justify-content:space-between;gap:20px}.export-heading-text{min-width:0}.export-heading h1{margin:0 0 14px;overflow-wrap:anywhere}.export-heading .meta{margin:0}.export-logo{flex:0 0 72px;width:72px;line-height:0}.export-logo svg{display:block;width:100%;height:auto}h2{font-size:25px}nav{display:grid;gap:8px;max-height:40vh;overflow:auto;margin-top:14px}a,summary{-webkit-tap-highlight-color:transparent;touch-action:manipulation}summary:focus:not(:focus-visible){outline:none}summary:focus-visible{outline:2px solid #2563eb;outline-offset:4px}a{color:#345e99;overflow-wrap:anywhere}figure{margin:24px 0;text-align:center}img{width:100%;max-width:100%;max-height:850px;object-fit:contain;border-radius:8px}figcaption,.meta{font-size:14px;color:#637087}p{white-space:pre-wrap;overflow-wrap:anywhere}.summary{background:#f5f7fa;padding:16px;border-left:3px solid #72849d}.article-card>summary{cursor:pointer;list-style:none}.article-card>summary::-webkit-details-marker{display:none}.article-card>summary h2{margin:12px 0}.card-cover{display:block;width:100%;max-height:420px;object-fit:contain}.article-card:not([open])>summary h2{margin-bottom:0}.article-content{padding-top:12px}.gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}@media(max-width:600px){body{padding:10px}header,article{padding:18px}h1{font-size:25px}.export-logo{flex-basis:56px;width:56px}.export-heading{gap:14px}}@media print{body{background:white}article{break-before:page}}"""


CARD_CSS = """article{overflow:hidden}article:has(>.article-card>summary[data-pressed]){background:#f1f4f8}@media(hover:hover){article:has(>.article-card>summary:active){background:#f1f4f8}}.article-card>summary{position:relative;padding-top:0;-webkit-user-select:none;user-select:none}.article-card.no-cover>summary h2{margin-top:0;padding-left:52px;min-height:52px}.card-excerpt{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden;white-space:normal;color:#637087;font-size:16px;line-height:1.65;margin:10px 0 0}.article-card[open] .card-excerpt{display:none}.read-ribbon{position:absolute;top:-28px;left:-28px;width:96px;height:96px;overflow:hidden;pointer-events:none}.ribbon-band{position:absolute;top:10px;left:-52px;width:160px;transform:rotate(-45deg);background:#2563eb;color:#fff;text-align:center;font-size:14px;line-height:28px;font-weight:650}.read-ribbon .read{display:none}.article-card[open] .ribbon-band,.article-card[data-read] .ribbon-band{background:#374151}.article-card[open] .read-ribbon .read,.article-card[data-read] .read-ribbon .read{display:inline}.article-card[open] .read-ribbon .unread,.article-card[data-read] .read-ribbon .unread{display:none}@media(max-width:600px){.read-ribbon{top:-18px;left:-18px}}"""
CARD_SCRIPT = """(()=>{
  let press=null,releaseTimer=null;
  const clearPress=()=>{clearTimeout(releaseTimer);if(press)delete press.summary.dataset.pressed;press=null;};
  document.addEventListener('pointerdown',event=>{
    if(!event.isPrimary||event.button!==0)return;
    clearPress();
    const summary=event.target.closest('details.article-card>summary');
    if(!summary)return;
    press={summary,id:event.pointerId,x:event.clientX,y:event.clientY,at:performance.now()};
    summary.dataset.pressed='true';
  },{passive:true});
  window.addEventListener('pointermove',event=>{
    if(press&&event.pointerId===press.id&&Math.hypot(event.clientX-press.x,event.clientY-press.y)>8)clearPress();
  },{passive:true});
  window.addEventListener('pointerup',event=>{
    if(!press||event.pointerId!==press.id)return;
    // Brief taps stay visible without delaying native expansion.
    releaseTimer=setTimeout(clearPress,Math.max(0,120-(performance.now()-press.at)));
  },{passive:true});
  window.addEventListener('pointercancel',clearPress,{passive:true});
  window.addEventListener('blur',clearPress);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)clearPress();});
})();
document.querySelectorAll('details.article-card').forEach(card=>{
  let requested=false;
  card.querySelector('summary').addEventListener('click',()=>{requested=!card.open;});
  card.addEventListener('toggle',()=>{
    if(!card.open){requested=false;return;}
    card.dataset.read='true';
    if(!requested)return;
    requested=false;
    requestAnimationFrame(()=>{
      if(!card.open)return;
      const body=card.querySelector('.article-content');
      const distance=body.getBoundingClientRect().top-window.innerHeight*.5;
      if(distance>0)window.scrollBy({top:distance,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
    });
  });
});"""


def safe_link(url):
    try:
        public_url(url)
        return html.escape(url, quote=True)
    except (ValueError, TypeError): return ''


def image_candidates(url):
    """Unwrap documented public image transforms, never invent file names."""
    from urllib.parse import urlsplit, urlunsplit
    result=[url]
    try:
        p=urlsplit(url)
        public_url(url)
        if p.scheme!='https' or p.username or p.password:return result
        # WordPress image proxy: the upstream host/path is explicit in the URL.
        if re.fullmatch(r'i[0-3]\.wp\.com',p.hostname or '') and p.port in (None,443):
            upstream=p.path.lstrip('/')
            host,sep,path=upstream.partition('/')
            if sep and host and '%' not in host and ':' not in host and '@' not in host:
                candidate='https://'+host+'/'+path
                public_url(candidate)
                result.append(candidate)
                p=urlsplit(candidate)
        # Cloudflare image resizing keeps the original path after its options.
        match=re.fullmatch(r'/cdn-cgi/image/[^/]+(/.+)',p.path)
        if match:
            candidate=urlunsplit((p.scheme,p.netloc,match[1],p.query,''))
            public_url(candidate)
            result.append(candidate)
    except (ValueError,TypeError):pass
    return list(dict.fromkeys(result))[:3]


def image_failure(error):
    """Bounded diagnostics without exception text containing arbitrary secrets."""
    import urllib.error
    if isinstance(error.__cause__,urllib.error.HTTPError):
        status=error.__cause__.code
        return f'图片服务器返回 HTTP {status} / Image server returned HTTP {status}'
    message=str(error)
    status=re.search(r'HTTP (\d{3})',message)
    if status:return '图片服务器返回 HTTP '+status[1]
    if 'limit' in message.lower() or 'exceed' in message.lower():return '图片超过导出限制 / Image exceeds export limits'
    if 'timeout' in message.lower() or 'timed out' in message.lower() or isinstance(error,TimeoutError):return '图片读取超时 / Image request timed out'
    return '图片无法读取或解码 / Image could not be read or decoded'


def image_bytes(store, owner, url, quality):
    from PIL import Image, ImageOps
    if url.startswith('/v1/platform/intelligence/imports/'):
        from .manual_import import asset_path
        match = re.fullmatch(r'/v1/platform/intelligence/imports/([0-9a-f]{64})/[^/]+', url)
        if not match: raise ValueError('Invalid local image reference')
        path = asset_path(store, owner, match[1])
        if path.stat().st_size > 8 * 1024 * 1024: raise ValueError('Image exceeds 8 MiB')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != match[1]: raise ValueError('Local image hash mismatch')
    else:
        from ai2apps.research.provider import SafeHttpClient
        public_url(url)
        class Client(SafeHttpClient):
            ALLOWED_TYPES = frozenset({'image/jpeg','image/png','image/webp','image/gif','image/avif'})
        response = Client(timeout_seconds=10, max_bytes=8*1024*1024, max_redirects=3).get(url)
        if response.truncated: raise ValueError('Image exceeds 8 MiB')
        raw = response.body
    with Image.open(io.BytesIO(raw)) as image:
        if image.width * image.height > 40_000_000: raise ValueError('Image pixel limit exceeded')
        mime = Image.MIME.get(image.format)
        if mime not in ('image/jpeg','image/png','image/webp','image/gif','image/avif'): raise ValueError('Unsupported image format')
        if quality == 'original':
            image.verify()
            return raw, mime
        image = ImageOps.exif_transpose(image)
        edge = 1600
        encoding_quality = 82
        image.thumbnail((edge,edge))
        out = io.BytesIO()
        if image.mode in ('RGBA','LA') or 'transparency' in image.info:
            image.convert('RGBA').save(out,format='WEBP',quality=encoding_quality)
            return out.getvalue(),'image/webp'
        image.convert('RGB').save(out,format='JPEG',quality=encoding_quality,optimize=False)
        return out.getvalue(),'image/jpeg'


def compact_image(encoded):
    """Re-encode already validated local bytes; never fetch an image twice."""
    from PIL import Image
    raw=base64.b64decode(encoded.split(',',1)[1])
    with Image.open(io.BytesIO(raw)) as image:
        image.thumbnail((720,720))
        out=io.BytesIO()
        image.convert('RGBA' if image.mode in ('RGBA','LA') or 'transparency' in image.info else 'RGB').save(
            out,format='WEBP',quality=62,method=4)
    value='data:image/webp;base64,'+base64.b64encode(out.getvalue()).decode('ascii')
    return value if len(value)<len(encoded) else encoded


async def build_html(store, owner, selected, *, quality='reading', scope=None, report=None, loader=None, include_toc=True, author_name=None, share_cover=None):
    if quality not in ('reading','original'): raise ValueError('Invalid image quality')
    loader = loader or image_bytes
    channels = selected['channels']
    if len(channels) != 1: raise ValueError('HTML export requires exactly one channel')
    channel = channels[0]['data']
    articles = [{**r['data'], 'id':r['id']} for r in selected['articles']]
    articles.sort(key=lambda a:a.get('created_at',''),reverse=True)
    if len(articles)>5000 or sum(len(a.get('body','')) for a in articles)>20_000_000: raise ValueError('HTML content exceeds limit; select a smaller time range')
    urls = {}
    for a in articles:
        for item in [a.get('cover_image') or {}, *a.get('images',[])]:
            if item.get('url'): urls.setdefault(item['url'],hashlib.sha256(item['url'].encode()).hexdigest())
    if share_cover:urls.setdefault(share_cover,hashlib.sha256(share_cover.encode()).hexdigest())
    if len(urls)>MAX_IMAGES: raise ValueError('Too many images; select a smaller time range')
    data, failures, done, size, recovered = {}, [], 0, 0, 0
    semaphore = asyncio.Semaphore(4)
    async def load(url, key):
        nonlocal done, size, recovered
        async with semaphore:
            try:
                candidates=image_candidates(url)
                for candidate in candidates:
                    try:
                        raw, mime = await asyncio.to_thread(loader, store, owner, candidate, quality)
                        break
                    except asyncio.CancelledError:raise
                    except Exception:
                        if candidate==candidates[-1]:raise
                encoded = 'data:'+mime+';base64,'+base64.b64encode(raw).decode('ascii')
                if mime not in ('image/jpeg','image/png','image/webp','image/gif','image/avif'): raise ValueError('Unsupported image format')
                key = hashlib.sha256(raw).hexdigest()
                if key not in data:
                    if size+len(encoded)>MAX_BYTES-24*1024*1024: raise ValueError('HTML image budget exceeded')
                    data[key] = encoded
                    size += len(encoded)
                urls[url] = key
                if candidate!=url:recovered+=1
            except asyncio.CancelledError: raise
            except Exception as error:
                failures.append({'url':url,'reason':image_failure(error)})
            done += 1
            if report: report({'images_done':done,'images_total':len(urls),'images_failed':len(failures),'articles':len(articles)})
    tasks = [asyncio.create_task(load(url, key)) for url,key in urls.items()]
    try:
        async with asyncio.timeout(600): await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            if not task.done(): task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
    # Social cover is independent of article rendering and compression.
    cover_key=urls.get(share_cover) if share_cover else None
    if share_cover and cover_key not in data:raise ValueError('Selected sharing cover could not be read')
    if not cover_key:
        cover_key=next((urls.get(i.get('url')) for a in articles for i in [a.get('cover_image') or {}, *a.get('images',[])] if urls.get(i.get('url')) in data),None)
    if cover_key:
        share_image=data[cover_key]
    else:
        logo=(Path(__file__).resolve().parents[1]/'web/static/img/ai2apps-share-logo.png').read_bytes()
        share_image='data:image/png;base64,'+base64.b64encode(logo).decode('ascii')
    from PIL import Image
    with Image.open(io.BytesIO(base64.b64decode(share_image.split(',',1)[1]))) as image:
        image.thumbnail((600,600));image=image.convert('RGBA')
        background=Image.new('RGB',image.size,'white');background.paste(image,mask=image.getchannel('A'))
        out=io.BytesIO();background.save(out,format='JPEG',quality=82,optimize=True)
    share_image='data:image/jpeg;base64,'+base64.b64encode(out.getvalue()).decode('ascii')
    description=' · '.join([a['title'] for a in articles[:3]]) or str(channel.get('interests') or channel['name'])
    description=re.sub(r'\s+',' ',description).strip()[:180]
    social=''.join('<meta '+attribute+'="'+name+'" content="'+html.escape(str(value),quote=True)+'">' for attribute,name,value in [
        ('name','description',description),('property','og:type','website'),('property','og:site_name','AI2Apps'),
        ('property','og:title',channel['name']),('property','og:description',description),('property','og:image',share_image),
        ('property','og:image:type','image/jpeg'),('property','og:image:width',background.width),('property','og:image:height',background.height),
        ('name','twitter:card','summary_large_image'),('name','twitter:title',channel['name']),
        ('name','twitter:description',description),('name','twitter:image',share_image)])
    def render():
        esc = html.escape
        chinese=str(channel.get('output_language','zh')).startswith('zh')
        def figure(item):
            url = item.get('url','');key = urls.get(url)
            caption = esc(str(item.get('alt','')))
            if key in data:
                return f'<figure><img src="{data[key]}" alt="{caption}"><figcaption>{caption}</figcaption></figure>'
            return ''
        content, navigation = [], []
        for index,a in enumerate(articles):
            aid=f'article-{index}'
            navigation.append(f'<a href="#{aid}">{esc(a["title"])}</a>')
            section = str(a.get('section_id') or '')
            value=f'<article id="{aid}" data-section="{esc(section,quote=True)}">'
            cover=next((i for i in [a.get('cover_image') or {}, *a.get('images',[])] if urls.get(i.get('url')) in data), a.get('cover_image') or {})
            if not include_toc:
                has_cover=urls.get(cover.get('url')) in data
                value+='<details class="article-card'+(' has-cover' if has_cover else ' no-cover')+'"><summary><span class="read-ribbon"><span class="ribbon-band"><span class="unread">'+('未读' if chinese else 'Unread')+'</span><span class="read">'+('已读' if chinese else 'Read')+'</span></span></span>'
                if urls.get(cover.get('url')) in data:
                    value+=f'<img class="card-cover" src="{data[urls[cover["url"]]]}" alt="{esc(str(cover.get("alt", "")))}">'
                value+=f'<h2>{esc(a["title"])}</h2>'
                if not has_cover:
                    excerpt=str(a.get('summary') or a.get('body') or '').strip()
                    if excerpt:value+='<p class="card-excerpt">'+esc(excerpt)+'</p>'
                value+='</summary><div class="article-content">'
            else:
                value+=f'<h2>{esc(a["title"])}</h2>'
            value+=f'<p class="meta">{esc(a.get("updated_at",a.get("created_at","")))}</p>'
            value+=f'<p class="summary">{esc(a.get("summary",""))}</p>'
            shown=set();images={i.get('id'):i for i in a.get('images',[]) if i.get('id')}
            if cover.get('url'):
                if include_toc: value+=figure(cover)
                shown.add(cover['url'])
            from .article_content import validate_content, paragraphs
            try:
                validate_content(a)
                blocks=a.get('content_blocks') or [{'type':'paragraph','text':p} for p in paragraphs(a.get('body',''))]
            except (ValueError,TypeError,KeyError):
                blocks=[{'type':'paragraph','text':p} for p in paragraphs(a.get('body',''))]
            for block in blocks:
                if block.get('type')=='paragraph':
                    value+='<p>'+esc(block['text'])+'</p>'
                elif block.get('type')=='image' and block.get('image_id') in images:
                    item=images[block['image_id']];value+=figure(item);shown.add(item['url'])
            extras=[i for i in a.get('images',[]) if i.get('url') and i['url'] not in shown and urls.get(i['url']) in data]
            if extras:value+='<details><summary>更多文章图片 / More images</summary><div class="gallery">'+''.join(figure(i) for i in extras)+'</div></details>'
            value+='<section><h3>来源 / Sources</h3><ol>'
            for ref in a.get('sources',[]):
                link=safe_link(ref.get('url',''));title=esc(str(ref.get('title') or ref.get('source_name') or ref.get('url','')))
                value+='<li>'+(f'<a href="{link}" target="_blank" rel="noopener noreferrer">{title}</a>' if link else title)+'</li>'
            value+='</ol></section>'
            value+='<a href="#top">返回目录 / Contents ↑</a>' if include_toc else '</div></details>'
            value+='</article>';content.append(value)
        # Images use literal data URLs so script-disabled mobile file previews work.
        script_hash=base64.b64encode(hashlib.sha256(CARD_SCRIPT.encode()).digest()).decode()
        script_policy="'sha256-"+script_hash+"'" if not include_toc else "'none'"
        csp="default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src "+script_policy+"; base-uri 'none'; form-action 'none'"
        export_date=datetime.now().astimezone().date().isoformat()
        toc='<nav>'+''.join(navigation)+'</nav>' if include_toc else ''
        chinese=str(channel.get('output_language','zh')).startswith('zh')
        name=str(author_name or '').strip()[:120]
        attribution=('由 '+name+' 的 AI2Apps 总结' if chinese else 'Summarized by '+name+'’s AI2Apps')
        if not name:attribution='由 AI2Apps 总结' if chinese else 'Summarized by AI2Apps'
        credit='<p class="meta"><a href="https://ai2apps.com/" target="_blank" rel="noopener noreferrer">'+esc(attribution)+'</a></p>'
        heading='<div class="export-heading"><div class="export-heading-text"><h1>'+esc(channel['name'])+'</h1>'+credit+'</div><a class="export-logo" href="https://ai2apps.com/" target="_blank" rel="noopener noreferrer" aria-label="AI2Apps">'+AI2APPS_LOGO+'</a></div>'
        document='<!doctype html><html lang="'+('zh' if str(channel.get('output_language','zh')).startswith('zh') else 'en')+'"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="'+esc(csp,quote=True)+'"><title>'+esc(channel['name'])+'</title>'+social+'<style>'+CSS+('' if include_toc else CARD_CSS)+'</style></head><body><header id="top">'+heading+'<p class="export-date">'+esc(export_date)+'</p><p class="meta">'+str(len(articles))+' 篇 / articles · '+str(len(data))+' images</p>'+toc+'</header>'+''.join(content)+('' if include_toc else '<script>'+CARD_SCRIPT+'</script>')+'</body></html>'
        payload=document.encode('utf-8')
        return payload

    payload=render()
    initial_size=len(payload)
    compressed=0
    if quality=='reading' and initial_size>COMPACT_THRESHOLD:
        # Protect the actual displayed cover, including fallback/shared images.
        covers=set()
        for article in articles:
            key=next((urls.get(i.get('url')) for i in [article.get('cover_image') or {}, *article.get('images',[])] if urls.get(i.get('url')) in data),None)
            if key:covers.add(key)
        for key in data.keys()-covers:
            original=data[key]
            data[key]=await asyncio.to_thread(compact_image,original)
            if data[key]!=original:compressed+=1
        payload=render()
    if len(payload)>MAX_BYTES: raise ValueError('HTML exceeds 128 MiB; select a smaller time range')
    return payload,{'articles':len(articles),'images':len(data),'images_failed':len(failures),'images_recovered':recovered,'missing_images':failures,'include_toc':bool(include_toc),'image_profile':quality,'images_compacted':compressed,'initial_size':initial_size}
