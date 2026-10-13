"""Live Photo export using existing Host dependencies; no native Runtime changes."""
from pathlib import Path
import asyncio
from .live_photo_pair import pair


def exporter_path():
    return Path(__file__)


async def export_live_photo(video, directory, seconds, cancelled):
    await asyncio.to_thread(pair, video, directory, seconds, cancelled)
