"""Nonblocking PTY I/O for the existing sandboxed Process lifecycle."""
import asyncio
import errno
import fcntl
import os
import struct
import termios


class PtyIO:
    def __init__(self, fd):
        self.fd = fd
        os.set_blocking(fd, False)

    def resize(self, cols, rows):
        if type(cols) is not int or type(rows) is not int or not (20 <= cols <= 500 and 5 <= rows <= 200):
            raise ValueError('PTY dimensions must be 20–500 columns and 5–200 rows')
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))

    async def ready(self, write=False):
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        def wake():
            if not future.done(): future.set_result(None)
        add = loop.add_writer if write else loop.add_reader
        remove = loop.remove_writer if write else loop.remove_reader
        add(self.fd, wake)
        try: await future
        finally: remove(self.fd)

    async def read(self, size):
        while self.fd >= 0:
            try: return os.read(self.fd, size)
            except BlockingIOError: await self.ready()
            except OSError as error:
                if error.errno in (errno.EIO, errno.EBADF): return b''
                raise
        return b''

    async def write(self, data):
        while data:
            try: data = data[os.write(self.fd, data):]
            except BlockingIOError: await self.ready(write=True)

    def close(self):
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1
