"""
CryptoMind Pro Plus AI - 自动化测试套件
"""
import json
import os
import sqlite3
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestTechnicalIndicators(unittest.TestCase):
    def test_sma(self):
        from core.analysis.technical.indicators import calc_sma
        result = calc_sma([10, 20, 30, 40, 50], 3)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        self.assertAlmostEqual(result[-1], 40.0)

    def test_ema(self):
        from core.analysis.technical.indicators import calc_ema
        result = calc_ema([10, 20, 30, 40, 50], 3)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_rsi(self):
        from core.analysis.technical.indicators import calc_rsi
        prices = list(range(50, 80))
        rsi = calc_rsi(prices, 14)
        if isinstance(rsi, list):
            self.assertGreater(rsi[-1], 50)
        else:
            self.assertGreater(rsi, 50)

    def test_rsi_empty(self):
        from core.analysis.technical.indicators import calc_rsi
        rsi = calc_rsi([], 14)
        self.assertIsInstance(rsi, (list, float, int))

    def test_detect_trend_up(self):
        from core.analysis.technical.indicators import detect_trend
        trend, strength = detect_trend([100, 102, 104, 106, 108], 104, 103, 101)
        self.assertEqual(trend, "UP")

    def test_detect_trend_down(self):
        from core.analysis.technical.indicators import detect_trend
        trend, strength = detect_trend([108, 106, 104, 102, 100], 102, 103, 105)
        self.assertEqual(trend, "DOWN")


