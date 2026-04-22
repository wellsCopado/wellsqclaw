"""归因分析屏幕"""
from kivy.uix.screenmanager import Screen
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.toolbar import MDTopAppBar
import requests


class AttributionScreen(Screen):
    """归因分析屏幕"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = MDBoxLayout(orientation="vertical")
        toolbar = MDTopAppBar(
            title="归因分析",
            left_action_items=[["arrow-left", lambda x: self.go_back()]],
        )
        layout.add_widget(toolbar)
        scroll = MDScrollView()
        container = BoxLayout(
            orientation="vertical",
            spacing=8,
            size_hint_y=None,
            height=0,
            padding=[8, 8, 8, 8],
        )
        container.bind(minimum_height=container.setter('height'))
        scroll.add_widget(container)
        layout.add_widget(scroll)
        self.add_widget(layout)
        self.attr_container = container

    def go_back(self):
        """返回上一页"""
        if self.manager:
            self.manager.current = "home"

    def on_enter(self):
        self.load_analysis()

    def load_analysis(self):
        # 获取全局 app 对象以读取服务器地址
        from kivy.app import App
        app = App.get_running_app()

        container = self.attr_container

        container.clear_widgets()

        try:
            resp = requests.get(app.server_url + "/api/attribution/summary", timeout=5)
            summary = resp.json().get("summary", {})
        except:
            summary = {}

        factors = summary.get("factors", [
            {"name": "技术面", "contribution": summary.get("technical", 0.3)},
            {"name": "资金面", "contribution": summary.get("funding", 0.25)},
            {"name": "情绪面", "contribution": summary.get("sentiment", 0.2)},
            {"name": "执行面", "contribution": summary.get("execution", 0.15)},
            {"name": "风险面", "contribution": summary.get("risk", 0.1)},
        ])

        for factor in factors:
            card = MDCard(
                padding="12dp",
                size_hint_y=None,
                height="80dp",
                md_bg_color=(0.1, 0.11, 0.13, 1),
            )
            box = MDBoxLayout(orientation="vertical", spacing="4dp")
            box.add_widget(MDLabel(
                text=factor.get("name", "因子"),
                halign="left",
                theme_text_color="Primary"
            ))
            from kivymd.uix.progressbar import MDProgressBar
            bar = MDProgressBar(
                value=factor.get("contribution", 0) * 100,
                max_value=100,
                color=(0.49, 0.73, 1.0, 1),
            )
            box.add_widget(bar)
            box.add_widget(MDLabel(
                text=f"贡献度: {factor.get('contribution', 0)*100:.1f}%",
                halign="right",
                theme_text_color="Secondary",
                font_size="12sp"
            ))
            card.add_widget(box)
            container.add_widget(card)
