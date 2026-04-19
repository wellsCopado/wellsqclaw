"""Paper Trading 模拟交易屏幕"""
from kivy.uix.screenmanager import Screen
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton
import requests
import json


class PaperTradingScreen(Screen):
    """Paper Trading 模拟账户屏幕"""
    
    def on_enter(self):
        self.load_account()
        self.load_positions()
    
    def load_account(self):
        container = self.ids.get('pt_container')
        if not container:
            return
        
        container.clear_widgets()
        
        try:
            resp = requests.get("http://localhost:8000/api/trading/account", timeout=5)
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
            box = MDBoxLayout(orientation="horizontal")
            box.add_widget(MDLabel(text=label, halign="left", theme_text_color="Secondary"))
            lbl = MDLabel(text=value, halign="right", bold=True)
            if label == "总盈亏":
                from kivy.core.text import LabelBase
                lbl.theme_text_color = "Custom"
                lbl.text_color = pnl_color
            else:
                lbl.theme_text_color = "Primary"
            box.add_widget(lbl)
            card.add_widget(box)
            container.add_widget(card)
    
    def load_positions(self):
        container = self.ids.get('pt_positions')
        if not container:
            return
        
        container.clear_widgets()
        
        try:
            resp = requests.get("http://localhost:8000/api/trading/positions", timeout=5)
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
            box = MDBoxLayout(orientation="horizontal")
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
