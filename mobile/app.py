"""
CryptoMind Pro Plus AI - KivyMD 主应用
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
        Config.set('kivy', 'default_font', ['NotoSansCJKsc', _FONT_PATH, 'Roboto'])
        from kivy.resources import resource_add_path
        resource_add_path(_FONT_DIR)

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from mobile.screens.news_screen import NewsScreen
from mobile.screens.onchain_screen import OnchainScreen
from mobile.screens.knowledge_screen import KnowledgeScreen
from mobile.screens.attribution_screen import AttributionScreen
from mobile.screens.paper_trading_screen import PaperTradingScreen
from kivymd.uix.navigationdrawer import MDNavigationDrawer
# MDBottomNavigation/MDBottomNavigationItem removed: not available as Python class in KivyMD 1.2.0
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.button import MDRaisedButton, MDIconButton
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.textfield import MDTextField
from kivymd.uix.dialog import MDDialog
# MDSpinner removed: not available in KivyMD 1.2.0
from kivy.uix.image import Image
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.snackbar import Snackbar
from kivymd.icon_definitions import md_icons
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, BooleanProperty
from kivy.clock import Clock

# UI 颜色主题
from kivymd.color_definitions import palette


class HomeScreen(MDScreen):
    """首页 - 市场概览"""
    
    def on_enter(self):
        """进入页面时刷新数据"""
        Clock.schedule_once(self.refresh_data, 0.5)
    
    def refresh_data(self, *args):
        """刷新市场数据"""
        self.ids.btc_price.text = "Loading..."
        # 异步加载数据
        Clock.schedule_once(self.load_mock_data, 1)
    
    def load_mock_data(self, *args):
        """加载数据（临时用模拟数据）"""
        self.ids.btc_price.text = "$95,432.56"
        self.ids.eth_price.text = "$3,234.18"
        self.ids.btc_change.text = "+2.34%"
        self.ids.eth_change.text = "-1.21%"
        self.ids.ai_status.text = "🟢 AI就绪"
        self.ids.data_status.text = "📊 数据同步中..."


class AnalysisScreen(MDScreen):
    """分析页面 - AI分析结果"""
    
    def on_enter(self):
        self.ids.analysis_result.text = "点击开始分析获取AI分析结果"
    
    def start_analysis(self):
        """开始AI分析"""
        self.ids.analysis_result.text = "🔄 AI分析中，请稍候..."
        self.ids.analysis_result.text = "🔄 AI分析中..."
        self.ids.spinner.value = 50
        # 模拟分析
        Clock.schedule_once(self.show_result, 2)
    
    def show_result(self, *args):
        self.ids.spinner.value = 100
        self.ids.analysis_result.text = (
            "📊 BTC/USDT 分析报告\n\n"
            "趋势判断: 中期看涨 (4h级别)\n"
            "关键支撑: $93,500 / $91,200\n"
            "关键压力: $97,000 / $99,500\n"
            "资金费率: 0.012% (偏多)\n"
            "持仓量: 创历史新高\n"
            "爆仓数据: 多头爆仓占优\n\n"
            "⚠️ 风险提示: 高杠杆多头需注意回调风险"
        )


class SettingsScreen(MDScreen):
    """设置页面 - API Key 配置"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dialog = None
    
    def open_api_key_dialog(self, key_type: str):
        """打开API Key输入对话框"""
        if not self.dialog:
            self.dialog = MDDialog(
                title="配置 API Key",
                type="custom",
                content_cls=APIKeyInputContent(),
                buttons=[
                    MDRaisedButton(text="取消", on_release=lambda x: self.dialog.dismiss()),
                    MDRaisedButton(text="保存", on_release=self.save_api_key),
                ],
            )
        self.dialog.open()
    
    def save_api_key(self, *args):
        if self.dialog:
            self.dialog.dismiss()
            Snackbar(text="API Key 已保存").open()


class APIKeyInputContent(BoxLayout):
    """API Key 输入框"""
    api_key = StringProperty("")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.spacing = "12dp"
        self.padding = "12dp"
        
        self.add_widget(MDTextField(
            hint_text="API Key",
            password=True,
            on_text_validate=self.validate
        ))
    
    def validate(self):
        pass


# ============================================================
# 全局服务器地址配置（所有 screen 共享）
# ============================================================
import json as _json

