# CryptoMind Pro Plus AI - API Reference

## 基础信息
- **Base URL**: `http://localhost:8000`
- **认证**: `X-API-Key` header 或 `?api_key=` query
- **限流**: 免费用户 60次/分钟

## ⚠️ 免责声明
所有 API 返回数据仅供参考，不构成投资建议。加密货币交易具有高风险。

---

## 健康检查

### GET /api/health
深度健康检查（默认）。

**响应示例**:
```json
{
  "status": "ok",
  "checks": {
    "database": {"status": "ok"},
    "binance": {"status": "ok", "btc_price": 67500.00},
    "okx": {"status": "ok", "btc_price": 67510.00},
    "bybit": {"status": "ok", "btc_price": 67498.00},
    "ollama": {"status": "warning", "detail": "Ollama not running"},
    "paper_trading": {"status": "ok", "balance": 10000.00},
    "backup": {"status": "ok"},
    "data_freshness": {"status": "ok", "age_minutes": 1.2}
  },
  "timestamp": 1745068800000,
  "disclaimer": "本系统提供的所有分析仅供参考，不构成投资建议。"
}
```

---

## 市场数据

### GET /api/btc/price
获取BTC实时价格，自动故障切换到备用交易所。

### GET /api/market/top
获取热门币种行情。
- `symbols`: 币种列表，默认 `BTC,ETH,SOL,BNB,XRP`

### GET /api/klines
获取K线数据。
- `symbol`: 交易对，默认 `BTCUSDT`
- `interval`: 周期，默认 `1h`，可选 `1m,5m,15m,1h,4h,1d,1w`
- `limit`: 条数，默认 `200`

---

## 衍生品数据

### GET /api/derivatives/summary
获取衍生品汇总（资金费率、持仓量、多空比等）。
- `symbol`: 币种，默认 `BTC`

### GET /api/funding/history
资金费率历史。
- `symbol`: 币种
- `limit`: 条数

### GET /api/oi/history
持仓量历史。

---

## 信号分析

### GET /api/signal
获取综合交易信号。
- `symbol`: 币种，默认 `BTC`

**响应**:
```json
{
  "signal": "BUY",
  "confidence": 0.78,
  "disclaimer": "本信号仅供参考，不构成投资建议。"
}
```

---

## 链上数据

### GET /api/onchain/ethereum
以太坊链上指标（Gas、活跃地址、大额转账等）。

### GET /api/onchain/bitcoin
比特币链上指标（MVRV、矿工收益等）。

---

## 新闻资讯

### GET /api/news
获取加密货币新闻。
- `max_items`: 最大条数，默认 `30`

---

## 知识库

### GET /api/knowledge/stats
知识库统计（成功模式数、准确率等）。

### GET /api/knowledge/similar
查询相似历史模式。
- `pattern`: 查询模式

---

## 验证与归因

### GET /api/validation/report
回归验证报告（预测准确率）。

### GET /api/attribution/summary
归因分析摘要（各因子贡献度）。

---

## 模拟交易

### GET /api/trading/account
获取模拟账户信息。

### GET /api/trading/positions
获取当前持仓。

### POST /api/trading/order
模拟下单。
```json
{
  "symbol": "BTC",
  "side": "buy",
  "quantity": 0.1,
  "order_type": "market"
}
```

---

## 实时推送

### GET /api/sse/stream
SSE实时推送（BTC价格实时更新，每5秒）。

---

## 数据管理

### GET /api/cleaner/report
智能清理报告。

### POST /api/cleaner/run
触发智能清理。
