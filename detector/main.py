import asyncio
import logging
import os
import signal
import sys

import config as cfg_mod
from monitor   import LogMonitor
from baseline  import BaselineEngine
from detector  import AnomalyDetector
from blocker   import Blocker
from unbanner  import Unbanner
from notifier  import Notifier
from dashboard import DashboardServer

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream = sys.stdout,
)
log = logging.getLogger("main")


async def main() -> None:
    cfg = cfg_mod.load()

    log.info("=" * 60)
    log.info("cloud.ng Anomaly Detection Engine starting")
    log.info(f"  Log path   : {cfg.log_path}")
    log.info(f"  Audit log  : {cfg.audit_log_path}")
    log.info(f"  Dashboard  : :{cfg.dashboard_port}")
    log.info(f"  Slack      : {'configured' if cfg.slack_webhook else 'NOT configured'}")
    log.info("=" * 60)

    queue     = asyncio.Queue(maxsize=20_000)
    notifier  = Notifier(cfg)
    blocker   = Blocker(cfg, notifier)
    baseline  = BaselineEngine(cfg)
    detector  = AnomalyDetector(cfg, baseline, blocker, queue)
    monitor   = LogMonitor(cfg, queue)
    unbanner  = Unbanner(cfg, blocker, notifier)
    dashboard = DashboardServer(cfg, baseline, blocker, detector)

    await blocker.setup_chain()

    loop = asyncio.get_running_loop()

    async def _shutdown() -> None:
        log.info("Shutdown signal received — cancelling tasks…")
        for task in asyncio.all_tasks(loop):
            if task is not asyncio.current_task():
                task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(_shutdown()))

    await asyncio.gather(
        monitor.run(),
        detector.run(),
        baseline.run(),
        unbanner.run(),
        dashboard.run(),
        return_exceptions=True,
    )


if __name__ == "__main__":
    asyncio.run(main())