# 默认后端地址 — 手机上请改为电脑的局域网 IP
DEFAULT_SERVER_URL = "http://192.168.31.218:8000"


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
    with open(_target, 'w', encoding='utf-8') as _f:
        _json.dump({'server_url': url.rstrip('/')}, _f, ensure_ascii=False, indent=2)


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
    
    def _register_chinese_font_safe(self):
        """Android: 完全跳过字体定制，避免 SDL2_ttf CJK 崩溃"""
        # Android: 跳过所有字体定制
        import os as _os
        if _os.name == 'posix' and 'ANDROID_ROOT' in _os.environ:
            return
        # 桌面: 字体定制逻辑可在此添加（当前 Android 优先，待后续稳定后扩展）
        try:
            _app_dir = _os.path.dirname(_os.path.abspath(__file__))
            for _fd in [_os.path.join(_app_dir, 'fonts'), _os.path.join(_os.path.dirname(_app_dir), 'fonts')]:
                if _os.path.isdir(_fd):
                    font_dir = _fd
                    break
            else:
                return
            font_path = _os.path.join(font_dir, 'NotoSansCJKsc-Regular.otf')
            if not _os.path.isfile(font_path):
                return
            _original_styles = self.theme_cls.font_styles.copy()
            _text_styles = [
                'H1', 'H2', 'H3', 'H4', 'H5', 'H6',
                'Subtitle1', 'Subtitle2', 'Body1', 'Body2',
                'Button', 'Caption', 'Overline'
            ]
            for _style in _text_styles:
                _orig = _original_styles.get(_style)
                if _orig:
                    self.theme_cls.font_styles[_style] = [
                        font_path, _orig[1], _orig[2], _orig[3]
                    ]
        except Exception:
            pass

    def build(self):
        """构建应用界面 - ScreenManager + 底部导航栏
        
        KivyMD 1.2.0 的 MDBottomNavigationItem 不作为 Python 类导出，
        只在 KV 语言中可用。因此用 ScreenManager + 自定义底部栏实现导航。
        """
        from kivy.uix.screenmanager import ScreenManager
        from kivy.uix.boxlayout import BoxLayout

        # Android 安全字体注册
        self._register_chinese_font_safe()

        # Tab 定义: (name, text, icon)
        tabs = [
            ("home", "首页", "home"),
            ("analysis", "分析", "brain"),
            ("news", "新闻", "newspaper-variant-outline"),
            ("onchain", "链上", "chain"),
            ("knowledge", "知识库", "brain"),
            ("attribution", "归因", "chart-pie"),
            ("paper_trading", "模拟", "cash"),
            ("settings", "设置", "cog"),
        ]
        
        # ScreenManager
        sm = ScreenManager()
        
        # 首页
        home = MDScreen(name="home")
        home.add_widget(self.create_home_ui())
        sm.add_widget(home)
        
        # 分析页
        analysis = MDScreen(name="analysis")
        analysis.add_widget(self.create_analysis_ui())
        sm.add_widget(analysis)
        
        # 新闻页
        news_screen = NewsScreen(name="news")
        sm.add_widget(news_screen)

        # 链上数据页
        onchain_screen = OnchainScreen(name="onchain")
        sm.add_widget(onchain_screen)

        # 知识库页
        knowledge_screen = KnowledgeScreen(name="knowledge")
        sm.add_widget(knowledge_screen)

        # 归因分析页
        attr_screen = AttributionScreen(name="attribution")
        sm.add_widget(attr_screen)

        # Paper Trading页
        paper_screen = PaperTradingScreen(name="paper_trading")
        sm.add_widget(paper_screen)
        
        # 设置页
        settings = MDScreen(name="settings")
        settings.add_widget(self.create_settings_ui())
        sm.add_widget(settings)
        
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
                btn.text_color = [0.63, 0.54, 1, 1]  # 紫色高亮
            else:
                btn.theme_text_color = "Secondary"
                btn.text_color = [0.6, 0.6, 0.6, 1]
    
    def create_home_ui(self):
        """创建首页UI"""
        from kivymd.uix.floatlayout import MDFloatLayout
        from kivymd.uix.label import MDLabel
        
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
        btc_content.add_widget(MDLabel(id="btc_price", text="$--"))
        btc_content.add_widget(MDLabel(id="btc_change", text="--", theme_text_color="Secondary"))
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
        eth_content.add_widget(MDLabel(id="eth_price", text="$--"))
        eth_content.add_widget(MDLabel(id="eth_change", text="--", theme_text_color="Secondary"))
        eth_card.add_widget(eth_content)
        layout.add_widget(eth_card)
        
        # 状态卡片
        status_card = MDCard(
            pos_hint={"center_x": 0.5, "center_y": 0.3},
            size_hint=(0.9, 0.18),
            padding="16dp"
        )
        status_content = BoxLayout(orientation="vertical", spacing="8dp")
        status_content.add_widget(MDLabel(id="ai_status", text="🔴 AI加载中...", font_style="Body1"))
        status_content.add_widget(MDLabel(id="data_status", text="⚪ 数据状态未知", font_style="Body1"))
        status_content.add_widget(MDLabel(id="db_size", text="📦 数据库: --", font_style="Body1"))
        status_card.add_widget(status_content)
        layout.add_widget(status_card)
        
        return layout
    
    def create_analysis_ui(self):
        """创建分析页UI"""
        from kivymd.uix.floatlayout import MDFloatLayout
        from kivymd.uix.label import MDLabel
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
        from kivymd.uix.menu import MDDropdownMenu
        
        symbol_btn = MDRaisedButton(
            text="BTCUSDT",
            pos_hint={"center_x": 0.35, "center_y": 0.85},
            size_hint=(0.3, 0.05)
        )
        layout.add_widget(symbol_btn)
        
        # 开始分析按钮
        analyze_btn = MDRaisedButton(
            text="🚀 开始分析",
            pos_hint={"center_x": 0.7, "center_y": 0.85},
            size_hint=(0.3, 0.05),
            on_release=lambda x: self.start_analysis()
        )
        layout.add_widget(analyze_btn)
        
        # 分析结果区域
        result_card = MDCard(
            pos_hint={"center_x": 0.5, "center_y": 0.45},
            size_hint=(0.95, 0.5),
            padding="16dp"
        )
        
        scroll = MDScrollView()
        result_label = MDLabel(
            id="analysis_result",
            text="点击开始分析获取AI分析结果",
            valign="top",
            text_size=(None, None)
        )
        scroll.add_widget(result_label)
        result_card.add_widget(scroll)
        layout.add_widget(result_card)
        
        # 加载指示器 - MDProgressBar
        progress = MDProgressBar(
            pos_hint={"center_x": 0.5, "center_y": 0.15},
            size_hint_x=0.4,
            value=0
        )
        progress.id = "spinner"
        layout.add_widget(progress)
        
        return layout
    
    def create_settings_ui(self):
        """创建设置页UI — 包含服务器地址配置（手机端关键功能）"""
        from kivymd.uix.floatlayout import MDFloatLayout
        from kivymd.uix.label import MDLabel
        from kivymd.uix.list import MDList, OneLineListItem
        from kivymd.uix.textfield import MDTextField
        from kivymd.uix.button import MDRaisedButton
        
        layout = MDFloatLayout()
        
        # 标题
        title = MDLabel(
            text="设置",
            font_style="H5",
            halign="center",
            pos_hint={"center_x": 0.5, "center_y": 0.95}
        )
        layout.add_widget(title)
        
        # ===== 服务器地址配置（手机上最关键）=====
        server_section = MDLabel(
            text="[b]后端服务器地址[/b]（手机必填）",
            pos_hint={"center_x": 0.5, "center_y": 0.88},
            halign="left",
            markup=True,
            font_size="14sp"
        )
        layout.add_widget(server_section)
        
        self.server_input = MDTextField(
            hint_text="例如: http://192.168.1.100:8000",
            text=self.server_url,
            size_hint=(0.9, None),
            height="48dp",
            pos_hint={"center_x": 0.5, "center_y": 0.83},
            mode="fill",
        )
        layout.add_widget(self.server_input)
        
        save_btn = MDRaisedButton(
            text="保存并连接",
            size_hint=(0.5, None),
            height="40dp",
            pos_hint={"center_x": 0.5, "center_y": 0.77},
            on_release=self.save_server_config,
            theme_text_color="Custom",
            md_bg_color=(0.49, 0.73, 1.0, 1),
        )
        layout.add_widget(save_btn)
        
        self.server_status_label = MDLabel(
            text=f"当前: {self.server_url}",
            font_size="11sp",
            halign="center",
            theme_text_color="Secondary",
            pos_hint={"center_x": 0.5, "center_y": 0.73},
        )
        layout.add_widget(self.server_status_label)
        
        # 分隔线提示
        hint_label = MDLabel(
            text="↓ 以下为进阶配置 ↓",
            font_size="11sp",
            halign="center",
            theme_text_color="Hint",
            pos_hint={"center_x": 0.5, "center_y": 0.67},
        )
        layout.add_widget(hint_label)
        
        # API Key 配置区
        api_section = MDLabel(
            text="[b]API Key 配置[/b]",
            pos_hint={"center_x": 0.5, "center_y": 0.60},
            halign="left",
            markup=True
        )
        layout.add_widget(api_section)
        
        for i, exchange in enumerate(["币安 API", "OKX API", "Bybit API"]):
            item = OneLineListItem(
                text=exchange,
                pos_hint={"center_x": 0.5, "center_y": 0.50 - i * 0.07},
                size_hint=(0.9, None),
                height="44dp",
                on_release=lambda x, t=exchange: self.open_api_dialog(t)
            )
            layout.add_widget(item)
        
        return layout
    
    def save_server_config(self, *args):
        """保存服务器地址配置"""
        new_url = self.server_input.text.strip()
        if not new_url:
            Snackbar(text="请输入服务器地址").open()
            return
        if not new_url.startswith('http'):
            new_url = 'http://' + new_url
        save_server_url(new_url)
        self.server_url = new_url
        self.server_status_label.text = f"已保存: {new_url}"
        Snackbar(text=f"服务器地址已保存！请返回其他页面刷新数据").open()
    
    def start_analysis(self):
        """开始分析"""
        screen = self.root.get_screen("analysis")
        if hasattr(screen, 'start_analysis'):
            screen.start_analysis()
    
    def open_api_dialog(self, exchange: str):
        """打开API配置对话框"""
        Snackbar(text=f"配置 {exchange}").open()


if __name__ == "__main__":
    CryptoMindApp().run()
