"""
CryptoMind Mobile - Embedded Server (Lightweight)
App启动时在后台线程启动轻量HTTP服务器，提供首页所需的最小API

使用 Python 标准库 http.server，零第三方依赖，彻底避免
FastAPI/pydantic 在 Android 上的兼容性问题。

Kivy前端通过 localhost:8000 访问
"""
import os
import sys
import json
import threading
import time
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

logger = logging.getLogger("embedded_server")

_server_started = threading.Event()
_server_ready = False


def get_android_data_dir():
    """获取Android上App私有数据目录"""
    if 'ANDROID_ROOT' not in os.environ:
        return None
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        app_path = PythonActivity.mActivity.getFilesDir().getAbsolutePath()
        return app_path
    except Exception as e:
        logger.warning(f"Failed to get Android data dir: {e}")
        return None


def _setup_android_paths():
    """Android上重定向数据目录到App私有目录"""
    data_dir = get_android_data_dir()
    if not data_dir:
        return False

    # 创建子目录
    for sub in ["data", "data/logs", "data/cache", "models"]:
        os.makedirs(os.path.join(data_dir, sub), exist_ok=True)

    # 重定向 config.settings 的路径
    try:
        import config.settings as settings
        settings.BASE_DIR = data_dir
        settings.DATA_DIR = os.path.join(data_dir, "data")
        settings.DB_PATH = os.path.join(data_dir, "data", "cryptomind.db")
        settings.KNOWLEDGE_DB_PATH = os.path.join(data_dir, "data", "knowledge.db")
        settings.CACHE_DIR = os.path.join(data_dir, "data", "cache")
        settings.MODEL_DIR = os.path.join(data_dir, "models")
        settings.LOG_DIR = os.path.join(data_dir, "data", "logs")

        # 重定向 logger 路径
        import core.utils.logger as log_mod
        log_mod.LOG_DIR = settings.LOG_DIR

        # 重定向 API key 存储路径
        import config.api_keys as ak_mod
        ak_mod.API_KEYS_FILE = os.path.join(data_dir, "data", "api_keys.enc")

        # 重定向 user_config.json 路径
        import config.config_manager as cm_mod
        cm_mod.CONFIG_DIR = os.path.join(data_dir, "data")
        cm_mod.CONFIG_FILE = os.path.join(data_dir, "data", "user_config.json")
    except Exception as e:
        logger.warning(f"Failed to setup Android paths: {e}")

    logger.info(f"Android data dir: {data_dir}")
    return True


# ---- Price cache (shared between handler threads) ----
_price_cache = {
    "btc": {"price": 0.0, "source": "init", "updated": 0},
    "eth": {"price": 0.0, "source": "init", "updated": 0},
}
_cache_lock = threading.Lock()


def _fetch_btc_price():
    """从Binance公开API获取BTC价格（无需API Key）"""
    try:
        import requests
        resp = requests.get(
            "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            price = float(data["price"])
            with _cache_lock:
                _price_cache["btc"] = {
                    "price": price,
                    "source": "Binance",
                    "updated": time.time(),
                }
            logger.info(f"BTC price updated: ${price:,.2f}")
            return True
    except Exception as e:
        logger.warning(f"Failed to fetch BTC price: {e}")
    return False


def _fetch_eth_price():
    """从Binance公开API获取ETH价格（无需API Key）"""
    try:
        import requests
        resp = requests.get(
            "https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT",
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            price = float(data["price"])
            with _cache_lock:
                _price_cache["eth"] = {
                    "price": price,
                    "source": "Binance",
                    "updated": time.time(),
                }
            logger.info(f"ETH price updated: ${price:,.2f}")
            return True
    except Exception as e:
        logger.warning(f"Failed to fetch ETH price: {e}")
    return False


def _price_refresh_loop():
    """后台定期刷新价格（每60秒）"""
    while True:
        _fetch_btc_price()
        _fetch_eth_price()
        time.sleep(60)


class MobileAPIHandler(BaseHTTPRequestHandler):
    """轻量级API处理器，仅实现首页所需的3个端点"""

    def do_GET(self):
        if self.path == "/api/health":
            self._json_response({"status": "ok", "mode": "embedded"})
        elif self.path == "/api/btc/price":
            with _cache_lock:
                btc = _price_cache["btc"]
            self._json_response({
                "price": btc["price"],
                "source": btc["source"],
                "symbol": "BTC",
            })
        elif self.path.startswith("/api/market/top"):
            with _cache_lock:
                eth = _price_cache["eth"]
            self._json_response({
                "coins": [
                    {
                        "symbol": "ETH",
                        "price": eth["price"],
                        "source": eth["source"],
                    }
                ]
            })
        else:
            self._json_response({"error": "not found"}, status=404)

    def _json_response(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def log_message(self, format, *args):
        # Suppress default HTTP logging to reduce noise
        pass


def start_server(host="127.0.0.1", port=8000):
    """在后台线程启动轻量HTTP服务器"""
    global _server_ready

    def _run():
        global _server_ready
        try:
            # Android路径适配
            _setup_android_paths()

            server = HTTPServer((host, port), MobileAPIHandler)
            _server_ready = True
            _server_started.set()
            logger.info(f"Embedded server starting on {host}:{port} (lightweight mode)")

            # 启动价格刷新线程
            price_thread = threading.Thread(
                target=_price_refresh_loop, daemon=True, name="price-refresh"
            )
            price_thread.start()

            # 首次立即获取价格
            _fetch_btc_price()
            _fetch_eth_price()

            server.serve_forever()

        except Exception as e:
            logger.error(f"Embedded server failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            _server_started.set()

    thread = threading.Thread(target=_run, daemon=True, name="api-server")
    thread.start()
    return thread


def wait_for_server(timeout=10):
    """等待服务器就绪"""
    import requests
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _server_ready:
            try:
                resp = requests.get("http://127.0.0.1:8000/api/health", timeout=2)
                if resp.status_code == 200:
                    logger.info("Embedded server is ready")
                    return True
            except Exception:
                pass
        time.sleep(0.5)
    logger.warning(f"Server not ready after {timeout}s")
    return False
