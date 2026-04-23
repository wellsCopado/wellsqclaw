"""新闻资讯屏幕"""
from kivy.uix.screenmanager import Screen
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.toolbar import MDTopAppBar
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
        """返回上一页"""
        if self.manager:
            self.manager.current = "home"

    def on_enter(self):
        self.load_news()

    def load_news(self):
        # 获取全局 app 对象以读取服务器地址
        from kivy.app import App
        app = App.get_running_app()

        container = self.news_container
        container.clear_widgets()

        # 显示加载中
        loading_label = MDLabel(
            text="加载中...",
            halign="center",
            theme_text_color="Secondary"
        )
        container.add_widget(loading_label)

        def _fetch_news(dt):
            container.clear_widgets()
            news = []
            error_msg = ""

            try:
                resp = requests.get(app.server_url + "/api/news?max_items=20", timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    # 兼容多种响应格式
                    if isinstance(data, dict):
                        news = data.get("news", data.get("data", []))
                    elif isinstance(data, list):
                        news = data
                else:
                    error_msg = f"服务器返回错误: {resp.status_code}"
            except requests.exceptions.ConnectionError:
                error_msg = "连接失败，请检查服务器地址"
            except requests.exceptions.Timeout:
                error_msg = "请求超时，请稍后重试"
            except Exception as e:
                error_msg = f"获取失败: {str(e)}"

            if error_msg:
                container.add_widget(MDLabel(
                    text=error_msg,
                    halign="center",
                    theme_text_color="Error"
                ))
                return

            if not news:
                container.add_widget(MDLabel(
                    text="暂无新闻数据",
                    halign="center",
                    theme_text_color="Secondary"
                ))
                return

            for item in news[:20]:
                # 安全获取 sentiment（支持字符串和数字）
                sentiment_raw = item.get("sentiment", 0)
                if isinstance(sentiment_raw, (int, float)):
                    sentiment = float(sentiment_raw)
                elif isinstance(sentiment_raw, str):
                    sentiment_str = sentiment_raw.lower()
                    if sentiment_str in ("bullish", "positive", "乐观"):
                        sentiment = 1.0
                    elif sentiment_str in ("bearish", "negative", "悲观"):
                        sentiment = -1.0
                    else:
                        sentiment = 0.0
                else:
                    sentiment = 0.0

                sentiment_color = (
                    (0.2, 0.73, 0.3, 1) if sentiment > 0
                    else (0.97, 0.32, 0.29, 1) if sentiment < 0
                    else (0.82, 0.6, 0.14, 1)
                )
                sentiment_text = (
                    "看涨" if sentiment > 0
                    else "看跌" if sentiment < 0
                    else "中性"
                )

                card = MDCard(
                    padding="12dp",
                    size_hint_y=None,
                    height="100dp",
                    md_bg_color=(0.1, 0.11, 0.13, 1),
                )
                box = BoxLayout(orientation="vertical", spacing="4dp")
                title_text = item.get("title", "无标题")
                if not title_text or title_text.strip() == "":
                    title_text = f"{item.get('name', '未知')} ({item.get('symbol', '').upper()})"
                box.add_widget(MDLabel(
                    text=title_text[:60],
                    halign="left",
                    theme_text_color="Primary",
                    font_size="14sp"
                ))
                box.add_widget(MDLabel(
                    text=f"情绪: {sentiment_text} | 来源: {item.get('source', '未知')}",
                    halign="left",
                    color=sentiment_color,
                    font_size="12sp"
                ))
                card.add_widget(box)
                container.add_widget(card)

        # 延迟执行网络请求，避免阻塞UI
        from kivy.clock import Clock
        Clock.schedule_once(_fetch_news, 0.1)
