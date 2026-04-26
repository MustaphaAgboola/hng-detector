from collections import deque, defaultdict

# One float per second, keep last 30 minutes = 1800 slots
self._req_counts: deque[float] = deque(maxlen=1800)

# Per-hour lists: hour(0-23) → [counts...]
self._hour_req: dict[int, list[float]] = defaultdict(list)

# Current second's accumulator
self._cur_bucket: int = int(time.time())
self._cur_reqs:   int = 0

async def record(self, is_error: bool):
    bucket = int(time.time())
    async with self._lock:
        if bucket != self._cur_bucket:
            # flush previous second into both collections
            self._req_counts.append(float(self._cur_reqs))
            hour = datetime.fromtimestamp(self._cur_bucket).hour
            self._hour_req[hour].append(float(self._cur_reqs))
            # reset for new second
            self._cur_bucket = bucket
            self._cur_reqs = 0
        self._cur_reqs += 1

async def _recalculate(self):
    # Prefer current hour's data if it has enough samples
    cur_hour = datetime.now().hour
    if len(self._hour_req[cur_hour]) >= self.cfg.baseline_min_data_points:
        data = self._hour_req[cur_hour][-1800:]
        source = "current_hour"
    else:
        data = list(self._req_counts)
        source = "rolling"

    mean   = max(sum(data)/len(data), self.cfg.mean_floor)
    stddev = max(sqrt(sum((x-mean)**2 for x in data)/len(data)), self.cfg.stddev_floor)