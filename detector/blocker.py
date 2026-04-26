@dataclass
class BanRecord:
    ip:        str
    banned_at: float
    level:     int       # 0 = first offence, 1 = second, etc.
    duration:  int       # seconds; -1 = permanent
    condition: str
    rate:      float
    baseline:  float
    unban_at:  float     # epoch when to release; inf if permanent

async def ban(self, ip, condition, rate, baseline):
    existing = self._bans.get(ip)
    level = min(existing.level + 1, len(durations) - 1) if existing else 0
    duration = self.cfg.ban_durations[level]

await asyncio.create_subprocess_shell(
    f"iptables -A {self.cfg.iptables_chain} -s {ip} -j DROP"
)

async def setup_chain(self):
    await _sh(f"iptables -N {chain} 2>/dev/null; true")
    await _sh(f"iptables -C INPUT -j {chain} 2>/dev/null || "
              f"iptables -I INPUT -j {chain}")