"""Paper Trading 模拟交易屏幕"""
from kivy.uix.screenmanager import Screen
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.toolbar import MDTopAppBar
import requests
import json


class PaperTradingScreen(Screen):
    """Paper Trading 模拟账户屏幕"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical")
        toolbar = MDTopAppBar(
            title="模拟交易",
            left_action_items=[["arrow-left", lambda x: self.go_back()]],
        )
        layout.add_widget(toolbar)
        scroll = MDScrollView()
        main = BoxLayout(
            orientation="vertical",
            spacing=8,
            size_hint_y=None,
            height=0,
            padding=[8, 8, 8, 8],
        )
        main.bind(minimum_height=main.setter('height'))
        pt_container = BoxLayout(
            orientation="vertical",
            spacing=8,
            size_hint_y=None,
            height=0,
        )
        pt_container.bind(minimum_height=pt_container.setter('height'))
        main.add_widget(pt_container)
        pt_positions = BoxLayout(
            orientation="vertical",
            spacing=8,
            size_hint_y=None,
            height=0,
        )
        pt_positions.bind(minimum_height=pt_positions.setter('height'))
        main.add_widget(pt_positions)
        scroll.add_widget(main)
        layout.add_widget(scroll)
        self.add_widget(layout)
        self.pt_container = pt_container
        self.pt_positions = pt_positions

    def go_back(self):
        """返回上一页"""
        if self.manager:
            self.manager.current = "home"

    def on_enter(self):
        self.load_account()
        self.load_positions()

    def load_account(self):
        # 获取全局 app 对象以读取服务器地址
        from kivy.app import App
        app = App.get_running_app()

        container = self.pt_container

        container.clear_widgets()

        try:
            resp = requests.get(app.server_url + "/api/trading/account", timeout=5)
            acct = resp.json().get("account", {})
        except:
            acct = {}

        balance = acct.get("balance", 0)
        pnl = acct.get("pnl", acct.get("total_pnl", 0))
        pnl_color = (0.2, 0.73, 0.3, 1) if pnl >= 0 else (0.97, 0.32, 0.29, 1)

        metrics = [
            ("账户余额", f"${balance:,.2f}"),
            ("总盈亏", f"${pnl:,.2f}"),
            ("胜率", f"{acct.get('win_rate', acct.get('winRate', 0))}%"),
            ("开仓数", str(acct.get("open_positions", 0))),
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
            lbl = MDLabel(text=value, halign="right", bold=True)
            if label == "总盈亏":
                lbl.theme_text_color = "Custom"
                lbl.text_color = pnl_color
            else:
                lbl.theme_text_color = "Primary"
            box.add_widget(lbl)
            card.add_widget(box)
            container.add_widget(card)

    def load_positions(self):
        # 获取全局 app 对象以读取服务器地址
        from kivy.app import App
        app = App.get_running_app()

        container = self.pt_positions

        container.clear_widgets()

        try:
            resp = requests.get(app.server_url + "/api/trading/positions", timeout=5)
            positions = resp.json().get("positions", [])
        except:
            positions = []

        if not positions:
            container.add_widget(MDLabel(
                text="暂无持仓",
                halign="center",
                theme_text_color="Secondary"
            ))
            return

        for pos in positions:
            pnl = pos.get("pnl", 0)
            pnl_color = (0.2, 0.73, 0.3, 1) if pnl >= 0 else (0.97, 0.32, 0.29, 1)
            card = MDCard(
                padding="12dp",
                size_hint_y=None,
                height="80dp",
                md_bg_color=(0.1, 0.11, 0.13, 1),
            )
            box = BoxLayout(orientation="horizontal")
            box.add_widget(MDLabel(
                text=f"{pos.get('symbol','BTC')} {pos.get('side','LONG')} {pos.get('quantity',0)}",
                halign="left",
                theme_text_color="Primary"
            ))
            lbl = MDLabel(text=f"{pnl:+.2f}", halign="right")
            lbl.theme_text_color = "Custom"
            lbl.text_color = pnl_color
            box.add_widget(lbl)
            card.add_widget(box)
            container.add_widget(card)
