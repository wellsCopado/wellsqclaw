"""知识库屏幕"""
from kivy.uix.screenmanager import Screen
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.toolbar import MDTopAppBar
import requests


class KnowledgeScreen(Screen):
    """知识库管理屏幕"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
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
        from kivy.app import App
        app = App.get_running_app()

        container = self.kb_container
        container.clear_widgets()

        # 显示加载中
        container.add_widget(MDLabel(
            text="加载中...",
            halign="center",
            theme_text_color="Secondary"
        ))

        def _fetch(dt):
            container.clear_widgets()
            stats = {}
            error_msg = ""

            try:
                resp = requests.get(app.server_url + "/api/knowledge/stats", timeout=10)
                if resp.status_code == 200:
                    result = resp.json()
                    # 兼容多种响应格式
                    if isinstance(result, dict):
                        stats = result.get("stats", result.get("patterns", result))
                    else:
                        stats = {}
                else:
                    error_msg = f"服务器返回错误: {resp.status_code}"
            except requests.exceptions.ConnectionError:
                error_msg = "连接失败，请检查服务器地址"
            except requests.exceptions.Timeout:
                error_msg = "请求超时"
            except Exception as e:
                error_msg = f"获取失败: {str(e)}"

            if error_msg:
                container.add_widget(MDLabel(
                    text=error_msg,
                    halign="center",
                    theme_text_color="Error"
                ))
                return

            metrics = [
                ("成功模式数", str(stats.get("success_patterns", stats.get("success", 0)))),
                ("失败教训数", str(stats.get("failure_patterns", stats.get("failure", 0)))),
                ("准确率", f"{stats.get('accuracy', stats.get('regression_accuracy', 0))}%"),
                ("知识库条目", str(stats.get("total_entries", stats.get("total_patterns", 0)))),
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

        from kivy.clock import Clock
        Clock.schedule_once(_fetch, 0.1)