class TestPatternRecognition(unittest.TestCase):
    def test_empty(self):
        from core.analysis.technical.patterns import recognize_patterns
        result = recognize_patterns([])
        self.assertIn("patterns_found", result)
        self.assertEqual(result["patterns_found"], 0)

    def test_single(self):
        from core.analysis.technical.patterns import recognize_patterns
        result = recognize_patterns([{"open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 100, "timestamp": 0}])
        self.assertIn("patterns_found", result)

    def test_multiple(self):
        from core.analysis.technical.patterns import recognize_patterns
        klines = [{"open": 100, "high": 100.5, "low": 95, "close": 100, "volume": 1000, "timestamp": i} for i in range(5)]
        result = recognize_patterns(klines)
        self.assertIn("patterns_found", result)


class TestSupportResistance(unittest.TestCase):
    def test_analyze(self):
        from core.analysis.technical.support_resistance import analyze_support_resistance
        klines = [{"open":90,"high":110,"low":90,"close":100,"volume":1,"timestamp":i} for i in range(30)]
        result = analyze_support_resistance(klines)
        self.assertIn("current_price", result)

    def test_empty(self):
        from core.analysis.technical.support_resistance import analyze_support_resistance
        result = analyze_support_resistance([])
        self.assertIsInstance(result, dict)

    def test_min(self):
        from core.analysis.technical.support_resistance import analyze_support_resistance
        klines = [{"open":90,"high":110,"low":90,"close":100,"volume":1,"timestamp":i} for i in range(10)]
        result = analyze_support_resistance(klines)
        self.assertIsInstance(result, dict)


class TestPaperTrading(unittest.TestCase):
    def _new_engine(self, balance=10000):
        from core.trading.paper_trading import PaperTradingEngine
        db = f"/tmp/test_pt_{int(time.time()*1000)}.db"
        e = PaperTradingEngine(db_path=db, config={"initial_balance": balance, "cooldown_sec": 0})
        self.addCleanup(lambda: (e.close(), os.remove(db) if os.path.exists(db) else None))
        return e

    def test_initial_balance(self):
        engine = self._new_engine()
        acct = engine.get_account()
        self.assertEqual(acct["balance"], 10000)

    def test_buy_order(self):
        engine = self._new_engine()
        result = engine.place_order(symbol="BTC/USDT", side="buy", quantity=0.1, current_price=50000)
        self.assertTrue(result["success"])
        self.assertEqual(result["side"], "buy")
        self.assertGreater(result["fee"], 0)
        self.assertGreater(result["slippage"], 0)

    def test_sell_order(self):
        engine = self._new_engine()
        engine._config["max_drawdown_pct"] = 0.50
        engine.place_order("ETH/USDT", "buy", 0.1, current_price=3000)
        result = engine.place_order("ETH/USDT", "sell", 0.1, current_price=3100)
        self.assertTrue(result["success"])

    def test_sell_without_position(self):
        engine = self._new_engine()
        engine._config["max_drawdown_pct"] = 0.50
        result = engine.place_order("DOGE/USDT", "sell", 1000, current_price=0.1)
        self.assertFalse(result["success"])

    def test_cooldown(self):
        from core.trading.paper_trading import SignalCooldown
        cd = SignalCooldown(default_cooldown_sec=60)
        ok, remaining = cd.can_trade("BTC")
        self.assertTrue(ok)
        cd.record_trade("BTC")
        ok, remaining = cd.can_trade("BTC")
        self.assertFalse(ok)

    def test_max_drawdown_protection(self):
        from core.trading.paper_trading import PaperTradingEngine
        db = f"/tmp/test_dd_{int(time.time()*1000)}.db"
        engine = PaperTradingEngine(db_path=db, config={"initial_balance": 1000, "max_drawdown_pct": 0.10, "cooldown_sec": 0})
        engine.equity = 800
        engine.max_equity = 1000
        result = engine.place_order("BTC/USDT", "buy", 0.01, current_price=50000)
        self.assertFalse(result["success"])
        engine.close()
        if os.path.exists(db): os.remove(db)

    def test_performance_stats(self):
        engine = self._new_engine()
        engine._config["max_drawdown_pct"] = 0.50
        engine.place_order("BTC/USDT", "buy", 0.01, current_price=50000)
        engine.place_order("BTC/USDT", "sell", 0.01, current_price=51000)
        perf = engine.get_performance()
        self.assertIn("total_trades", perf)


class TestBackupManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from core.data.backup_manager import BackupManager
        test_dir = "/tmp/test_backup_data"
        os.makedirs(test_dir, exist_ok=True)
        conn = sqlite3.connect(os.path.join(test_dir, "test.db"))
        conn.execute("CREATE TABLE IF NOT EXISTS t1 (id INTEGER)")
        conn.execute("INSERT INTO t1 VALUES (1)")
        conn.commit()
        conn.close()
        cls.backup_mgr = BackupManager(data_dir=test_dir, backup_dir="/tmp/test_backups")

    @classmethod
    def tearDownClass(cls):
        import shutil
        for d in ["/tmp/test_backup_data", "/tmp/test_backups"]:
            if os.path.exists(d): shutil.rmtree(d)

    def test_create_backup(self):
        result = self.backup_mgr.backup(label="test")
        self.assertTrue(result["success"])

    def test_list_backups(self):
        self.backup_mgr.backup(label="test2")
        backups = self.backup_mgr.list_backups()
        self.assertGreaterEqual(len(backups), 2)

    def test_restore_backup(self):
        result = self.backup_mgr.backup(label="restore_test")
        restore_result = self.backup_mgr.restore(result["backup_id"])
        self.assertTrue(restore_result["success"])

    def test_backup_stats(self):
        self.backup_mgr.backup(label="stats_test")
        stats = self.backup_mgr.get_stats()
        self.assertGreaterEqual(stats["total_backups"], 1)


class TestSignalCooldown(unittest.TestCase):
    def test_no_cooldown(self):
        from core.trading.paper_trading import SignalCooldown
        cd = SignalCooldown(default_cooldown_sec=0)
        ok, _ = cd.can_trade("BTC")
        self.assertTrue(ok)

    def test_cooldown_active(self):
        from core.trading.paper_trading import SignalCooldown
        cd = SignalCooldown(default_cooldown_sec=300)
        cd.record_trade("BTC")
        ok, remaining = cd.can_trade("BTC")
        self.assertFalse(ok)

    def test_different_symbols(self):
        from core.trading.paper_trading import SignalCooldown
        cd = SignalCooldown(default_cooldown_sec=300)
        cd.record_trade("BTC")
        ok, _ = cd.can_trade("ETH")
        self.assertTrue(ok)


@unittest.skip("Requires running API server")
class TestAPIServerSmoke(unittest.TestCase):
    SERVER_URL = "http://localhost:8765"

    def test_health(self):
        import urllib.request
        resp = urllib.request.urlopen(f"{self.SERVER_URL}/api/health", timeout=5)
        data = json.loads(resp.read())
        self.assertEqual(data.get("status"), "ok")

    def test_auth_required(self):
        import urllib.request
        try:
            urllib.request.urlopen(f"{self.SERVER_URL}/api/btc/price", timeout=5)
            self.fail("Should return 401")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 401)


if __name__ == "__main__":
    unittest.main(verbosity=2)
