"""链上数据屏幕"""
from kivy.uix.screenmanager import Screen
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.toolbar import MDTopAppBar
import requests


class OnchainScreen(Screen):
    """链上数据详情屏幕"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical")
        toolbar = MDTopAppBar(
            title="链上数据",
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
        self.onchain_container = container

    def go_back(self):
        """返回上一页"""
        if self.manager:
            self.manager.current = "home"

    def on_enter(self):
        self.load_data()

    def load_data(self):
        from kivy.app import App
        app = App.get_running_app()

        container = self.onchain_container
        container.clear_widgets()

        # 显示加载中
        container.add_widget(MDLabel(
            text="加载中...",
            halign="center",
            theme_text_color="Secondary"
        ))

        def _fetch(dt):
            container.clear_widgets()
            data = {}
            error_msg = ""

            try:
                resp = requests.get(app.server_url + "/api/onchain/ethereum", timeout=10)
                if resp.status_code == 200:
                    result = resp.json()
                    # 兼容多种响应格式
                    if isinstance(result, dict):
                        data = result.get("data", result)
                    else:
                        data = {}
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

            # 创建指标卡片
            metrics = [
                ("Gas价格 (Gwei)", str(data.get("gas_price", data.get("mean_gas_price", "--")))),
                ("区块高度", str(data.get("block_height", "--"))),
                ("活跃地址", str(data.get("active_addresses", "--"))),
                ("大额转账 (24h)", str(data.get("large_transfers", data.get("large_transfers_24h", "--")))),
                ("MVRV比率", str(data.get("mvrv", "--"))),
                ("矿工收益 (ETH/日)", str(data.get("miner_revenue", "--"))),
            ]

            for label, value in metrics:
                card = MDCard(
                    padding="12dp",
                    size_hint_y=None,
                    height="80dp",
                    md_bg_color=(0.1, 0.11, 0.13, 1),
                )
                box = BoxLayout(orientation="horizontal")
                box.add_widget(MDLabel(text=label, halign="left", theme_text_color="Secondary"))
                box.add_widget(MDLabel(text=value, halign="right", theme_text_color="Primary"))
                card.add_widget(box)
                container.add_widget(card)

        from kivy.clock import Clock
        Clock.schedule_once(_fetch, 0.1)
