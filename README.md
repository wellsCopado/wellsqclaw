# CryptoMind Pro Plus AI

全维度智能自进化数字货币分析系统 - Android APK

## 技术栈
- **UI框架**: Kivy/KivyMD
- **核心逻辑**: Python 3.11+ async
- **本地AI**: Gemma 3 4B (GGUF Q4_K_M) via llama.cpp
- **云端AI**: 可配置 OpenAI/Anthropic 等兼容 API
- **数据存储**: 加密 SQLite + sqlite-vss 向量检索
- **打包工具**: Buildozer → Android APK

## 项目结构
```
CryptoMindProPlusAI/
├── core/                    # 核心业务逻辑
│   ├── data/                # 数据层
│   │   ├── collectors/      # 四大数据采集器
│   │   ├── cache/           # 智能缓存
│   │   ├── resume/          # 断点续传
│   │   ├── cleaner/         # 智能数据清理
│   │   └── lifecycle/       # 数据生命周期管理
│   ├── analysis/            # 分析层
│   │   ├── technical/       # 技术分析
│   │   ├── ai/              # AI分析引擎
│   │   ├── validation/      # 数据验证
│   │   ├── regression/      # 回归验证
│   │   ├── attribution/     # 归因分析
│   │   └── knowledge_base/  # 知识库
│   ├── evolution/           # 自进化模块
│   ├── trading/             # 交易层
│   └── utils/               # 工具模块
├── mobile/                  # 移动端
│   ├── ui/                  # Kivy UI
│   ├── screens/             # 页面
│   └── widgets/             # 自定义控件
├── models/                  # AI模型文件
├── config/                  # 配置
├── tests/                   # 测试
└── scripts/                 # 脚本
```

## 开发阶段
- Phase 1 (7天): 基础框架 + 数据采集 + 智能数据管理
- Phase 2 (8天): AI分析引擎 + 知识库
- Phase 3 (6天): 验证 + 归因系统
- Phase 4 (4天): 自进化 + 自动化优化
