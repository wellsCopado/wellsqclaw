# CryptoMind Pro Plus AI - 系统架构

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     用户层 (Kivy Android/iOS)              │
│   HomeScreen | AnalysisScreen | NewsScreen | OnchainScreen │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP/SSE
┌──────────────────────────▼──────────────────────────────────┐
│                   Dashboard (Web)                         │
│   实时K线图 | 雷达图 | 新闻 | 衍生品 | 链上 | Paper Trading │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST API
┌──────────────────────────▼──────────────────────────────────┐
│                   FastAPI Backend                          │
│  auth | rate_limit | audit | 50+ endpoints                 │
└──┬──────────────┬──────────────┬───────────────┬────────────┘
   │              │              │               │
┌──▼─────┐  ┌────▼────┐  ┌────▼────┐  ┌──────▼──────┐
│ 数据采集 │  │ AI分析   │  │ 自进化   │  │  模拟交易    │
│ 4大维度  │  │ 信号生成  │  │ 回归验证  │  │  Paper Trading│
└──┬──────┘  └────┬────┘  └────┬────┘  └──────┬──────┘
   │              │             │               │
┌──▼──────────────▼─────────────▼───────────────▼──────────┐
│                  数据层 (SQLite + File Cache)              │
│  crypto.db | knowledge.db | cache/ | backup/              │
└────────────────────────────────────────────────────────────┘
```

## 四大数据维度

| 维度 | 数据源 | 文件位置 | 说明 |
|------|--------|----------|------|
| 现货 | Binance/OKX/Bybit | collectors/spot/ | K线/深度/价格 |
| 衍生品 | Coinglass | collectors/derivatives/ | 资金费率/OI/爆仓 |
| 链上 | Ethereum RPC/Bitcoin RPC | collectors/onchain/ | Gas/活跃地址/MVRV |
| 新闻 | 自定义爬虫+API | collectors/news/ | 情绪分析 |

## 核心模块

### 数据采集层 (core/data/collectors/)
- `spot/` - 现货数据采集（Binance/OKX/Bybit）
- `derivatives/` - 衍生品数据（Coinglass API）
- `onchain/` - 链上数据（ETH/BTC RPC）
- `news/` - 新闻与社交媒体

### 数据管理层 (core/data/)
- `storage.py` - SQLite主存储
- `cleaner/intelligent_cleaner.py` - 智能数据清理
- `cache/cache_manager.py` - 多层缓存（L1内存/L2磁盘）
- `lifecycle/lifecycle_manager.py` - 数据生命周期管理
- `resume/resume_manager.py` - 断点续传
- `orchestrator.py` - 统一数据编排器

### 分析层 (core/analysis/)
- `technical/` - 技术分析（指标/K线形态/支撑阻力）
- `analytics/signal_analyzer.py` - 5因子信号分析
- `regression/regression_validator.py` - 预测回归验证
- `attribution/attribution_analyzer.py` - 多因子归因分析
- `knowledge_base/knowledge_base.py` - 知识库系统
- `multi_dimension/multi_dim_analyzer.py` - 多维度聚合分析

### 自进化层 (core/evolution/)
- `self_evolution_engine.py` - 自进化引擎（5阶段循环）
- `model_improver.py` - 模型质量改进
- `prompt_optimizer.py` - 提示词优化
- `strategy_evolver.py` - 策略进化
- `feedback_loop.py` - 反馈回路

### 交易层 (core/trading/)
- `paper_trading.py` - Paper Trading模拟引擎

### 移动端 (mobile/)
- `app.py` - KivyMD主应用
- `screens/` - 各功能屏幕
- `cryptomind.kv` - UI布局定义

## 自进化循环

```
学习 → 分析 → 优化 → 测试 → 部署
  ↑                          ↓
  └──────────────────────────┘
     (7天周期，持续迭代)
```

## 数据流

1. **采集**: Orchestrator定时任务调度 → 各Collector采集
2. **存储**: 数据写入SQLite + Cache缓存
3. **分析**: SignalAnalyzer综合5因子 → 输出信号
4. **验证**: RegressionValidator追踪预测准确性
5. **进化**: SelfEvolutionEngine周期性优化策略
6. **呈现**: Dashboard(Web) / App(Mobile) 展示

## 安全机制

- API Key认证 + 限流
- 审计日志记录所有操作
- 数据加密存储
- 自动备份机制
