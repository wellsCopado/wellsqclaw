"""
设置页面 - API Key 配置
支持用户在手机上配置所有 API Key
"""
from kivymd.uix.screen import MDScreen
from kivymd.uix.floatlayout import MDFloatLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.boxlayout import BoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.snackbar import Snackbar
from kivymd.uix.card import MDCard
from kivy.clock import Clock
import sys
import os

# 确保项目根目录在 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config.api_keys import api_key_manager


class SettingsScreen(MDScreen):
    """设置页面 - API Key 配置"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dialog = None
        self._build_ui()
    
    def _build_ui(self):
        """构建设置页面UI"""
        layout = MDFloatLayout()
        
        # 标题
        title = MDLabel(
            text="⚙️ 设置",
            font_style="H5",
            halign="center",
            pos_hint={"center_x": 0.5, "center_y": 0.95}
        )
        layout.add_widget(title)
        
        # 创建可滚动区域
        scroll = MDScrollView(
            pos_hint={"center_x": 0.5, "center_y": 0.45},
            size_hint=(0.95, 0.85)
        )
        
        content = BoxLayout(
            orientation="vertical",
            spacing="16dp",
            padding="16dp",
            size_hint_y=None
        )
        content.bind(minimum_height=content.setter('height'))
        
        # 1. 服务器地址配置
        server_card = self._create_section_card("服务器配置", [
            ("server_url", "服务器地址", "例如: http://192.168.1.100:8000"),
        ])
        content.add_widget(server_card)
        
        # 2. 交易所 API Key
        exchange_card = self._create_section_card("交易所 API", [
            ("binance_api_key", "Binance API Key", "输入 Binance API Key"),
            ("binance_api_secret", "Binance Secret", "输入 Binance Secret"),
            ("okx_api_key", "OKX API Key", "输入 OKX API Key"),
            ("okx_api_secret", "OKX Secret", "输入 OKX Secret"),
            ("okx_passphrase", "OKX Passphrase", "输入 OKX Passphrase"),
            ("bybit_api_key", "Bybit API Key", "输入 Bybit API Key"),
            ("bybit_api_secret", "Bybit Secret", "输入 Bybit Secret"),
        ])
        content.add_widget(exchange_card)
        
        # 3. 数据源 API
        data_card = self._create_section_card("数据源 API", [
            ("coinglass_api_key", "Coinglass API Key", "输入 Coinglass API Key"),
            ("glassnode_api_key", "Glassnode API Key", "输入 Glassnode API Key"),
        ])
        content.add_widget(data_card)
        
        # 4. 链上数据
        onchain_card = self._create_section_card("链上数据", [
            ("eth_rpc_url", "Ethereum RPC", "例如: https://eth-mainnet.g.alchemy.com/v2/..."),
            ("btc_rpc_url", "Bitcoin RPC", "例如: https://bitcoin-mainnet.public.blastapi.io"),
            ("infura_api_key", "Infura API Key", "输入 Infura API Key"),
            ("alchemy_api_key", "Alchemy API Key", "输入 Alchemy API Key"),
        ])
        content.add_widget(onchain_card)
        
        # 5. AI 模型配置
        ai_card = self._create_section_card("AI 模型配置", [
            ("openai_api_key", "OpenAI API Key", "输入 OpenAI API Key"),
            ("openai_base_url", "OpenAI Base URL", "例如: https://api.openai.com/v1"),
            ("anthropic_api_key", "Anthropic API Key", "输入 Anthropic API Key"),
            ("deepseek_api_key", "DeepSeek API Key", "输入 DeepSeek API Key"),
            ("deepseek_base_url", "DeepSeek Base URL", "例如: https://api.deepseek.com"),
            ("custom_ai_api_key", "自定义 AI API Key", "输入自定义 AI API Key"),
            ("custom_ai_base_url", "自定义 AI Base URL", "输入自定义 AI Base URL"),
            ("custom_ai_model", "自定义模型名称", "例如: gemma3:4b"),
        ])
        content.add_widget(ai_card)
        
        # 保存按钮
        save_btn = MDRaisedButton(
            text="💾 保存所有配置",
            size_hint=(0.8, None),
            height="48dp",
            pos_hint={"center_x": 0.5},
            on_release=self.save_all_config
        )
        content.add_widget(save_btn)
        
        # 状态标签
        self.status_label = MDLabel(
            text="配置未保存",
            halign="center",
            theme_text_color="Secondary",
            size_hint_y=None,
            height="30dp"
        )
        content.add_widget(self.status_label)
        
        scroll.add_widget(content)
        layout.add_widget(scroll)
        self.add_widget(layout)
    
    def _create_section_card(self, title, fields):
        """创建配置区域卡片"""
        card = MDCard(
            size_hint=(1, None),
            height=str(80 + len(fields) * 70) + "dp",
            padding="12dp",
            spacing="8dp",
            elevation=2
        )
        
        section_layout = BoxLayout(
            orientation="vertical",
            spacing="8dp",
            size_hint_y=None
        )
        section_layout.bind(minimum_height=section_layout.setter('height'))
        
        # 标题
        title_label = MDLabel(
            text=title,
            font_style="H6",
            size_hint_y=None,
            height="30dp"
        )
        section_layout.add_widget(title_label)
        
        # 输入字段
        for key_id, label, hint in fields:
            field_box = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height="60dp",
                spacing="8dp"
            )
            
            # 标签
            field_label = MDLabel(
                text=label,
                size_hint=(0.35, None),
                height="40dp",
                valign="center"
            )
            field_box.add_widget(field_label)
            
            # 输入框
            text_field = MDTextField(
                hint_text=hint,
                size_hint=(0.65, None),
                height="40dp",
                mode="rectangle",
                password="secret" in key_id.lower() or "passphrase" in key_id.lower(),
                text=api_key_manager.get(key_id) or ""
            )
            text_field.key_id = key_id  # 存储 key_id 用于保存
            field_box.add_widget(text_field)
            
            section_layout.add_widget(field_box)
        
        card.add_widget(section_layout)
        return card
    
    def save_all_config(self, *args):
        """保存所有配置"""
        try:
            # 遍历所有输入框并保存
            saved_count = 0
            for widget in self.walk():
                if isinstance(widget, MDTextField) and hasattr(widget, 'key_id'):
                    key_id = widget.key_id
                    value = widget.text.strip()
                    if value:
                        api_key_manager.set(key_id, value)
                        saved_count += 1
            
            self.status_label.text = f"✅ 已保存 {saved_count} 项配置"
            self.status_label.theme_text_color = "Custom"
            self.status_label.text_color = (0.2, 0.8, 0.2, 1)
            
            Snackbar(text=f"配置已保存！({saved_count} 项)").open()
            
        except Exception as e:
            self.status_label.text = f"❌ 保存失败: {str(e)}"
            self.status_label.theme_text_color = "Error"
            Snackbar(text=f"保存失败: {str(e)}").open()
    
    def on_enter(self):
        """进入页面时刷新数据"""
        # 重新加载已保存的配置到输入框
        Clock.schedule_once(self._refresh_fields, 0.5)
    
    def _refresh_fields(self, dt):
        """刷新所有输入框的值"""
        for widget in self.walk():
            if isinstance(widget, MDTextField) and hasattr(widget, 'key_id'):
                saved_value = api_key_manager.get(widget.key_id)
                if saved_value and not widget.text:
                    widget.text = saved_value
