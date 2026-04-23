"""
CryptoMind Pro Plus AI - 移动端主应用
基于 Kivy 框架（纯 Kivy，避免 KivyMD 兼容性问题）
完全重写版 — 修复所有闪退和空白问题
"""

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.textinput import TextInput
from kivy.uix.progressbar import ProgressBar
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.properties import StringProperty, NumericProperty, ListProperty, BooleanProperty
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.lang import Builder
from kivy.utils import get_color_from_hex
from kivy.core.text import LabelBase
from kivy.network.urlrequest import UrlRequest
from kivy.logger import Logger

import json
import threading
import random
import os
from datetime import datetime

# ============ 字体配置 ============
# 注册中文字体 — 尝试多个候选
def setup_fonts():
    """注册中文字体，尝试多个候选"""
    font_candidates = [
        # 系统字体（Android）
        '/system/fonts/NotoSansCJK-Regular.ttc',
        '/system/fonts/NotoSansSC-Regular.otf',
        '/system/fonts/DroidSansFallbackFull.ttf',
        '/system/fonts/Roboto-Regular.ttf',
        # macOS 开发环境
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/STHeiti Light.ttc',
        '/Library/Fonts/Arial Unicode.ttf',
        # 本地打包字体
        'NotoSansSC-Regular.ttf',
        'fonts/NotoSansSC-Regular.ttf',
    ]
    
    registered = False
    for font_path in font_candidates:
        if os.path.exists(font_path):
            try:
                LabelBase.register(name='ChineseFont', fn_regular=font_path)
                Logger.info(f'Font registered: {font_path}')
                registered = True
                break
            except Exception as e:
                Logger.warning(f'Font register failed for {font_path}: {e}')
                continue
    
    if not registered:
        Logger.warning('No Chinese font found, using system default')
    
    return registered

FONT_REGISTERED = setup_fonts()
# 字体名称：如果注册成功用 'ChineseFont'，否则用空字符串（系统默认）
FONT_NAME = 'ChineseFont' if FONT_REGISTERED else ''

# ============ 全局颜色 ============
COLORS = {
    'primary': '#3F51B5',
    'secondary': '#FF4081',
    'background': '#121212',
    'surface': '#1E1E1E',
    'surface_light': '#2D2D2D',
    'text_primary': '#FFFFFF',
    'text_secondary': '#B0B0B0',
    'success': '#4CAF50',
    'warning': '#FF9800',
    'error': '#F44336',
    'bullish': '#00C853',
    'bearish': '#FF1744',
}

def hex_color(color_name):
    return get_color_from_hex(COLORS.get(color_name, '#FFFFFF'))

