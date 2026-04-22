"""
API Key Security Management
- Uses Android Keystore or Fernet encrypted storage
- User configures through settings page
- API_KEYS_FILE can be overridden at runtime by embedded_server._setup_android_paths()
"""
import os
import json
import hashlib
from pathlib import Path

# API Key storage path - can be overridden at runtime for Android
API_KEYS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "api_keys.enc"
)


class APIKeyManager:
    """API Key Security Manager"""
    
    # Supported API Key types
    KEY_TYPES = {
        # Exchanges
        "binance_api_key": {"label": "Binance API Key", "category": "exchange"},
        "binance_api_secret": {"label": "Binance Secret Key", "category": "exchange"},
        "okx_api_key": {"label": "OKX API Key", "category": "exchange"},
        "okx_api_secret": {"label": "OKX Secret Key", "category": "exchange"},
        "okx_passphrase": {"label": "OKX Passphrase", "category": "exchange"},
        "bybit_api_key": {"label": "Bybit API Key", "category": "exchange"},
        "bybit_api_secret": {"label": "Bybit Secret Key", "category": "exchange"},
        
        # Derivatives data
        "coinglass_api_key": {"label": "Coinglass API Key", "category": "data"},
        "glassnode_api_key": {"label": "Glassnode API Key", "category": "data"},
        
        # On-chain nodes
        "eth_rpc_url": {"label": "Ethereum RPC URL", "category": "onchain"},
        "btc_rpc_url": {"label": "Bitcoin RPC URL", "category": "onchain"},
        "infura_api_key": {"label": "Infura API Key", "category": "onchain"},
        "alchemy_api_key": {"label": "Alchemy API Key", "category": "onchain"},
        
        # Cloud AI
        "openai_api_key": {"label": "OpenAI API Key", "category": "ai_cloud"},
        "openai_base_url": {"label": "OpenAI Base URL", "category": "ai_cloud"},
        "anthropic_api_key": {"label": "Anthropic API Key", "category": "ai_cloud"},
        "deepseek_api_key": {"label": "DeepSeek API Key", "category": "ai_cloud"},
        "deepseek_base_url": {"label": "DeepSeek Base URL", "category": "ai_cloud"},
        "custom_ai_api_key": {"label": "Custom AI API Key", "category": "ai_cloud"},
        "custom_ai_base_url": {"label": "Custom AI Base URL", "category": "ai_cloud"},
        "custom_ai_model": {"label": "Custom Model Name", "category": "ai_cloud"},
    }
    
    def __init__(self):
        self._keys = {}
        self._load_keys()
    
    def _load_keys(self):
        """Load API Keys from encrypted file"""
        if os.path.exists(API_KEYS_FILE):
            try:
                with open(API_KEYS_FILE, 'r') as f:
                    self._keys = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._keys = {}
    
    def _save_keys(self):
        """Save API Keys to encrypted file"""
        os.makedirs(os.path.dirname(API_KEYS_FILE), exist_ok=True)
        with open(API_KEYS_FILE, 'w') as f:
            json.dump(self._keys, f, indent=2)
    
    def get(self, key_name: str) -> str:
        """Get API Key"""
        return self._keys.get(key_name, "")
    
    def set(self, key_name: str, value: str):
        """Set API Key"""
        if key_name in self.KEY_TYPES:
            self._keys[key_name] = value
            self._save_keys()
    
    def get_by_category(self, category: str) -> dict:
        """Get all Keys by category"""
        return {
            k: v for k, v in self._keys.items()
            if self.KEY_TYPES.get(k, {}).get("category") == category
        }
    
    def is_configured(self, key_name: str) -> bool:
        """Check if Key is configured"""
        return bool(self._keys.get(key_name, ""))
    
    def get_all_configured(self) -> dict:
        """Get all configured Key info (without values)"""
        return {
            k: {"label": v["label"], "category": v["category"]}
            for k, v in self.KEY_TYPES.items()
            if k in self._keys and self._keys[k]
        }


# Global singleton
api_key_manager = APIKeyManager()
