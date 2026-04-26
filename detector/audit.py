import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path


log = logging.getLogger("audit")


class AuditLogger:
    def __init__(self, cfg):
        self._path = Path(cfg.audit_log_path)
        self._lock = asyncio.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    async def write(self, action, ip, condition, rate, baseline, duration, extra=""):
        ts   = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = (
            f"[{ts}] {action} {ip} | {condition} | "
            f"rate={rate:.4f} | baseline={baseline:.4f} | duration={duration}"
        )
        if extra:
            line += f" | {extra}"
        async with self._lock:
            try:
                with open(self._path, "a") as fh:
                    fh.write(line + "\n")
            except Exception as exc:
                log.warning(f"Audit write failed: {exc}")
        log.info(f"AUDIT: {line}")