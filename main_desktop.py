import json
"""
CryptoMind Pro Plus AI - 移动端 App (最终版)
KivyMD 实现，真实数据驱动
包含：K线图 / 知识库 / 历史信号 / 设置
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import threading
import time as time_module
import io
import base64
from datetime import datetime

import kivy
kivy.require('2.3.0')
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget
from kivy.properties import StringProperty, NumericProperty, BooleanProperty, ColorProperty
from kivy.graphics import Color, Rectangle, Line, Ellipse
from kivy.graphics.texture import Texture
from kivy.clock import Clock

from kivymd.app import MDApp
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDIconButton, MDRectangleFlatButton
from kivymd.uix.bottomnavigation import MDBottomNavigation, MDBottomNavigationItem
from kivymd.uix.dialog import MDDialog
from kivymd.theming import ThemableBehavior

from core.data.collectors.spot.binance import BinanceSpotCollector
from core.data.collectors.spot.okx import OKXSpotCollector
from core.data.collectors.spot.bybit import BybitSpotCollector
from core.data.collectors.derivatives import get_coinglass_collector
from core.analysis.technical.patterns import recognize_patterns
from core.analysis.technical.support_resistance import analyze_support_resistance
from core.analysis.knowledge_base.knowledge_base import KnowledgeBase
from core.utils.logger import logger

# 颜色
C_BG = (0.05, 0.07, 0.10, 1)
C_CARD = (0.08, 0.11, 0.15, 1)
C_BULL = (0.25, 0.73, 0.31, 1)
C_BEAR = (0.97, 0.32, 0.29, 1)
C_TEXT = (0.90, 0.91, 0.93, 1)
C_DIM = (0.55, 0.58, 0.62, 1)
C_ACCENT = (0.35, 0.65, 1.0, 1)


# ─────────────────────────────────────────────────────────
# 主屏幕
# ─────────────────────────────────────────────────────────
class MainScreen(Screen):
    btc_price = StringProperty("$--")
    btc_change = StringProperty("+0.00%")
    btc_change_color = ColorProperty(C_BULL)
    signal_text = StringProperty("分析中")
    signal_color = ColorProperty(C_TEXT)
    confidence_text = StringProperty("0%")
    fr_value = StringProperty("--")
    oi_value = StringProperty("--")
    liq_value = StringProperty("--")
    ls_value = StringProperty("--")
    rsi_value = StringProperty("--")
    macd_value = StringProperty("--")
    bb_value = StringProperty("--")
    analysis_summary = StringProperty("正在获取数据...")
    news_text = StringProperty("加载中...")
    last_update = StringProperty("--")
    model_name = StringProperty("Gemma 3 4B")
    is_loading = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.binance = BinanceSpotCollector()
        self.okx = OKXSpotCollector()
        self.bybit = BybitSpotCollector()
        self.cg = get_coinglass_collector()
        self.signal_analyzer = None
        try:
            from core.analytics import get_signal_analyzer
            self.signal_analyzer = get_signal_analyzer()
        except Exception:
            pass
        Clock.schedule_once(lambda *_: self._init_data(), 0.5)

    def _init_data(self):
        self.refresh_data()
        Clock.schedule_interval(lambda *_: self.refresh_data(), 60)

    def refresh_data(self):
        if self.is_loading:
            return
        self.is_loading = True
        threading.Thread(target=self._fetch_all_data, daemon=True).start()

    def _fetch_all_data(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._do_fetch())
            loop.close()
        except Exception as e:
            logger.error(f"数据获取失败: {e}")
        finally:
            self.is_loading = False

    async def _do_fetch(self):
        try:
            # BTC价格
            ticker = await self.binance.get_ticker("BTCUSDT")
            if ticker:
                price = float(ticker.get("last", 0))
                prev = float(ticker.get("prev_close", price))
                chg = (price - prev) / prev * 100 if prev > 0 else 0

                def ui():
                    self.btc_price = f"${price:,.0f}"
                    self.btc_change = f"{'+' if chg >= 0 else ''}{chg:.2f}%"
                    self.btc_change_color = C_BULL if chg >= 0 else C_BEAR
                    self.last_update = f"更新 {datetime.now().strftime('%H:%M')}"
                Clock.schedule_once(lambda *_: ui())

            # 衍生品数据
            summary = await self.cg.get_market_summary("BTC")
            if summary:
                fr = summary.get("funding_rate", 0)
                oi = summary.get("open_interest", 0)
                liq = summary.get("total_liquidation", 0)
                ls = summary.get("long_short_ratio", 1.0)

                def ui_d():
                    self.fr_value = f"{fr*100:+.4f}%" if fr else "--"
                    self.oi_value = f"${oi/1e9:.2f}B" if oi else "--"
                    self.liq_value = f"${liq/1e6:.1f}M" if liq else "--"
                    self.ls_value = f"{ls:.2f}" if ls else "--"
                Clock.schedule_once(lambda *_: ui_d())

            # 技术分析
            klines = await self.binance.get_klines("BTCUSDT", "4h", 100)
            if klines:
                patterns = recognize_patterns(klines, limit=50)
                sr = analyze_support_resistance(klines, lookback=100)

                if patterns.get("patterns_found", 0) > 0:
                    sp = patterns.get("strongest_pattern", {})
                    ps = patterns.get("signal", "NEUTRAL")
                    pc = C_BULL if "BUY" in ps else C_BEAR if "SELL" in ps else C_TEXT

                    # 支撑阻力摘要
                    sup = sr.get("nearest_support", {})
                    res = sr.get("nearest_resistance", {})
                    sup_p = sup.get("price", 0) if sup else 0
                    res_p = res.get("price", 0) if res else 0

                    def ui_ta(ps=ps, sp=sp, pc=pc, sup_p=sup_p, res_p=res_p, patterns=patterns):
                        self.signal_text = ps
                        self.signal_color = pc
                        self.confidence_text = f"{patterns.get('bullish_count', 0) + patterns.get('bearish_count', 0) * 10}%"
                        self.analysis_summary = (
                            f"形态: {sp.get('description', '无')[:40]}\n"
                            f"支撑: ${sup_p:,.0f} | 阻力: ${res_p:,.0f}\n"
                            f"看多: {patterns.get('bullish_count', 0)} | 看空: {patterns.get('bearish_count', 0)}"
                        )
                        # RSI近似计算
                        if klines:
                            closes = [float(k.get('close', 0)) for k in klines[-14:] if k.get('close')]
                            if len(closes) == 14:
                                rsi_val = self._calc_rsi(closes)
                                self.rsi_value = f"{rsi_val:.0f}"
                                if rsi_val > 70:
                                    self.macd_value = "超买"
                                elif rsi_val < 30:
                                    self.macd_value = "超卖"
                                else:
                                    self.macd_value = "中性"
                            self.bb_value = f"{patterns.get('bullish_count',0)+patterns.get('bearish_count',0)*2}/10"
                    Clock.schedule_once(lambda *_: ui_ta())

            # 新闻情感
            try:
                from core.data.collectors.news.crypto_news import get_news_collector
                nc = get_news_collector()
                news_data = await nc.get_sentiment_summary()
                if news_data:
                    sentiment = news_data.get("sentiment", "neutral")
                    emoji = "📈" if sentiment == "bullish" else "📉" if sentiment == "bearish" else "➡️"
                    latest = news_data.get("latest_news", [{}])[0] or {}

                    def ui_news(sentiment=sentiment, emoji=emoji, latest=latest):
                        self.news_text = f"{emoji} {sentiment}\n{latest.get('title','')[:50]}"
                    Clock.schedule_once(lambda *_: ui_news())
            except Exception:
                pass

        except Exception as e:
            logger.error(f"_do_fetch: {e}")

    def _calc_rsi(self, closes, period=14):
        if len(closes) < period + 1:
            return 50.0
        gains = [max(closes[i] - closes[i-1], 0) for i in range(1, len(closes))]
        losses = [max(closes[i-1] - closes[i], 0) for i in range(1, len(closes))]
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))


# ─────────────────────────────────────────────────────────
# 图表全屏
# ─────────────────────────────────────────────────────────
class ChartScreen(Screen):
    """K线图表全屏 - 纯Canvas绘制"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.klines_data = []
        self.candle_widget = None
        self.volume_widget = None
        self.summary_label = None
        self.patterns_label = None

    def on_enter(self):
        self._load_chart()

    def _load_chart(self):
        """从API获取数据并绘制"""
        threading.Thread(target=self._fetch_chart_data, daemon=True).start()

    def _fetch_chart_data(self):
        try:
            import urllib.request, json
            # 获取K线数据
            req = urllib.request.Request(
                "http://localhost:8765/api/analysis/patterns?symbol=BTCUSDT&limit=50",
                headers={"Accept": "application/json"}
            )
            # 如果API不可用，直接用binance
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._draw_chart_async())
            loop.close()
        except Exception as e:
            logger.error(f"图表数据加载失败: {e}")

    async def _draw_chart_async(self):
        binance = BinanceSpotCollector()
        klines = await binance.get_klines("BTCUSDT", "4h", 50)
        if not klines:
            return

        candles = []
        volumes = []
        for k in klines:
            o = float(k.get("open", 0))
            h = float(k.get("high", 0))
            l = float(k.get("low", 0))
            c = float(k.get("close", 0))
            v = float(k.get("volume", 0))
            ts = k.get("timestamp", 0)
            is_bull = c >= o
            candles.append({"open": o, "high": h, "low": l, "close": c, "ts": ts, "bull": is_bull})
            volumes.append({"vol": v, "bull": is_bull})

        def ui():
            self._draw_candles(candles)
            self._draw_volumes(volumes)
            self._update_summary(klines)
        Clock.schedule_once(lambda *_: ui())

    def _draw_candles(self, candles):
        """用Kivy Canvas绘制K线"""
        container = self.manager.get_screen("chart").ids.get("chart_container")
        if not container:
            return

        container.clear_widgets()
        w = Widget(size=container.size, pos=container.pos)
        container.add_widget(w)

        if not candles:
            return

        w, h = container.size
        n = len(candles)
        padding = 40
        chart_w = w - padding * 2
        chart_h = h - padding * 2

        # 计算价格范围
        all_prices = []
        for c in candles:
            all_prices.extend([c["high"], c["low"]])
        price_min = min(all_prices)
        price_max = max(all_prices)
        price_range = max(price_max - price_min, 1)

        def px(price):
            return padding + (price - price_min) / price_range * chart_h

        def pw(i):
            return padding + i / n * chart_w

        bar_w = max(chart_w / n * 0.7, 2)

        with w.canvas:
            for i, c in enumerate(candles):
                bx = pw(i) - bar_w / 2
                color = C_BULL if c["bull"] else C_BEAR

                # K线实体
                body_top = px(c["close"])
                body_bot = px(c["open"])
                if body_top < body_bot:
                    body_top, body_bot = body_bot, body_top

                Color(*color)
                if abs(body_top - body_bot) < 1:
                    # 十字星
                    Line(points=[bx + bar_w/2, px(c["low"]), bx + bar_w/2, px(c["high"])], width=1)
                else:
                    # 实体
                    Rectangle(pos=(bx, body_bot), size=(bar_w, max(body_top - body_bot, 1)))
                    # 上影线
                    Line(points=[bx + bar_w/2, px(c["high"]), bx + bar_w/2, body_top], width=1)
                    # 下影线
                    Line(points=[bx + bar_w/2, body_bot, bx + bar_w/2, px(c["low"])], width=1)

    def _draw_volumes(self, volumes):
        """绘制成交量柱"""
        container = self.manager.get_screen("chart").ids.get("volume_container")
        if not container:
            return

        container.clear_widgets()
        wdg = Widget(size=container.size, pos=container.pos)
        container.add_widget(wdg)

        if not volumes:
            return

        w, h = container.size
        n = len(volumes)
        padding = 30
        chart_w = w - padding * 2
        chart_h = h - padding * 2

        vols = [v["vol"] for v in volumes]
        max_vol = max(vols) if vols else 1

        bar_w = max(chart_w / n * 0.7, 2)

        def py(vol):
            return padding + (vol / max_vol) * chart_h

        def pw(i):
            return padding + i / n * chart_w

        with wdg.canvas:
            for i, v in enumerate(volumes):
                bx = pw(i) - bar_w / 2
                color = (C_BULL[0], C_BULL[1], C_BULL[2], 0.5) if v["bull"] else (C_BEAR[0], C_BEAR[1], C_BEAR[2], 0.5)
                Color(*color)
                Rectangle(pos=(bx, padding), size=(bar_w, py(v["vol"]) - padding))

    def _update_summary(self, klines):
        """更新摘要标签"""
        screen = self.manager.get_screen("chart")
        summary_lbl = screen.ids.get("chart_summary_lbl")
        patterns_lbl = screen.ids.get("chart_patterns_lbl")

        if klines:
            patterns = recognize_patterns(klines, limit=50)
            sr = analyze_support_resistance(klines, lookback=50)

            if summary_lbl:
                sup = sr.get("nearest_support", {})
                res = sr.get("nearest_resistance", {})
                summary_lbl.text = (
                    f"最近支撑: ${sup.get('price', 0):,.0f} | "
                    f"最近阻力: ${res.get('price', 0):,.0f}"
                )
            if patterns_lbl:
                p = patterns.get("strongest_pattern", {})
                patterns_lbl.text = f"{patterns.get('patterns_found', 0)}个形态 | " \
                    f"信号: {patterns.get('signal', 'NEUTRAL')}\n" \
                    f"最强: {p.get('description', '无')}"


