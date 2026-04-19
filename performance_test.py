#!/usr/bin/env python3
"""
CryptoMind Pro Plus AI - 性能压测
模拟高并发：100个并发请求，1000次迭代
"""
import asyncio
import aiohttp
import time
import sys
import os
import statistics
from datetime import datetime

BASE = "http://localhost:8765"

class Colors:
    G, R, Y, B, P = "\033[92m", "\033[91m", "\033[93m", "\033[94m", "\033[95m"
    C, RESET = "\033[96m", "\033[0m"

def banner():
    print(f"""
{Colors.C}╔══════════════════════════════════════════════╗
║   CryptoMind Pro Plus AI - 性能压测          ║
╚══════════════════════════════════════════════╝{Colors.RESET}
""")

async def single_request(session, method, path, sem):
    """单次请求"""
    url = BASE + path
    start = time.perf_counter()
    status = 0
    try:
        async with sem:
            async with session.request(method, url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                status = resp.status
                _ = await resp.json()
                elapsed = (time.perf_counter() - start) * 1000
                return {"status": status, "ms": elapsed, "ok": status == 200, "path": path}
    except asyncio.TimeoutError:
        return {"status": 0, "ms": (time.perf_counter() - start) * 1000, "ok": False, "path": path, "error": "timeout"}
    except Exception as e:
        return {"status": 0, "ms": (time.perf_counter() - start) * 1000, "ok": False, "path": path, "error": str(e)[:30]}

async def run_concurrent_batch(session, requests, concurrency, label):
    """并发批量执行"""
    sem = asyncio.Semaphore(concurrency)
    start = time.time()
    results = await asyncio.gather(*[single_request(session, r["method"], r["path"], sem) for r in requests])
    total_ms = (time.perf_counter() - start) * 1000
    return results, total_ms

def analyze_results(results, total_ms, label):
    ok = [r for r in results if r["ok"]]
    errors = [r for r in results if not r["ok"]]
    latencies = [r["ms"] for r in ok]
    
    p50 = statistics.median(latencies) if latencies else 0
    p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) > 20 else max(latencies, default=0)
    p99 = max(latencies, default=0)
    rps = len(results) / (total_ms / 1000) if total_ms > 0 else 0

    print(f"\n{Colors.B}━━━ {label} ━━━{Colors.RESET}")
    print(f"  请求数: {len(results)} | 成功: {len(ok)} | 失败: {len(errors)}")
    print(f"  成功率: {len(ok)/len(results)*100:.1f}%")
    print(f"  延迟: 均值={statistics.mean(latencies):.0f}ms 中位={p50:.0f}ms P95={p95:.0f}ms P99={p99:.0f}ms")
    print(f"  吞吐: {rps:.1f} req/s | 总耗时: {total_ms:.0f}ms")

    if errors:
        for e in errors[:5]:
            err = e.get("error", f"HTTP {e['status']}")
            print(f"  {Colors.R}{Colors.R}  ❌ {e['path']}: {err}{Colors.RESET}")

    return {"ok": len(ok), "total": len(results), "latencies": latencies, "rps": rps}

async def main():
    banner()

    # ── 连接测试 ──
    print(f"{Colors.C}🔗 测试API连接...{Colors.RESET}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(BASE + "/api/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                result = await resp.json()
                print(f"  ✅ API在线: {result}")
    except Exception as e:
        print(f"  {Colors.R}❌ API连接失败: {e}{Colors.RESET}")
        print(f"  请先启动: python3 api_server.py")
        return

    # ── 压测场景 ──
    scenarios = [
        {
            "label": "场景1: 健康检查 (100并发×10轮)",
            "requests": [{"method": "GET", "path": "/api/health"}] * 100,
            "concurrency": 100,
            "rounds": 10,
        },
        {
            "label": "场景2: BTC价格 (50并发×20轮)",
            "requests": [{"method": "GET", "path": "/api/btc/price"}] * 50,
            "concurrency": 50,
            "rounds": 20,
        },
        {
            "label": "场景3: 技术分析 (20并发×10轮)",
            "requests": [{"method": "GET", "path": "/api/analysis/technical?symbol=BTC&interval=4h"}] * 20,
            "concurrency": 20,
            "rounds": 10,
        },
        {
            "label": "场景4: 多维度分析 (10并发×5轮)",
            "requests": [{"method": "GET", "path": "/api/analysis/multi-dim?symbol=BTC&timeframe=4h"}] * 10,
            "concurrency": 10,
            "rounds": 5,
        },
        {
            "label": "场景5: 全API轮询 (30并发×5轮)",
            "requests": [
                {"method": "GET", "path": "/api/btc/price"},
                {"method": "GET", "path": "/api/analysis/technical"},
                {"method": "GET", "path": "/api/knowledge/stats"},
                {"method": "GET", "path": "/api/validation/report"},
                {"method": "GET", "path": "/api/cleaner/report"},
            ] * 6,
            "concurrency": 30,
            "rounds": 5,
        },
    ]

    summary = []
    async with aiohttp.ClientSession() as session:
        for scenario in scenarios:
            print(f"\n{Colors.P}⚡ {scenario['label']}{Colors.RESET}")
            all_results = []
            total_time = 0

            for round_num in range(scenario["rounds"]):
                results, ms = await run_concurrent_batch(
                    session, scenario["requests"], 
                    scenario["concurrency"], f"Round {round_num+1}/{scenario['rounds']}"
                )
                all_results.extend(results)
                total_time += ms

            r = analyze_results(all_results, total_time, scenario["label"])
            summary.append({"label": scenario["label"], **r})

    # ── 最终报告 ──
    print(f"\n{Colors.G}╔══════════════════════════════════════════════╗")
    print(f"║  压测总结                                    ║")
    print(f"╚══════════════════════════════════════════════╝{Colors.RESET}")
    
    total_requests = sum(s["total"] for s in summary)
    total_ok = sum(s["ok"] for s in summary)
    avg_rps = statistics.mean([s["rps"] for s in summary])
    
    print(f"  总请求: {total_requests} | 成功: {total_ok} | 成功率: {total_ok/total_requests*100:.1f}%")
    print(f"  平均吞吐: {avg_rps:.1f} req/s")
    print(f"\n  场景详情:")
    for s in summary:
        ok_pct = s["ok"]/s["total"]*100
        icon = f"{Colors.G}✅" if ok_pct >= 95 else (f"{Colors.Y}⚠️" if ok_pct >= 70 else f"{Colors.R}❌")
        print(f"  {icon} {s['label'].split(':')[1].strip():<35} {ok_pct:5.1f}%  {s['rps']:.1f} req/s{Colors.RESET}")

if __name__ == "__main__":
    asyncio.run(main())
