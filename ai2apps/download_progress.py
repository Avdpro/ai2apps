"""Transfer measurements shared by Package and Checkpoint downloads."""

from collections import deque
import math
import time


class DownloadProgress:
    def __init__(self):
        self.samples = deque()
        self.identity = None
        self.latest = None

    def update(self, value, now=None):
        now = time.monotonic() if now is None else now
        if str(value.get('stage', '')).startswith('downloading_'):
            completed = value.get('totalBytesCompleted', value.get('bytesCompleted'))
            total = value.get('totalBytesTotal', value.get('bytesTotal'))
            if completed is not None and total is not None:
                key = (value.get('distributionId') or value.get('fileName'), total)
                if key != self.identity or (self.samples and completed < self.samples[-1][1]):
                    self.samples.clear()
                    self.identity = key
                self.samples.append((now, completed))
                while len(self.samples) > 2 and self.samples[1][0] <= now - 5:
                    self.samples.popleft()
                elapsed = now - self.samples[0][0]
                speed = (completed - self.samples[0][1]) / elapsed if elapsed >= 0.25 else None
                self.latest = {
                    'fileName': value.get('fileName', ''),
                    'bytesCompleted': completed,
                    'bytesTotal': total,
                    'bytesPerSecond': speed,
                    'etaSeconds': math.ceil((total - completed) / speed)
                    if speed and total > completed else None,
                    'sampledAt': time.time(),
                }
        if self.latest is None:
            return value
        return {**value, 'download': dict(self.latest)}
