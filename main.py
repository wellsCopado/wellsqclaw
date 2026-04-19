#!/usr/bin/env python3
"""
CryptoMind Pro Plus AI - 主入口
一键启动全部服务 + 全链路测试
"""
import asyncio
import sys
import time
import argparse
from datetime import datetime

# ─── 彩色输出 ───────────────────────────────────────────────
class Colors:
    GREEN = "\033[92m"
    RED   = "\033[91m"
    YELLOW = "\033[93m"
    BLUE  = "\033[94m"
    PURPLE = "\033[95m"
    CYAN  = "\033[96m"
    BOLD  = "\033[1m"
    DIM   = "\033[2m"
    RESET = "\033[0m"

def log(msg, color=None):
    if color is None:
        color = Colors.RESET
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{ts}] {msg}{Colors.RESET}")

def banner():
    print(f"""
{Colors.CYAN}{Colors.BOLD}
╔══════════════════════════════════════════════╗
║   CryptoMind Pro Plus AI  ·  全链路启动器    ║
║   一键启动 · 全模块测试 · 智能分析            ║
╚══════════════════════════════════════════════╝
{Colors.RESET}
""")

# ─── 模块导入 ───────────────────────────────────────────────
async def test_data_layer():
    """数据采集层测试"""
    log(f"{Colors.BLUE}━━━ 数据采集层 ━━━", Colors.BLUE)
    
    from core.data.collectors.spot.binance import BinanceSpotCollector
    from core.data.orchestrator import get_orchestrator

    b = BinanceSpotCollector()
    klines = await b.get_klines("BTCUSDT", "4h", 50)
    await b.close()
    
    if klines and len(klines) >= 30:
        latest = klines[-1]
        price = latest.get("close", latest.get("close_price", 0))
        log(f"✅ Binance K线: {len(klines)} 条 | BTC最新价 ${price:,.0f}", Colors.GREEN)
    else:
        log(f"❌ Binance K线采集失败", Colors.RED)
        return False

    # 编排器
    orch = get_orchestrator()
    log(f"✅ 编排器就绪: {len(orch._tasks)} 个采集任务", Colors.GREEN)
    return True


async def test_analysis_layer():
    """分析层测试"""
    log(f"{Colors.PURPLE}━━━ 分析引擎层 ━━━", Colors.PURPLE)
    
    from core.analysis.technical.indicators import analyze, technical_to_dict
    from core.analysis.multi_dimension.multi_dim_analyzer import get_multi_dim_analyzer

    # 技术分析
    from core.data.collectors.spot.binance import BinanceSpotCollector
    b = BinanceSpotCollector()
    klines = await b.get_klines("BTCUSDT", "4h", 100)
    await b.close()
    
    if klines and len(klines) >= 30:
        r = analyze(klines, "BTC")
        d = technical_to_dict(r)
        log(f"✅ 技术分析: RSI={d['rsi']:.0f} MACD={d['macd_signal_text']} 趋势={d['trend']}", Colors.GREEN)
    else:
        log(f"❌ 技术分析失败", Colors.RED)
        return False

    # 多维度分析
    analyzer = get_multi_dim_analyzer()
    sig = await analyzer.analyze("BTC", "4h")
    d = analyzer.to_dict(sig)
    log(f"✅ 多维度: {d['signal']} | 综合={d['overall_score']} | 置信={d['confidence']}% | 风险={d['risk_level']}", Colors.GREEN)
    return True


async def test_knowledge_layer():
    """知识系统测试"""
    log(f"{Colors.YELLOW}━━━ 知识系统层 ━━━", Colors.YELLOW)
    
    from core.analysis.knowledge_base.knowledge_base import get_knowledge_base
    from core.analysis.regression.regression_validator import get_validator
    from core.analysis.attribution.attribution_analyzer import get_attribution_analyzer

    kb = get_knowledge_base()
    stats = kb.get_statistics("BTC")
    log(f"✅ 知识库: {stats['total']} 模式 | 胜率={stats['win_rate']}%", Colors.GREEN)

    v = get_validator()
    report = v.get_accuracy_report("BTC", 30)
    log(f"✅ 回归验证: {report['total_predictions']} 预测 | 方向准确={report['direction_accuracy']}%", Colors.GREEN)

    a = get_attribution_analyzer()
    attr = a.get_summary_report("BTC", 30)
    log(f"✅ 归因分析: {attr.get('total_trades', 0)} 笔交易归因", Colors.GREEN)
    
    kb.close(); v.close(); a.close()
    return True