# ─────────────────────────────────────────────────────────
# 知识库详情
# ─────────────────────────────────────────────────────────
class KnowledgeDetailScreen(Screen):
    kb_stats = StringProperty("加载中...")

    def on_enter(self):
        self._load_stats()

    def _load_stats(self):
        threading.Thread(target=self._fetch_stats, daemon=True).start()

    def _fetch_stats(self):
        try:
            import urllib.request, json
            r = urllib.request.urlopen(
                "http://localhost:8765/api/knowledge/stats",
                timeout=10
            )
            d = json.loads(r.read())
            stats_text = (
                f"总模式: {d.get('total_patterns', 0)}\n"
                f"成功: {d.get('successes', 0)} | 失败: {d.get('failures', 0)} | 中性: {d.get('neutrals', 0)}\n"
                f"胜率: {d.get('win_rate', 0):.0f}%\n"
                f"平均利润: {d.get('avg_profit_success', 0):.2f}%\n"
                f"向量维度: {d.get('vector_dimension', 0)} | sqlite-vss: {'是' if d.get('vss_enabled') else '余弦降级'}"
            )
            Clock.schedule_once(lambda *_: setattr(self, 'kb_stats', stats_text))
        except Exception as e:
            Clock.schedule_once(lambda *_: setattr(self, 'kb_stats', f"加载失败: {e}"))




