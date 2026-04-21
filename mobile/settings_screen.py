"""
移动端配置管理界面
支持所有配置的查看和修改
"""
import json
import threading
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.switch import Switch
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.uix.card import Card
from kivy.clock import Clock
from kivy.properties import StringProperty, BooleanProperty
import logging

# 简单 logger，避免依赖 core 模块
logger = logging.getLogger('settings')
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    logger.addHandler(handler)

# Android 上没有本地后端，禁用 API 调用
API_BASE = None


class ConfigItem(BoxLayout):
    """单个配置项组件"""
    key = StringProperty()
    value = StringProperty()
    
    def __init__(self, key, value, on_save_callback, **kwargs):
        super().__init__(**kwargs)
        self.key = key
        self.value = str(value)
        self.on_save = on_save_callback
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = '50dp'
        self.padding = 5
        self.spacing = 10
        
        # 配置项名称
        label = Label(
            text=key,
            size_hint_x = 0.35,
            text_size = (None, None),
            halign = 'left',
            valign = 'middle',
            color = (0.9, 0.91, 0.93, 1)
        )
        self.add_widget(label)
        
        # 根据值类型显示不同控件
        if isinstance(value, bool):
            switch = Switch(active=value)
            switch.bind(active=lambda s, v, k=key: self.on_save(k, v))
            self.add_widget(switch)
        elif isinstance(value, list):
            spinner = Spinner(
                text=str(value[0]) if value else '请选择',
                values=[str(v) for v in value],
                size_hint_x = 0.55
            )
            spinner.bind(text=lambda s, v, k=key: self.on_save(k, v))
            self.add_widget(spinner)
        elif isinstance(value, (int, float)):
            # 数值类型用文本框
            ti = TextInput(
                text=str(value),
                multiline = False,
                size_hint_x = 0.55,
                input_filter = 'float' if isinstance(value, float) else 'int'
            )
            ti.bind(on_text_validate=lambda t, k=key: self.on_save(k, t.text))
            self.add_widget(ti)
        else:
            # 字符串类型
            ti = TextInput(
                text=str(value),
                multiline = False,
                size_hint_x = 0.55
            )
            ti.bind(on_text_validate=lambda t, k=key: self.on_save(k, t.text))
            self.add_widget(ti)


