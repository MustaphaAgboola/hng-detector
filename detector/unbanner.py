import asyncio
import logging
import time

log = logging.getLogger("unbanner")

CHECK_INTERVAL = 30


class Unbanner:
    def __init__(self, cfg, blocker, notifier):
        self.cfg      = cfg
        self.blocker  = blocker
        self.notifier = notifier

    async def run(self):
        log.info("Unbanner started")
        while True:
            await asyncio.sleep(CHECK_INTERVAL)
            await self._sweep()

    async def _sweep(self):
        now  = time.time()
        bans = await self.blocker.get_bans()
        for ip, record in bans.items():
            if record.duration < 0:
                continue
            if now >= record.unban_at:
                log.info(f"Auto-unbanning {ip} (level={record.level})")
                await self.blocker.unban(ip)