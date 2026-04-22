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
Config.set("graphics", "maxfps", 30)

# Android 字体路径兼容 — 仅桌面端启用中文字体，Android 端跳过避免 SDL2_ttf 崩溃
import os as _os

if _os.name == 'posix' and 'ANDROID_ROOT' in _os.environ:
    # Android 环境: 不在 import 阶段注册字体，延迟到 build() 中处理
    pass
else:
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
    if _os.path.isfile(_FONT_PATH):
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


class CryptoMindApp(MDApp):
    """CryptoMind Pro Plus AI 主应用"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "CryptoMind Pro"
        self.theme_cls.primary_palette = "DeepPurple"
        self.theme_cls.accent_palette = "Teal"
        self.theme_cls.theme_style = "Dark"  # 深色主题
    
    def _register_chinese_font_safe(self):
        """桌面端字体注册 — Android 上完全跳过（Kivy SDL2_ttf 无法加载 CJK 字体）"""
        import os as _os
        # Android 端: 完全跳过字体注册，避免 SDL2_ttf ValueError
        if _os.name == 'posix' and 'ANDROID_ROOT' in _os.environ:
            return
        try:
            # 字体查找: 先找 mobile/fonts/, 再找项目根 fonts/
            _app_dir = _os.path.dirname(_os.path.abspath(__file__))
            for _fd in [_os.path.join(_app_dir, 'fonts'), _os.path.join(_os.path.dirname(_app_dir), 'fonts')]:
                if _os.path.isdir(_fd):
                    font_dir = _fd
                    break
            else:
                return  # 找不到 fonts 目录
            font_path = _os.path.join(font_dir, 'NotoSansCJKsc-Regular.otf')
            if not _os.path.isfile(font_path):
                return
            # 只覆盖文字样式，保留 Icon 样式
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
            pass  # 字体注册失败不影响启动

    def build(self):
        """构建应用界面 - ScreenManager + 底部导航栏
        
        KivyMD 1.2.0 的 MDBottomNavigationItem 不作为 Python 类导出，
        只在 KV 语言中可用。因此用 ScreenManager + 自定义底部栏实现导航。
        """
        from kivy.uix.screenmanager import ScreenManager
        from kivymd.uix.boxlayout import MDBoxLayout

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
        nav_bar = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height="56dp",
            md_bg_color=[0.07, 0.10, 0.13, 1],
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
        root = MDBoxLayout(orientation="vertical")
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
        """创建设置页UI"""
        from kivymd.uix.floatlayout import MDFloatLayout
        from kivymd.uix.label import MDLabel
        from kivymd.uix.list import MDList, OneLineListItem
        
        layout = MDFloatLayout()
        
        # 标题
        title = MDLabel(
            text="设置",
            font_style="H5",
            halign="center",
            pos_hint={"center_x": 0.5, "center_y": 0.95}
        )
        layout.add_widget(title)
        
        # API Key 配置区
        api_section = MDLabel(
            text="[b]API Key 配置[/b]",
            pos_hint={"center_x": 0.5, "center_y": 0.85},
            halign="left",
            markup=True
        )
        layout.add_widget(api_section)
        
        # 交易所配置
        for i, exchange in enumerate(["币安 API", "OKX API", "Bybit API"]):
            item = OneLineListItem(
                text=exchange,
                pos_hint={"center_x": 0.5, "center_y": 0.75 - i * 0.08},
                size_hint=(0.9, None),
                height="48dp",
                on_release=lambda x, t=exchange: self.open_api_dialog(t)
            )
            layout.add_widget(item)
        
        # AI 模型配置
        ai_section = MDLabel(
            text="[b]AI 模型设置[/b]",
            pos_hint={"center_x": 0.5, "center_y": 0.42},
            halign="left",
            markup=True
        )
        layout.add_widget(ai_section)
        
        model_items = [
            "本地模型 (Gemma 3 4B)",
            "云端 API",
        ]
        for i, model in enumerate(model_items):
            item = OneLineListItem(
                text=model,
                pos_hint={"center_x": 0.5, "center_y": 0.34 - i * 0.08},
                size_hint=(0.9, None),
                height="48dp"
            )
            layout.add_widget(item)
        
        return layout
    
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