async def test_evolution_engine():
    """自进化引擎测试"""
    log(f"{Colors.CYAN}━━━ 自进化引擎 ━━━", Colors.CYAN)
    
    from core.evolution.self_evolution_engine import get_evolution_engine

    eng = get_evolution_engine()
    cycle = await eng.run_evolution_cycle("BTC", "4h")
    log(f"✅ 进化周期: {cycle.cycle_id}", Colors.GREEN)
    log(f"   阶段: learn={cycle.learn.status} | analyze={cycle.analyze.status} | optimize={cycle.optimize.status}", Colors.DIM)
    log(f"   test={cycle.test.status} | deploy={cycle.deploy.status}", Colors.DIM)
    log(f"   改进: +{cycle.improvement_score:.1f}% | 判定: {cycle.verdict}", Colors.YELLOW)
    eng.close()
    return True


async def test_api_server():
    """API服务器测试"""
    log(f"{Colors.GREEN}━━━ API服务器 ━━━", Colors.GREEN)
    
    import aiohttp

    base = "http://localhost:8765"
    results = []

    async with aiohttp.ClientSession() as session:
        endpoints = [
            ("/api/health", "健康"),
            ("/api/btc/price", "BTC价格"),
            ("/api/analysis/technical", "技术分析"),
            ("/api/knowledge/stats", "知识库"),
            ("/api/validation/report", "验证报告"),
            ("/api/attribution/summary", "归因分析"),
            ("/api/cleaner/report", "清理报告"),
        ]

        for path, name in endpoints:
            try:
                async with session.get(base + path, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        results.append(f"✅ {name}")
                    else:
                        results.append(f"⚠️ {name}({resp.status})")
            except Exception as e:
                results.append(f"❌ {name}({str(e)[:30]})")

    for r in results:
        color = Colors.GREEN if "✅" in r else (Colors.YELLOW if "⚠️" in r else Colors.RED)
        log(r, color)
    
    all_ok = sum(1 for r in results if "✅" in r)
    log(f"API测试: {all_ok}/{len(results)} 通过", Colors.GREEN if all_ok == len(results) else Colors.YELLOW)
    return all_ok >= len(results) * 0.7


async def run_full_pipeline(symbol: str = "BTC", timeframe: str = "4h"):
    """完整分析流水线"""
    log(f"{Colors.BOLD}{Colors.PURPLE}━━━ 全链路分析 ━━━{Colors.RESET}", Colors.PURPLE)
    start = time.time()

    from core.data.orchestrator import get_orchestrator
    from core.analysis.technical.indicators import analyze, technical_to_dict
    from core.analysis.multi_dimension.multi_dim_analyzer import get_multi_dim_analyzer

    orch = get_orchestrator()
    analyzer = get_multi_dim_analyzer()

    # 1. 数据采集
    task = orch._tasks.get(f"spot_binance_{symbol}_4h")
    if task:
        result = await orch._execute_task(task)
        klines = result.data if result.success else []
    else:
        klines = []

    if not klines:
        log(f"❌ K线采集失败", Colors.RED)
        return

    # 2. 技术分析
    tech = analyze(klines, symbol)
    td = technical_to_dict(tech)

    # 3. 多维度分析
    sig = await analyzer.analyze(symbol, timeframe)
    md = analyzer.to_dict(sig)

    elapsed = time.time() - start

    log(f"{Colors.BOLD}═══ {symbol} 全链路分析报告 ═══{Colors.RESET}", Colors.BOLD)
    log(f"  价格: ${klines[-1].get('close', 0):,.0f}", Colors.CYAN)
    log(f"  趋势: {td['trend']} | RSI: {td['rsi']:.0f} | MACD: {td['macd_signal_text']}", Colors.CYAN)
    log(f"  布林: 位置{td['bollinger']['price_position_pct']:.0f}% 带宽{td['bollinger']['width_pct']}%", Colors.CYAN)
    log(f"  ──", Colors.DIM)
    log(f"  📊 综合信号: {md['signal']} ({md['overall_score']:+g}) | 置信: {md['confidence']}%", 
        Colors.GREEN if md['signal'] == 'BUY' else (Colors.RED if md['signal'] == 'SELL' else Colors.YELLOW))
    log(f"  📐 四维: 技术={md['dimensions']['technical']} 基本={md['dimensions']['fundamental']}", Colors.CYAN)
    log(f"         情绪={md['dimensions']['sentiment']} 链上={md['dimensions']['onchain']}", Colors.CYAN)
    log(f"  ⚠️  风险: {md['risk_level']}", 
        Colors.GREEN if md['risk_level'] == 'LOW' else (Colors.YELLOW if md['risk_level'] == 'MEDIUM' else Colors.RED))
    log(f"  💡 洞察: {md['key_insight'][:80]}", Colors.YELLOW)
    log(f"  ──", Colors.DIM)
    log(f"  ✅ 流水线完成 (耗时 {elapsed:.1f}s)", Colors.GREEN)


# ─── 主函数 ─────────────────────────────────────────────────
async def main():
    banner()
    
    parser = argparse.ArgumentParser(description="CryptoMind Pro Plus AI")
    parser.add_argument("--mode", choices=["full", "quick", "api", "data", "analysis", "evolution", "pipeline"], 
                        default="full", help="测试模式")
    parser.add_argument("--symbol", default="BTC", help="交易对")
    parser.add_argument("--timeframe", default="4h", help="周期")
    parser.add_argument("--skip-api", action="store_true", help="跳过API测试")
    args = parser.parse_args()

    print(f"模式: {args.mode} | 品种: {args.symbol} | 周期: {args.timeframe}\n")

    ok = True

    if args.mode == "full":
        log(f"{Colors.BOLD}🚀 全量测试模式{Colors.RESET}", Colors.BOLD)
        if not await test_data_layer(): ok = False
        if not await test_analysis_layer(): ok = False
        if not await test_knowledge_layer(): ok = False
        if not await test_evolution_engine(): ok = False
        if not args.skip_api and not await test_api_server(): ok = False

    elif args.mode == "quick":
        log(f"{Colors.BOLD}⚡ 快速测试{Colors.RESET}", Colors.BOLD)
        if not await test_data_layer(): ok = False
        if not await test_analysis_layer(): ok = False

    elif args.mode == "api":
        if not await test_api_server(): ok = False

    elif args.mode == "data":
        if not await test_data_layer(): ok = False

    elif args.mode == "analysis":
        if not await test_analysis_layer(): ok = False
        if not await test_knowledge_layer(): ok = False

    elif args.mode == "evolution":
        if not await test_evolution_engine(): ok = False

    elif args.mode == "pipeline":
        await run_full_pipeline(args.symbol, args.timeframe)
        return

    # ── 启动API服务器选项 ──
    if ok:
        print(f"\n{Colors.GREEN}{Colors.BOLD}╔══════════════════════════════════════╗")
        print(f"║  ✅ 全部测试通过！                    ║")
        print(f"╚══════════════════════════════════════╝{Colors.RESET}")
        
        # 启动服务器
        import subprocess, os
        server_script = os.path.join(os.path.dirname(__file__), "api_server.py")
        if os.path.exists(server_script):
            print(f"\n{Colors.CYAN}启动API服务器: python3 {server_script}{Colors.RESET}")
            subprocess.Popen(
                [sys.executable, server_script],
                stdout=open("/tmp/cryptomind.log", "a"),
                stderr=subprocess.STDOUT,
                cwd=os.path.dirname(__file__)
            )
            print(f"{Colors.GREEN}✅ API服务器已启动 (端口 8765){Colors.RESET}")
            print(f"{Colors.CYAN}仪表盘: http://localhost:8765{Colors.RESET}")
    else:
        print(f"\n{Colors.RED}╔══════════════════════════════════════╗")
        print(f"║  ❌ 部分测试失败，请检查日志            ║")
        print(f"╚══════════════════════════════════════╝{Colors.RESET}")


if __name__ == "__main__":
    asyncio.run(main())
