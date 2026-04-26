async def main():
    cfg = config.load()

    queue     = asyncio.Queue(maxsize=20_000)
    notifier  = Notifier(cfg)
    blocker   = Blocker(cfg, notifier)
    baseline  = BaselineEngine(cfg)
    detector  = AnomalyDetector(cfg, baseline, blocker, queue)
    monitor   = LogMonitor(cfg, queue)
    unbanner  = Unbanner(cfg, blocker, notifier)
    dashboard = DashboardServer(cfg, baseline, blocker, detector)

    await blocker.setup_chain()   # create iptables chain before traffic arrives

    await asyncio.gather(
        monitor.run(),    # tails log → pushes LogEntry to queue
        detector.run(),   # consumes queue → triggers bans
        baseline.run(),   # recalculates every 60s
        unbanner.run(),   # releases expired bans every 30s
        dashboard.run(),  # serves web UI on :8080
    )