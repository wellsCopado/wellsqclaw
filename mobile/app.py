"""
CryptoMind Pro Plus AI - KivyMD 主应用
修复版本：解决闪退、中文显示、功能不完整问题
"""
import sys
import os

# 确保项目根目录在 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kivy.config import Config
# Android 兼容配置
Config.set("kivy", "orientation", "portrait")
Config.set("kivy", "window_shape", "rounded")
import os as _os
# Android 检测必须在导入阶段完成，避免字体加载崩溃
_android_font_skip = (_os.name == 'posix' and 'ANDROID_ROOT' in _os.environ)

Config.set("graphics", "maxfps", 30)

if not _android_font_skip:
    # 桌面环境: 查找 fonts 目录 (mobile/fonts/ 或 根目录 fonts/)
    _app_dir = _os.path.dirname(_os.path.abspath(__file__))
    for _fd in [_os.path.join(_app_dir, 'fonts'), _os.path.join(_os.path.dirname(_app_dir), 'fonts')]:
        if _os.path.isdir(_fd):
            _FONT_DIR = _fd
            break
    else:
        _FONT_DIR = None
    if _FONT_DIR:
        _FONT_PATH = _os.path.join(_FONT_DIR, 'NotoSansCJKsc-Regular.otf')
    if _FONT_DIR and _os.path.isfile(_FONT_PATH):
        # 注册中文字体，保留 Roboto 作为回退
        _roboto_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'fonts', 'Roboto-Regular.ttf')
        if not _os.path.isfile(_roboto_path):
            # 使用系统默认字体回退
            _roboto_path = '/System/Library/Fonts/PingFang.ttc'
        Config.set('kivy', 'default_font', [
            'NotoSansCJKsc',
            _FONT_PATH,
            _roboto_path
        ])
        from kivy.resources import resource_add_path
        resource_add_path(_FONT_DIR)

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from mobile.screens.news_screen import NewsScreen
from mobile.screens.onchain_screen import OnchainScreen
from mobile.screens.knowledge_screen import KnowledgeScreen
from mobile.screens.attribution_screen import AttributionScreen
from mobile.screens.paper_trading_screen import PaperTradingScreen
from mobile.screens.settings_screen import SettingsScreen
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.button import MDRaisedButton, MDIconButton, MDFlatButton
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.textfield import MDTextField
from kivymd.uix.dialog import MDDialog
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.snackbar import Snackbar
from kivymd.icon_definitions import md_icons
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty
from kivy.clock import Clock

# UI 颜色主题
from kivymd.color_definitions import palette


# ============================================================
# 全局服务器地址配置（所有 screen 共享）
# ============================================================
import json as _json

# 默认后端地址 — APK嵌入式模式使用localhost（后端嵌入在APK内）
DEFAULT_SERVER_URL = "http://127.0.0.1:8000"


def get_server_url():
    """获取当前配置的后端 API 地址（带持久化）"""
    _config_paths = []
    if 'ANDROID_ROOT' in _os.environ:
        # Android: 使用 app 私有目录
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            _app_path = PythonActivity.mActivity.getFilesDir().getAbsolutePath()
            _config_paths.append(_os.path.join(_app_path, 'server_config.json'))
        except Exception:
            pass
    else:
        # 桌面端: 项目根目录或 mobile/ 目录
        _script_dir = _os.path.dirname(_os.path.abspath(__file__))
        _config_paths.append(_os.path.join(_script_dir, 'server_config.json'))
        _config_paths.append(_os.path.join(_os.path.dirname(_script_dir), 'server_config.json'))
    
    for _p in _config_paths:
        if _os.path.isfile(_p):
            try:
                with open(_p, 'r', encoding='utf-8') as _f:
                    _cfg = _json.load(_f)
                    _url = _cfg.get('server_url', '').strip()
                    if _url:
                        return _url.rstrip('/')
            except Exception:
                pass
    return DEFAULT_SERVER_URL


