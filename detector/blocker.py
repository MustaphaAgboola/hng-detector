import asyncio
import logging
import time
from dataclasses import dataclass

log = logging.getLogger("blocker")


@dataclass
class BanRecord:
    ip:        str
    banned_at: float
    level:     int
    duration:  int
    condition: str
    rate:      float
    baseline:  float
    unban_at:  float


async def _sh(cmd):
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return proc.returncode == 0
    except Exception as exc:
        log.warning(f"Shell error: {exc}")
        return False


class Blocker:
    def __init__(self, cfg, notifier):
        self.cfg      = cfg
        self.notifier = notifier
        self._bans    = {}
        self._lock    = asyncio.Lock()

    async def setup_chain(self):
        chain = self.cfg.iptables_chain
        await _sh(f"iptables -N {chain} 2>/dev/null; true")
        await _sh(
            f"iptables -C INPUT -j {chain} 2>/dev/null || "
            f"iptables -I INPUT -j {chain}"
        )
        log.info(f"iptables chain '{chain}' ready")

    async def is_banned(self, ip):
        async with self._lock:
            return ip in self._bans

    async def ban(self, ip, condition, rate, baseline, detail=""):
        from audit import AuditLogger
        audit = AuditLogger(self.cfg)
        async with self._lock:
            existing = self._bans.get(ip)
            level    = min(existing.level + 1, len(self.cfg.ban_durations) - 1) if existing else 0
            duration = self.cfg.ban_durations[level]
            now      = time.time()
            unban_at = float("inf") if duration < 0 else now + duration
            dur_str  = "permanent" if duration < 0 else f"{duration}s"
            self._bans[ip] = BanRecord(
                ip=ip, banned_at=now, level=level, duration=duration,
                condition=condition, rate=rate, baseline=baseline, unban_at=unban_at,
            )

        chain = self.cfg.iptables_chain
        ok = await _sh(
            f"iptables -C {chain} -s {ip} -j DROP 2>/dev/null || "
            f"iptables -A {chain} -s {ip} -j DROP"
        )
        if ok:
            log.info(f"Blocked {ip} (level={level} duration={dur_str})")
        else:
            log.warning(f"iptables failed for {ip}")

        await audit.write("BAN", ip, condition, rate, baseline, dur_str)
        await self.notifier.ban_alert(ip=ip, condition=condition, rate=rate,
                                      baseline=baseline, duration=dur_str)

    async def unban(self, ip):
        from audit import AuditLogger
        audit = AuditLogger(self.cfg)
        async with self._lock:
            record = self._bans.pop(ip, None)
        if not record:
            return
        chain   = self.cfg.iptables_chain
        dur_str = "permanent" if record.duration < 0 else f"{record.duration}s"
        await _sh(f"iptables -D {chain} -s {ip} -j DROP 2>/dev/null; true")
        log.info(f"Unbanned {ip} (was level={record.level})")
        await audit.write("UNBAN", ip, record.condition, record.rate, record.baseline, dur_str)
        await self.notifier.unban_alert(ip=ip, level=record.level, condition=record.condition)

    async def global_alert(self, condition, rate, baseline, detail=""):
        from audit import AuditLogger
        audit = AuditLogger(self.cfg)
        await audit.write("GLOBAL_ANOMALY", "-", condition, rate, baseline, "-")
        await self.notifier.global_alert(condition=condition, rate=rate, baseline=baseline)

    async def get_bans(self):
        async with self._lock:
            return dict(self._bans)

    async def bans_snapshot(self):
        now = time.time()
        async with self._lock:
            return [
                {
                    "ip":        r.ip,
                    "level":     r.level,
                    "duration":  r.duration,
                    "ttl":       -1 if r.unban_at == float("inf") else max(0.0, r.unban_at - now),
                    "condition": r.condition,
                    "rate":      r.rate,
                    "baseline":  r.baseline,
                    "banned_at": r.banned_at,
                }
                for r in self._bans.values()
            ]