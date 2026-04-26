import asyncio
import logging
import time
from pathlib import Path

import psutil
from aiohttp import web

log = logging.getLogger("dashboard")

_START = time.time()


def _fmt_uptime(s):
    h, r   = divmod(int(s), 3600)
    m, sec = divmod(r, 60)
    return f"{h:02d}h {m:02d}m {sec:02d}s"


class DashboardServer:
    def __init__(self, cfg, baseline, blocker, detector):
        self.cfg      = cfg
        self.baseline = baseline
        self.blocker  = blocker
        self.detector = detector

    async def run(self):
        app = web.Application()
        app.router.add_get("/",                 self._ui)
        app.router.add_get("/api/stats",        self._stats)
        app.router.add_get("/api/bans",         self._bans)
        app.router.add_get("/api/audit",        self._audit)
        app.router.add_delete("/api/bans/{ip}", self._unban)

        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self.cfg.dashboard_port)
        await site.start()
        log.info(f"Dashboard live on :{self.cfg.dashboard_port}")
        while True:
            await asyncio.sleep(3600)

    async def _stats(self, _r):
        ws   = await self.detector.stats()
        snap = self.baseline.snapshot()
        bans = await self.blocker.bans_snapshot()
        cpu  = psutil.cpu_percent(interval=None)
        mem  = psutil.virtual_memory()
        return web.json_response({
            "global_rps":     ws.global_rps,
            "global_rpm":     round(ws.global_rps * 60, 2),
            "top_ips":        ws.top_ips,
            "active_ips":     ws.active_ips,
            "total_requests": ws.total_processed,
            "banned_count":   len(bans),
            "bans":           bans,
            "baseline": {
                "mean":           round(snap.mean * 60, 3),
                "stddev":         round(snap.stddev * 60, 3),
                "error_mean":     round(snap.error_mean, 6),
                "samples":        snap.samples,
                "source":         snap.source,
                "hour_snapshots": {str(h): round(v * 60, 3) for h, v in snap.hour_snapshots.items()},
            },
            "system": {
                "cpu_pct":      cpu,
                "mem_pct":      mem.percent,
                "mem_used_mb":  round(mem.used / 1_048_576, 1),
                "mem_total_mb": round(mem.total / 1_048_576, 1),
                "uptime_s":     int(time.time() - _START),
                "uptime_human": _fmt_uptime(time.time() - _START),
            },
            "ts": time.time(),
        })

    async def _bans(self, _r):
        return web.json_response(await self.blocker.bans_snapshot())

    async def _audit(self, _r):
        p = Path(self.cfg.audit_log_path)
        if not p.exists():
            return web.json_response([])
        return web.json_response(p.read_text().splitlines()[-200:])

    async def _unban(self, req):
        ip   = req.match_info["ip"]
        bans = await self.blocker.get_bans()
        if ip not in bans:
            return web.json_response({"error": "not found"}, status=404)
        await self.blocker.unban(ip)
        return web.json_response({"ok": True, "unblocked": ip})

    async def _ui(self, _r):
        return web.Response(content_type="text/html", text=_HTML)


_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>cloud.ng — Anomaly Detector</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:#0d1117;color:#e6edf3;min-height:100vh}
header{background:#161b22;border-bottom:1px solid #30363d;padding:14px 24px;
  display:flex;align-items:center;justify-content:space-between}
