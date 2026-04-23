"""新闻资讯屏幕"""
from kivy.uix.screenmanager import Screen
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.toolbar import MDTopAppBar
from kivy.clock import Clock
import requests


class NewsScreen(Screen):
    """新闻资讯屏幕"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical")
        toolbar = MDTopAppBar(
            title="最新资讯",
            left_action_items=[["arrow-left", lambda x: self.go_back()]],
        )
        layout.add_widget(toolbar)
        scroll = MDScrollView()
        container = BoxLayout(
            orientation="vertical",
            spacing=8,
            size_hint_y=None,
            padding=[8, 8, 8, 8],
        )
        container.bind(minimum_height=container.setter('height'))
        scroll.add_widget(container)
        layout.add_widget(scroll)
        self.add_widget(layout)
        self.news_container = container

    def go_back(self):
        if self.manager:
            self.manager.current = "home"

    def on_enter(self):
        self.load_news()

    def load_news(self):
        from kivy.app import App
        app = App.get_running_app()
        container = self.news_container
        container.clear_widgets()

        try:
            resp = requests.get(app.server_url + "/api/news?max_items=20", timeout=5)
            news = resp.json().get("news", [])
        except Exception:
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
            if isinstance(sentiment, str):
                sentiment = 1 if sentiment == "bullish" else -1 if sentiment == "bearish" else 0
            
            sentiment_color = (0.2, 0.73, 0.3, 1) if sentiment > 0 else (0.97, 0.32, 0.29, 1) if sentiment < 0 else (0.82, 0.6, 0.14, 1)
            
            card = MDCard(
                padding="12dp",
                size_hint_y=None,
                height="80dp",
            )
            box = BoxLayout(orientation="vertical", spacing="4dp")
            title = item.get("title", "无标题")[:50]
            box.add_widget(MDLabel(
                text=title,
                halign="left",
                theme_text_color="Primary",
                font_size="13sp"
            ))
            box.add_widget(MDLabel(
                text=f"来源: {item.get('source', '')}",
                halign="left",
                color=sentiment_color,
                font_size="11sp"
            ))
            card.add_widget(box)
            container.add_widget(card)
