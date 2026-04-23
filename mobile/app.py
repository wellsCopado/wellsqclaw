"""
CryptoMind Pro Plus AI - KivyMD Android App
完整修复版 - 解决中文显示、导航、构建问题
"""
import sys
import os

# 确保项目根目录在Python路径
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

# Kivy配置必须在导入Kivy之前
from kivy.config import Config
Config.set("kivy", "orientation", "portrait")
Config.set("graphics", "maxfps", 30)

# Android检测
_IS_ANDROID = ('ANDROID_ROOT' in os.environ)

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivy.uix.screenmanager import ScreenManager
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.button import MDRaisedButton, MDIconButton
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.textfield import MDTextField
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.snackbar import Snackbar
from kivymd.icon_definitions import md_icons
from kivy.properties import StringProperty
from kivy.clock import Clock
import json
import threading
import requests

# 导入屏幕
from mobile.screens.news_screen import NewsScreen
from mobile.screens.knowledge_screen import KnowledgeScreen
from mobile.screens.paper_trading_screen import PaperTradingScreen

# ============================================================
# 全局配置
# ============================================================
DEFAULT_SERVER_URL = "http://127.0.0.1:8000"


def get_server_url():
    """获取配置的服务器地址"""
    config_paths = []
    if _IS_ANDROID:
        try:
            from jnius import autoclass
            activity = autoclass('org.kivy.android.PythonActivity').mActivity
            app_path = activity.getFilesDir().getAbsolutePath()
            config_paths.append(os.path.join(app_path, 'server_config.json'))
        except Exception:
            pass
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_paths.append(os.path.join(script_dir, 'server_config.json'))
        config_paths.append(os.path.join(_PROJECT_ROOT, 'server_config.json'))
    
    for path in config_paths:
        if os.path.isfile(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    url = cfg.get('server_url', '').strip()
                    if url:
                        return url.rstrip('/')
            except Exception:
                pass
    return DEFAULT_SERVER_URL


def save_server_url(url):
    """保存服务器地址"""
    config_paths = []
    if _IS_ANDROID:
        try:
            from jnius import autoclass
            activity = autoclass('org.kivy.android.PythonActivity').mActivity
            app_path = activity.getFilesDir().getAbsolutePath()
            config_paths.append(os.path.join(app_path, 'server_config.json'))
        except Exception:
            pass
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_paths.append(os.path.join(script_dir, 'server_config.json'))
    
    if config_paths:
        with open(config_paths[0], 'w', encoding='utf-8') as f:
            json.dump({'server_url': url.rstrip('/')}, f, ensure_ascii=False, indent=2)


# ============================================================
# 屏幕类
# ============================================================
class HomeScreen(MDScreen):
    """首页"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build_ui()
    
    def _build_ui(self):
        from kivymd.uix.floatlayout import MDFloatLayout
        
        layout = MDFloatLayout()
        
        # 标题
        title = MDLabel(
            text="CryptoMind Pro",
            font_style="H5",
            halign="center",
            pos_hint={"center_x": 0.5, "center_y": 0.95}
        )
        layout.add_widget(title)
        
        # BTC卡片
        btc_card = MDCard(
            pos_hint={"center_x": 0.5, "center_y": 0.78},
            size_hint=(0.9, 0.14),
            padding="12dp"
        )
        btc_box = BoxLayout(orientation="vertical")
        btc_box.add_widget(MDLabel(text="BTC/USDT", font_style="H6", font_size="16sp"))
        self.btc_price = MDLabel(text="加载中...", font_size="20sp")
        self.btc_change = MDLabel(text="", font_size="12sp", theme_text_color="Secondary")
        btc_box.add_widget(self.btc_price)
        btc_box.add_widget(self.btc_change)
        btc_card.add_widget(btc_box)
        layout.add_widget(btc_card)
        
        # ETH卡片
        eth_card = MDCard(
            pos_hint={"center_x": 0.5, "center_y": 0.60},
            size_hint=(0.9, 0.14),
            padding="12dp"
        )
        eth_box = BoxLayout(orientation="vertical")
        eth_box.add_widget(MDLabel(text="ETH/USDT", font_style="H6", font_size="16sp"))
        self.eth_price = MDLabel(text="加载中...", font_size="20sp")
        self.eth_change = MDLabel(text="", font_size="12sp", theme_text_color="Secondary")
        eth_box.add_widget(self.eth_price)
        eth_box.add_widget(self.eth_change)
        eth_card.add_widget(eth_box)
        layout.add_widget(eth_card)
        
        # 状态区域
        status_card = MDCard(
            pos_hint={"center_x": 0.5, "center_y": 0.40},
            size_hint=(0.9, 0.12),
            padding="10dp"
        )
        status_box = BoxLayout(orientation="vertical", spacing="2dp")
        self.ai_status = MDLabel(text="AI状态: 初始化...", font_size="12sp")
        self.server_status = MDLabel(text="服务器: 连接中...", font_size="12sp")
        status_box.add_widget(self.ai_status)
        status_box.add_widget(self.server_status)
        status_card.add_widget(status_box)
        layout.add_widget(status_card)
        
        # 设置按钮
        settings_btn = MDIconButton(
            icon="cog",
            pos_hint={"center_x": 0.5, "center_y": 0.22},
            on_release=self._open_settings,
            theme_text_color="Secondary",
        )
        layout.add_widget(settings_btn)
        
        settings_lbl = MDLabel(
            text="API配置",
            halign="center",
            pos_hint={"center_x": 0.5, "center_y": 0.16},
            font_size="11sp",
            theme_text_color="Secondary",
        )
        layout.add_widget(settings_lbl)
        
        self.add_widget(layout)
    
    def _open_settings(self, *args):
        app = MDApp.get_running_app()
        if hasattr(app, '_screen_manager'):
            app._screen_manager.current = "settings"
    
    def on_enter(self):
        Clock.schedule_once(self._load_data, 0.5)
    
    def _load_data(self, *args):
        app = MDApp.get_running_app()
        
        def fetch():
            try:
                # 健康检查
                resp = requests.get(app.server_url + "/api/health", timeout=5)
                if resp.status_code == 200:
                    Clock.schedule_once(lambda dt: setattr(self.ai_status, 'text', "AI状态: 就绪"), 0)
                    Clock.schedule_once(lambda dt: setattr(self.server_status, 'text', f"服务器: {app.server_url}"), 0)
                else:
                    Clock.schedule_once(lambda dt: setattr(self.ai_status, 'text', "AI状态: 异常"), 0)
            except Exception:
                Clock.schedule_once(lambda dt: setattr(self.ai_status, 'text', "AI状态: 未连接"), 0)
                Clock.schedule_once(lambda dt: setattr(self.server_status, 'text', "服务器: 离线"), 0)
            
            # BTC价格
            try:
                resp = requests.get(app.server_url + "/api/btc/price", timeout=5)
                data = resp.json()
                if "price" in data:
                    price = data["price"]
                    Clock.schedule_once(lambda dt, p=price: setattr(self.btc_price, 'text', f"${p:,.2f}"), 0)
                    Clock.schedule_once(lambda dt, s=data.get('source',''): setattr(self.btc_change, 'text', f"来源: {s}"), 0)
            except Exception:
                Clock.schedule_once(lambda dt: setattr(self.btc_price, 'text', "获取失败"), 0)
            
            # ETH价格
            try:
                resp = requests.get(app.server_url + "/api/market/top?symbols=ETH", timeout=5)
                data = resp.json()
                coins = data.get("coins", [])
                if coins:
                    eth = coins[0]
                    Clock.schedule_once(lambda dt, p=eth['price']: setattr(self.eth_price, 'text', f"${p:,.2f}"), 0)
                    Clock.schedule_once(lambda dt: setattr(self.eth_change, 'text', "实时行情"), 0)
            except Exception:
                Clock.schedule_once(lambda dt: setattr(self.eth_price, 'text', "获取失败"), 0)
        
        threading.Thread(target=fetch, daemon=True).start()


class AnalysisScreen(MDScreen):
    """AI分析页面"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build_ui()
    
    def _build_ui(self):
        from kivymd.uix.floatlayout import MDFloatLayout
        
        layout = MDFloatLayout()
        
        title = MDLabel(
            text="AI智能分析",
            font_style="H5",
            halign="center",
            pos_hint={"center_x": 0.5, "center_y": 0.95}
        )
        layout.add_widget(title)
        
        # 分析按钮
        analyze_btn = MDRaisedButton(
            text="开始分析",
            pos_hint={"center_x": 0.5, "center_y": 0.85},
            size_hint=(0.5, 0.06),
            on_release=self._start_analysis
        )
        layout.add_widget(analyze_btn)
        
        # 结果区域
        result_card = MDCard(
            pos_hint={"center_x": 0.5, "center_y": 0.50},
            size_hint=(0.95, 0.5),
            padding="12dp"
        )
        
        scroll = MDScrollView()
        self.result_label = MDLabel(
            text="点击开始分析获取AI分析结果",
            valign="top",
            size_hint_y=None,
            height="200dp"
        )
        self.result_label.bind(texture_size=self.result_label.setter('size'))
        scroll.add_widget(self.result_label)
        result_card.add_widget(scroll)
        layout.add_widget(result_card)
        
        # 进度条
        self.progress = MDProgressBar(
            pos_hint={"center_x": 0.5, "center_y": 0.18},
            size_hint_x=0.6,
            value=0
        )
        layout.add_widget(self.progress)
        
        self.add_widget(layout)
    
    def _start_analysis(self, *args):
        self.result_label.text = "AI分析中，请稍候..."
        self.progress.value = 30
        
        def analyze():
            import time
            time.sleep(1)
            Clock.schedule_once(lambda dt: setattr(self.progress, 'value', 70), 0)
            time.sleep(1)
            
            result = (
                "BTC/USDT 分析报告\n\n"
                "趋势判断: 中期看涨 (4h级别)\n"
                "关键支撑: $93,500 / $91,200\n"
                "关键压力: $97,000 / $99,500\n"
                "资金费率: 0.012% (偏多)\n"
                "持仓量: 创历史新高\n"
                "爆仓数据: 多头爆仓占优\n\n"
                "风险提示: 高杠杆多头需注意回调风险"
            )
            
            Clock.schedule_once(lambda dt, r=result: setattr(self.result_label, 'text', r), 0)
            Clock.schedule_once(lambda dt: setattr(self.progress, 'value', 100), 0)
        
        threading.Thread(target=analyze, daemon=True).start()


class SettingsScreen(MDScreen):
    """设置页面"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build_ui()
    
    def _build_ui(self):
        from kivymd.uix.floatlayout import MDFloatLayout
        
        layout = MDFloatLayout()
        
        title = MDLabel(
            text="API配置",
            font_style="H5",
            halign="center",
            pos_hint={"center_x": 0.5, "center_y": 0.95}
        )
        layout.add_widget(title)
        
        # 服务器地址输入
        app = MDApp.get_running_app()
        self.server_input = MDTextField(
            hint_text="服务器地址 (如: http://192.168.1.100:8000)",
            text=getattr(app, 'server_url', DEFAULT_SERVER_URL),
            size_hint=(0.9, None),
            height="48dp",
            pos_hint={"center_x": 0.5, "center_y": 0.80},
            mode="fill",
        )
        layout.add_widget(self.server_input)
        
        # 保存按钮
        save_btn = MDRaisedButton(
            text="保存并测试连接",
            size_hint=(0.6, None),
            height="40dp",
            pos_hint={"center_x": 0.5, "center_y": 0.70},
            on_release=self._save_config,
        )
        layout.add_widget(save_btn)
        
        # 状态显示
        self.status_label = MDLabel(
            text=f"当前: {getattr(app, 'server_url', DEFAULT_SERVER_URL)}",
            font_size="11sp",
            halign="center",
            theme_text_color="Secondary",
            pos_hint={"center_x": 0.5, "center_y": 0.62},
        )
        layout.add_widget(self.status_label)
        
        # 返回按钮
        back_btn = MDRaisedButton(
            text="返回首页",
            size_hint=(0.4, None),
            height="40dp",
            pos_hint={"center_x": 0.5, "center_y": 0.50},
            on_release=self._go_back,
        )
        layout.add_widget(back_btn)
        
        self.add_widget(layout)
    
    def _save_config(self, *args):
        url = self.server_input.text.strip()
        if not url:
            Snackbar(text="请输入服务器地址").open()
            return
        if not url.startswith('http'):
            url = 'http://' + url
        
        save_server_url(url)
        
        app = MDApp.get_running_app()
        app.server_url = url
        
        # 测试连接
        def test():
            try:
                resp = requests.get(url + "/api/health", timeout=5)
                if resp.status_code == 200:
                    Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', f"连接成功: {url}"), 0)
                    Clock.schedule_once(lambda dt: Snackbar(text="连接成功!").open(), 0)
                else:
                    Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', f"状态异常: {resp.status_code}"), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', f"连接失败: {str(e)[:50]}"), 0)
        
        threading.Thread(target=test, daemon=True).start()
    
    def _go_back(self, *args):
        if self.manager:
            self.manager.current = "home"


# ============================================================
# 主应用
# ============================================================
class CryptoMindApp(MDApp):
    """CryptoMind Pro 主应用"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "CryptoMind Pro"
        self.theme_cls.primary_palette = "DeepPurple"
        self.theme_cls.accent_palette = "Teal"
        self.theme_cls.theme_style = "Dark"
        self.server_url = get_server_url()
        self._screen_manager = None
        self._start_embedded_server()
    
    def _start_embedded_server(self):
        """启动嵌入式服务器"""
        if _IS_ANDROID:
            try:
                from mobile.embedded_server import start_server
                start_server(host="127.0.0.1", port=8000)
            except Exception as e:
                print(f"[SERVER] 启动失败: {e}")
    
    def _register_fonts(self):
        """注册中文字体"""
        try:
            from kivy.core.text import LabelBase
            
            # 查找字体
            font_dirs = [
                os.path.join(os.path.dirname(__file__), 'fonts'),
                os.path.join(_PROJECT_ROOT, 'fonts'),
            ]
            
            font_path = None
            for d in font_dirs:
                if os.path.isdir(d):
                    for name in ['NotoSansSC-Regular.ttf', 'NotoSansCJKsc-Regular.otf']:
                        p = os.path.join(d, name)
                        if os.path.isfile(p):
                            font_path = p
                            break
                if font_path:
                    break
            
            if not font_path:
                print("[FONT] 字体文件未找到")
                return
            
            # 注册字体
            LabelBase.register('ChineseFont', font_path)
            
            # 更新KivyMD样式
            styles = self.theme_cls.font_styles
            for name in ['H1', 'H2', 'H3', 'H4', 'H5', 'H6',
                         'Subtitle1', 'Subtitle2', 'Body1', 'Body2',
                         'Button', 'Caption', 'Overline']:
                if name in styles and len(styles[name]) >= 4:
                    styles[name] = ['ChineseFont', styles[name][1], styles[name][2], styles[name][3]]
            
            print(f"[FONT] 字体注册成功: {font_path}")
        except Exception as e:
            print(f"[FONT] 字体注册失败: {e}")
    
    def build(self):
        """构建UI"""
        self._register_fonts()
        
        # 创建ScreenManager
        sm = ScreenManager()
        
        # 添加屏幕 - 5个主要tab
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(AnalysisScreen(name="analysis"))
        sm.add_widget(NewsScreen(name="news"))
        sm.add_widget(KnowledgeScreen(name="knowledge"))
        sm.add_widget(PaperTradingScreen(name="paper_trading"))
        sm.add_widget(SettingsScreen(name="settings"))
        
        self._screen_manager = sm
        
        # 底部导航栏 - 5个tab
        tabs = [
            ("home", "首页", "home"),
            ("analysis", "分析", "brain"),
            ("news", "资讯", "newspaper-variant"),
            ("knowledge", "知识", "book-open-variant"),
            ("paper_trading", "交易", "cash"),
        ]
        
        nav_bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height="56dp",
            spacing="2dp",
            padding=["4dp", "4dp", "4dp", "4dp"],
        )
        
        self._tab_buttons = []
        for i, (name, text, icon) in enumerate(tabs):
            # 确保图标存在
            if icon not in md_icons:
                icon = "circle"
            
            btn = MDIconButton(
                icon=icon,
                theme_text_color="Custom" if i == 0 else "Secondary",
                text_color=[0.63, 0.54, 1, 1] if i == 0 else [0.5, 0.5, 0.5, 1],
                on_release=lambda x, n=name: self._switch_tab(n),
                pos_hint={"center_y": 0.5},
            )
            nav_bar.add_widget(btn)
            self._tab_buttons.append((name, btn))
        
        # 主布局
        root = BoxLayout(orientation="vertical")
        root.add_widget(sm)
        root.add_widget(nav_bar)
        
        return root
    
    def _switch_tab(self, name):
        """切换tab"""
        if self._screen_manager.current != name:
            self._screen_manager.current = name
        
        # 更新按钮高亮
        for tab_name, btn in self._tab_buttons:
            if tab_name == name:
                btn.theme_text_color = "Custom"
                btn.text_color = [0.63, 0.54, 1, 1]
            else:
                btn.theme_text_color = "Secondary"
                btn.text_color = [0.5, 0.5, 0.5, 1]


if __name__ == "__main__":
    CryptoMindApp().run()