h1{font-size:16px;font-weight:600}
.dot{width:8px;height:8px;border-radius:50%;background:#3fb950;
  animation:pulse 2s infinite;display:inline-block;margin-right:6px}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.badge{font-size:11px;background:#21262d;border:1px solid #30363d;
  border-radius:12px;padding:2px 10px;color:#8b949e}
main{padding:20px 24px;max-width:1300px;margin:0 auto}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:12px;margin-bottom:18px}
.card{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px 16px}
.card-label{font-size:10px;color:#8b949e;text-transform:uppercase;letter-spacing:.07em;margin-bottom:5px}
.card-value{font-size:24px;font-weight:700}
.green{color:#3fb950}.red{color:#f85149}.yellow{color:#d29922}.blue{color:#58a6ff}
.row2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
@media(max-width:700px){.row2{grid-template-columns:1fr}}
.panel{background:#161b22;border:1px solid #30363d;border-radius:10px;margin-bottom:12px}
.panel-hd{padding:10px 16px;border-bottom:1px solid #30363d;font-size:13px;font-weight:600;
  display:flex;justify-content:space-between;align-items:center}
.panel-hd small{font-size:10px;color:#8b949e;font-weight:400}
table{width:100%;border-collapse:collapse;font-size:12px}
th{padding:7px 14px;text-align:left;color:#8b949e;font-weight:500;border-bottom:1px solid #30363d}
td{padding:7px 14px;border-bottom:1px solid #21262d}
tr:last-child td{border-bottom:none}
.pill{display:inline-block;padding:1px 7px;border-radius:3px;font-size:10px;font-weight:700}
.pr{background:#3d1616;color:#f85149}.pg{background:#122117;color:#3fb950}
.py{background:#2d2009;color:#d29922}.pb{background:#0c2035;color:#58a6ff}
.audit-box{background:#0d1117;border-radius:0 0 10px 10px;max-height:220px;overflow-y:auto;
  padding:10px 14px;font-family:monospace;font-size:11px;line-height:1.7;color:#8b949e}
.ab{color:#f85149}.au{color:#3fb950}.ab2{color:#58a6ff}.ag{color:#d29922}
.bar-row{display:flex;align-items:center;gap:8px;margin-bottom:5px;font-size:11px}
.bar-label{width:36px;color:#8b949e;text-align:right;flex-shrink:0}
.bar-track{flex:1;background:#21262d;border-radius:3px;height:14px;overflow:hidden}
.bar-fill{height:100%;background:#58a6ff;border-radius:3px;transition:width .4s}
.bar-val{width:65px;color:#e6edf3;flex-shrink:0}
</style>
</head>
<body>
<header>
  <div style="display:flex;align-items:center;gap:8px">
    <span class="dot"></span>
    <h1>cloud.ng &mdash; Anomaly Detection Engine</h1>
  </div>
  <div style="display:flex;gap:8px">
    <span class="badge" id="uptime-b">uptime: —</span>
    <span class="badge" id="refresh-b">—</span>
  </div>
</header>
<main>
<div class="grid">
  <div class="card"><div class="card-label">Global req/s</div><div class="card-value green" id="v-rps">—</div></div>
  <div class="card"><div class="card-label">Global RPM</div><div class="card-value" id="v-rpm">—</div></div>
  <div class="card"><div class="card-label">Banned IPs</div><div class="card-value red" id="v-bans">—</div></div>
  <div class="card"><div class="card-label">Baseline mean RPM</div><div class="card-value green" id="v-mean">—</div></div>
  <div class="card"><div class="card-label">Baseline stddev</div><div class="card-value" id="v-std">—</div></div>
  <div class="card"><div class="card-label">Baseline source</div><div class="card-value blue" id="v-src" style="font-size:14px">—</div></div>
  <div class="card"><div class="card-label">CPU</div><div class="card-value" id="v-cpu">—</div></div>
  <div class="card"><div class="card-label">Memory</div><div class="card-value" id="v-mem">—</div></div>
</div>
<div class="row2">
  <div class="panel">
    <div class="panel-hd">Banned IPs <small id="ban-count">0</small></div>
    <table><thead><tr><th>IP</th><th>Lvl</th><th>TTL</th><th>Condition</th><th>Rate</th><th></th></tr></thead>
    <tbody id="ban-tb"></tbody></table>
  </div>
  <div class="panel">
    <div class="panel-hd">Top 10 Source IPs <small>last 60s</small></div>
    <table><thead><tr><th>#</th><th>IP</th><th>RPM</th></tr></thead>
    <tbody id="top-tb"></tbody></table>
  </div>
</div>
<div class="panel">
  <div class="panel-hd">Baseline per-hour effective mean (RPM) <small>hourly slots</small></div>
  <div style="padding:14px 16px" id="graph"></div>
</div>
<div class="panel">
  <div class="panel-hd">Audit Log <small>last 200 entries</small></div>
  <div class="audit-box" id="audit-log">Loading...</div>
</div>
</main>
<script>
const R=3000;let auditTs=0;
function set(id,v){const e=document.getElementById(id);if(e)e.textContent=v}
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
async function go(){
  try{
    const s=await fetch('/api/stats').then(r=>r.json());
    set('v-rps',s.global_rps.toFixed(3));
    set('v-rpm',s.global_rpm.toFixed(1));
    set('v-bans',s.banned_count);
    set('v-mean',s.baseline.mean.toFixed(2));
    set('v-std',s.baseline.stddev.toFixed(2));
    set('v-src',s.baseline.source);
    set('v-cpu',s.system.cpu_pct.toFixed(1)+'%');
    set('v-mem',s.system.mem_pct.toFixed(1)+'%');
    set('uptime-b','uptime: '+s.system.uptime_human);
    set('refresh-b','updated '+new Date().toLocaleTimeString());
    set('ban-count',s.bans.length);
    const bt=document.getElementById('ban-tb');
    bt.innerHTML=s.bans.length?s.bans.map(b=>`<tr>
      <td><span class="pill pr">${esc(b.ip)}</span></td>
      <td>${b.level}</td>
      <td>${b.ttl<0?'∞':Math.ceil(b.ttl)+'s'}</td>
      <td style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
        font-size:10px;color:#8b949e">${esc(b.condition)}</td>
      <td>${b.rate.toFixed(1)}</td>
      <td><button onclick="unban('${esc(b.ip)}')" style="all:unset;cursor:pointer;
        background:#3d1616;color:#f85149;border:1px solid #5a2020;border-radius:4px;
        padding:2px 8px;font-size:10px">Unban</button></td>
    </tr>`).join('')
    :'<tr><td colspan="6" style="color:#3fb950;text-align:center;padding:12px">No active bans ✓</td></tr>';
    const tt=document.getElementById('top-tb');
    tt.innerHTML=s.top_ips.length?s.top_ips.map(([ip,rpm],i)=>`<tr>
      <td style="color:#8b949e">${i+1}</td><td>${esc(ip)}</td>
      <td><span class="pill ${rpm>300?'pr':rpm>100?'py':'pg'}">${rpm} rpm</span></td>
    </tr>`).join('')
    :'<tr><td colspan="3" style="color:#8b949e;text-align:center;padding:12px">No traffic yet</td></tr>';
    const snaps=s.baseline.hour_snapshots;
    const hours=Object.keys(snaps).map(Number).sort((a,b)=>a-b);
    const maxV=Math.max(...Object.values(snaps),1);
    const gw=document.getElementById('graph');
    gw.innerHTML=hours.length?hours.map(h=>{
      const v=snaps[h],pct=Math.min(100,(v/maxV)*100).toFixed(1);
      return`<div class="bar-row">
        <span class="bar-label">${String(h).padStart(2,'0')}:00</span>
        <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
        <span class="bar-val">${v.toFixed(2)} rpm</span>
      </div>`;}).join('')
    :'<p style="color:#8b949e;font-size:12px">Building hourly data...</p>';
    if(Date.now()-auditTs>10000){
      auditTs=Date.now();
      const lines=await fetch('/api/audit').then(r=>r.json());
      const al=document.getElementById('audit-log');
      al.innerHTML=lines.slice().reverse().map(l=>{
        const c=l.includes(' BAN ')?'ab':l.includes(' UNBAN ')?'au':
          l.includes('BASELINE')?'ab2':l.includes('GLOBAL')?'ag':'';
        return`<div class="${c}">${esc(l)}</div>`;
      }).join('')||'<span>No entries yet.</span>';
    }
  }catch(e){console.error(e)}
}
async function unban(ip){await fetch('/api/bans/'+ip,{method:'DELETE'});go()}
go();setInterval(go,R);
</script>
</body>
</html>"""