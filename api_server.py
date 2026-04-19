"""
CryptoMind Pro Plus AI - FastAPI 后端
提供真实 API 数据的 REST API

⚠️ 免责声明 / DISCLAIMER ⚠️
本系统提供的所有分析、信号、建议仅供参考，不构成任何投资建议。
加密货币交易具有高风险，可能导致全部本金损失。
使用者应自行承担所有交易风险和决策责任。
All analyses, signals, and suggestions are for reference only and do NOT constitute
investment advice. Crypto trading carries high risk including total capital loss.
Users bear full responsibility for all trading decisions.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import hashlib
import json
import time
from collections import defaultdict
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Optional

from core.data.collectors.spot.binance import BinanceSpotCollector
from core.data.collectors.spot.okx import OKXSpotCollector
from core.data.collectors.spot.bybit import BybitSpotCollector
from core.data.collectors.derivatives import get_coinglass_collector
from core.trading.paper_trading import PaperTradingEngine
from core.data.backup_manager import BackupManager
from core.utils.logger import logger
from config.config_manager import config_manager

app = FastAPI(title="CryptoMind Pro Plus API", version="6.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化组件
binance = BinanceSpotCollector()
okx = OKXSpotCollector()
bybit = BybitSpotCollector()
coinglass = get_coinglass_collector()
paper_trading = PaperTradingEngine()
backup_mgr = BackupManager()

# ==================== 认证 + 限流 ====================
API_KEYS_FILE = os.path.join(os.path.dirname(__file__), "data", "api_keys.json")

def _load_api_keys() -> dict:
    if os.path.exists(API_KEYS_FILE):
        with open(API_KEYS_FILE) as f:
            return json.load(f)
    default_key = "cmp_free_" + hashlib.sha256(b"cryptomind_default_2026").hexdigest()[:16]
    keys = {
        hashlib.sha256(default_key.encode()).hexdigest(): {
            "name": "default_free",
            "created": int(time.time()),
            "active": True,
            "tier": "free",
            "rate_limit": 60
        }
    }
    os.makedirs(os.path.dirname(API_KEYS_FILE), exist_ok=True)
    with open(API_KEYS_FILE, "w") as f:
        json.dump(keys, f, indent=2, ensure_ascii=False)
    logger.info(f"默认API Key已生成: {default_key}")
    return keys

_api_keys_db = _load_api_keys()

async def verify_api_key(request: Request):
    key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if not key:
        return JSONResponse(status_code=401, content={"detail": "Missing API key"})
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    key_info = _api_keys_db.get(key_hash)
    if not key_info or not key_info.get("active"):
        return JSONResponse(status_code=403, content={"detail": "Invalid API key"})
    return key_info

# 限流
_rate_limit_store = defaultdict(list)

@app.middleware("http")
async def auth_and_rate_limit(request: Request, call_next):
    whitelist = ["/api/health", "/docs", "/openapi.json", "/redoc", "/", "/dashboard"]
    if any(request.url.path.startswith(p) for p in whitelist):
        return await call_next(request)
    
    key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if not key:
        return JSONResponse(status_code=401, content={"detail": "Missing API key"})
    
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    key_info = _api_keys_db.get(key_hash)
    if not key_info or not key_info.get("active"):
        return JSONResponse(status_code=403, content={"detail": "Invalid API key"})
    
    now = time.time()
    window = 60
    limit = key_info.get("rate_limit", 60)
    _rate_limit_store[key_hash] = [t for t in _rate_limit_store[key_hash] if now - t < window]
    if len(_rate_limit_store[key_hash]) >= limit:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
    _rate_limit_store[key_hash].append(now)
    
    return await call_next(request)

# 审计日志
_audit_log_file = os.path.join(os.path.dirname(__file__), "data", "audit.log")

def audit_log(request: Request, action: str, detail: str = ""):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "ip": request.client.host if request.client else "unknown",
        "action": action,
        "detail": detail,
        "path": request.url.path
    }
    os.makedirs(os.path.dirname(_audit_log_file), exist_ok=True)
    with open(_audit_log_file, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

# ==================== API端点 ====================

@app.get("/api/health")
async def health():
    """深度健康检查 - 默认启用深度检查"""
    return await health_detail()

@app.get("/api/health/detail")
async def health_detail():
    """深度健康检查（含依赖状态）"""
    checks = {}
    
    # 1. SQLite
    try:
        import sqlite3
        db_path = os.path.join(os.path.dirname(__file__), "data", "crypto.db")
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            conn.execute("SELECT 1")
            conn.close()
            checks["database"] = {"status": "ok"}
        else:
            checks["database"] = {"status": "warning", "detail": "crypto.db not found"}
    except Exception as e:
        checks["database"] = {"status": "error", "detail": str(e)}
    
    # 2. Binance API
    try:
        price = await binance.get_price("BTCUSDT")
        checks["binance"] = {"status": "ok", "btc_price": price} if price else {"status": "error"}
    except Exception as e:
        checks["binance"] = {"status": "error", "detail": str(e)[:100]}
    
    # 3. OKX API
    try:
        okx_price = await okx.get_price("BTCUSDT")
        checks["okx"] = {"status": "ok", "btc_price": okx_price} if okx_price else {"status": "error"}
    except Exception as e:
        checks["okx"] = {"status": "error", "detail": str(e)[:100]}
    
    # 4. Bybit API
    try:
        bybit_price = await bybit.get_price("BTCUSDT")
        checks["bybit"] = {"status": "ok", "btc_price": bybit_price} if bybit_price else {"status": "error"}
    except Exception as e:
        checks["bybit"] = {"status": "error", "detail": str(e)[:100]}
    
    # 5. Ollama
    try:
        import urllib.request
        resp = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
        checks["ollama"] = {"status": "ok"}
    except Exception:
        checks["ollama"] = {"status": "warning", "detail": "Ollama not running (cloud fallback active)"}
    
    # 6. Paper Trading
    try:
        acct = paper_trading.get_account()
        checks["paper_trading"] = {"status": "ok", "balance": acct.get("balance", 0)}
    except Exception as e:
        checks["paper_trading"] = {"status": "error", "detail": str(e)[:100]}
    
    # 7. Backup
    try:
        checks["backup"] = {"status": "ok", "stats": backup_mgr.get_stats()}
    except Exception as e:
        checks["backup"] = {"status": "error", "detail": str(e)[:100]}
    
    # 8. 数据新鲜度检查
    try:
        from core.data.storage import get_storage
        storage = get_storage()
        latest = storage.get_latest_timestamp("BTCUSDT", "1h")
        if latest:
            age_minutes = (time.time() - latest) / 60
            if age_minutes < 5:
                freshness = {"status": "ok", "age_minutes": round(age_minutes, 1)}
            elif age_minutes < 30:
                freshness = {"status": "warning", "age_minutes": round(age_minutes, 1)}
            else:
                freshness = {"status": "error", "age_minutes": round(age_minutes, 1), "detail": "Data stale"}
        else:
            freshness = {"status": "warning", "detail": "No data timestamp available"}
        checks["data_freshness"] = freshness
    except Exception as e:
        checks["data_freshness"] = {"status": "error", "detail": str(e)[:100]}
    
    overall = "ok" if all(c.get("status") != "error" for c in checks.values()) else "degraded"
    return {
        "status": overall,
        "checks": checks,
        "timestamp": int(time.time() * 1000),
        "disclaimer": "本系统提供的所有分析仅供参考，不构成投资建议。加密货币交易具有高风险。"
    }

@app.get("/api/btc/price")
async def btc_price():
    """BTC 实时价格 - 带故障切换"""
    for exchange, collector in [("binance", binance), ("okx", okx), ("bybit", bybit)]:
        try:
            price = await collector.get_price("BTCUSDT")
            if price:
                return {
                    "symbol": "BTCUSDT",
                    "price": price,
                    "source": exchange,
                    "timestamp": int(time.time() * 1000),
                    "disclaimer": "价格数据仅供参考，交易请以交易所为准。"
                }
        except Exception as e:
            logger.warning(f"{exchange} price fetch failed: {e}")
            continue
    return {"error": "All price sources failed", "disclaimer": "数据获取失败，请稍后重试。"}

@app.get("/api/market/top")
async def top_coins(symbols: str = "BTC,ETH,SOL,BNB,XRP"):
    """热门币种行情"""
    result = []
    for sym in symbols.split(","):
        try:
            price = await binance.get_price(f"{sym}USDT")
            if price:
                result.append({"symbol": sym, "price": price})
        except Exception as e:
            logger.warning(f"Failed to get {sym} price: {e}")
    return {"coins": result, "disclaimer": "行情数据仅供参考。"}

@app.get("/api/derivatives/summary")
async def derivatives_summary(symbol: str = "BTC"):
    """衍生品数据汇总"""
    try:
        funding = await coinglass.get_funding_rate(symbol)
        oi = await coinglass.get_open_interest(symbol)
        return {
            "symbol": symbol,
            "funding_rate": funding,
            "open_interest": oi,
            "disclaimer": "衍生品数据仅供参考。"
        }
    except Exception as e:
        return {"error": str(e), "disclaimer": "数据获取失败。"}

@app.get("/api/signal")
async def signal_analysis(symbol: str = "BTC"):
    """信号分析 - 带免责声明"""
    try:
        from core.analytics.signal_analyzer import get_analyzer
        analyzer = get_analyzer()
        result = await analyzer.analyze(symbol)
        result["disclaimer"] = "本信号仅供参考，不构成投资建议。加密货币交易具有高风险。"
        return result
    except Exception as e:
        return {"error": str(e), "disclaimer": "分析失败，请稍后重试。"}

@app.get("/api/onchain/ethereum")
async def ethereum_onchain():
    """以太坊链上数据"""
    try:
        from core.data.collectors.onchain.ethereum import get_ethereum_collector
        collector = get_ethereum_collector()
        data = await collector.get_metrics()
        return {"data": data, "disclaimer": "链上数据仅供参考。"}
    except Exception as e:
        return {"error": str(e), "disclaimer": "数据获取失败。"}

@app.get("/api/onchain/bitcoin")
async def bitcoin_onchain():
    """比特币链上数据"""
    try:
        from core.data.collectors.onchain.bitcoin import get_bitcoin_collector
        collector = get_bitcoin_collector()
        data = await collector.get_metrics()
        return {"data": data, "disclaimer": "链上数据仅供参考。"}
    except Exception as e:
        return {"error": str(e), "disclaimer": "数据获取失败。"}

@app.get("/api/news")
async def crypto_news(max_items: int = 30):
    """加密货币新闻"""
    try:
        from core.data.collectors.news.crypto_news import get_news_collector
        collector = get_news_collector()
        news = await collector.get_news(limit=max_items)
        return {"news": news, "disclaimer": "新闻内容仅供参考，不构成投资建议。"}
    except Exception as e:
        return {"error": str(e), "disclaimer": "新闻获取失败。"}

@app.get("/api/knowledge/stats")
async def knowledge_stats():
    """知识库统计"""
    try:
        from core.analysis.knowledge_base.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        stats = kb.get_stats()
        return {"stats": stats, "disclaimer": "知识库数据仅供参考。"}
    except Exception as e:
        return {"error": str(e), "disclaimer": "数据获取失败。"}

@app.get("/api/validation/report")
async def validation_report():
    """验证报告"""
    try:
        from core.analysis.regression.regression_validator import get_validator
        validator = get_validator()
        report = validator.get_accuracy_report()
        return {"report": report, "disclaimer": "验证结果仅供参考。"}
    except Exception as e:
        return {"error": str(e), "disclaimer": "报告获取失败。"}

@app.get("/api/attribution/summary")
async def attribution_summary():
    """归因分析摘要"""
    try:
        from core.analysis.attribution.attribution_analyzer import get_analyzer
        analyzer = get_analyzer()
        summary = analyzer.get_summary()
        return {"summary": summary, "disclaimer": "归因分析仅供参考。"}
    except Exception as e:
        return {"error": str(e), "disclaimer": "分析获取失败。"}

@app.get("/api/trading/account")
async def trading_account():
    """模拟交易账户"""
    try:
        acct = paper_trading.get_account()
        return {"account": acct, "disclaimer": "模拟交易数据，非真实资金。"}
    except Exception as e:
        return {"error": str(e), "disclaimer": "数据获取失败。"}

@app.post("/api/trading/order")
async def trading_order(request: Request):
    """模拟下单"""
    try:
        data = await request.json()
        result = paper_trading.place_order(
            symbol=data.get("symbol", "BTC"),
            side=data.get("side", "buy"),
            quantity=data.get("quantity", 0.1),
            order_type=data.get("order_type", "market")
        )
        audit_log(request, "PAPER_TRADE", f"{data.get('side')} {data.get('quantity')} {data.get('symbol')}")
        return {"result": result, "disclaimer": "模拟交易，非真实下单。"}
    except Exception as e:
        return {"error": str(e), "disclaimer": "下单失败。"}

@app.get("/")
async def dashboard():
    """Dashboard主页"""
    try:
        with open("dashboard.html", "r", encoding="utf-8") as f:
            html = f.read()
        return HTMLResponse(content=html)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Dashboard Error</h1><p>{e}</p>", status_code=500)

@app.get("/dashboard")
async def dashboard2():
    """Dashboard别名"""
    return await dashboard()



# ==================== K线 + 实时推送端点 ====================

@app.get("/api/klines")
async def get_klines(symbol: str = "BTCUSDT", interval: str = "1h", limit: int = 200):
    """获取K线数据"""
    try:
        from core.data.storage import get_db
        db = get_db()
        klines = db.get_klines(symbol, interval, limit=limit)
        return {"klines": klines, "symbol": symbol, "interval": interval}
    except Exception as e:
        return {"klines": [], "error": str(e), "symbol": symbol, "interval": interval}

@app.get("/api/all")
async def get_all_data():
    """聚合所有实时数据（供轮询）"""
    try:
        result = {"timestamp": int(time.time() * 1000)}
        
        # BTC价格
        for exchange, collector in [("binance", binance), ("okx", okx), ("bybit", bybit)]:
            try:
                price = await collector.get_price("BTCUSDT")
                if price:
                    result["btc_price"] = price
                    result["price_source"] = exchange
                    break
            except:
                continue
        
        # 简洁信号
        try:
            from core.analytics.signal_analyzer import get_analyzer
            analyzer = get_analyzer()
            signal = await analyzer.analyze("BTC")
            result["signal"] = signal.get("signal", "NEUTRAL")
            result["confidence"] = signal.get("confidence", 0)
        except:
            pass
        
        return result
    except Exception as e:
        return {"timestamp": int(time.time() * 1000), "error": str(e)}

@app.get("/api/sse/stream")
async def sse_stream(request: Request):
    """SSE实时推送端点"""
    async def event_generator():
        import asyncio
        while True:
            try:
                price = None
                for ex, col in [("binance", binance), ("okx", okx), ("bybit", bybit)]:
                    try:
                        p = await col.get_price("BTCUSDT")
                        if p:
                            price = p
                            break
                    except:
                        continue
                
                import datetime
                msg = {"type": "tick", "timestamp": int(datetime.datetime.now().timestamp() * 1000), "btc_price": price, "status": "ok"}
                yield "data: " + json.dumps(msg, ensure_ascii=False) + "\n\n"
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                err = {"error": str(e)}
                yield "data: " + json.dumps(err, ensure_ascii=False) + "\n\n"
                await asyncio.sleep(10)
    
    from fastapi.responses import StreamingResponse
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/trading/positions")
async def trading_positions():
    """获取当前持仓"""
    try:
        positions = paper_trading.get_positions()
        return {"positions": positions}
    except Exception as e:
        return {"positions": [], "error": str(e)}



# ═══════════════════════════════════════════════════════════════
# 补充端点（docs/API.md中列出但缺失的）
# ═══════════════════════════════════════════════════════════════

@app.get("/api/cleaner/report")
async def cleaner_report():
    """智能清理报告"""
    from core.data.cleaner.intelligent_cleaner import IntelligentDataCleaner
    try:
        cleaner = IntelligentDataCleaner()
        # get_cleanup_history() 是同步方法，不是async
        report = cleaner.get_cleanup_history()
        return {"status": "ok", "report": report}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/cleaner/run")
async def cleaner_run():
    """触发智能清理"""
    from core.data.cleaner.intelligent_cleaner import IntelligentDataCleaner
    try:
        cleaner = IntelligentDataCleaner()
        result = await cleaner.intelligent_cleanup()
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/knowledge/similar")
async def knowledge_similar(q: str = "", threshold: float = 0.7, limit: int = 5):
    """相似历史模式查询"""
    from core.analysis.knowledge_base.knowledge_base import KnowledgeBase
    try:
        kb = KnowledgeBase()
        # find_similar() 实际签名: find_similar(signal, trend, sentiment, rsi, bb_pos, limit)
        # q 参数作为 signal，sentiment/trend/rsi/bb_pos 用默认值
        results = kb.find_similar(
            signal=q or "BUY",
            trend="uptrend",
            sentiment="neutral",
            rsi=50.0,
            bb_pos=0.5,
            limit=limit
        )
        return {"status": "ok", "results": results, "query": q}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/funding/history")
async def funding_history(symbol: str = "BTC", limit: int = 30):
    """资金费率历史"""
    from core.data.collectors.derivatives.coinglass import CoinGlassCollector
    try:
        cg = CoinGlassCollector()
        # 实际签名: get_funding_rate(symbol, interval, lookback_days)
        history, total = await cg.get_funding_rate(symbol=symbol, lookback_days=limit)
        return {"status": "ok", "symbol": symbol, "history": history, "total": total}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/oi/history")
async def oi_history(symbol: str = "BTC", limit: int = 30):
    """持仓量历史"""
    from core.data.collectors.derivatives.coinglass import CoinGlassCollector
    try:
        cg = CoinGlassCollector()
        history, total = await cg.get_open_interest(symbol=symbol, lookback_days=limit)
        return {"status": "ok", "symbol": symbol, "history": history, "total": total}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/onchain/summary")
async def onchain_summary(symbol: str = "ETH"):
    """链上汇总（ETH或BTC）"""
    try:
        if symbol.upper() in ("BTC", "BITCOIN"):
            from core.data.collectors.onchain.bitcoin import BitcoinRPCCollector
            collector = BitcoinRPCCollector()
            data = collector.get_full_metrics()
            return {"status": "ok", "symbol": "BTC", "data": data}
        else:
            from core.data.collectors.onchain.ethereum import EthereumRPCCollector
            collector = EthereumRPCCollector()
            data = await collector.get_full_metrics()
            return {"status": "ok", "symbol": "ETH", "data": data}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/evolve/trigger")
async def evolve_trigger():
    """触发一次自进化循环"""
    from core.evolution.self_evolution_engine import SelfEvolutionEngine
    try:
        engine = SelfEvolutionEngine()
        result = await engine.run_evolution_cycle(symbol="BTC", timeframe="1h")
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/attribution/detailed")
async def attribution_detailed(trade_id: str = ""):
    """详细归因分析报告"""
    from core.analysis.attribution.attribution_analyzer import AttributionAnalyzer
    try:
        analyzer = AttributionAnalyzer()
        # get_summary_report() 是同步方法
        report = analyzer.get_summary_report()
        return {"status": "ok", "report": report}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/validation/daily")
async def validation_daily(symbol: str = "BTC", days: int = 7):
    """每日验证统计"""
    from core.analysis.regression.regression_validator import RegressionValidator
    try:
        validator = RegressionValidator()
        # 使用 get_accuracy_report() 替代不存在的 get_daily_stats()
        stats = validator.get_accuracy_report(symbol=symbol, days=days)
        return {"status": "ok", "symbol": symbol, "days": days, "stats": stats}
    except Exception as e:
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


# ═══════════════════════════════════════════════════════════════════════════
# 配置管理 API 端点
# ═══════════════════════════════════════════════════════════════════════════


@app.post("/api/config/reset")
async def reset_config(request: Request):
    """重置配置"""
    try:
        body = await request.json()
        section = body.get("section")  # None表示全部
        
        success = config_manager.reset_to_default(section)
        if success:
            msg = "所有配置" if not section else f"配置节 {section}"
            return {"status": "ok", "message": f"已重置 {msg}"}
        return {"status": "error", "error": "重置失败"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/config")
async def get_all_config():
    """获取所有配置（API Key已隐藏）"""
    return {
        "status": "ok",
        "data": config_manager.get_all()
    }


@app.get("/api/config/{section}/{key}")
async def get_config_value(section: str, key: str):
    """获取单个配置值"""
    value = config_manager.get(f"{section}.{key}")
    if value is None:
        return {"status": "error", "error": f"配置不存在: {section}.{key}"}
    return {
        "status": "ok",
        "data": {
            "section": section,
            "key": key,
            "value": value
        }
    }


@app.put("/api/config/{section}/{key}")
async def set_config_value(section: str, key: str, request: Request):
    """设置单个配置值"""
    try:
        body = await request.json()
        value = body.get("value")
        
        valid_sections = ["data_collection", "ai_model", "trading", "display",
                         "data_management", "evolution", "security"]
        if section not in valid_sections:
            return {"status": "error", "error": f"无效的配置节: {section}"}
        
        if section == "api_keys":
            return {"status": "error", "error": "API Key请使用专门的 /api/keys 端点"}
        
        success = config_manager.set(f"{section}.{key}", value)
        if success:
            return {"status": "ok", "message": f"已更新 {section}.{key}"}
        return {"status": "error", "error": "保存失败"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/keys/{key_name}")
async def set_api_key(key_name: str, request: Request):
    """设置API Key（专用端点）"""
    try:
        body = await request.json()
        value = body.get("value", "")
        
        success = config_manager.set_api_key(key_name, value)
        if success:
            return {"status": "ok", "message": f"已保存 {key_name}"}
        return {"status": "error", "error": "保存失败"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/keys/status")
async def get_api_keys_status():
    """获取API Key配置状态（不暴露值）"""
    from config.api_keys import api_key_manager
    
    status = {}
    for key_name, info in api_key_manager.KEY_TYPES.items():
        is_set = config_manager.is_api_key_configured(key_name)
        status[key_name] = {
            "label": info["label"],
            "category": info["category"],
            "configured": is_set
        }
    
    return {
        "status": "ok",
        "data": status
    }


@app.get("/api/config/{section}")
async def get_config_section(section: str):
    """获取指定配置节"""
    # 避免与 /api/config/reset 冲突
    if section == "reset":
        return {"status": "error", "error": "使用 POST /api/config/reset"}
    
    section_data = config_manager.get_section(section)
    if not section_data:
        return {"status": "error", "error": f"配置节不存在: {section}"}
    return {
        "status": "ok",
        "data": section_data
    }


@app.post("/api/config/{section}")
async def set_config_section(section: str, request: Request):
    """批量设置配置节"""
    try:
        body = await request.json()
        data = body.get("data", {})
        
        valid_sections = ["data_collection", "ai_model", "trading", "display",
                         "data_management", "evolution", "security"]
        if section not in valid_sections:
            return {"status": "error", "error": f"无效的配置节: {section}"}
        
        success = config_manager.set_section(section, data)
        if success:
            return {"status": "ok", "message": f"已更新 {section}"}
        return {"status": "error", "error": "保存失败"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

