import asyncio
import argparse
import random
import time
import aiohttp

PAGES = [
    "/", "/index.php", "/apps/files/",
    "/ocs/v2.php/cloud/capabilities",
    "/remote.php/dav", "/login",
    "/nonexistent-will-404",
]


async def fire(session, base, ip=None):
    url  = base + random.choice(PAGES)
    hdrs = {"X-Forwarded-For": ip} if ip else {}
    try:
        async with session.get(
            url, headers=hdrs, timeout=aiohttp.ClientTimeout(total=4)
        ):
            pass
    except Exception:
        pass


async def normal(base, duration=90, rpm=40):
    print(f"[NORMAL] {rpm} RPM from diverse IPs for {duration}s — building baseline...")
    conn = aiohttp.TCPConnector(limit=20)
    async with aiohttp.ClientSession(connector=conn) as s:
        end = time.time() + duration
        while time.time() < end:
            ip = f"10.{random.randint(0,254)}.{random.randint(0,254)}.{random.randint(1,254)}"
            await fire(s, base, ip)
            await asyncio.sleep(60 / rpm)


async def attack(base, ip="192.168.100.99", duration=30, rpm=10000):
    print(f"[ATTACK] {rpm} RPM from single IP {ip} for {duration}s — should trigger ban...")
    conn = aiohttp.TCPConnector(limit=60)
    async with aiohttp.ClientSession(connector=conn) as s:
        end = time.time() + duration
        while time.time() < end:
            await asyncio.gather(*[fire(s, base, ip) for _ in range(10)])
            await asyncio.sleep(10 * 60 / rpm)


async def spike(base, duration=20):
    print(f"[SPIKE] 10x traffic surge from 200 IPs for {duration}s — should trigger global alert...")
    conn = aiohttp.TCPConnector(limit=200)
    async with aiohttp.ClientSession(connector=conn) as s:
        end = time.time() + duration
        while time.time() < end:
            ips = [
                f"172.{random.randint(16,31)}.{random.randint(0,254)}.{random.randint(1,254)}"
                for _ in range(20)
            ]
            await asyncio.gather(*[fire(s, base, ip) for ip in ips])
            await asyncio.sleep(0.1)


async def _delayed(coro, delay):
    await asyncio.sleep(delay)
    await coro


async def run_all(base):
    await asyncio.gather(
        normal(base, duration=120),
        _delayed(attack(base), 95),
        _delayed(spike(base), 110),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--host",     default="http://localhost")
    p.add_argument("--scenario", choices=["normal","attack","spike","all"], default="all")
    args = p.parse_args()

    scenarios = {
        "normal": lambda: normal(args.host),
        "attack": lambda: attack(args.host),
        "spike":  lambda: spike(args.host),
        "all":    lambda: run_all(args.host),
    }
    asyncio.run(scenarios[args.scenario]())