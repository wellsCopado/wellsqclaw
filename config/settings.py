"""
CryptoMind Pro Plus AI - Global Configuration
Supports runtime path override for Android embedded mode
"""
import os

# ============ Application Basics ============
APP_NAME = "CryptoMind Pro Plus AI"
APP_VERSION = "6.0.0"
APP_ID = "com.cryptomind.proplus"

# ============ Data Paths (defaults, can be overridden at runtime) ============
# These will be set to Android private dir by embedded_server._setup_android_paths()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "cryptomind.db")
KNOWLEDGE_DB_PATH = os.path.join(DATA_DIR, "knowledge.db")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
MODEL_DIR = os.path.join(BASE_DIR, "models")
LOG_DIR = os.path.join(DATA_DIR, "logs")

# Ensure directories exist (for desktop)
for d in [DATA_DIR, CACHE_DIR, LOG_DIR]:
    os.makedirs(d, exist_ok=True)

# ============ Data Collection ============
class DataConfig:
    SPOT_EXCHANGES = ["binance", "okx", "bybit"]
    SPOT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    SPOT_INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"]
    SPOT_KLINE_LIMIT = 1000

    DERIVATIVES_INTERVALS = {
        "funding_rate": 300,
        "open_interest": 60,
        "liquidations": 60,
    }

    ONCHAIN_CHAINS = ["ethereum", "bitcoin"]
    ONCHAIN_RPC = {
        "ethereum": os.environ.get("ETH_RPC_URL", "https://eth.llamarpc.com"),
        "bitcoin": os.environ.get("BTC_RPC_URL", "https://blockstream.info/api"),
    }

    NEWS_SOURCES = ["coindesk", "cointelegraph", "theblock", "decrypt"]
    NEWS_UPDATE_INTERVAL = 300
    SOCIAL_PLATFORMS = ["twitter", "reddit"]

# ============ AI Model ============
class AIConfig:
    LOCAL_MODEL_NAME = "gemma-3-4b-it-q4_k_m.gguf"
    LOCAL_MODEL_PATH = os.path.join(MODEL_DIR, LOCAL_MODEL_NAME)
    LOCAL_MODEL_N_CTX = 4096
    LOCAL_MODEL_N_THREADS = 4
    LOCAL_MODEL_N_GPU_LAYERS = 0
    LOCAL_TEMPERATURE = 0.7
    LOCAL_TOP_P = 0.9
    LOCAL_TOP_K = 40

    CLOUD_PROVIDERS = ["openai", "anthropic", "deepseek", "custom"]
    CLOUD_MODEL_MAP = {
        "openai": "gpt-4o",
        "anthropic": "claude-sonnet-4-20250514",
        "deepseek": "deepseek-chat",
    }
    CLOUD_API_URLS = {
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "custom": "",
    }
    CLOUD_TEMPERATURE = 0.7
    CLOUD_MAX_TOKENS = 4096
    DEFAULT_MODE = "cloud"  # Android: default to cloud (no local model)

# ============ Performance ============
class PerformanceConfig:
    APK_MAX_SIZE_MB = 5000
    RUNTIME_MAX_MEMORY_MB = 3000
    STARTUP_TIMEOUT_SEC = 10
    RESUME_TIMEOUT_SEC = 600
    INFERENCE_TIMEOUT_SEC = 60
    DATA_CLEANUP_INTERVAL = 3600

# ============ Knowledge Base ============
class KnowledgeConfig:
    VECTOR_DIMENSION = 768
    SIMILARITY_THRESHOLD = 0.7
    MAX_RETURN_PATTERNS = 5
    EVOLUTION_MIN_SAMPLES = 10

# ============ Security ============
class SecurityConfig:
    DB_ENCRYPTION_KEY_LENGTH = 32
    AUTO_EVOLUTION_APPROVAL_REQUIRED = True
    MAX_DAILY_EVOLUTIONS = 5
    API_KEY_ENCRYPTED = True
