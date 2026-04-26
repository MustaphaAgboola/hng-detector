import aiohttp

class Notifier:
    def __init__(self, cfg):
        self.cfg = cfg

    async def ban_alert(self, ip, condition, rate, baseline, duration):
        text = (
            f":rotating_light: *[cloud.ng] IP BANNED*\n"
            f">*IP:* `{ip}`\n"
            f">*Condition:* `{condition}`\n"
            f">*Current rate:* `{rate:.1f} rpm`\n"
            f">*Baseline:* `{baseline:.1f} rpm`\n"
            f">*Ban duration:* `{duration}`\n"
            f">*Time:* `{_now()}`"
        )
        await self._post(text)

    async def unban_alert(self, ip, level, condition): ...
    async def global_alert(self, condition, rate, baseline): ...

    async def _post(self, text):
        webhook = self.cfg.slack_webhook
        if not webhook:
            # no webhook configured — log it and move on
            return
        async with aiohttp.ClientSession() as s:
            await s.post(webhook, json={"text": text}, timeout=...)