class Unbanner:
    async def run(self):
        while True:
            await asyncio.sleep(30)
            await self._sweep()

    async def _sweep(self):
        now  = time.time()
        bans = await self.blocker.get_bans()
        for ip, record in bans.items():
            if record.duration < 0:
                continue              # permanent — never auto-release
            if now >= record.unban_at:
                await self.blocker.unban(ip)