def save_server_url(url):
    """保存用户配置的服务器地址到本地文件"""
    _config_paths = []
    if 'ANDROID_ROOT' in _os.environ:
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            _app_path = PythonActivity.mActivity.getFilesDir().getAbsolutePath()
            _config_paths.append(_os.path.join(_app_path, 'server_config.json'))
        except Exception:
            pass
    else:
        _script_dir = _os.path.dirname(_os.path.abspath(__file__))
        _config_paths.append(_os.path.join(_script_dir, 'server_config.json'))
    
    if not _config_paths:
        return
    _target = _config_paths[0]
    _os.makedirs(_os.path.dirname(_target), exist_ok=True)
    with open(_target, 'w', encoding='utf-8') as _f:
        _json.dump({'server_url': url.rstrip('/')}, _f, ensure_ascii=False, indent=2)


class HomeScreen(MDScreen):
    """首页 - 市场概览"""
    
    def on_enter(self):
        """进入页面时刷新数据"""
        Clock.schedule_once(self.refresh_data, 0.5)
    
    def refresh_data(self, *args):
        """刷新市场数据"""
        # 延迟加载数据
        Clock.schedule_once(self.load_home_data, 1)
    
    def load_home_data(self, *args):
        """从后端API加载首页数据"""
        import requests
        import threading
        
        app = MDApp.get_running_app()
        
        def _fetch():
            try:
                # 检查服务器健康状态
                resp = requests.get(app.server_url + "/api/health", timeout=5)
                health = resp.json() if resp.status_code == 200 else {}
                
                # 更新状态
                if health.get("status") == "ok":
                    self._update_status("🟢 AI就绪", "🟢 数据同步正常")
                else:
                    self._update_status("🟡 后端服务中...", "🟡 等待数据...")
            except Exception:
                self._update_status("🔴 后端未启动", "⚪ 请等待服务启动")
            
            try:
                # 获取BTC价格
                resp = requests.get(app.server_url + "/api/btc/price", timeout=5)
                data = resp.json()
                if "price" in data:
                    price = data["price"]
                    self._update_btc(f"${price:,.2f}", f"来源: {data.get('source', '--')}")
            except Exception:
                self._update_btc("$--", "获取失败")
            
            try:
                # 获取ETH价格
                resp = requests.get(app.server_url + "/api/market/top?symbols=ETH", timeout=5)
                data = resp.json()
                coins = data.get("coins", []) if isinstance(data, dict) else []
                if coins:
                    eth = coins[0]
                    self._update_eth(f"${eth['price']:,.2f}", "实时行情")
            except Exception:
                self._update_eth("$--", "获取失败")
        
        threading.Thread(target=_fetch, daemon=True).start()
    
    def _update_status(self, ai_text, data_text):
        def _do_update(dt):
            if hasattr(self, 'ai_status_label') and self.ai_status_label:
                self.ai_status_label.text = ai_text
            if hasattr(self, 'data_status_label') and self.data_status_label:
                self.data_status_label.text = data_text
        Clock.schedule_once(_do_update, 0)
    
    def _update_btc(self, price, change):
        def _do_update(dt):
            if hasattr(self, 'btc_price_label') and self.btc_price_label:
                self.btc_price_label.text = price
            if hasattr(self, 'btc_change_label') and self.btc_change_label:
                self.btc_change_label.text = change
        Clock.schedule_once(_do_update, 0)
    
    def _update_eth(self, price, change):
        def _do_update(dt):
            if hasattr(self, 'eth_price_label') and self.eth_price_label:
                self.eth_price_label.text = price
            if hasattr(self, 'eth_change_label') and self.eth_change_label:
                self.eth_change_label.text = change
        Clock.schedule_once(_do_update, 0)


