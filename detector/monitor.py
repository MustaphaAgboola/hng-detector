import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

from dateutil import parser as dparse

log = logging.getLogger("monitor")

POLL_INTERVAL = 0.05
ROTATE_CHECK  = 2.0


@dataclass
class LogEntry:
    source_ip:     str
    timestamp:     float
    method:        str
    path:          str
    status:        int
    response_size: int


class LogMonitor:
    def __init__(self, cfg, queue):
        self.cfg   = cfg
        self.queue = queue
        self._path = Path(cfg.log_path)

    async def run(self):
        log.info(f"LogMonitor: watching {self._path}")
        async for entry in self._follow():
            await self.queue.put(entry)

    async def _follow(self):
        while not self._path.exists():
            log.info(f"Waiting for {self._path} to appear...")
            await asyncio.sleep(2)

        fh = open(self._path, "r", buffering=1)
        fh.seek(0, 2)
        current_inode  = os.fstat(fh.fileno()).st_ino
        last_rot_check = asyncio.get_event_loop().time()
        partial        = ""

        log.info(f"Tailing {self._path} (inode={current_inode})")

        while True:
            chunk = fh.read(65536)
            if chunk:
                data    = partial + chunk
                lines   = data.split("\n")
                partial = lines[-1]
                for line in lines[:-1]:
                    line = line.strip()
                    if not line:
                        continue
                    entry = self._parse(line)
                    if entry:
                        yield entry
                await asyncio.sleep(0)
            else:
                await asyncio.sleep(POLL_INTERVAL)

            now = asyncio.get_event_loop().time()
            if now - last_rot_check >= ROTATE_CHECK:
                last_rot_check = now
                try:
                    new_inode = os.stat(self._path).st_ino
                    if new_inode != current_inode:
                        log.info("Log rotation detected — reopening")
                        fh.close()
                        fh = open(self._path, "r", buffering=1)
                        current_inode = new_inode
                        partial = ""
                except FileNotFoundError:
                    log.warning("Log file disappeared — retrying...")
                    await asyncio.sleep(2)

    @staticmethod
    def _parse(line):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            return None
        try:
            ip = (
                d.get("source_ip")
                or d.get("remote_addr")
                or (d.get("http_x_forwarded_for") or "").split(",")[0].strip()
                or "0.0.0.0"
            )
            ts_raw = d.get("timestamp") or d.get("time") or d.get("time_local")
            if ts_raw is None:
                ts = time.time()
            elif isinstance(ts_raw, (int, float)):
                ts = float(ts_raw)
            else:
                ts = dparse.parse(str(ts_raw)).timestamp()
            return LogEntry(
                source_ip     = ip.strip(),
                timestamp     = ts,
                method        = str(d.get("method") or d.get("request_method") or "GET"),
                path          = str(d.get("path") or d.get("uri") or d.get("request_uri") or "/"),
                status        = int(d.get("status", 200)),
                response_size = int(d.get("response_size") or d.get("bytes_sent") or 0),
            )
        except Exception as exc:
            log.debug(f"Parse error ({exc}): {line[:120]}")
            return None