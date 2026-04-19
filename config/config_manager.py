"""
配置管理器 - 支持持久化配置
手机端可通过API或UI修改所有配置
"""
import json
import os
from typing import Any, Dict, Optional
from pathlib import Path

# 配置存储路径
CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
CONFIG_FILE = os.path.join(CONFIG_DIR, "user_config.json")


class ConfigManager:
    """
    用户配置管理器
    支持：数据采集、AI模型、交易、显示偏好等配置
    """
    
    # 默认配置 - 所有可配置项的默认值
    DEFAULT_CONFIG = {
        # === 数据采集配置 ===
        "data_collection": {
            "enabled": True,
            "spot_exchanges": ["binance", "okx", "bybit"],
            "spot_symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
            "spot_intervals": ["1m", "5m", "15m", "1h", "4h", "1d", "1w"],
            "derivatives_enabled": True,
            "onchain_enabled": True,
            "news_enabled": True,
            "update_interval_seconds": 60,
        },
        
        # === API密钥配置 ===
        "api_keys": {
            "binance_api_key": "",
            "binance_api_secret": "",
            "okx_api_key": "",
            "okx_api_secret": "",
            "okx_passphrase": "",
            "bybit_api_key": "",
            "bybit_api_secret": "",
            "coinglass_api_key": "",
            "glassnode_api_key": "",
            "openai_api_key": "",
            "anthropic_api_key": "",
            "deepseek_api_key": "",
        },
        
        # === AI模型配置 ===
        "ai_model": {
            "mode": "local",  # "local" / "cloud" / "auto"
            "local_model_name": "gemma3:4b",
            "local_ollama_url": "http://localhost:11434",
            "cloud_provider": "openai",  # "openai" / "anthropic" / "deepseek" / "custom"
            "cloud_model": "gpt-4o",
            "custom_api_url": "",
            "custom_api_key": "",
            "custom_model_name": "",
            "temperature": 0.7,
            "max_tokens": 2048,
        },
        
        # === 交易配置 ===
        "trading": {
            "paper_trading_enabled": True,
            "paper_initial_balance": 10000.0,
            "signal_confidence_threshold": 60,  # 低于此置信度不推荐
            "max_position_size_percent": 20,  # 最大仓位百分比
            "auto_trading_enabled": False,  # 自动交易需手动开启
            "auto_trading_confirm": True,  # 自动交易前确认
        },
        
        # === 显示配置 ===
        "display": {
            "default_symbol": "BTCUSDT",
            "default_timeframe": "4h",
            "theme": "dark",  # "dark" / "light"
            "currency": "USDT",  # 显示货币
            "language": "zh_CN",  # 语言
            "show_tutorial": True,
            "chart_type": "candle",  # "candle" / "line"
        },
        
        # === 数据管理配置 ===
        "data_management": {
            "auto_cleanup_enabled": True,
            "cleanup_interval_hours": 24,
            "max_cache_size_mb": 500,
            "kline_retention_days": {
                "1m": 3,
                "5m": 7,
                "15m": 14,
                "1h": 30,
                "4h": 90,
                "1d": 365,
                "1w": 730,
            },
        },
        
        # === 进化配置 ===
        "evolution": {
            "auto_evolution_enabled": False,
            "evolution_interval_hours": 168,  # 7天
            "min_samples_to_evolve": 10,
            "approval_required": True,  # 进化需审批
            "max_evolution_per_day": 5,
        },
        
        # === 安全配置 ===
        "security": {
            "api_key_encryption": True,
            "biometric_unlock": False,
            "auto_lock_minutes": 30,
        },
    }
    
    def __init__(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        self._config = self._load_config()
    
    def _load_config(self) -> Dict:
        """从文件加载配置"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # 合并默认配置，确保所有键存在
                    return self._merge_config(self.DEFAULT_CONFIG, loaded)
            except (json.JSONDecodeError, IOError) as e:
                print(f"配置加载失败，使用默认: {e}")
        return self._deep_copy(self.DEFAULT_CONFIG)
    
    def _save_config(self):
        """保存配置到文件"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"配置保存失败: {e}")
            return False
    
    def _merge_config(self, default: Dict, loaded: Dict) -> Dict:
        """深度合并配置"""
        result = self._deep_copy(default)
        for key, value in loaded.items():
            if key in result:
                if isinstance(value, dict) and isinstance(result[key], dict):
                    result[key] = self._merge_config(result[key], value)
                else:
                    result[key] = value
        return result
    
    def _deep_copy(self, obj):
        """深拷贝"""
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(item) for item in obj]
        else:
            return obj
    
    # === 通用读写方法 ===
    
    def get(self, path: str, default: Any = None) -> Any:
        """
        获取配置值
        path格式: "section.key" 或 "section.subsection.key"
        例如: get("ai_model.mode") 返回 "local"
        """
        keys = path.split('.')
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
    
    def set(self, path: str, value: Any) -> bool:
        """
        设置配置值
        path格式: "section.key" 或 "section.subsection.key"
        """
        keys = path.split('.')
        config = self._config
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        config[keys[-1]] = value
        return self._save_config()
    
    def get_section(self, section: str) -> Dict:
        """获取整个配置节"""
        return self._deep_copy(self._config.get(section, {}))
    
    def set_section(self, section: str, data: Dict) -> bool:
        """设置整个配置节"""
        self._config[section] = data
        return self._save_config()
    
    def get_all(self) -> Dict:
        """获取所有配置"""
        # 隐藏敏感信息
        config = self._deep_copy(self._config)
        sensitive_keys = ['api_key', 'secret', 'password', 'token']
        for section in config.values():
            if isinstance(section, dict):
                for key in list(section.keys()):
                    for sensitive in sensitive_keys:
                        if sensitive in key.lower():
                            if section[key]:
                                section[key] = "***已配置***"
                            else:
                                section[key] = ""
        return config
    
    def reset_to_default(self, section: str = None) -> bool:
        """重置配置到默认值"""
        if section:
            self._config[section] = self._deep_copy(self.DEFAULT_CONFIG.get(section, {}))
        else:
            self._config = self._deep_copy(self.DEFAULT_CONFIG)
        return self._save_config()
    
    def get_api_key(self, key_name: str) -> str:
        """获取API Key（不暴露）"""
        return self.get(f"api_keys.{key_name}", "")
    
    def set_api_key(self, key_name: str, value: str) -> bool:
        """设置API Key"""
        return self.set(f"api_keys.{key_name}", value)
    
    def is_api_key_configured(self, key_name: str) -> bool:
        """检查API Key是否已配置"""
        key = self.get(f"api_keys.{key_name}", "")
        return bool(key and key != "***已配置***")


# 全局单例
config_manager = ConfigManager()
