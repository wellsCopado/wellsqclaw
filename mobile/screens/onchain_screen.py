"""链上数据屏幕"""
from kivy.uix.screenmanager import Screen
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout
import requests
import asyncio


class OnchainScreen(Screen):
    """链上数据详情屏幕"""
    
    def on_enter(self):
        self.load_data()
    

    def go_back(self):
        """返回上一页"""
        if self.manager:
            self.manager.current = self.manager.previous() or "home"
    def load_data(self):
        container = self.ids.get('onchain_container')
        if not container:
            return
        
        container.clear_widgets()
        
        # 加载ETH数据
        try:
            resp = requests.get("http://localhost:8000/api/onchain/ethereum", timeout=5)
            data = resp.json().get("data", {})
        except:
            data = {"error": "数据获取失败"}
        
        # 创建指标卡片
        metrics = [
            ("Gas价格 (Gwei)", str(data.get("gas_price", data.get("mean_gas_price", "--")))),
            ("活跃地址", str(data.get("active_addresses", "--"))),
            ("大额转账", str(data.get("large_transfers", "--"))),
            ("MVRV比率", str(data.get("mvrv", "--"))),
            ("矿工收益", str(data.get("miner_revenue", "--"))),
        ]
        
        for label, value in metrics:
            card = MDCard(
                padding="12dp",
                size_hint_y=None,
                height="80dp",
                md_bg_color=(0.1, 0.11, 0.13, 1),
            )
            box = MDBoxLayout(orientation="horizontal")
            box.add_widget(MDLabel(text=label, halign="left", theme_text_color="Secondary"))
            box.add_widget(MDLabel(text=value, halign="right", theme_text_color="Primary"))
            card.add_widget(box)
            container.add_widget(card)