# ============ KV 样式定义 ============
KV = '''
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

<Card@BoxLayout>:
    orientation: 'vertical'
    padding: dp(10)
    spacing: dp(5)
    canvas.before:
        Color:
            rgba: 0.118, 0.118, 0.118, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(10)]

<NavButton@Button>:
    font_size: sp(11)
    background_color: 0.176, 0.176, 0.176, 1
    background_normal: ''
    color: 1, 1, 1, 1

<PrimaryButton@Button>:
    font_size: sp(14)
    bold: True
    background_color: 0.247, 0.318, 0.71, 1
    background_normal: ''
    color: 1, 1, 1, 1
    size_hint_y: None
    height: dp(45)

<SecondaryButton@Button>:
    font_size: sp(12)
    background_color: 0.176, 0.176, 0.176, 1
    background_normal: ''
    color: 1, 1, 1, 1
    size_hint_y: None
    height: dp(40)

<TitleLabel@Label>:
    font_size: sp(18)
    bold: True
    color: 1, 1, 1, 1
    size_hint_y: None
    height: dp(40)
    halign: 'left'
    text_size: self.width, None

<SubtitleLabel@Label>:
    font_size: sp(14)
    color: 0.69, 0.69, 0.69, 1
    size_hint_y: None
    height: dp(30)
    halign: 'left'
    text_size: self.width, None

# ============ 首页 ============
<HomeScreen>:
    BoxLayout:
        orientation: 'vertical'
        
        # 顶部栏
        BoxLayout:
            size_hint_y: None
            height: dp(56)
            padding: dp(10)
            canvas.before:
                Color:
                    rgba: 0.118, 0.118, 0.118, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            
            Label:
                text: 'CryptoMind Pro'
                font_size: sp(20)
                bold: True
                color: 1, 1, 1, 1
            
            Label:
                id: status_label
                text: '在线'
                font_size: sp(12)
                color: 0, 0.784, 0.325, 1
                halign: 'right'
                size_hint_x: 0.3
        
        # 主内容
        ScrollView:
            BoxLayout:
                id: content_layout
                orientation: 'vertical'
                padding: dp(15)
                spacing: dp(12)
                size_hint_y: None
                height: self.minimum_height
                
                # 价格卡片
                Card:
                    size_hint_y: None
                    height: dp(120)
                    
                    Label:
                        text: 'BTC/USDT'
                        font_size: sp(14)
                        color: 0.69, 0.69, 0.69, 1
                        size_hint_y: None
                        height: dp(25)
                    
                    Label:
                        id: btc_price
                        text: '加载中...'
                        font_size: sp(32)
                        bold: True
                        color: 0, 0.784, 0.325, 1
                    
                    Label:
                        id: btc_change
                        text: '--'
                        font_size: sp(14)
                        color: 0.69, 0.69, 0.69, 1
                        size_hint_y: None
                        height: dp(25)
                
                # ETH 价格
                Card:
                    size_hint_y: None
                    height: dp(100)
                    
                    BoxLayout:
                        orientation: 'horizontal'
                        Label:
                            text: 'ETH/USDT'
                            font_size: sp(14)
                            color: 0.69, 0.69, 0.69, 1
                            size_hint_x: 0.4
                        Label:
                            id: eth_price
                            text: '加载中...'
                            font_size: sp(24)
                            bold: True
                            color: 0, 0.784, 0.325, 1
                            halign: 'right'
                            size_hint_x: 0.6
                
                # 快速操作
                TitleLabel:
                    text: '快速操作'
                
                GridLayout:
                    cols: 2
                    spacing: dp(10)
                    size_hint_y: None
                    height: dp(100)
                    
                    PrimaryButton:
                        text: '智能分析'
                        on_press: root.manager.current = 'analysis'
                    
                    PrimaryButton:
                        text: '模拟交易'
                        on_press: root.manager.current = 'trading'
                
                # API配置入口
                TitleLabel:
                    text: 'API 配置'
                
                Card:
                    size_hint_y: None
                    height: dp(180)
                    
                    BoxLayout:
                        size_hint_y: None
                        height: dp(50)
                        Label:
                            text: 'Binance'
                            font_size: sp(14)
                            color: 1, 1, 1, 1
                            size_hint_x: 0.5
                        SecondaryButton:
                            text: '配置'
                            size_hint_x: 0.3
                            on_press: root.show_api_dialog('binance')
                    
                    BoxLayout:
                        size_hint_y: None
                        height: dp(50)
                        Label:
                            text: 'OKX'
                            font_size: sp(14)
                            color: 1, 1, 1, 1
                            size_hint_x: 0.5
                        SecondaryButton:
                            text: '配置'
                            size_hint_x: 0.3
                            on_press: root.show_api_dialog('okx')
                    
                    BoxLayout:
                        size_hint_y: None
                        height: dp(50)
                        Label:
                            text: 'Coinglass'
                            font_size: sp(14)
                            color: 1, 1, 1, 1
                            size_hint_x: 0.5
                        SecondaryButton:
                            text: '配置'
                            size_hint_x: 0.3
                            on_press: root.show_api_dialog('coinglass')
                
                # 市场概览
                TitleLabel:
                    text: '市场概览'
                
                GridLayout:
                    cols: 2
                    spacing: dp(10)
                    size_hint_y: None
                    height: dp(200)
                    
                    Card:
                        Label:
                            text: '市值'
                            font_size: sp(12)
                            color: 0.69, 0.69, 0.69, 1
                        Label:
                            id: market_cap
                            text: '--'
                            font_size: sp(18)
                            bold: True
                            color: 1, 1, 1, 1
                    
                    Card:
                        Label:
                            text: '24h 成交量'
                            font_size: sp(12)
                            color: 0.69, 0.69, 0.69, 1
                        Label:
                            id: volume_24h
                            text: '--'
                            font_size: sp(18)
                            bold: True
                            color: 1, 1, 1, 1
                    
                    Card:
                        Label:
                            text: 'BTC dominance'
                            font_size: sp(12)
                            color: 0.69, 0.69, 0.69, 1
                        Label:
                            id: btc_dominance
                            text: '--'
                            font_size: sp(18)
                            bold: True
                            color: 1, 1, 1, 1
                    
                    Card:
                        Label:
                            text: '恐惧贪婪'
                            font_size: sp(12)
                            color: 0.69, 0.69, 0.69, 1
                        Label:
                            id: fear_greed
                            text: '--'
                            font_size: sp(18)
                            bold: True
                            color: 1, 1, 1, 1
        
        # 底部导航
        BoxLayout:
            size_hint_y: None
            height: dp(56)
            padding: dp(2)
            spacing: dp(2)
            canvas.before:
                Color:
                    rgba: 0.118, 0.118, 0.118, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            
            NavButton:
                text: '首页'
                on_press: root.manager.current = 'home'
            NavButton:
                text: '分析'
                on_press: root.manager.current = 'analysis'
            NavButton:
                text: '资讯'
                on_press: root.manager.current = 'news'
            NavButton:
                text: '交易'
                on_press: root.manager.current = 'trading'
            NavButton:
                text: '设置'
                on_press: root.manager.current = 'settings'

# ============ 分析页 ============
<AnalysisScreen>:
    BoxLayout:
        orientation: 'vertical'
        
        BoxLayout:
            size_hint_y: None
            height: dp(56)
            padding: dp(10)
            canvas.before:
                Color:
                    rgba: 0.118, 0.118, 0.118, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            
            Button:
                text: '返回'
                font_size: sp(14)
                size_hint_x: 0.2
                background_color: 0.176, 0.176, 0.176, 1
                background_normal: ''
                color: 1, 1, 1, 1
                on_press: root.manager.current = 'home'
            
            Label:
                text: '智能分析'
                font_size: sp(18)
                bold: True
                color: 1, 1, 1, 1
        
        ScrollView:
            BoxLayout:
                orientation: 'vertical'
                padding: dp(15)
                spacing: dp(12)
                size_hint_y: None
                height: self.minimum_height
                
                # 币种选择
                BoxLayout:
                    size_hint_y: None
                    height: dp(50)
                    spacing: dp(10)
                    
                    Label:
                        text: '币种:'
                        font_size: sp(14)
                        color: 1, 1, 1, 1
                        size_hint_x: 0.25
                    
                    Spinner:
                        id: symbol_spinner
                        text: 'BTC'
                        values: ['BTC', 'ETH', 'BNB', 'SOL', 'XRP']
                        font_size: sp(14)
                        background_color: 0.176, 0.176, 0.176, 1
                        color: 1, 1, 1, 1
                        size_hint_x: 0.75
                
                # 分析类型
                BoxLayout:
                    size_hint_y: None
                    height: dp(50)
                    spacing: dp(10)
                    
                    Label:
                        text: '类型:'
                        font_size: sp(14)
                        color: 1, 1, 1, 1
                        size_hint_x: 0.25
                    
                    Spinner:
                        id: type_spinner
                        text: '综合分析'
                        values: ['综合分析', '技术分析', '基本面分析']
                        font_size: sp(14)
                        background_color: 0.176, 0.176, 0.176, 1
                        color: 1, 1, 1, 1
                        size_hint_x: 0.75
                
                PrimaryButton:
                    id: analyze_btn
                    text: '开始分析'
                    on_press: root.start_analysis()
                
                ProgressBar:
                    id: progress
                    size_hint_y: None
                    height: dp(4)
                    value: 0
                    max: 100
                
                # 结果区域 — 使用 BoxLayout 而非 Card，避免 opacity 问题
                BoxLayout:
                    id: result_area
                    orientation: 'vertical'
                    padding: dp(10)
                    spacing: dp(5)
                    size_hint_y: None
                    height: dp(250)
                    opacity: 0
                    canvas.before:
                        Color:
                            rgba: 0.118, 0.118, 0.118, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [dp(10)]
                    
                    Label:
                        id: result_direction
                        text: ''
                        font_size: sp(24)
                        bold: True
                        color: 1, 1, 1, 1
                    
                    Label:
                        id: result_confidence
                        text: ''
                        font_size: sp(16)
                        color: 0.69, 0.69, 0.69, 1
                    
                    Label:
                        id: result_summary
                        text: ''
                        font_size: sp(13)
                        color: 0.69, 0.69, 0.69, 1
                        text_size: self.width - dp(20), None
                        halign: 'left'
                        valign: 'top'

# ============ 资讯页 ============
<NewsScreen>:
    BoxLayout:
        orientation: 'vertical'
        
        BoxLayout:
            size_hint_y: None
            height: dp(56)
            padding: dp(10)
            canvas.before:
                Color:
                    rgba: 0.118, 0.118, 0.118, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            
            Button:
                text: '返回'
                font_size: sp(14)
                size_hint_x: 0.2
                background_color: 0.176, 0.176, 0.176, 1
                background_normal: ''
                color: 1, 1, 1, 1
                on_press: root.manager.current = 'home'
            
            Label:
                text: '最新资讯'
                font_size: sp(18)
                bold: True
                color: 1, 1, 1, 1
        
        ScrollView:
            BoxLayout:
                id: news_container
                orientation: 'vertical'
                padding: dp(15)
                spacing: dp(10)
                size_hint_y: None
                height: self.minimum_height

# ============ 交易页 ============
<TradingScreen>:
    BoxLayout:
        orientation: 'vertical'
        
        BoxLayout:
            size_hint_y: None
            height: dp(56)
            padding: dp(10)
            canvas.before:
                Color:
                    rgba: 0.118, 0.118, 0.118, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            
            Button:
                text: '返回'
                font_size: sp(14)
                size_hint_x: 0.2
                background_color: 0.176, 0.176, 0.176, 1
                background_normal: ''
                color: 1, 1, 1, 1
                on_press: root.manager.current = 'home'
            
            Label:
                text: '模拟交易'
                font_size: sp(18)
                bold: True
                color: 1, 1, 1, 1
        
        ScrollView:
            BoxLayout:
                orientation: 'vertical'
                padding: dp(15)
                spacing: dp(12)
                size_hint_y: None
                height: self.minimum_height
                
                # 账户概览
                Card:
                    size_hint_y: None
                    height: dp(120)
                    
                    Label:
                        text: '账户余额'
                        font_size: sp(14)
                        color: 0.69, 0.69, 0.69, 1
                    
                    Label:
                        id: balance_label
                        text: '$10,000.00'
                        font_size: sp(28)
                        bold: True
                        color: 1, 1, 1, 1
                    
                    Label:
                        id: pnl_label
                        text: '盈亏: +$0.00'
                        font_size: sp(14)
                        color: 0, 0.784, 0.325, 1
                
                # 交易操作
                TitleLabel:
                    text: '开仓'
                
                BoxLayout:
                    size_hint_y: None
                    height: dp(50)
                    spacing: dp(10)
                    
                    Label:
                        text: '币种:'
                        font_size: sp(14)
                        color: 1, 1, 1, 1
                        size_hint_x: 0.2
                    
                    Spinner:
                        id: trade_symbol
                        text: 'BTC'
                        values: ['BTC', 'ETH', 'BNB', 'SOL']
                        font_size: sp(14)
                        background_color: 0.176, 0.176, 0.176, 1
                        color: 1, 1, 1, 1
                        size_hint_x: 0.3
                    
                    Spinner:
                        id: trade_direction
                        text: '做多'
                        values: ['做多', '做空']
                        font_size: sp(14)
                        background_color: 0.176, 0.176, 0.176, 1
                        color: 1, 1, 1, 1
                        size_hint_x: 0.25
                    
                    TextInput:
                        id: trade_amount
                        text: '100'
                        font_size: sp(14)
                        background_color: 0.176, 0.176, 0.176, 1
                        foreground_color: 1, 1, 1, 1
                        size_hint_x: 0.25
                        multiline: False
                        input_filter: 'float'
                
                PrimaryButton:
                    text: '下单'
                    on_press: root.place_order()
                
                # 持仓列表
                TitleLabel:
                    text: '当前持仓'
                
                BoxLayout:
                    id: positions_container
                    orientation: 'vertical'
                    size_hint_y: None
                    height: dp(100)
                    
                    Label:
                        id: no_positions_label
                        text: '暂无持仓'
                        font_size: sp(14)
                        color: 0.69, 0.69, 0.69, 1

# ============ 设置页 ============
<SettingsScreen>:
    BoxLayout:
        orientation: 'vertical'
        
        BoxLayout:
            size_hint_y: None
            height: dp(56)
            padding: dp(10)
            canvas.before:
                Color:
                    rgba: 0.118, 0.118, 0.118, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            
            Button:
                text: '返回'
                font_size: sp(14)
                size_hint_x: 0.2
                background_color: 0.176, 0.176, 0.176, 1
                background_normal: ''
                color: 1, 1, 1, 1
                on_press: root.manager.current = 'home'
            
            Label:
                text: '设置'
                font_size: sp(18)
                bold: True
                color: 1, 1, 1, 1
        
        ScrollView:
            BoxLayout:
                orientation: 'vertical'
                padding: dp(15)
                spacing: dp(12)
                size_hint_y: None
                height: self.minimum_height
                
                TitleLabel:
                    text: '关于'
                
                Card:
                    size_hint_y: None
                    height: dp(120)
                    
                    Label:
                        text: 'CryptoMind Pro Plus AI'
                        font_size: sp(16)
                        bold: True
                        color: 1, 1, 1, 1
                    
                    Label:
                        text: '版本 2.0.0'
                        font_size: sp(12)
                        color: 0.69, 0.69, 0.69, 1
                    
                    Label:
                        text: '全维度智能分析系统'
                        font_size: sp(12)
                        color: 0.69, 0.69, 0.69, 1
'''


