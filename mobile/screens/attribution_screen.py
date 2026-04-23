"""归因分析屏幕"""
from kivy.uix.screenmanager import Screen
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.progressbar import MDProgressBar
import requests


class AttributionScreen(Screen):
    """归因分析屏幕"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical")
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
        from kivy.app import App
        app = App.get_running_app()

        container = self.attr_container
        container.clear_widgets()

        # 显示加载中
        container.add_widget(MDLabel(
            text="加载中...",
            halign="center",
            theme_text_color="Secondary"
        ))

        def _fetch(dt):
            container.clear_widgets()
            summary = {}
            error_msg = ""

            try:
                resp = requests.get(app.server_url + "/api/attribution/summary", timeout=10)
                if resp.status_code == 200:
                    result = resp.json()
                    # 兼容多种响应格式
                    if isinstance(result, dict):
                        summary = result.get("summary", result)
                    else:
                        summary = {}
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

            # 显示综合评分
            overall = summary.get("overall", 50)
            overall_color = (0.2, 0.73, 0.3, 1) if overall >= 60 else (0.97, 0.32, 0.29, 1) if overall < 40 else (0.82, 0.6, 0.14, 1)
            
            overall_card = MDCard(
                padding="16dp",
                size_hint_y=None,
                height="100dp",
                md_bg_color=(0.1, 0.11, 0.13, 1),
            )
            overall_box = BoxLayout(orientation="vertical", spacing="4dp")
            overall_box.add_widget(MDLabel(
                text="综合评分",
                halign="center",
                theme_text_color="Primary",
                font_style="H6",
            ))
            overall_label = MDLabel(
                text=f"{overall:.1f}/100",
                halign="center",
                theme_text_color="Custom",
                text_color=overall_color,
                font_style="H4",
            )
            overall_box.add_widget(overall_label)
            overall_card.add_widget(overall_box)
            container.add_widget(overall_card)

            # 获取因子列表
            factors = summary.get("factors", [])
            if not factors:
                # 回退到旧格式
                factors = [
                    {"name": "技术面", "score": summary.get("technical", 30), "contribution": summary.get("technical", 0.3), "weight": 0.3},
                    {"name": "资金面", "score": summary.get("funding", 25), "contribution": summary.get("funding", 0.25), "weight": 0.25},
                    {"name": "情绪面", "score": summary.get("sentiment", 20), "contribution": summary.get("sentiment", 0.2), "weight": 0.2},
                    {"name": "执行面", "score": summary.get("execution", 15), "contribution": summary.get("execution", 0.15), "weight": 0.15},
                    {"name": "风险面", "score": summary.get("risk", 10), "contribution": summary.get("risk", 0.1), "weight": 0.1},
                ]

            for factor in factors:
                card = MDCard(
                    padding="12dp",
                    size_hint_y=None,
                    height="100dp",
                    md_bg_color=(0.1, 0.11, 0.13, 1),
                )
                box = BoxLayout(orientation="vertical", spacing="4dp")
                
                # 名称和分数
                name_row = BoxLayout(orientation="horizontal")
                name_row.add_widget(MDLabel(
                    text=factor.get("name", "因子"),
                    halign="left",
                    theme_text_color="Primary"
                ))
                score = factor.get("score", factor.get("contribution", 0) * 100)
                name_row.add_widget(MDLabel(
                    text=f"{score:.1f}分",
                    halign="right",
                    theme_text_color="Secondary"
                ))
                box.add_widget(name_row)
                
                # 进度条
                bar = MDProgressBar(
                    value=min(100, max(0, score)),
                    max_value=100,
                    color=(0.49, 0.73, 1.0, 1),
                )
                box.add_widget(bar)
                
                # 权重信息
                weight = factor.get("weight", 0)
                box.add_widget(MDLabel(
                    text=f"权重: {weight*100:.0f}%",
                    halign="right",
                    theme_text_color="Secondary",
                    font_size="12sp"
                ))
                
                card.add_widget(box)
                container.add_widget(card)

        from kivy.clock import Clock
        Clock.schedule_once(_fetch, 0.1)
