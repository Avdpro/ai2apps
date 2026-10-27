"""Private stat-bound input references for durable Studio jobs."""
from pathlib import Path
import stat

def describe(path):
    selected=Path(path)
    if not selected.is_absolute():raise ValueError('Source path must be absolute')
    try:
        resolved=selected.resolve(strict=True);info=resolved.stat()
    except (OSError,RuntimeError) as error:raise ValueError('Source moved or is unavailable; select it again') from error
    if not stat.S_ISREG(info.st_mode):raise ValueError('Source is not a regular file')
    return {'path':str(selected),'resolved':str(resolved),'fingerprint':[info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns]}

def resolve(reference):
    try:current=describe(reference['path'])
    except ValueError:raise
    if current!=reference:raise ValueError('Source changed or was replaced; select it again')
    return Path(current['resolved'])
