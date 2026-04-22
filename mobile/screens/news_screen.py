"""新闻资讯屏幕"""
from kivy.uix.screenmanager import Screen
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.toolbar import MDTopAppBar
import requests


class NewsScreen(Screen):
    """新闻资讯屏幕"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = MDBoxLayout(orientation="vertical")
        toolbar = MDTopAppBar(
            title="最新资讯",
            left_action_items=[["arrow-left", lambda x: self.go_back()]],
        )
        layout.add_widget(toolbar)
        scroll = MDScrollView()
        container = MDBoxLayout(
            id="news_container",
            orientation="vertical",
            spacing="8dp",
            size_hint_y=None,
            padding="8dp",
        )
        container.bind(minimum_height=container.setter('height'))
        scroll.add_widget(container)
        layout.add_widget(scroll)
        self.add_widget(layout)

    def go_back(self):
        """返回上一页"""
        if self.manager:
            self.manager.current = "home"

    def on_enter(self):
        self.load_news()

    def load_news(self):
        # 获取全局 app 对象以读取服务器地址
        from kivy.app import App
        app = App.get_running_app()

        container = self.ids.get('news_container')
        if not container:
            return

        container.clear_widgets()

        try:
            resp = requests.get(app.server_url + "/api/news?max_items=20", timeout=5)
            news = resp.json().get("news", [])
        except:
            news = []

        if not news:
            container.add_widget(MDLabel(
                text="暂无新闻数据",
                halign="center",
                theme_text_color="Secondary"
            ))
            return

        for item in news[:20]:
            sentiment = item.get("sentiment", 0)
            sentiment_color = (0.2, 0.73, 0.3, 1) if sentiment > 0 else (0.97, 0.32, 0.29, 1) if sentiment < 0 else (0.82, 0.6, 0.14, 1)
            card = MDCard(
                padding="12dp",
                size_hint_y=None,
                height="100dp",
                md_bg_color=(0.1, 0.11, 0.13, 1),
            )
            box = MDBoxLayout(orientation="vertical", spacing="4dp")
            box.add_widget(MDLabel(
                text=item.get("title", "无标题")[:50],
                halign="left",
                theme_text_color="Primary",
                font_size="14sp"
            ))
            box.add_widget(MDLabel(
                text=f"情绪: {sentiment:.2f} | {item.get('source', '')}",
                halign="left",
                color=sentiment_color,
                font_size="12sp"
            ))
            card.add_widget(box)
            container.add_widget(card)
