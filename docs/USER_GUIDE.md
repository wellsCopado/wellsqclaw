# CryptoMind Pro Plus AI - 用户指南

## ⚠️ 重要声明
本系统仅供学习和参考，不构成任何投资建议。加密货币交易具有极高风险，可能导致全部本金损失。使用者应自行承担所有交易决策的风险。

---

## 快速开始

### 1. 启动服务
```bash
cd ~/Desktop/crypto/CryptoMindProPlusAI
source .venv/bin/activate
python api_server.py
```
服务运行在 `http://localhost:8000`

### 2. Web Dashboard
打开浏览器访问 `http://localhost:8000`
- 实时BTC价格
- K线图表（支持多周期切换）
- 技术分析信号
- 衍生品/链上/新闻数据

### 3. API访问
```bash
# 获取API Key（首次自动生成）
# 查看 data/api_keys.json 获取Key

# 调用API
curl -H "X-API-Key: YOUR_KEY" http://localhost:8000/api/btc/price
curl -H "X-API-Key: YOUR_KEY" http://localhost:8000/api/signal?symbol=BTC
```

---

## 功能说明

### 📊 信号分析
系统综合5个因子分析市场：
- 技术面（RSI/MACD/均线）
- 资金费率（交易所融资利率）
- 持仓量变化（OI）
- 多空比（多空人数/仓位）
- 爆仓结构（多空爆仓比例）

**信号等级**: STRONG_BUY > BUY > NEUTRAL > SELL > STRONG_SELL

### 💹 Paper Trading
- 虚拟资金$10,000
- 支持市价/限价单
- 追踪胜率/盈亏
- ⚠️ 非真实交易

### 🧠 知识库
- 自动记录成功/失败模式
- 相似历史查询辅助决策
- 知识增强AI分析

### 📈 自进化
- 7天周期评估策略表现
- 自动优化提示词和参数
- 回归测试验证改进效果

---

## 移动端 (Android)

### 构建APK
```bash
cd ~/Desktop/crypto/CryptoMindProPlusAI
source .venv/bin/activate
cd mobile
python build.py build apk --debug
```

### 安装
```bash
adb install bin/build/target/cryptomind.apk
```

### 使用
1. 启动后进入首页
2. 查看实时信号和BTC价格
3. 底部导航切换：首页/分析/知识库/归因/新闻/链上/模拟交易/设置

---

## 配置说明

### API Key配置
编辑 `config/api_keys.py` 或设置环境变量：
```bash
export BINANCE_API_KEY=your_key
export BINANCE_API_SECRET=your_secret
export COINGLASS_API_KEY=your_key
```

### 数据保留策略
编辑 `core/data/cleaner/intelligent_cleaner.py` 的 RETENTION_POLICIES

### 端口修改
编辑 `api_server.py` 底部 `uvicorn.run(..., port=8000)`

---

## 常见问题

**Q: 健康检查报错？**
A: 检查各API配置是否正确，确保网络可访问交易所

**Q: K线图不显示？**
A: 确认已采集过K线数据，运行orchestrator任务

**Q: 移动端无法连接？**
A: 确保手机和电脑在同一网络，修改api_server.py的host为0.0.0.0

**Q: 信号不更新？**
A: 信号缓存5分钟，可手动触发重新分析

---

## 版本信息
当前版本: v6.0.0
最后更新: 2026-04-19
