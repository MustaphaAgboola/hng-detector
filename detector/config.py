import os
from pathlib import Path
import yaml


def load(path=None):
    cfg_path = path or Path(__file__).parent / "config.yaml"
    with open(cfg_path) as fh:
        raw = yaml.safe_load(fh)
    if os.getenv("SLACK_WEBHOOK"):
        raw.setdefault("slack", {})["webhook_url"] = os.environ["SLACK_WEBHOOK"]
    if os.getenv("LOG_PATH"):
        raw.setdefault("log", {})["path"] = os.environ["LOG_PATH"]
    if os.getenv("AUDIT_LOG_PATH"):
        raw.setdefault("log", {})["audit_path"] = os.environ["AUDIT_LOG_PATH"]
    return Config(raw)


class Config:
    def __init__(self, raw):
        self._r = raw

    @property
    def log_path(self):
        return self._r["log"]["path"]

    @property
    def audit_log_path(self):
        return self._r["log"].get("audit_path", "/var/log/detector/audit.log")

    @property
    def slack_webhook(self):
        return self._r.get("slack", {}).get("webhook_url", "")

    @property
    def window_seconds(self):
        return int(self._r["detection"]["window_seconds"])

    @property
    def z_score_threshold(self):
        return float(self._r["detection"]["z_score_threshold"])

    @property
    def rate_multiplier(self):
        return float(self._r["detection"]["rate_multiplier"])

    @property
    def error_surge_multiplier(self):
        return float(self._r["detection"]["error_surge_multiplier"])

    @property
    def error_surge_factor(self):
        return float(self._r["detection"]["error_surge_factor"])

    @property
    def min_requests_to_flag(self):
        return int(self._r["detection"].get("min_requests_to_flag", 5))

    @property
    def baseline_window_minutes(self):
        return int(self._r["baseline"]["window_minutes"])

    @property
    def baseline_recalc_interval(self):
        return int(self._r["baseline"]["recalc_interval_seconds"])

    @property
    def baseline_min_data_points(self):
        return int(self._r["baseline"]["min_data_points"])

    @property
    def prefer_current_hour(self):
        return bool(self._r["baseline"].get("prefer_current_hour", True))

    @property
    def mean_floor(self):
        return float(self._r["baseline"].get("mean_floor", 0.01))

    @property
    def stddev_floor(self):
        return float(self._r["baseline"].get("stddev_floor", 0.01))

    @property
    def ban_durations(self):
        return list(self._r["blocking"]["ban_durations"])

    @property
    def iptables_chain(self):
        return str(self._r["blocking"].get("iptables_chain", "DETECTOR_BLOCK"))

    @property
    def dashboard_port(self):
        return int(self._r["dashboard"]["port"])

    @property
    def dashboard_refresh_seconds(self):
        return int(self._r["dashboard"].get("refresh_seconds", 3))

    @property
    def top_ips_count(self):
        return int(self._r["dashboard"].get("top_ips_count", 10))