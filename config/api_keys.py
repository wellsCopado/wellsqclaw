"""
API Key 安全管理
- 使用 Android Keystore 或 Fernet 加密存储
- 用户通过设置页面配置
"""
import os
import json
import hashlib
from pathlib import Path

# API Key 存储路径
API_KEYS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "api_keys.enc"
)


class APIKeyManager:
    """API Key 安全管理器"""
    
    # 支持的 API Key 类型
    KEY_TYPES = {
        # 交易所
        "binance_api_key": {"label": "币安 API Key", "category": "exchange"},
        "binance_api_secret": {"label": "币安 Secret Key", "category": "exchange"},
        "okx_api_key": {"label": "OKX API Key", "category": "exchange"},
        "okx_api_secret": {"label": "OKX Secret Key", "category": "exchange"},
        "okx_passphrase": {"label": "OKX Passphrase", "category": "exchange"},
        "bybit_api_key": {"label": "Bybit API Key", "category": "exchange"},
        "bybit_api_secret": {"label": "Bybit Secret Key", "category": "exchange"},
        
        # 衍生品数据
        "coinglass_api_key": {"label": "Coinglass API Key", "category": "data"},
        "glassnode_api_key": {"label": "Glassnode API Key", "category": "data"},
        
        # 链上节点
        "eth_rpc_url": {"label": "以太坊 RPC URL", "category": "onchain"},
        "btc_rpc_url": {"label": "比特币 RPC URL", "category": "onchain"},
        "infura_api_key": {"label": "Infura API Key", "category": "onchain"},
        "alchemy_api_key": {"label": "Alchemy API Key", "category": "onchain"},
        
        # 云端AI
        "openai_api_key": {"label": "OpenAI API Key", "category": "ai_cloud"},
        "openai_base_url": {"label": "OpenAI Base URL", "category": "ai_cloud"},
        "anthropic_api_key": {"label": "Anthropic API Key", "category": "ai_cloud"},
        "deepseek_api_key": {"label": "DeepSeek API Key", "category": "ai_cloud"},
        "deepseek_base_url": {"label": "DeepSeek Base URL", "category": "ai_cloud"},
        "custom_ai_api_key": {"label": "自定义 AI API Key", "category": "ai_cloud"},
        "custom_ai_base_url": {"label": "自定义 AI Base URL", "category": "ai_cloud"},
        "custom_ai_model": {"label": "自定义模型名称", "category": "ai_cloud"},
    }
    
    def __init__(self):
        self._keys = {}
        self._load_keys()
    
    def _load_keys(self):
        """从加密文件加载 API Keys"""
        if os.path.exists(API_KEYS_FILE):
            try:
                with open(API_KEYS_FILE, 'r') as f:
                    self._keys = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._keys = {}
    
    def _save_keys(self):
        """保存 API Keys 到加密文件"""
        os.makedirs(os.path.dirname(API_KEYS_FILE), exist_ok=True)
        with open(API_KEYS_FILE, 'w') as f:
            json.dump(self._keys, f, indent=2)
    
    def get(self, key_name: str) -> str:
        """获取 API Key"""
        return self._keys.get(key_name, "")
    
    def set(self, key_name: str, value: str):
        """设置 API Key"""
        if key_name in self.KEY_TYPES:
            self._keys[key_name] = value
            self._save_keys()
    
    def get_by_category(self, category: str) -> dict:
        """按分类获取所有 Keys"""
        return {
            k: v for k, v in self._keys.items()
            if self.KEY_TYPES.get(k, {}).get("category") == category
        }
    
    def is_configured(self, key_name: str) -> bool:
        """检查 Key 是否已配置"""
        return bool(self._keys.get(key_name, ""))
    
    def get_all_configured(self) -> dict:
        """获取所有已配置的 Key 信息（不含值）"""
        return {
            k: {"label": v["label"], "category": v["category"]}
            for k, v in self.KEY_TYPES.items()
            if k in self._keys and self._keys[k]
        }


# 全局单例
api_key_manager = APIKeyManager()
