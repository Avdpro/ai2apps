from pathlib import Path
import struct
import pytest
from PIL import Image
from ai2apps.extensions.development import DevelopmentPackageLoader
from ai2apps.studio.live_photo_pair import pair, boxes, pvt_bundle
from ai2apps.studio.frozen_time_pipeline import encode_frames

def test_package_mount_contract():
    root=Path(__file__).resolve().parents[2]
    loaded=DevelopmentPackageLoader(root)._load(root/'packages/ai2apps-frozen-time')
    assert loaded.package_id=='ai2apps.frozen-time'
    mini=loaded.manifest['mini_apps'][0]
    assert mini['id']=='ai2apps.imagine.frozen-time'
    assert mini['placements'][0]['studio']=='ai2apps.imagine-studio'
    assert mini['localizations']['zh-CN']['name']=='静止时间'
    from ai2apps.api.imagine_studio import MINI_APP_BY_ID
    assert mini['id'] not in MINI_APP_BY_ID

def test_live_photo_pair_metadata(tmp_path):
    import numpy as np
    frame=np.zeros((64,96,3),dtype='uint8')
    encode_frames(tmp_path/'video.mp4',(frame for _ in range(73)),96,64)
    Image.fromarray(frame).save(tmp_path/'poster.jpg')
    pair(tmp_path/'video.mp4',tmp_path,1.5,lambda:False)
    image=Image.open(tmp_path/'LivePhoto.jpg')
    note=image.getexif().get_ifd(34665)[37500]
    identifier=note[32:68]
    data=(tmp_path/'LivePhoto.mov').read_bytes()
    assert identifier in data and len(identifier)==36
    assert b'com.apple.quicktime.still-image-time' in data
    assert b'com.apple.quicktime.content.identifier' in data
    movie=next(value for kind,_,value in boxes(data) if kind==b'moov')
    tracks=[value for kind,_,value in boxes(movie[8:]) if kind==b'trak']
    assert len(tracks)==2
    offset=struct.unpack_from('>I',tracks[-1],tracks[-1].index(b'stco')+12)[0]
    assert data[offset:offset+9]==bytes.fromhex('000000090000000100')
    import zipfile
    with zipfile.ZipFile(tmp_path/'live-photo.zip') as archive:
        assert set(archive.namelist())=={'LivePhoto.jpg','LivePhoto.mov','README.txt'}
    import plistlib
    assert plistlib.loads((tmp_path/'LivePhoto.pvt'/'metadata.plist').read_bytes())=={'PFVideoComplementMetadataVersionKey':'1'}
    assert (tmp_path/'LivePhoto.pvt'/'LivePhoto.mov').read_bytes()==data
    with zipfile.ZipFile(tmp_path/'LivePhoto.pvt.zip') as archive:
        assert set(archive.namelist())=={'LivePhoto.pvt/LivePhoto.jpg','LivePhoto.pvt/LivePhoto.mov','LivePhoto.pvt/metadata.plist'}
    saved=pvt_bundle(tmp_path,tmp_path/'Saved.pvt')
    assert (saved/'LivePhoto.jpg').read_bytes()==(tmp_path/'LivePhoto.jpg').read_bytes()
    with pytest.raises(FileExistsError): pvt_bundle(tmp_path,saved)
    import av
    with av.open(str(tmp_path/'LivePhoto.mov')) as container:
        assert len(list(container.decode(video=0)))==73
    with pytest.raises(ValueError): pair(tmp_path/'video.mp4',tmp_path,10,lambda:False)
    with pytest.raises(RuntimeError): pair(tmp_path/'video.mp4',tmp_path,1.5,lambda:True)
