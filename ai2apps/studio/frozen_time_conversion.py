"""Local re-exports of retained Frozen Time results; no model invocation."""
import asyncio
import json
import shutil
import zipfile
from pathlib import Path

from .frozen_time import CameraKey, interactive_html
from .frozen_time_pipeline import encode_frames, export_video, mux_soundtrack, save_original_still
from .live_photo import export_live_photo

CACHE_FILES=('raw.mp4','input.png','conversion.json','legacy-playback.mp4')


async def convert_saved(source: Path, destination: Path, output: str, original_output: str, cancelled, soundtrack: Path | None = None):
    import av
    for name in CACHE_FILES:
        if (source/name).is_file():
            await asyncio.to_thread(shutil.copyfile,source/name,destination/name)
    raw=destination/'raw.mp4'
    if not raw.is_file():
        if original_output=='html' and output!='html':
            raise ValueError('This older HTML has no saved camera path. Its return movement cannot be reconstructed safely.')
        with av.open(str(source/'output.mp4')) as container:
            frames=[frame.to_ndarray(format='rgb24') for frame in container.decode(video=0)]
        if not 73<=len(frames)<=109:
            raise ValueError('Invalid legacy Frozen Time video')
        h,w=frames[0].shape[:2]
        await asyncio.to_thread(encode_frames,raw,frames[:73],w,h)
        if original_output!='html':
            shutil.copyfile(source/'output.mp4',destination/'legacy-playback.mp4')
        (destination/'conversion.json').write_text(json.dumps({'legacy':True}),encoding='utf-8')
    metadata=json.loads((destination/'conversion.json').read_text())
    video,poster=destination/'output.mp4',destination/'poster.jpg'
    if metadata.get('legacy'):
        if output!='html':
            playback=destination/'legacy-playback.mp4'
            if not playback.is_file():
                raise ValueError('No saved return movement for this older result')
            shutil.copyfile(playback,video)
        else:
            shutil.copyfile(raw,video)
        shutil.copyfile(source/'poster.jpg',poster)
        with av.open(str(video)) as container:
            count=sum(1 for _ in container.decode(video=0))
        still_time=(count-1)/24 if output!='html' else 36/24
    else:
        plan=tuple(CameraKey(**key) for key in metadata['plan'])
        still_time=await asyncio.to_thread(export_video,raw,video,poster,plan,output,cancelled,metadata.get('return_origin'),metadata.get('playback'),metadata.get('poster'))
    if output=='mp4':
        selected=soundtrack
        if selected is None and original_output=='mp4' and (source/'output.mp4').is_file():
            with av.open(str(source/'output.mp4')) as previous:
                if previous.streams.audio:
                    selected=source/'output.mp4'
        if selected is not None:
            await asyncio.to_thread(mux_soundtrack,video,selected,cancelled)
    if cancelled():
        return
    artifacts=[('output.mp4','video','video/mp4')]
    if output=='html':
        (destination/'output.html').write_text(interactive_html(video.read_bytes()),encoding='utf-8')
        artifacts.insert(0,('output.html','document','text/html'))
    elif output=='live-photo':
        if (destination/'input.png').is_file():
            await asyncio.to_thread(save_original_still,destination/'input.png',poster)
        elif (source/'live-photo.zip').is_file():
            # Use only the known still member, never extract paths from an archive.
            with zipfile.ZipFile(source/'live-photo.zip') as archive:
                member=archive.getinfo('LivePhoto.jpg')
                if member.file_size>64*1024*1024:
                    raise ValueError('Live Photo still exceeds export limit')
                poster.write_bytes(archive.read(member))
        await export_live_photo(video,destination,still_time,cancelled)
        artifacts[:0]=live_photo_artifacts()
    return artifacts


def live_photo_artifacts():
    return [('LivePhoto.pvt.zip','archive','application/zip'),('live-photo.zip','archive','application/zip'),
            ('LivePhoto.jpg','image','image/jpeg'),('LivePhoto.mov','video','video/quicktime')]
