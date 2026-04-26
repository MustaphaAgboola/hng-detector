import asyncio
import logging
import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime

log = logging.getLogger("baseline")


@dataclass
class BaselineSnapshot:
    mean:           float = 0.0
    stddev:         float = 0.0
    error_mean:     float = 0.0
    samples:        int   = 0
    source:         str   = "none"
    computed_at:    float = field(default_factory=time.time)
    hour_snapshots: dict  = field(default_factory=dict)


def _mean(data):
    return sum(data) / len(data) if data else 0.0


def _stddev(data, mean):
    if len(data) < 2:
        return 0.0
    return math.sqrt(sum((x - mean) ** 2 for x in data) / len(data))


class BaselineEngine:
    def __init__(self, cfg):
        self.cfg    = cfg
        max_samples = cfg.baseline_window_minutes * 60
        self._req_counts = deque(maxlen=max_samples)
        self._err_counts = deque(maxlen=max_samples)
        self._hour_req   = defaultdict(list)
        self._hour_err   = defaultdict(list)
        self._cur_bucket = int(time.time())
        self._cur_reqs   = 0
        self._cur_errs   = 0
        self._snapshot   = BaselineSnapshot()
        self._lock       = asyncio.Lock()

    async def record(self, is_error):
        bucket = int(time.time())
        async with self._lock:
            if bucket != self._cur_bucket:
                self._flush_bucket()
                self._cur_bucket = bucket
                self._cur_reqs   = 0
                self._cur_errs   = 0
            self._cur_reqs += 1
            if is_error:
                self._cur_errs += 1

    def snapshot(self):
        return self._snapshot

    async def run(self):
        log.info("BaselineEngine started")
        while True:
            await asyncio.sleep(self.cfg.baseline_recalc_interval)
            await self._recalculate()

    def _flush_bucket(self):
        self._req_counts.append(float(self._cur_reqs))
        self._err_counts.append(float(self._cur_errs))
        hour = datetime.fromtimestamp(self._cur_bucket).hour
        self._hour_req[hour].append(float(self._cur_reqs))
        self._hour_err[hour].append(float(self._cur_errs))
        cap = 3600
        if len(self._hour_req[hour]) > cap:
            self._hour_req[hour] = self._hour_req[hour][-cap:]
            self._hour_err[hour] = self._hour_err[hour][-cap:]

    async def _recalculate(self):
        from audit import AuditLogger
        audit = AuditLogger(self.cfg)
        async with self._lock:
            self._flush_bucket()
            req_data      = list(self._req_counts)
            err_data      = list(self._err_counts)
            hour_req_copy = {h: list(v) for h, v in self._hour_req.items()}
            hour_err_copy = {h: list(v) for h, v in self._hour_err.items()}

        if len(req_data) < self.cfg.baseline_min_data_points:
            log.debug("Baseline: not enough data yet")
            return

        source      = "rolling"
        chosen_req  = req_data
        chosen_err  = err_data

        if self.cfg.prefer_current_hour:
            cur_hour = datetime.now().hour
            if cur_hour in hour_req_copy:
                h_data = hour_req_copy[cur_hour]
                if len(h_data) >= self.cfg.baseline_min_data_points:
                    chosen_req = h_data[-1800:]
                    chosen_err = (hour_err_copy.get(cur_hour) or [])[-1800:]
                    source     = "current_hour"

        mean      = max(_mean(chosen_req),          self.cfg.mean_floor)
        stddev    = max(_stddev(chosen_req, mean),  self.cfg.stddev_floor)
        err_mean  = max(_mean(chosen_err),          self.cfg.mean_floor / 10)

        hour_snaps = {
            h: round(max(_mean(v), self.cfg.mean_floor), 4)
            for h, v in hour_req_copy.items() if v
        }

        self._snapshot = BaselineSnapshot(
            mean           = mean,
            stddev         = stddev,
            error_mean     = err_mean,
            samples        = len(chosen_req),
            source         = source,
            computed_at    = time.time(),
            hour_snapshots = hour_snaps,
        )

        await audit.write(
            action    = "BASELINE_RECALC",
            ip        = "-",
            condition = f"source={source}",
            rate      = mean,
            baseline  = mean,
            duration  = "-",
            extra     = f"stddev={stddev:.4f} error_mean={err_mean:.6f} samples={len(chosen_req)}",
        )
        log.info(
            f"Baseline [{source}] mean={mean:.4f}/s stddev={stddev:.4f} "
            f"err_mean={err_mean:.6f} n={len(chosen_req)}"
        )