import asyncio
import logging
from datetime import datetime, timezone

import aiohttp

log = logging.getLogger("notifier")

_TIMEOUT = aiohttp.ClientTimeout(total=8)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Notifier:
    def __init__(self, cfg):
        self.cfg      = cfg
        self._session = None

    async def ban_alert(self, ip, condition, rate, baseline, duration):
        text = (
            f":rotating_light: *[cloud.ng] IP BANNED*\n"
            f">*IP:* `{ip}`\n"
            f">*Condition:* `{condition}`\n"
            f">*Current rate:* `{rate:.1f} rpm`\n"
            f">*Baseline:* `{baseline:.1f} rpm`\n"
            f">*Ban duration:* `{duration}`\n"
            f">*Timestamp:* `{_now()}`"
        )
        await self._post(text)

    async def unban_alert(self, ip, level, condition):
        text = (
            f":white_check_mark: *[cloud.ng] IP UNBANNED*\n"
            f">*IP:* `{ip}`\n"
            f">*Original condition:* `{condition}`\n"
            f">*Ban level was:* `{level}`\n"
            f">*Timestamp:* `{_now()}`"
        )
        await self._post(text)

    async def global_alert(self, condition, rate, baseline):
        text = (
            f":warning: *[cloud.ng] GLOBAL TRAFFIC SPIKE*\n"
            f">*Condition:* `{condition}`\n"
            f">*Current global rate:* `{rate:.1f} rpm`\n"
            f">*Baseline mean:* `{baseline:.1f} rpm`\n"
            f">*Timestamp:* `{_now()}`"
        )
        await self._post(text)

    async def _post(self, text):
        webhook = self.cfg.slack_webhook
        if not webhook:
            log.info(f"[SLACK-NO-WEBHOOK] {text[:120]}")
            return
        try:
            if not self._session or self._session.closed:
                self._session = aiohttp.ClientSession()
            async with self._session.post(
                webhook, json={"text": text}, timeout=_TIMEOUT
            ) as resp:
                if resp.status >= 400:
                    log.warning(f"Slack returned {resp.status}")
        except asyncio.TimeoutError:
            log.warning("Slack webhook timed out")
        except Exception as exc:
            log.warning(f"Slack post failed: {exc}")