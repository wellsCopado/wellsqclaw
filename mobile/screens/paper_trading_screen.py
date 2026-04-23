"""Paper Trading 模拟交易屏幕"""
from kivy.uix.screenmanager import Screen
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.toolbar import MDTopAppBar
import requests


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
        
        # 账户信息容器
        pt_container = BoxLayout(
            orientation="vertical",
            spacing=8,
            size_hint_y=None,
            height=0,
        )
        pt_container.bind(minimum_height=pt_container.setter('height'))
        main.add_widget(pt_container)
        
        # 持仓容器
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
        if self.manager:
            self.manager.current = "home"

    def on_enter(self):
        self.load_account()
        self.load_positions()

    def load_account(self):
        from kivy.app import App
        app = App.get_running_app()
        container = self.pt_container
        container.clear_widgets()

        try:
            resp = requests.get(app.server_url + "/api/trading/account", timeout=5)
            acct = resp.json().get("account", {})
        except Exception:
            acct = {}

        balance = acct.get("balance", 10000.0)
        pnl = acct.get("pnl", acct.get("total_pnl", 0))
        pnl_color = (0.2, 0.73, 0.3, 1) if pnl >= 0 else (0.97, 0.32, 0.29, 1)

        metrics = [
            ("账户余额", f"${balance:,.2f}"),
            ("总盈亏", f"${pnl:,.2f}"),
            ("胜率", f"{acct.get('win_rate', acct.get('winRate', 0))}%"),
            ("交易次数", str(acct.get("total_trades", 0))),
        ]

        for label, value in metrics:
            card = MDCard(
                padding="12dp",
                size_hint_y=None,
                height="70dp",
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
        from kivy.app import App
        app = App.get_running_app()
        container = self.pt_positions
        container.clear_widgets()

        try:
            resp = requests.get(app.server_url + "/api/trading/positions", timeout=5)
            positions = resp.json().get("positions", [])
        except Exception:
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
            )
            box = BoxLayout(orientation="horizontal")
            symbol = pos.get('symbol', 'BTC')
            side = pos.get('side', 'LONG')
            qty = pos.get('quantity', 0)
            box.add_widget(MDLabel(
                text=f"{symbol} {side} {qty}",
                halign="left",
                theme_text_color="Primary"
            ))
            lbl = MDLabel(text=f"{pnl:+.2f}", halign="right")
            lbl.theme_text_color = "Custom"
            lbl.text_color = pnl_color
            box.add_widget(lbl)
            card.add_widget(box)
            container.add_widget(card)