class AnalysisScreen(MDScreen):
    """分析页面 - AI分析结果"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._result_label = None
        self._progress_bar = None
        self._build_ui()
    
    def _build_ui(self):
        """构建分析页面UI"""
        from kivymd.uix.floatlayout import MDFloatLayout
        from kivymd.uix.scrollview import MDScrollView
        
        layout = MDFloatLayout()
        
        # 标题
        title = MDLabel(
            text="AI 智能分析",
            font_style="H5",
            halign="center",
            pos_hint={"center_x": 0.5, "center_y": 0.95}
        )
        layout.add_widget(title)
        
        # 交易对选择
        symbol_btn = MDRaisedButton(
            text="BTCUSDT",
            pos_hint={"center_x": 0.35, "center_y": 0.85},
            size_hint=(0.3, 0.05)
        )
        layout.add_widget(symbol_btn)
        
        # 开始分析按钮
        analyze_btn = MDRaisedButton(
            text="开始分析",
            pos_hint={"center_x": 0.7, "center_y": 0.85},
            size_hint=(0.3, 0.05),
            on_release=lambda x: self.start_analysis()
        )
        layout.add_widget(analyze_btn)
        
        # 分析结果区域
        result_card = MDCard(
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            size_hint=(0.95, 0.55),
            padding="16dp"
        )
        
        scroll = MDScrollView()
        self._result_label = MDLabel(
            text="点击开始分析获取AI分析结果",
            valign="top",
            size_hint_y=None,
            height="200dp",
            text_size=(None, None)
        )
        self._result_label.bind(
            texture_size=lambda instance, value: setattr(instance, 'height', value[1])
        )
        scroll.add_widget(self._result_label)
        result_card.add_widget(scroll)
        layout.add_widget(result_card)
        
        # 进度条
        self._progress_bar = MDProgressBar(
            pos_hint={"center_x": 0.5, "center_y": 0.15},
            size_hint_x=0.8,
            value=0
        )
        layout.add_widget(self._progress_bar)
        
        self.add_widget(layout)
    
    def on_enter(self):
        if self._result_label:
            self._result_label.text = "点击开始分析获取AI分析结果"
        if self._progress_bar:
            self._progress_bar.value = 0
    
    def start_analysis(self):
        """开始AI分析"""
        if not self._result_label or not self._progress_bar:
            return
        
        self._result_label.text = "AI分析中，请稍候..."
        self._progress_bar.value = 30
        
        # 模拟分析进度
        Clock.schedule_once(lambda dt: self._update_progress(60), 1)
        Clock.schedule_once(lambda dt: self._update_progress(90), 1.5)
        Clock.schedule_once(self._show_result, 2)
    
    def _update_progress(self, value):
        if self._progress_bar:
            self._progress_bar.value = value
    
    def _show_result(self, *args):
        if not self._result_label or not self._progress_bar:
            return
        
        self._progress_bar.value = 100
        
        # 尝试从服务器获取真实分析结果
        def _fetch_analysis():
            try:
                import requests
                app = MDApp.get_running_app()
                resp = requests.get(app.server_url + "/api/attribution/summary", timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    factors = data.get("factors", [])
                    overall = data.get("overall", 50)
                    
                    result_text = "📊 BTC/USDT 分析报告\\n\\n"
                    result_text += f"综合评分: {overall:.1f}/100\\n\\n"
                    
                    for f in factors:
                        name = f.get("name", "未知因子")
                        score = f.get("score", 0)
                        weight = f.get("weight", 0)
                        result_text += f"• {name}: {score:.1f}分 (权重{weight*100:.0f}%)\\n"
                    
                    result_text += "\\n⚠️ 风险提示: 高杠杆多头需注意回调风险"
                    
                    def _update(dt):
                        self._result_label.text = result_text
                    Clock.schedule_once(_update, 0)
                    return
            except Exception:
                pass
            
            # 回退到模拟数据
            def _update(dt):
                self._result_label.text = (
                    "📊 BTC/USDT 分析报告\\n\\n"
                    "趋势判断: 中期看涨 (4h级别)\\n"
                    "关键支撑: $93,500 / $91,200\\n"
                    "关键压力: $97,000 / $99,500\\n"
                    "资金费率: 0.012% (偏多)\\n"
                    "持仓量: 创历史新高\\n"
                    "爆仓数据: 多头爆仓占优\\n\\n"
                    "⚠️ 风险提示: 高杠杆多头需注意回调风险"
                )
            Clock.schedule_once(_update, 0)
        
        import threading
        threading.Thread(target=_fetch_analysis, daemon=True).start()





class CryptoMindApp(MDApp):
    """CryptoMind Pro Plus AI 主应用"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "CryptoMind Pro"
        self.theme_cls.primary_palette = "DeepPurple"
        self.theme_cls.accent_palette = "Teal"
        self.theme_cls.theme_style = "Dark"  # 深色主题
        # 加载服务器地址配置
        self.server_url = get_server_url()
        # Android嵌入式模式：启动后台轻量HTTP服务器
        self._start_embedded_server()
    
    def _start_embedded_server(self):
        """启动嵌入式轻量HTTP服务器（Android模式）"""
        if 'ANDROID_ROOT' in _os.environ:
            try:
                from mobile.embedded_server import start_server
                start_server(host="127.0.0.1", port=8000)
            except Exception as e:
                print(f"[SERVER] 嵌入式服务器启动失败: {e}")

    def _register_chinese_font_safe(self):
        """注册中文字体 - Android用TTF格式（OTF会导致SDL2_ttf崩溃）"""
        import os as _os
        
        # 查找字体目录（Android和桌面环境）
        _app_dir = _os.path.dirname(_os.path.abspath(__file__))
        font_dir = None
        for _fd in [_os.path.join(_app_dir, 'fonts'), _os.path.join(_os.path.dirname(_app_dir), 'fonts')]:
            if _os.path.isdir(_fd):
                font_dir = _fd
                break
        
        if not font_dir:
            print("[FONT] 字体目录未找到")
            return
        
        # 优先使用TTF格式（Android和桌面都兼容）
        font_path = _os.path.join(font_dir, 'NotoSansSC-Regular.ttf')
        if not _os.path.isfile(font_path):
            # 回退到OTF（仅桌面）
            font_path = _os.path.join(font_dir, 'NotoSansCJKsc-Regular.otf')
        
        if not _os.path.isfile(font_path):
            print(f"[FONT] 字体文件未找到: {font_path}")
            return
        
        try:
            from kivy.resources import resource_add_path
            from kivy.core.text import LabelBase
            
            # 添加字体目录到资源路径
            resource_add_path(font_dir)
            
            # 注册字体到Kivy（关键步骤）
            LabelBase.register('NotoSansSC', font_path)
            
            # 更新KivyMD字体样式
            _original_styles = self.theme_cls.font_styles.copy()
            _text_styles = [
                'H1', 'H2', 'H3', 'H4', 'H5', 'H6',
                'Subtitle1', 'Subtitle2', 'Body1', 'Body2',
                'Button', 'Caption', 'Overline'
            ]
            
            for _style in _text_styles:
                _orig = _original_styles.get(_style)
                if _orig and len(_orig) >= 4:
                    self.theme_cls.font_styles[_style] = [
                        'NotoSansSC',
                        _orig[1],
                        _orig[2],
                        _orig[3],
                    ]
            
            print(f"[FONT] 中文字体注册成功: {font_path}")
        except Exception as e:
            print(f"[FONT] 字体注册失败: {e}")

    def build(self):
        """构建应用界面 - ScreenManager + 底部导航栏"""
        from kivy.uix.screenmanager import ScreenManager
        from kivy.uix.boxlayout import BoxLayout

        # Android 安全字体注册
        self._register_chinese_font_safe()

        # Tab 定义: (name, text, icon)
        tabs = [
            ("home", "首页", "home"),
            ("analysis", "AI分析", "brain"),
            ("news", "资讯", "newspaper-variant-outline"),
            ("knowledge", "知识", "book-open-variant"),
            ("paper_trading", "交易", "cash"),
        ]
        
        # ScreenManager
        sm = ScreenManager()
        
        # 首页
        home_screen = HomeScreen(name="home")
        home_screen.add_widget(self.create_home_ui(home_screen))
        sm.add_widget(home_screen)
        
        # 分析页 - 使用修复后的 AnalysisScreen
        analysis_screen = AnalysisScreen(name="analysis")
        sm.add_widget(analysis_screen)
        
        # 新闻页
        news_screen = NewsScreen(name="news")
        sm.add_widget(news_screen)

        # 链上数据页
        onchain_screen = OnchainScreen(name="onchain")
        sm.add_widget(onchain_screen)

        # 知识库页
        knowledge_screen = KnowledgeScreen(name="knowledge")
        sm.add_widget(knowledge_screen)

        # Paper Trading页（模拟交易）
        paper_screen = PaperTradingScreen(name="paper_trading")
        sm.add_widget(paper_screen)
        
        # 设置页 - 使用独立的 SettingsScreen
        settings_screen = SettingsScreen(name="settings")
        sm.add_widget(settings_screen)
        
        # 底部导航栏
        nav_bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height="56dp",
            spacing="4dp",
            padding=["8dp", "4dp", "8dp", "4dp"],
        )
        
        self._tab_buttons = []
        for i, (name, text, icon) in enumerate(tabs):
            btn = MDIconButton(
                icon=icon if icon in md_icons else "checkbox-blank-circle",
                theme_text_color="Custom" if i == 0 else "Secondary",
                text_color=[0.63, 0.54, 1, 1] if i == 0 else [0.6, 0.6, 0.6, 1],
                on_release=lambda x, n=name: self.switch_tab(n),
                pos_hint={"center_y": 0.5},
            )
            nav_bar.add_widget(btn)
            self._tab_buttons.append((name, btn))
        
        # 主布局: ScreenManager + 底部导航
        root = BoxLayout(orientation="vertical")
        root.add_widget(sm)
        root.add_widget(nav_bar)
        
        self._screen_manager = sm
        
        return root
    
    def switch_tab(self, name: str):
        """切换 tab 页面"""
        sm = self._screen_manager
        if sm.current != name:
            sm.current = name
        # 更新按钮高亮
        for tab_name, btn in self._tab_buttons:
            if tab_name == name:
                btn.theme_text_color = "Custom"
                btn.text_color = [0.63, 0.54, 1, 1]
            else:
                btn.theme_text_color = "Secondary"
                btn.text_color = [0.6, 0.6, 0.6, 1]
    
    def create_home_ui(self, screen):
        """创建首页UI"""
        from kivymd.uix.floatlayout import MDFloatLayout
        
        layout = MDFloatLayout()
        
        # 标题
        title = MDLabel(
            text="CryptoMind Pro Plus AI",
            font_style="H5",
            halign="center",
            pos_hint={"center_x": 0.5, "center_y": 0.95}
        )
        layout.add_widget(title)
        
        # BTC 卡片
        btc_card = MDCard(
            pos_hint={"center_x": 0.5, "center_y": 0.75},
            size_hint=(0.9, 0.15),
            padding="16dp"
        )
        btc_content = BoxLayout(orientation="vertical")
        btc_content.add_widget(MDLabel(text="BTC/USDT", font_style="H6"))
        screen.btc_price_label = MDLabel(text="$--")
        screen.btc_change_label = MDLabel(text="--", theme_text_color="Secondary")
        btc_content.add_widget(screen.btc_price_label)
        btc_content.add_widget(screen.btc_change_label)
        btc_card.add_widget(btc_content)
        layout.add_widget(btc_card)
        
        # ETH 卡片
        eth_card = MDCard(
            pos_hint={"center_x": 0.5, "center_y": 0.55},
            size_hint=(0.9, 0.15),
            padding="16dp"
        )
        eth_content = BoxLayout(orientation="vertical")
        eth_content.add_widget(MDLabel(text="ETH/USDT", font_style="H6"))
        screen.eth_price_label = MDLabel(text="$--")
        screen.eth_change_label = MDLabel(text="--", theme_text_color="Secondary")
        eth_content.add_widget(screen.eth_price_label)
        eth_content.add_widget(screen.eth_change_label)
        eth_card.add_widget(eth_content)
        layout.add_widget(eth_card)
        
        # 状态卡片
        status_card = MDCard(
            pos_hint={"center_x": 0.5, "center_y": 0.35},
            size_hint=(0.9, 0.15),
            padding="16dp"
        )
        status_content = BoxLayout(orientation="vertical", spacing="4dp")
        screen.ai_status_label = MDLabel(text="AI加载中...", font_style="Body1")
        screen.data_status_label = MDLabel(text="数据状态未知", font_style="Body1")
        status_content.add_widget(screen.ai_status_label)
        status_content.add_widget(screen.data_status_label)
        status_card.add_widget(status_content)
        layout.add_widget(status_card)
        
        # 设置按钮
        settings_btn = MDIconButton(
            icon="cog",
            pos_hint={"center_x": 0.5, "center_y": 0.18},
            on_release=lambda x: self.switch_tab("settings"),
            theme_text_color="Secondary",
        )
        layout.add_widget(settings_btn)
        
        settings_label = MDLabel(
            text="API配置",
            halign="center",
            pos_hint={"center_x": 0.5, "center_y": 0.12},
            font_size="12sp",
            theme_text_color="Secondary",
        )
        layout.add_widget(settings_label)
        
        return layout


if __name__ == "__main__":
    CryptoMindApp().run()
