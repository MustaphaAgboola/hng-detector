import os, yaml
from pathlib import Path

def load(path=None):
    cfg_path = path or Path(__file__).parent / "config.yaml"
    with open(cfg_path) as fh:
        raw = yaml.safe_load(fh)
    # env vars override config file for secrets
    if os.getenv("SLACK_WEBHOOK"):
        raw["slack"]["webhook_url"] = os.environ["SLACK_WEBHOOK"]
    return Config(raw)

class Config:
    def __init__(self, raw):
        self._r = raw

    @property
    def z_score_threshold(self):
        return float(self._r["detection"]["z_score_threshold"])

    @property
    def ban_durations(self):
        return list(self._r["blocking"]["ban_durations"])
    # ... and so on for every setting