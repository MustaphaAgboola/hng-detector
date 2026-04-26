# All requests in last 60 seconds
self._global_window: deque[float] = deque()

# Per IP: (timestamp, is_error) tuples
self._ip_windows: dict[str, deque] = defaultdict(deque)

cutoff = now - 60   # window_seconds

dq = self._ip_windows[ip]
dq.append((now, is_err))              # new entry goes on the right

while dq and dq[0][0] < cutoff:      # evict from the left
    dq.popleft()

def _anomalous(rps, mean, stddev, z_thresh, r_thresh):
    # Check z-score first
    if stddev > 0:
        z = (rps - mean) / stddev
        if z >= z_thresh:
            return True, f"z_score={z:.3f} >= {z_thresh}"
    # Check rate multiplier second
    if mean > 0 and rps >= r_thresh * mean:
        return True, f"rate={rps:.4f} >= {r_thresh}x mean({mean:.4f})"
    return False, ""

surge = err_rate > cfg.error_surge_multiplier * snap.error_mean
factor = cfg.error_surge_factor if surge else 1.0  # 0.5 if surging

z_thresh = cfg.z_score_threshold * factor  # 3.0 → 1.5 — fires sooner
r_thresh = cfg.rate_multiplier   * factor  # 5.0 → 2.5 — fires sooner

    