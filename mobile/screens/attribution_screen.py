"""归因分析屏幕"""
from kivy.uix.screenmanager import Screen
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout
import requests


class AttributionScreen(Screen):
    """归因分析屏幕"""
    
    def on_enter(self):
        self.load_analysis()
    

    def go_back(self):
        """返回上一页"""
        if self.manager:
            self.manager.current = self.manager.previous() or "home"
    def load_analysis(self):
        container = self.ids.get('attr_container')
        if not container:
            return
        
        container.clear_widgets()
        
        try:
            resp = requests.get("http://localhost:8000/api/attribution/summary", timeout=5)
            summary = resp.json().get("summary", {})
        except:
            summary = {}
        
        factors = summary.get("factors", [
            {"name": "技术面", "contribution": summary.get("technical", 0.3)},
            {"name": "资金面", "contribution": summary.get("funding", 0.25)},
            {"name": "情绪面", "contribution": summary.get("sentiment", 0.2)},
            {"name": "执行面", "contribution": summary.get("execution", 0.15)},
            {"name": "风险面", "contribution": summary.get("risk", 0.1)},
        ])
        
        for factor in factors:
            card = MDCard(
                padding="12dp",
                size_hint_y=None,
                height="80dp",
                md_bg_color=(0.1, 0.11, 0.13, 1),
            )
            box = MDBoxLayout(orientation="vertical", spacing="4dp")
            box.add_widget(MDLabel(
                text=factor.get("name", "因子"),
                halign="left",
                theme_text_color="Primary"
            ))
            # 进度条
            from kivymd.uix.progressbar import MDProgressBar
            bar = MDProgressBar(
                value=factor.get("contribution", 0) * 100,
                max_value=100,
                color=(0.49, 0.73, 1.0, 1),
            )
            box.add_widget(bar)
            box.add_widget(MDLabel(
                text=f"贡献度: {factor.get('contribution', 0)*100:.1f}%",
                halign="right",
                theme_text_color="Secondary",
                font_size="12sp"
            ))
            card.add_widget(box)
            container.add_widget(card)
