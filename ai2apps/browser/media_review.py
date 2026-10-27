"""Durable bounded image review primitives; no App/site/business routing."""
from __future__ import annotations
import base64,hashlib,io,json,time
from PIL import Image

MAX_IMAGES=50
MAX_BYTES=10_000_000

def image_key(url):
    from urllib.parse import urlsplit
    u=urlsplit(url)
    if u.scheme!='https' or u.username or u.password:raise ValueError('Expected observed HTTPS image')
    return hashlib.sha256((u.netloc.lower()+u.path+('?' + u.query if u.query else '')).encode()).hexdigest()

def prepare_image(encoded):
    data=base64.b64decode(encoded,validate=True)
    if len(data)>16_000_000:raise ValueError('Image capture too large')
    with Image.open(io.BytesIO(data)) as source:
        if source.width*source.height>32_000_000:raise ValueError('Image dimensions too large')
        picture=source.convert('RGB');picture.thumbnail((1280,1280))
        out=io.BytesIO();picture.save(out,format='JPEG',quality=80,optimize=True)
    raw=out.getvalue()
    return 'data:image/jpeg;base64,'+base64.b64encode(raw).decode(),len(raw)

class MediaLedger:
    def __init__(self,database,scope,task):
        self.database,self.scope,self.task=database,scope,task
        with database.transaction(write=True) as c:
            c.execute('CREATE TABLE IF NOT EXISTS browser_image_reviews (scope TEXT NOT NULL, image_key TEXT NOT NULL, result_json TEXT NOT NULL, updated_at REAL NOT NULL, PRIMARY KEY(scope,image_key))')
            c.execute('CREATE TABLE IF NOT EXISTS browser_image_attempts (task TEXT NOT NULL, image_key TEXT NOT NULL, size INTEGER NOT NULL, PRIMARY KEY(task,image_key))')
    def get(self,key):
        with self.database.transaction() as c:
            row=c.execute('SELECT result_json FROM browser_image_reviews WHERE scope=? AND image_key=?',(self.scope,key)).fetchone()
        return json.loads(row['result_json']) if row else None
    def usage(self):
        with self.database.transaction() as c:
            row=c.execute('SELECT count(*) n,coalesce(sum(size),0) bytes FROM browser_image_attempts WHERE task=?',(self.task,)).fetchone()
        return dict(row)
    def reserve(self,key,size):
        if type(size) is not int or size<=0:raise ValueError('Invalid image byte count')
        with self.database.transaction(write=True) as c:
            row=c.execute('SELECT count(*) n,coalesce(sum(size),0) bytes FROM browser_image_attempts WHERE task=?',(self.task,)).fetchone()
            if row['n']>=MAX_IMAGES or row['bytes']+size>MAX_BYTES:return False
            return c.execute('INSERT OR IGNORE INTO browser_image_attempts VALUES (?,?,?)',(self.task,key,size)).rowcount==1
    def save(self,key,result):
        with self.database.transaction(write=True) as c:
            c.execute('INSERT OR REPLACE INTO browser_image_reviews VALUES (?,?,?,?)',(self.scope,key,json.dumps(result,ensure_ascii=False),time.time()))