# SettingsScreen 从独立模块导入
from mobile.settings_screen import SettingsScreen

# ─────────────────────────────────────────────────────────
# CryptoMindApp
# ─────────────────────────────────────────────────────────
class CryptoMindApp(MDApp):
    current_symbol = StringProperty("BTCUSDT")
    current_timeframe = StringProperty("4h")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sm: ScreenManager = None
        self.main_screen: MainScreen = None
        self.chart_screen: ChartScreen = None
        self.kb_screen: KnowledgeDetailScreen = None

    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Blue"

        Builder.load_file("cryptomind.kv")

        self.sm = ScreenManager(transition=NoTransition())
        self.main_screen = MainScreen(name="main")
        self.chart_screen = ChartScreen(name="chart")
        self.kb_screen = KnowledgeDetailScreen(name="knowledge_detail")

        self.sm.add_widget(self.main_screen)
        self.sm.add_widget(self.chart_screen)
        self.sm.add_widget(self.kb_screen)

        from mobile_app import SettingsScreen
        self.settings_screen = SettingsScreen(name="settings")
        self.sm.add_widget(self.settings_screen)

        return self.sm

    def refresh_data(self):
        if self.main_screen:
            self.main_screen.refresh_data()

    def show_chart_fullscreen(self):
        self.sm.current = "chart"

    def show_knowledge_base(self):
        self.sm.current = "knowledge_detail"

    def show_history(self):
        self.sm.current = "chart"

    def go_to_analysis(self):
        pass

    def go_to_settings(self):
        if hasattr(self, 'settings_screen') and self.settings_screen:
            self.sm.current = "settings"
        else:
            from mobile.settings_screen import SettingsScreen
            self.settings_screen = SettingsScreen(name="settings")
            self.sm.add_widget(self.settings_screen)
            self.sm.current = "settings"

    def save_settings(self):
        """保存设置到配置管理器"""
        try:
            from config.config_manager import config_manager
            
            # 获取SettingsScreen中的控件值
            settings_screen = self.sm.get_screen("settings")
            root = settings_screen.children[0]  # MDBoxLayout
            
            # 遍历控件保存配置
            # 这里简化处理，实际需要根据控件ID获取值
            
            logger.info("💾 正在保存设置...")
            # TODO: 实现完整的设置保存逻辑
            # config_manager.set("display.default_symbol", symbol)
            # config_manager.set("ai_model.temperature", temp)
            
        except Exception as e:
            logger.error(f"保存设置失败: {e}")

    def reset_settings(self):
        """重置设置为默认值"""
        try:
            import urllib.request
            url = "http://127.0.0.1:8000/api/config/reset"
            req = urllib.request.Request(url, method="POST")
            req.add_header("Content-Type", "application/json")
            req.data = b'{}'
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                logger.info(f"🔄 设置已重置: {result}")
        except Exception as e:
            logger.error(f"重置设置失败: {e}")

    def load_config_to_ui(self):
        """从配置管理器加载配置到UI"""
        try:
            import urllib.request
            req = urllib.request.Request("http://127.0.0.1:8000/api/config")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                return data.get('data', {})
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            return {}

    def on_stop(self):
        pass


if __name__ == "__main__":
    CryptoMindApp().run()
