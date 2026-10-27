"""Full-resolution adjustment exports independent of the browser canvas."""
import hashlib, io, math, os, tempfile
from pathlib import Path
import numpy as np
from PIL import Image,ImageOps,ImageFilter
from pydantic import BaseModel,ConfigDict,Field,field_validator

CONTROLS=('exposure','brilliance','highlights','shadows','contrast','brightness','saturation','vibrance','blackPoint','colorBalance','warmth','tint','sharpness','definition','noiseReduction','vignette')
class AdjustState(BaseModel):
    model_config=ConfigDict(extra='forbid')
    values:dict[str,float]=Field(default_factory=dict)
    rotation:int=0
    flipX:bool=False
    flipY:bool=False
    cropRatio:str='original'
    @field_validator('values')
    @classmethod
    def bounded(cls,v):
        if any(k not in CONTROLS or not math.isfinite(n) or not -100<=n<=100 for k,n in v.items()):raise ValueError('Invalid adjustment')
        return v
    @field_validator('rotation')
    @classmethod
    def quarter_turn(cls,v):
        if v%90 or abs(v)>360:raise ValueError('Invalid rotation')
        return v
    @field_validator('cropRatio')
    @classmethod
    def ratio(cls,v):
        if v!='original':
            parts=v.split(':')
            if len(parts)!=2 or any(not x.isdigit() or not 1<=int(x)<=10000 for x in parts):raise ValueError('Invalid crop')
        return v


def render(content,state,media_type='image/png'):
    state=AdjustState.model_validate(state).model_dump();v=state['values']
    with Image.open(io.BytesIO(content)) as source:
        if source.width*source.height>64_000_000:raise ValueError('Image exceeds 64 megapixels')
        image=ImageOps.exif_transpose(source).convert('RGBA')
    w,h=image.size;ratio=state['cropRatio']
    if ratio!='original':
        a,b=map(int,ratio.split(':'));r=a/b
        if w/h>r:
            nw=max(1,math.floor(h*r+.5));x=math.floor((w-nw)/2+.5);image=image.crop((x,0,x+nw,h))
        else:
            nh=max(1,math.floor(w/r+.5));y=math.floor((h-nh)/2+.5);image=image.crop((0,y,w,y+nh))
    blur=max(0,v.get('noiseReduction',0))/100*1.8
    if blur:image=image.filter(ImageFilter.GaussianBlur(blur))
    if state['flipX']:image=ImageOps.mirror(image)
    if state['flipY']:image=ImageOps.flip(image)
    image=image.rotate(-state['rotation'],expand=True)
    a=np.array(image);rgb=a[:,:,:3].astype(np.float64)*2**(v.get('exposure',0)/50)
    lum=rgb@np.array([.2126,.7152,.0722]);mid=1-np.abs(lum-128)/128
    tonal=v.get('highlights',0)/100*np.maximum(0,(lum-128)/127)*72+v.get('shadows',0)/100*np.maximum(0,(128-lum)/128)*72
    rgb+=(tonal+mid*v.get('brilliance',0)/100*54+v.get('brightness',0)*1.1)[:,:,None]
    rgb=(rgb-128)*(1+max(-.95,v.get('contrast',0)/100)+v.get('definition',0)/100*mid*.35)[:,:,None]+128
    lum=rgb@np.array([.2126,.7152,.0722]);sat=rgb.max(axis=2)-rgb.min(axis=2)
    factor=(1+v.get('saturation',0)/100)*(1+v.get('vibrance',0)/100*(1-np.minimum(1,sat/128)))
    rgb=lum[:,:,None]+(rgb-lum[:,:,None])*factor[:,:,None]
    balance=v.get('colorBalance',0)*.45;warmth=v.get('warmth',0)*.55;tint=v.get('tint',0)*.35
    rgb+=np.array([balance+warmth+tint*.35,-tint,-balance-warmth+tint*.35])
    black=max(0,v.get('blackPoint',0))*1.05
    if black:rgb=(rgb-black)*(255/max(1,255-black))
    height,width=rgb.shape[:2];vig=v.get('vignette',0)/100
    if vig:
        y,x=np.indices((height,width));distance=np.sqrt((x-width/2)**2+(y-height/2)**2)/(math.sqrt(width*width+height*height)/2)
        rgb*=(1-vig*np.maximum(0,(distance-.35)/.65)**2*.8)[:,:,None]
    rgb=np.rint(np.clip(rgb,0,255));strength=max(0,v.get('sharpness',0))/100
    if strength and width>2 and height>2:
        original=rgb.copy();rgb[1:-1,1:-1]=np.rint(np.clip(original[1:-1,1:-1]+(4*original[1:-1,1:-1]-original[1:-1,:-2]-original[1:-1,2:]-original[:-2,1:-1]-original[2:,1:-1])*strength*.35,0,255))
    a[:,:,:3]=rgb.astype(np.uint8);image=Image.fromarray(a)
    fmt={'image/png':'PNG','image/jpeg':'JPEG','image/webp':'WEBP'}[media_type]
    if fmt=='JPEG':
        bg=Image.new('RGB',image.size,'black');bg.paste(image,mask=image.getchannel('A'));image=bg
    out=io.BytesIO();image.save(out,format=fmt,**({'quality':92} if fmt!='PNG' else {}));return out.getvalue()


