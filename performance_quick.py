#!/usr/bin/env python3
"""快速性能压测 - 只测试轻量级端点"""
import asyncio, aiohttp, time, statistics

BASE = "http://localhost:8765"

async def test_endpoint(session, method, path, sem):
    async with sem:
        t0 = time.perf_counter()
        try:
            async with session.request(method, BASE+path, timeout=aiohttp.ClientTimeout(total=8)) as r:
                await r.json()
                return time.perf_counter()-t0, r.status
        except Exception as e:
            return time.perf_counter()-t0, 0

async def main():
    print("🚀 CryptoMind Pro Plus AI - 快速压测\n")
    
    # 连接检查
    async with aiohttp.ClientSession() as s:
        async with s.get(BASE+"/api/health", timeout=aiohttp.ClientTimeout(total=5)) as r:
            print(f"  ✅ API在线: {await r.json()}\n")
    
    scenarios = [
        ("健康检查", 200, 50),       # 200并发×50轮
        ("BTC价格", 100, 50),       # 100并发×50轮
        ("技术分析", 10, 5),        # 10并发×5轮
        ("清理报告", 50, 20),       # 50并发×20轮
    ]
    
    results_summary = []
    async with aiohttp.ClientSession() as s:
        for name, concurrency, rounds in scenarios:
            paths = {
                "健康检查": "/api/health",
                "BTC价格": "/api/btc/price", 
                "技术分析": "/api/analysis/technical?symbol=BTC&interval=4h",
                "清理报告": "/api/cleaner/report",
            }
            path = paths[name]
            sem = asyncio.Semaphore(concurrency)
            
            print(f"⚡ {name} ({concurrency}并发 × {rounds}轮)...")
            t0 = time.time()
            times = []
            ok_count = 0
            err_count = 0
            
            for _ in range(rounds):
                tasks = [test_endpoint(s, "GET", path, sem) for _ in range(concurrency)]
                batch = await asyncio.gather(*tasks)
                for dt, status in batch:
                    times.append(dt*1000)
                    if status == 200: ok_count += 1
                    else: err_count += 1
            
            total_ms = (time.time()-t0)*1000
            total = ok_count + err_count
            rps = total / (total_ms/1000)
            mean = statistics.mean(times)
            p95 = statistics.quantiles(times, n=20)[18] if len(times)>20 else max(times, default=0)
            
            ok_pct = ok_count/total*100
            icon = "✅" if ok_pct>=95 else ("⚠️" if ok_pct>=70 else "❌")
            print(f"   {icon} {ok_pct:.0f}% OK | 均值{mean:.0f}ms P95={p95:.0f}ms | {rps:.0f} req/s")
            results_summary.append((name, ok_pct, mean, p95, rps))
    
    print(f"\n╔══════════════════════════════════════╗")
    print(f"║  压测总结                             ║")
    print(f"╚══════════════════════════════════════╝")
    for name, ok, mean, p95, rps in results_summary:
        icon = "✅" if ok>=95 else ("⚠️" if ok>=70 else "❌")
        print(f"  {icon} {name:<10} {ok:5.1f}%  均值{mean:5.0f}ms  P95={p95:5.0f}ms  {rps:6.0f} r/s")

asyncio.run(main())
