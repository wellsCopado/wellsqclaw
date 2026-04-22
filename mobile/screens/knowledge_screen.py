"""知识库屏幕"""
from kivy.uix.screenmanager import Screen
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.toolbar import MDTopAppBar
import requests


class KnowledgeScreen(Screen):
    """知识库管理屏幕"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 程序化构建UI（不依赖KV，避免KV加载失败导致黑屏）
        layout = BoxLayout(orientation="vertical")
        toolbar = MDTopAppBar(
            title="知识库",
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
        self.kb_container = container

    def go_back(self):
        """返回上一页"""
        if self.manager:
            self.manager.current = "home"

    def on_enter(self):
        self.load_stats()

    def load_stats(self):
        # 获取全局 app 对象以读取服务器地址
        from kivy.app import App
        app = App.get_running_app()

        container = self.kb_container

        container.clear_widgets()

        try:
            resp = requests.get(app.server_url + "/api/knowledge/stats", timeout=5)
            stats = resp.json().get("stats", {})
        except:
            stats = {}

        metrics = [
            ("成功模式数", str(stats.get("success_patterns", stats.get("total_patterns", 0)))),
            ("失败教训数", str(stats.get("failure_patterns", 0))),
            ("准确率", str(stats.get("accuracy", stats.get("regression_accuracy", 0))) + "%"),
            ("知识库条目", str(stats.get("total_entries", 0))),
        ]

        for label, value in metrics:
            card = MDCard(
                padding="12dp",
                size_hint_y=None,
                height="70dp",
                md_bg_color=(0.1, 0.11, 0.13, 1),
            )
            box = BoxLayout(orientation="horizontal")
            box.add_widget(MDLabel(text=label, halign="left", theme_text_color="Secondary"))
            box.add_widget(MDLabel(text=value, halign="right", theme_text_color="Primary", bold=True))
            card.add_widget(box)
            container.add_widget(card)