def freeze_target(runtime,principal,target):
    from ai2apps.api.imagine_studio import BatchOutputTarget
    selected=BatchOutputTarget.model_validate(target);v=selected.model_dump(by_alias=True)
    if selected.kind=='local':
        if principal.authentication_type=='owner_home_lease':raise ValueError('Mobile cannot write Desktop file paths')
        source=Path(selected.source_path or '').expanduser()
        if not source.is_absolute() or not source.is_file():raise ValueError('Source file unavailable')
        source=source.resolve()
        if selected.overwrite:destination=source
        else:
            root=Path(selected.output_root or '').expanduser();relative=Path(selected.relative_path or selected.name)
            if not root.is_absolute() or not root.is_dir() or relative.is_absolute() or '..' in relative.parts:raise ValueError('Invalid output directory')
            destination=(root.resolve()/relative).resolve();destination.relative_to(root.resolve())
            if destination.exists():raise ValueError('Output already exists')
        suffixes={'image/png':{'.png'},'image/jpeg':{'.jpg','.jpeg'},'image/webp':{'.webp'}}
        if destination.suffix.lower() not in suffixes[selected.media_type]:raise ValueError('Output format does not match extension')
        v.update(destination=str(destination),sourceHash=hashlib.sha256(source.read_bytes()).hexdigest() if selected.overwrite else None)
    else:
        from ai2apps.gallery import GalleryRepository
        gallery=GalleryRepository(runtime.database,runtime.config.paths.artifacts_path/'gallery',getattr(runtime,'events',None))
        if selected.overwrite:
            _,path=gallery.asset_path(principal.actor_user_id,selected.asset_id);v['sourceHash']=hashlib.sha256(path.read_bytes()).hexdigest()
    return v


def publish_target(runtime,principal,target,data,key):
    if target['kind']=='local':
        destination=Path(target['destination'])
        if destination.resolve()!=destination:raise ValueError('Output path changed')
        if destination.exists():
            digest=hashlib.sha256(destination.read_bytes()).hexdigest()
            if digest==hashlib.sha256(data).hexdigest():return
            if not target['overwrite'] or digest!=target['sourceHash']:raise ValueError('Destination changed after submission')
        elif target['overwrite']:raise ValueError('Source was removed')
        destination.parent.mkdir(parents=True,exist_ok=True)
        fd,name=tempfile.mkstemp(prefix='.ai2apps-adjust-',dir=destination.parent)
        try:
            with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
            if target["overwrite"]:
                os.replace(name,destination)
            else:
                os.link(name,destination)  # Atomic create; never replace a newly created file.
        finally:Path(name).unlink(missing_ok=True)
    else:
        from ai2apps.gallery import GalleryRepository
        gallery=GalleryRepository(runtime.database,runtime.config.paths.artifacts_path/'gallery',getattr(runtime,'events',None))
        if target['overwrite']:
            _,path=gallery.asset_path(principal.actor_user_id,target['assetId']);digest=hashlib.sha256(path.read_bytes()).hexdigest()
            if digest==hashlib.sha256(data).hexdigest():return
            if digest!=target['sourceHash']:raise ValueError('Gallery source changed after submission')
            gallery.replace_asset_stream(principal.actor_user_id,target['assetId'],io.BytesIO(data),media_type=target['mediaType'],source_app_id='ai2apps.imagine-studio',metadata={'adjustment':'batch','taskId':key},max_bytes=64*1024*1024)
        else:gallery.import_stream(principal.actor_user_id,io.BytesIO(data),name=target['name'],media_type=target['mediaType'],collection_id=target.get('collectionId'),source_app_id='ai2apps.imagine-studio',source_ref='imagine-adjust:'+key,metadata={'adjustment':'batch'},max_bytes=64*1024*1024)
