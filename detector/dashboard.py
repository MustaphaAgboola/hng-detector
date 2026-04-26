async def _handle_stats(self, req):
    w_stats = await self.detector.stats()   # top IPs, global RPS
    snap    = self.baseline.snapshot()       # mean, stddev, hour data
    bans    = await self.blocker.bans_snapshot()

    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory()

    return web.json_response({
        "global_rps":  w_stats.global_rps,
        "top_ips":     w_stats.top_ips,
        "bans":        bans,
        "baseline": {
            "mean":           snap.mean * 60,  # convert rps → rpm
            "stddev":         snap.stddev * 60,
            "source":         snap.source,
            "hour_snapshots": snap.hour_snapshots,  # for the graph
        },
        "system": {
            "cpu_pct":      cpu,
            "mem_pct":      mem.percent,
            "uptime_human": _fmt_uptime(int(time.time() - START)),
        }
    })