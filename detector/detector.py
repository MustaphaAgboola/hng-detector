import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field

log = logging.getLogger("detector")

MAX_TRACKED_IPS = 50_000


@dataclass
class WindowStats:
    global_rps:      float = 0.0
    top_ips:         list  = field(default_factory=list)
    active_ips:      int   = 0
    total_processed: int   = 0


def _anomalous(rps, mean, stddev, z_thresh, r_thresh):
    if stddev > 0:
        z = (rps - mean) / stddev
        if z >= z_thresh:
            return True, f"z_score={z:.3f} >= {z_thresh}"
    if mean > 0 and rps >= r_thresh * mean:
        return True, f"rate={rps:.4f} >= {r_thresh}x mean({mean:.4f})"
    return False, ""


class AnomalyDetector:
    def __init__(self, cfg, baseline, blocker, queue):
        self.cfg      = cfg
        self.baseline = baseline
        self.blocker  = blocker
        self.queue    = queue
        self._global_window    = deque()
        self._ip_windows       = defaultdict(deque)
        self._ip_last_flagged  = {}
        self._global_last_flag = 0.0
        self._total            = 0
        self._lock             = asyncio.Lock()

    async def run(self):
        log.info("AnomalyDetector started")
        while True:
            entry = await self.queue.get()
            try:
                await self._process(entry)
            except Exception as exc:
                log.exception(f"Detector error: {exc}")
            finally:
                self.queue.task_done()

    async def stats(self):
        now    = time.time()
        W      = self.cfg.window_seconds
        cutoff = now - W
        async with self._lock:
            while self._global_window and self._global_window[0] < cutoff:
                self._global_window.popleft()
            g_count = len(self._global_window)
            ip_counts = []
            for ip, dq in self._ip_windows.items():
                cnt = sum(1 for ts, _ in dq if ts >= cutoff)
                if cnt > 0:
                    ip_counts.append((ip, cnt))
        ip_counts.sort(key=lambda x: x[1], reverse=True)
        top = [(ip, round(cnt * 60 / W, 1)) for ip, cnt in ip_counts[:self.cfg.top_ips_count]]
        return WindowStats(
            global_rps      = round(g_count / W, 3),
            top_ips         = top,
            active_ips      = len(ip_counts),
            total_processed = self._total,
        )

    async def _process(self, entry):
        now    = entry.timestamp
        ip     = entry.source_ip
        is_err = entry.status >= 400
        W      = self.cfg.window_seconds
        cutoff = now - W

        await self.baseline.record(is_err)

        async with self._lock:
            self._total += 1
            self._global_window.append(now)
            while self._global_window and self._global_window[0] < cutoff:
                self._global_window.popleft()

            if len(self._ip_windows) >= MAX_TRACKED_IPS:
                drop = next(iter(self._ip_windows))
                del self._ip_windows[drop]

            dq = self._ip_windows[ip]
            dq.append((now, is_err))
            while dq and dq[0][0] < cutoff:
                dq.popleft()

            ip_count  = len(dq)
            ip_errors = sum(1 for _, e in dq if e)
            g_count   = len(self._global_window)

        ip_rps      = ip_count / W
        g_rps       = g_count  / W
        ip_err_rate = ip_errors / ip_count if ip_count > 0 else 0.0
        snap        = self.baseline.snapshot()

        if snap.samples < self.cfg.baseline_min_data_points:
            return

        if ip_count >= self.cfg.min_requests_to_flag:
            if not await self.blocker.is_banned(ip):
                await self._check_ip(ip, ip_rps, ip_err_rate, snap, now)

        if now - self._global_last_flag >= 10:
            fired = await self._check_global(g_rps, snap, now)
            if fired:
                self._global_last_flag = now

    async def _check_ip(self, ip, rps, err_rate, snap, now):
        surge  = snap.error_mean > 0 and err_rate > self.cfg.error_surge_multiplier * snap.error_mean
        factor = self.cfg.error_surge_factor if surge else 1.0
        z_thresh = self.cfg.z_score_threshold * factor
        r_thresh = self.cfg.rate_multiplier   * factor

        flagged, condition = _anomalous(rps, snap.mean, snap.stddev, z_thresh, r_thresh)
        if not flagged:
            return
        if now - self._ip_last_flagged.get(ip, 0) < 5:
            return
        self._ip_last_flagged[ip] = now

        rpm    = rps * 60
        detail = (
            f"ip_rate rpm={rpm:.1f} err_rate={err_rate:.3f} "
            f"surge={'yes' if surge else 'no'}"
        )
        log.warning(f"[ANOMALY/IP] {ip} — {condition} — {detail}")
        await self.blocker.ban(ip=ip, condition=condition, rate=rpm,
                               baseline=snap.mean * 60, detail=detail)

    async def _check_global(self, rps, snap, now):
        flagged, condition = _anomalous(
            rps, snap.mean, snap.stddev,
            self.cfg.z_score_threshold,
            self.cfg.rate_multiplier,
        )
        if not flagged:
            return False
        rpm    = rps * 60
        detail = (
            f"global_spike rpm={rpm:.1f} "
            f"baseline_mean={snap.mean*60:.1f} "
            f"baseline_stddev={snap.stddev*60:.1f}"
        )
        log.warning(f"[ANOMALY/GLOBAL] {condition} — {detail}")
        await self.blocker.global_alert(condition=condition, rate=rpm,
                                        baseline=snap.mean * 60, detail=detail)
        return True