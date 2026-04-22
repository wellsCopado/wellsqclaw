"""
CryptoMind Mobile - Embedded Server
App启动时在后台线程启动FastAPI服务器，提供与桌面端一致的数据采集+存储+API

使用 uvicorn 在线程中运行，Kivy前端通过 localhost:8000 访问
"""
import os
import sys
import threading
import time
import logging

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

    logger.info(f"Android data dir: {data_dir}")
    return True


def start_server(host="127.0.0.1", port=8000):
    """在后台线程启动FastAPI服务器"""
    global _server_ready

    def _run():
        global _server_ready
        try:
            # Android路径适配
            _setup_android_paths()

            import uvicorn
            import api_server

            # 在子线程中创建新的事件循环
            loop = None
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            except Exception:
                pass

            config = uvicorn.Config(
                api_server.app,
                host=host,
                port=port,
                log_level="warning",
                access_log=False,
                timeout_keep_alive=30,
            )

            server = uvicorn.Server(config)

            _server_ready = True
            _server_started.set()
            logger.info(f"Embedded server starting on {host}:{port}")

            server.run()

        except Exception as e:
            logger.error(f"Embedded server failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            _server_started.set()  # Unblock waiters even on failure

    thread = threading.Thread(target=_run, daemon=True, name="api-server")
    thread.start()
    return thread


def wait_for_server(timeout=10):
    """等待服务器就绪"""
    import requests
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _server_ready:
            # Double-check with a real request
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