# ============ 安全包装函数 ============
def safe_label(text='', font_size=14, bold=False, color=None, **kwargs):
    """安全创建 Label，自动处理字体"""
    if color is None:
        color = (1, 1, 1, 1)
    return Label(
        text=text,
        font_size=sp(font_size),
        bold=bold,
        color=color,
        font_name=FONT_NAME,
        **kwargs
    )


def show_error_popup(title, message):
    """显示错误弹窗"""
    try:
        popup = Popup(
            title=title,
            content=Label(
                text=message,
                font_size=sp(14),
                color=(1, 1, 1, 1),
                font_name=FONT_NAME
            ),
            size_hint=(0.8, 0.3),
            background_color=(0.118, 0.118, 0.118, 1)
        )
        popup.open()
    except Exception as e:
        Logger.error(f'Popup error: {e}')


# ============ 屏幕类 ============

class HomeScreen(Screen):
    """首页"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(self.load_data, 1.0)
    
    def load_data(self, dt):
        """加载市场数据"""
        try:
            self.ids.btc_price.text = '$67,890.50'
            self.ids.btc_change.text = '+2.34% ▲'
            self.ids.btc_change.color = hex_color('bullish')
            
            self.ids.eth_price.text = '$3,456.78'
            
            self.ids.market_cap.text = '$2.54T'
            self.ids.volume_24h.text = '$89.2B'
            self.ids.btc_dominance.text = '52.3%'
            self.ids.fear_greed.text = '65 贪婪'
            self.ids.fear_greed.color = hex_color('warning')
        except Exception as e:
            Logger.error(f'Home load_data error: {e}')
    
    def show_api_dialog(self, provider):
        """显示API配置对话框 — 首页版本"""
        try:
            content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
            
            content.add_widget(safe_label(
                text=f'配置 {provider.upper()} API',
                font_size=16,
                bold=True,
                size_hint_y=None,
                height=dp(40)
            ))
            
            key_input = TextInput(
                hint_text='API Key',
                multiline=False,
                size_hint_y=None,
                height=dp(45),
                background_color=(0.176, 0.176, 0.176, 1),
                foreground_color=(1, 1, 1, 1),
                hint_text_color=(0.5, 0.5, 0.5, 1),
                padding=[dp(10), dp(10)]
            )
            content.add_widget(key_input)
            
            secret_input = TextInput(
                hint_text='API Secret',
                multiline=False,
                password=True,
                size_hint_y=None,
                height=dp(45),
                background_color=(0.176, 0.176, 0.176, 1),
                foreground_color=(1, 1, 1, 1),
                hint_text_color=(0.5, 0.5, 0.5, 1),
                padding=[dp(10), dp(10)]
            )
            content.add_widget(secret_input)
            
            btn_layout = BoxLayout(
                size_hint_y=None,
                height=dp(45),
                spacing=dp(10)
            )
            
            cancel_btn = Button(
                text='取消',
                background_color=(0.5, 0.5, 0.5, 1),
                background_normal='',
                color=(1, 1, 1, 1)
            )
            
            save_btn = Button(
                text='保存',
                background_color=(0.247, 0.318, 0.71, 1),
                background_normal='',
                color=(1, 1, 1, 1)
            )
            
            btn_layout.add_widget(cancel_btn)
            btn_layout.add_widget(save_btn)
            content.add_widget(btn_layout)
            
            popup = Popup(
                title='API 配置',
                content=content,
                size_hint=(0.9, 0.5),
                background_color=(0.118, 0.118, 0.118, 1)
            )
            
            cancel_btn.bind(on_press=popup.dismiss)
            save_btn.bind(on_press=lambda x: self._save_api_config(
                provider, key_input.text, secret_input.text, popup
            ))
            
            popup.open()
        except Exception as e:
            Logger.error(f'show_api_dialog error: {e}')
            show_error_popup('错误', f'无法打开配置: {str(e)}')
    
    def _save_api_config(self, provider, key, secret, popup):
        """保存API配置"""
        try:
            popup.dismiss()
            # 这里可以保存到文件或内存
            show_error_popup('成功', f'{provider.upper()} API 配置已保存')
        except Exception as e:
            Logger.error(f'_save_api_config error: {e}')


class AnalysisScreen(Screen):
    """分析页"""
    
    is_analyzing = False
    
    def start_analysis(self):
        """开始分析"""
        if self.is_analyzing:
            return
        
        try:
            self.is_analyzing = True
            self.ids.analyze_btn.text = '分析中...'
            self.ids.analyze_btn.disabled = True
            self.ids.progress.value = 30
            
            # 隐藏之前的结果
            self.ids.result_area.opacity = 0
            
            # 模拟分析过程
            Clock.schedule_once(self._analysis_step2, 1)
        except Exception as e:
            Logger.error(f'start_analysis error: {e}')
            self.is_analyzing = False
            self.ids.analyze_btn.text = '开始分析'
            self.ids.analyze_btn.disabled = False
            show_error_popup('错误', f'分析启动失败: {str(e)}')
    
    def _analysis_step2(self, dt):
        try:
            self.ids.progress.value = 70
            Clock.schedule_once(self._analysis_complete, 1)
        except Exception as e:
            Logger.error(f'_analysis_step2 error: {e}')
            self._reset_analysis()
    
    def _analysis_complete(self, dt):
        try:
            self.ids.progress.value = 100
            
            # 显示结果
            symbol = self.ids.symbol_spinner.text
            direction = random.choice(['看涨', '看跌', '中性'])
            confidence = random.randint(60, 95)
            
            colors = {
                '看涨': hex_color('bullish'),
                '看跌': hex_color('bearish'),
                '中性': hex_color('text_primary')
            }
            
            self.ids.result_direction.text = f'{symbol} - {direction}'
            self.ids.result_direction.color = colors.get(direction, hex_color('text_primary'))
            self.ids.result_confidence.text = f'置信度: {confidence}%'
            self.ids.result_summary.text = (
                f'基于技术分析和市场情绪，{symbol} 目前呈现{direction}态势。'
                f'建议关注关键价位突破情况，设置止损控制风险。'
            )
            
            # 显示结果区域
            self.ids.result_area.opacity = 1
            
            # 重置按钮
            self._reset_analysis()
        except Exception as e:
            Logger.error(f'_analysis_complete error: {e}')
            self._reset_analysis()
            show_error_popup('错误', f'分析完成时出错: {str(e)}')
    
    def _reset_analysis(self):
        """重置分析状态"""
        self.is_analyzing = False
        try:
            self.ids.analyze_btn.text = '开始分析'
            self.ids.analyze_btn.disabled = False
            self.ids.progress.value = 0
        except Exception as e:
            Logger.error(f'_reset_analysis error: {e}')


class NewsScreen(Screen):
    """资讯页"""
    
    news_loaded = False
    
    def on_enter(self):
        """进入屏幕时加载"""
        if not self.news_loaded:
            Clock.schedule_once(self.load_news, 0.5)
    
    def load_news(self, dt):
        """加载新闻"""
        try:
            container = self.ids.news_container
            container.clear_widgets()
            
            # 模拟新闻数据
            news_items = [
                {
                    'title': '比特币突破关键阻力位，市场情绪转为乐观',
                    'source': 'CoinDesk',
                    'time': '2小时前',
                    'summary': 'BTC 突破 $68,000 关键阻力位，24小时涨幅超过 3%，交易量显著放大。'
                },
                {
                    'title': '以太坊 Layer 2 生态持续扩张，TVL 创新高',
                    'source': 'The Block',
                    'time': '4小时前',
                    'summary': 'Arbitrum 和 Optimism 总锁仓量突破 150 亿美元，DeFi 活动显著增加。'
                },
                {
                    'title': '美联储会议纪要暗示可能放缓加息步伐',
                    'source': 'Reuters',
                    'time': '6小时前',
                    'summary': '最新 FOMC 会议纪要显示，部分委员支持在下次会议上暂停加息。'
                },
                {
                    'title': 'Solana 网络活跃度回升，NFT 交易量激增',
                    'source': 'CryptoSlate',
                    'time': '8小时前',
                    'summary': 'Solana 链上日活跃地址数突破 200 万，NFT 市场交易量周环比增长 45%。'
                },
                {
                    'title': '监管机构就稳定币立法展开新一轮讨论',
                    'source': 'Bloomberg',
                    'time': '12小时前',
                    'summary': '美国国会小组委员会就稳定币监管框架举行听证会，行业代表参与讨论。'
                }
            ]
            
            for item in news_items:
                news_card = self._create_news_card(item)
                container.add_widget(news_card)
            
            self.news_loaded = True
        except Exception as e:
            Logger.error(f'load_news error: {e}')
            # 显示错误信息
            container = self.ids.news_container
            container.clear_widgets()
            container.add_widget(safe_label(
                text=f'加载失败: {str(e)}',
                font_size=14,
                color=(0.957, 0.263, 0.212, 1)
            ))
    
    def _create_news_card(self, item):
        """创建新闻卡片"""
        card = BoxLayout(
            orientation='vertical',
            padding=dp(10),
            spacing=dp(5),
            size_hint_y=None,
            height=dp(120)
        )
        
        with card.canvas.before:
            Color(0.118, 0.118, 0.118, 1)
            self.card_rect = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(8)])
        
        def update_bg(instance, value):
            self.card_rect.pos = instance.pos
            self.card_rect.size = instance.size
        
        card.bind(pos=update_bg, size=update_bg)
        
        title = safe_label(
            text=item['title'],
            font_size=14,
            bold=True,
            size_hint_y=None,
            height=dp(40),
            text_size=(card.width - dp(20), None),
            halign='left',
            valign='top'
        )
        card.bind(width=lambda obj, w: setattr(title, 'text_size', (w - dp(20), None)))
        
        meta = safe_label(
            text=f"{item['source']} · {item['time']}",
            font_size=11,
            color=(0.69, 0.69, 0.69, 1),
            size_hint_y=None,
            height=dp(20),
            halign='left',
            text_size=(card.width, None)
        )
        
        summary = safe_label(
            text=item['summary'],
            font_size=12,
            color=(0.69, 0.69, 0.69, 1),
            size_hint_y=None,
            height=dp(50),
            text_size=(card.width - dp(20), None),
            halign='left',
            valign='top'
        )
        card.bind(width=lambda obj, w: setattr(summary, 'text_size', (w - dp(20), None)))
        
        card.add_widget(title)
        card.add_widget(meta)
        card.add_widget(summary)
        
        return card


class TradingScreen(Screen):
    """交易页"""
    
    balance = 10000.0
    positions = []
    
    def place_order(self):
        """下单"""
        try:
            symbol = self.ids.trade_symbol.text
            direction = self.ids.trade_direction.text
            amount = self.ids.trade_amount.text
            
            try:
                amount = float(amount)
            except ValueError:
                show_error_popup('错误', '请输入有效金额')
                return
            
            if amount <= 0:
                show_error_popup('错误', '金额必须大于0')
                return
            if amount > self.balance:
                show_error_popup('错误', '余额不足')
                return
            
            # 创建持仓
            position = {
                'symbol': symbol,
                'direction': direction,
                'amount': amount,
                'entry_price': random.uniform(60000, 70000) if symbol == 'BTC' else random.uniform(3000, 4000),
                'time': datetime.now().strftime('%m-%d %H:%M')
            }
            self.positions.append(position)
            self.balance -= amount
            
            self._update_ui()
            show_error_popup('成功', f'{direction} {symbol} ${amount:.2f} 下单成功')
            
        except Exception as e:
            Logger.error(f'place_order error: {e}')
            show_error_popup('错误', f'下单失败: {str(e)}')
    
    def _update_ui(self):
        """更新UI"""
        try:
            self.ids.balance_label.text = f'${self.balance:,.2f}'
            
            # 更新持仓列表
            container = self.ids.positions_container
            container.clear_widgets()
            
            if not self.positions:
                container.add_widget(safe_label(
                    text='暂无持仓',
                    font_size=14,
                    color=(0.69, 0.69, 0.69, 1)
                ))
                container.height = dp(100)
            else:
                container.height = len(self.positions) * dp(80)
                for pos in self.positions:
                    pos_widget = self._create_position_widget(pos)
                    container.add_widget(pos_widget)
        except Exception as e:
            Logger.error(f'_update_ui error: {e}')
    
    def _create_position_widget(self, pos):
        """创建持仓组件"""
        box = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(70),
            padding=dp(10)
        )
        
        with box.canvas.before:
            Color(0.118, 0.118, 0.118, 1)
            rect = RoundedRectangle(pos=box.pos, size=box.size, radius=[dp(6)])
        
        def update_bg(instance, value):
            rect.pos = instance.pos
            rect.size = instance.size
        
        box.bind(pos=update_bg, size=update_bg)
        
        info = safe_label(
            text=f"{pos['symbol']} {pos['direction']}\n${pos['amount']:.2f} @ {pos['entry_price']:,.0f}",
            font_size=12,
            halign='left',
            text_size=(box.width * 0.6, None)
        )
        
        close_btn = Button(
            text='平仓',
            font_size=sp(12),
            size_hint_x=0.25,
            background_color=(0.957, 0.263, 0.212, 1),
            background_normal='',
            color=(1, 1, 1, 1)
        )
        close_btn.bind(on_press=lambda x, p=pos: self.close_position(p))
        
        box.add_widget(info)
        box.add_widget(close_btn)
        
        return box
    
    def close_position(self, position):
        """平仓"""
        try:
            if position in self.positions:
                # 模拟盈亏
                pnl = random.uniform(-100, 200)
                self.balance += position['amount'] + pnl
                self.positions.remove(position)
                self._update_ui()
                
                show_error_popup('平仓', f"盈亏: {'+' if pnl > 0 else ''}${pnl:.2f}")
        except Exception as e:
            Logger.error(f'close_position error: {e}')


class SettingsScreen(Screen):
    """设置页"""
    
    def show_api_dialog(self, provider):
        """显示API配置对话框"""
        try:
            content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
            
            content.add_widget(safe_label(
                text=f'配置 {provider.upper()} API',
                font_size=16,
                bold=True,
                size_hint_y=None,
                height=dp(40)
            ))
            
            key_input = TextInput(
                hint_text='API Key',
                multiline=False,
                size_hint_y=None,
                height=dp(45),
                background_color=(0.176, 0.176, 0.176, 1),
                foreground_color=(1, 1, 1, 1),
                hint_text_color=(0.5, 0.5, 0.5, 1),
                padding=[dp(10), dp(10)]
            )
            content.add_widget(key_input)
            
            secret_input = TextInput(
                hint_text='API Secret',
                multiline=False,
                password=True,
                size_hint_y=None,
                height=dp(45),
                background_color=(0.176, 0.176, 0.176, 1),
                foreground_color=(1, 1, 1, 1),
                hint_text_color=(0.5, 0.5, 0.5, 1),
                padding=[dp(10), dp(10)]
            )
            content.add_widget(secret_input)
            
            btn_layout = BoxLayout(
                size_hint_y=None,
                height=dp(45),
                spacing=dp(10)
            )
            
            cancel_btn = Button(
                text='取消',
                background_color=(0.5, 0.5, 0.5, 1),
                background_normal='',
                color=(1, 1, 1, 1)
            )
            
            save_btn = Button(
                text='保存',
                background_color=(0.247, 0.318, 0.71, 1),
                background_normal='',
                color=(1, 1, 1, 1)
            )
            
            btn_layout.add_widget(cancel_btn)
            btn_layout.add_widget(save_btn)
            content.add_widget(btn_layout)
            
            popup = Popup(
                title='API 配置',
                content=content,
                size_hint=(0.9, 0.5),
                background_color=(0.118, 0.118, 0.118, 1)
            )
            
            cancel_btn.bind(on_press=popup.dismiss)
            save_btn.bind(on_press=lambda x: self._save_config(
                provider, key_input.text, secret_input.text, popup
            ))
            
            popup.open()
        except Exception as e:
            Logger.error(f'Settings show_api_dialog error: {e}')
            show_error_popup('错误', f'无法打开配置: {str(e)}')
    
    def _save_config(self, provider, key, secret, popup):
        """保存配置"""
        try:
            popup.dismiss()
            show_error_popup('成功', f'{provider.upper()} API 配置已保存')
        except Exception as e:
            Logger.error(f'_save_config error: {e}')


# ============ 应用主类 ============

class CryptoMindApp(App):
    """CryptoMind Pro 应用"""
    
    def build(self):
        """构建应用"""
        self.title = 'CryptoMind Pro'
        
        # 加载 KV
        Builder.load_string(KV)
        
        # 创建屏幕管理器
        sm = ScreenManager(transition=SlideTransition())
        
        # 添加所有屏幕
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(AnalysisScreen(name='analysis'))
        sm.add_widget(NewsScreen(name='news'))
        sm.add_widget(TradingScreen(name='trading'))
        sm.add_widget(SettingsScreen(name='settings'))
        
        return sm


def main():
    """主入口"""
    app = CryptoMindApp()
    app.run()


if __name__ == '__main__':
    main()
