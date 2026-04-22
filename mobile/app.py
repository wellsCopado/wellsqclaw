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

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from mobile.screens.news_screen import NewsScreen
from mobile.screens.onchain_screen import OnchainScreen
from mobile.screens.knowledge_screen import KnowledgeScreen
from mobile.screens.attribution_screen import AttributionScreen
from mobile.screens.paper_trading_screen import PaperTradingScreen
from kivymd.uix.navigationdrawer import MDNavigationDrawer
from kivymd.uix.bottomnavigation import MDBottomNavigation, MDBottomNavigationItem
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
    
    def build(self):
        """构建应用界面"""
        # 底部导航
        bottom_nav = MDBottomNavigation()
        
        # 首页
        home = MDScreen(name="home")
        home.add_widget(self.create_home_ui())
        bottom_nav.add_widget(MDBottomNavigationItem(
            name="home",
            text="首页",
            icon="home",
            on_tab_press=lambda x: None
        ))
        bottom_nav.add_widget(home)
        
        # 分析页
        analysis = MDScreen(name="analysis")
        analysis.add_widget(self.create_analysis_ui())
        bottom_nav.add_widget(MDBottomNavigationItem(
            name="analysis",
            text="分析",
            icon="brain",
            on_tab_press=lambda x: None
        ))
        bottom_nav.add_widget(analysis)
        
        # 设置页
        settings = MDScreen(name="settings")
        settings.add_widget(self.create_settings_ui())
        bottom_nav.add_widget(MDBottomNavigationItem(
            name="settings",
            text="设置",
            icon="cog",
            on_tab_press=lambda x: None
        ))
        bottom_nav.add_widget(settings)

        # 新闻页
        news_screen = NewsScreen(name="news")
        bottom_nav.add_widget(MDBottomNavigationItem(
            name="news",
            text="新闻",
            icon="newspaper-variant-outline",
            on_tab_press=lambda x: None
        ))
        bottom_nav.add_widget(news_screen)

        # 链上数据页
        onchain_screen = OnchainScreen(name="onchain")
        bottom_nav.add_widget(MDBottomNavigationItem(
            name="onchain",
            text="链上",
            icon="chain",
            on_tab_press=lambda x: None
        ))
        bottom_nav.add_widget(onchain_screen)

        # 知识库页
        knowledge_screen = KnowledgeScreen(name="knowledge")
        bottom_nav.add_widget(MDBottomNavigationItem(
            name="knowledge",
            text="知识库",
            icon="brain",
            on_tab_press=lambda x: None
        ))
        bottom_nav.add_widget(knowledge_screen)

        # 归因分析页
        attr_screen = AttributionScreen(name="attribution")
        bottom_nav.add_widget(MDBottomNavigationItem(
            name="attribution",
            text="归因",
            icon="chart-pie",
            on_tab_press=lambda x: None
        ))
        bottom_nav.add_widget(attr_screen)

        # Paper Trading页
        paper_screen = PaperTradingScreen(name="paper_trading")
        bottom_nav.add_widget(MDBottomNavigationItem(
            name="paper_trading",
            text="模拟",
            icon="cash",
            on_tab_press=lambda x: None
        ))
        bottom_nav.add_widget(paper_screen)
        
        return bottom_nav
    
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
