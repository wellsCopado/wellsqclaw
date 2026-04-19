"""
CryptoMind Pro Plus AI - 全局配置
"""
import os

# ============ 应用基础 ============
APP_NAME = "CryptoMind Pro Plus AI"
APP_VERSION = "6.0.0"
APP_ID = "com.cryptomind.proplus"

# ============ 数据路径 ============
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "cryptomind.db")
KNOWLEDGE_DB_PATH = os.path.join(DATA_DIR, "knowledge.db")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
MODEL_DIR = os.path.join(BASE_DIR, "models")
LOG_DIR = os.path.join(DATA_DIR, "logs")

# 确保目录存在
for d in [DATA_DIR, CACHE_DIR, MODEL_DIR, LOG_DIR]:
    os.makedirs(d, exist_ok=True)

# ============ 数据采集配置 ============
class DataConfig:
    # 现货数据
    SPOT_EXCHANGES = ["binance", "okx", "bybit"]
    SPOT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    SPOT_INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"]
    SPOT_KLINE_LIMIT = 1000  # 单次请求K线数量
    
    # 衍生品数据
    DERIVATIVES_INTERVALS = {
        "funding_rate": 300,      # 5分钟
        "open_interest": 60,      # 1分钟
        "liquidations": 60,       # 1分钟
    }
    
    # 链上数据
    ONCHAIN_CHAINS = ["ethereum", "bitcoin"]
    ONCHAIN_RPC = {
        "ethereum": os.environ.get("ETH_RPC_URL", "https://eth.llamarpc.com"),
        "bitcoin": os.environ.get("BTC_RPC_URL", "https://blockstream.info/api"),
    }
    
    # 新闻数据
    NEWS_SOURCES = ["coindesk", "cointelegraph", "theblock", "decrypt"]
    NEWS_UPDATE_INTERVAL = 300  # 5分钟
    
    # 社交媒体
    SOCIAL_PLATFORMS = ["twitter", "reddit"]

# ============ AI模型配置 ============
class AIConfig:
    # 本地模型
    LOCAL_MODEL_NAME = "gemma-3-4b-it-q4_k_m.gguf"
    LOCAL_MODEL_PATH = os.path.join(MODEL_DIR, LOCAL_MODEL_NAME)
    LOCAL_MODEL_N_CTX = 4096       # 上下文窗口
    LOCAL_MODEL_N_THREADS = 4      # 推理线程数
    LOCAL_MODEL_N_GPU_LAYERS = 0   # GPU层数（Android上通常为0）
    LOCAL_TEMPERATURE = 0.7
    LOCAL_TOP_P = 0.9
    LOCAL_TOP_K = 40
    
    # 云端模型（用户通过API Key页面配置）
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
    
    # 模型模式: "local" / "cloud" / "auto"
    DEFAULT_MODE = "local"

# ============ 性能约束 ============
class PerformanceConfig:
    APK_MAX_SIZE_MB = 5000       # 5GB
    RUNTIME_MAX_MEMORY_MB = 3000 # 3GB
    STARTUP_TIMEOUT_SEC = 10
    RESUME_TIMEOUT_SEC = 600     # 10分钟
    INFERENCE_TIMEOUT_SEC = 60
    DATA_CLEANUP_INTERVAL = 3600 # 1小时

# ============ 知识库配置 ============
class KnowledgeConfig:
    VECTOR_DIMENSION = 768       # 向量维度
    SIMILARITY_THRESHOLD = 0.7   # 相似度阈值
    MAX_RETURN_PATTERNS = 5      # 最大返回模式数
    EVOLUTION_MIN_SAMPLES = 10   # 触发进化的最小样本数

# ============ 安全配置 ============
class SecurityConfig:
    DB_ENCRYPTION_KEY_LENGTH = 32
    AUTO_EVOLUTION_APPROVAL_REQUIRED = True  # 自进化需人工审批
    MAX_DAILY_EVOLUTIONS = 5       # 每日最大自动进化次数
    API_KEY_ENCRYPTED = True
