"""JPEG/QuickTime paired resources; no extra Runtime or native executable."""
import base64
import struct
import uuid
import zipfile
import plistlib
import shutil


def pvt_bundle(directory, destination):
    """Create a macOS Live Photo package from an already paired JPEG/MOV."""
    destination.mkdir(exist_ok=False)
    try:
        for name in ('LivePhoto.jpg', 'LivePhoto.mov'):
            shutil.copyfile(directory/name, destination/name)
        (destination/'metadata.plist').write_bytes(plistlib.dumps(
            {'PFVideoComplementMetadataVersionKey': '1'}))
    except Exception:
        # Only remove the new directory exclusively created by this call.
        shutil.rmtree(destination)
        raise
    return destination
from PIL import Image

# Metadata-only track from our Apple-validated exporter (one int8 sample).
TRACK = base64.b64decode('AAACSHRyYWsAAABcdGtoZAAAAA/m7n3B5u59wQAAAAIAAAAAAAADnQAAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAADBlZHRzAAAAKGVsc3QAAAAAAAAAAgAAA4T/////AAEAAAAAABkAAAAAAAEAAAAAAbRtZGlhAAAAIG1kaGQAAAAA5u59webufcEAAAJYAAAAGVXEAAAAAAA0aGRscgAAAABtaGxybWV0YWFwcGwAAAABAAAAABNDb3JlIE1lZGlhIE1ldGFkYXRhAAABWG1pbmYAAAAgZ21oZAAAABhnbWluAAAAAABAgACAAIAAAAAAAAAAADhoZGxyAAAAAGRobHJhbGlzYXBwbAAAAAAAAAAAF0NvcmUgTWVkaWEgRGF0YSBIYW5kbGVyAAAAJGRpbmYAAAAcZHJlZgAAAAAAAAABAAAADGFsaXMAAAABAAAA1HN0YmwAAABwc3RzZAAAAAAAAAABAAAAYG1lYngAAAAAAAAAAQAAAFBrZXlzAAAASAAAAAEAAAAwa2V5ZG1kdGFjb20uYXBwbGUucXVpY2t0aW1lLnN0aWxsLWltYWdlLXRpbWUAAAAQZHR5cAAAAAAAAABBAAAAGHN0dHMAAAAAAAAAAQAAAAEAAAAZAAAAHHN0c2MAAAAAAAAAAQAAAAEAAAABAAAAAQAAABRzdHN6AAAAAAAAAAkAAAABAAAAFHN0Y28AAAAAAAAAAQACZrY=')
META = base64.b64decode('AAAArG1ldGEAAAAiaGRscgAAAAAAAAAAbWR0YQAAAAAAAAAAAAAAAAAAAAAAPmtleXMAAAAAAAAAAQAAAC5tZHRhY29tLmFwcGxlLnF1aWNrdGltZS5jb250ZW50LmlkZW50aWZpZXIAAABEaWxzdAAAADwAAAABAAAANGRhdGEAAAABAAAAAEI2N0FDNzBBLTg2NjUtNEE0Qy04OUFGLTNDN0NBNDY4Qzg0Mw==')

def boxes(data):
    offset = 0
    while offset < len(data):
        if offset+8 > len(data): raise ValueError('Truncated movie')
        size, kind = struct.unpack_from('>I4s', data, offset)
        if size < 8 or offset+size > len(data): raise ValueError('Unsupported movie box')
        yield kind, offset, data[offset:offset+size]
        offset += size

def box(kind, content): return struct.pack('>I4s', len(content)+8, kind)+content

def pair(video, directory, seconds, cancelled):
    if cancelled(): raise RuntimeError('Cancelled')
    data = video.read_bytes()
    _, position, movie = next(item for item in boxes(data) if item[0] == b'moov')
    if position+len(movie) != len(data): raise ValueError('Expected terminal movie metadata')
    children = list(boxes(movie[8:]))
    header = next(value for kind, _, value in children if kind == b'mvhd')
    scale, duration = struct.unpack_from('>II', header, 20)
    if not 0 <= seconds < duration/scale <= 10: raise ValueError('Invalid Live Photo timestamp')
    identifier = str(uuid.uuid4()).upper().encode()
    track = bytearray(TRACK)
    tk = track.index(b'tkhd')-4
    struct.pack_into('>I', track, tk+20, 2)
    struct.pack_into('>I', track, tk+28, round(seconds*scale)+round(scale/24))
    el = track.index(b'elst')-4
    struct.pack_into('>I', track, el+16, round(seconds*scale))
    struct.pack_into('>I', track, el+28, round(scale/24))
    co = track.index(b'stco')-4
    struct.pack_into('>I', track, co+16, position+8)
    updated_header = bytearray(header)
    struct.pack_into('>I', updated_header, len(updated_header)-4, 3)
    content = b''.join(bytes(updated_header) if kind == b'mvhd' else value for kind, _, value in children if kind != b'meta')
    prefix = bytearray(data[:position]); prefix[8:12] = b'qt  '
    (directory/'LivePhoto.mov').write_bytes(prefix+box(b'mdat', bytes.fromhex('000000090000000100'))+box(b'moov', content+track+META[:-36]+identifier))
    with Image.open(directory/'poster.jpg') as image:
        # MakerNote must use TIFF UNDEFINED (7), not Pillow's inferred BYTE (1).
        exif = bytes.fromhex('4578696600004d4d002a00000008000187690004000000010000001a000000000003927c00070000004500000044a002000400000001')
        exif += struct.pack('>I', image.width)+bytes.fromhex('a003000400000001')+struct.pack('>I', image.height)+bytes(4)
        exif += b'Apple iOS\x00\x00\x01MM\x00\x01\x00\x11\x00\x02\x00\x00\x00%\x00\x00\x00 \x00\x00\x00\x00'+identifier+b'\x00\x00'
        image.save(directory/'LivePhoto.jpg', quality=95, exif=exif)
    with zipfile.ZipFile(directory/'live-photo.zip', 'w', zipfile.ZIP_STORED) as archive:
        for name in ('LivePhoto.jpg', 'LivePhoto.mov'): archive.write(directory/name, name)
        archive.writestr('README.txt', 'Live Photo / 实况照片\nImport JPG and MOV together into Apple Photos.\n请将 JPG 和 MOV 同时导入 Apple 照片。\n')
    bundle = pvt_bundle(directory, directory/'LivePhoto.pvt')
    with zipfile.ZipFile(directory/'LivePhoto.pvt.zip', 'w', zipfile.ZIP_STORED) as archive:
        for name in ('LivePhoto.jpg', 'LivePhoto.mov', 'metadata.plist'):
            archive.write(bundle/name, 'LivePhoto.pvt/'+name)