class SettingsScreen(Screen):
    """设置页面 - 支持所有配置"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config_data = {}
        self.current_section = "display"
        self.loading = False
        
    def on_enter(self):
        """进入页面时加载配置"""
        Clock.schedule_once(self._load_config, 0.5)
    
    def _load_config(self, *args):
        """从API加载配置"""
        if self.loading:
            return
        self.loading = True
        
        def fetch():
            try:
                import urllib.request
                req = urllib.request.Request(f"{API_BASE}/api/config")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                    Clock.schedule_once(lambda dt: self._display_config(data.get('data', {})), 0)
            except Exception as e:
                logger.error(f"加载配置失败: {e}")
                Clock.schedule_once(lambda dt: self._show_error(str(e)), 0)
            finally:
                self.loading = False
        
        threading.Thread(target=fetch, daemon=True).start()
    
    def _display_config(self, data):
        """显示配置"""
        self.config_data = data
        
        # 找到主容器并清空
        main_layout = None
        for child in self.children:
            if isinstance(child, BoxLayout) and child.orientation == 'vertical':
                main_layout = child
                break
        
        if not main_layout:
            return
        
        # 清除旧的ScrollView
        for child in list(main_layout.children):
            if isinstance(child, ScrollView):
                main_layout.remove_widget(child)
        
        # 创建新内容
        content = BoxLayout(orientation='vertical', size_hint_y=None, height='1000dp')
        content.bind(minimum_height=content.setter('height'))
        
        # 显示配置的JSON（简化版）
        # 实际项目中这里应该用更友好的UI
        config_text = json.dumps(data, indent=2, ensure_ascii=False)
        
        # 创建可滚动的配置显示
        scroll = ScrollView(size_hint=(1, 1))
        config_layout = BoxLayout(orientation='vertical', size_hint_y=None, padding=10, spacing=5)
        config_layout.bind(minimum_height=config_layout.setter('height'))
        
        # 简化显示所有配置
        for section_name, section_data in data.items():
            section_label = Label(
                text=f"【{section_name}】",
                size_hint_y=None,
                height='40dp',
                color=(0.3, 0.7, 1.0, 1),
                font_size='16sp',
                bold=True
            )
            config_layout.add_widget(section_label)
            
            if isinstance(section_data, dict):
                for key, value in section_data.items():
                    item_text = f"  {key}: {value}"
                    item_label = Label(
                        text=item_text,
                        size_hint_y=None,
                        height='30dp',
                        color=(0.8, 0.82, 0.85, 1),
                        font_size='12sp',
                        halign='left',
                        text_size=(self.width - 40, None)
                    )
                    config_layout.add_widget(item_label)
        
        scroll.add_widget(config_layout)
        main_layout.add_widget(scroll)
    
    def _show_error(self, msg):
        """显示错误"""
        logger.error(f"设置页面错误: {msg}")
    
    def save_config(self, key, value):
        """保存配置"""
        parts = key.split('.')
        if len(parts) >= 2:
            section = parts[0]
            key_name = '.'.join(parts[1:])
            
            def save():
                try:
                    import urllib.request, urllib.parse
                    url = f"{API_BASE}/api/config/{section}/{urllib.parse.quote(key_name)}"
                    data = json.dumps({"value": value}).encode()
                    req = urllib.request.Request(
                        url, data=data,
                        headers={"Content-Type": "application/json"},
                        method="PUT"
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        result = json.loads(resp.read())
                        if result.get('status') == 'ok':
                            logger.info(f"配置已保存: {key} = {value}")
                        else:
                            logger.error(f"保存失败: {result.get('error')}")
                except Exception as e:
                    logger.error(f"保存配置失败: {e}")
            
            threading.Thread(target=save, daemon=True).start()


# ═══════════════════════════════════════════════════════════════════════════
# 快速设置组件 - 用于Dashboard页面
# ═══════════════════════════════════════════════════════════════════════════

class QuickSettingsCard(BoxLayout):
    """快速设置卡片"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 15
        self.spacing = 10
        self.size_hint = (0.95, None)
        self.height = '400dp'
        
        # 标题
        title = Label(
            text='⚙️ 快速设置',
            size_hint_y=None,
            height='40dp',
            color=(0.3, 0.7, 1.0, 1),
            font_size='18sp',
            bold=True
        )
        self.add_widget(title)
        
        # 快速设置项
        settings = [
            ("默认交易对", "BTCUSDT", "text"),
            ("时间周期", "4h", "select", ["1h", "4h", "1d", "1w"]),
            ("信号置信度阈值", "60", "number"),
            ("自动清理", True, "switch"),
            ("自动进化", False, "switch"),
        ]
        
        for label_text, default, stype, *extra in settings:
            row = BoxLayout(orientation='horizontal', size_hint_y=None, height='45dp')
            
            lbl = Label(
                text=label_text,
                size_hint_x=0.4,
                color=(0.9, 0.91, 0.93, 1),
                halign='left'
            )
            row.add_widget(lbl)
            
            if stype == "switch":
                sw = Switch(active=default)
                sw.size_hint_x = 0.5
                row.add_widget(sw)
            elif stype == "select":
                spinner = Spinner(text=default, values=extra[0], size_hint_x=0.5)
                row.add_widget(spinner)
            else:
                ti = TextInput(text=str(default), size_hint_x=0.5, multiline=False)
                row.add_widget(ti)
            
            self.add_widget(row)
        
        # 保存按钮
        save_btn = Button(
            text='💾 保存设置',
            size_hint_y=None,
            height='50dp',
            background_color=(0.2, 0.6, 1.0, 1),
            color=(1, 1, 1, 1)
        )
        save_btn.bind(on_press=lambda x: self._save_all())
        self.add_widget(save_btn)
    
    def _save_all(self):
        """保存所有设置"""
        logger.info("保存所有设置...")
        # 实现保存逻辑
