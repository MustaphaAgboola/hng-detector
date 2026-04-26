from dataclasses import dataclass
from collections import deque

@dataclass
class LogEntry:
    source_ip:     str
    timestamp:     float   # unix epoch
    method:        str
    path:          str
    status:        int
    response_size: int

async def _follow(self):
    # wait for file to exist (nginx may not have written anything yet)
    while not self._path.exists():
        await asyncio.sleep(2)

    fh = open(self._path, "r")
    fh.seek(0, 2)                  # jump to end — only read NEW lines
    current_inode = os.fstat(fh.fileno()).st_ino
    partial = ""

    while True:
        chunk = fh.read(65536)
        if chunk:
            data = partial + chunk
            lines = data.split("\n")
            partial = lines[-1]    # keep incomplete last line
            for line in lines[:-1]:
                entry = self._parse(line)
                if entry:
                    yield entry    # send to detector
        else:
            await asyncio.sleep(0.05)

        # check for log rotation every 2 seconds
        new_inode = os.stat(self._path).st_ino
        if new_inode != current_inode:
            fh = open(self._path, "r")
            current_inode = new_inode