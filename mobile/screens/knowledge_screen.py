"""知识库屏幕"""
from kivy.uix.screenmanager import Screen
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout
import requests


class KnowledgeScreen(Screen):
    """知识库管理屏幕"""
    
    def on_enter(self):
        self.load_stats()
    

    def go_back(self):
        """返回上一页"""
        if self.manager:
            self.manager.current = self.manager.previous() or "home"
    def load_stats(self):
        container = self.ids.get('kb_container')
        if not container:
            return
        
        container.clear_widgets()
        
        try:
            resp = requests.get("http://localhost:8000/api/knowledge/stats", timeout=5)
            stats = resp.json().get("stats", {})
        except:
            stats = {}
        
        metrics = [
            ("成功模式数", str(stats.get("success_patterns", stats.get("total_patterns", 0)))),
            ("失败教训数", str(stats.get("failure_patterns", 0))),
            ("准确率", str(stats.get("accuracy", stats.get("regression_accuracy", 0))) + "%"),
            ("知识库条目", str(stats.get("total_entries", 0))),
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
            box.add_widget(MDLabel(text=value, halign="right", theme_text_color="Primary", bold=True))
            card.add_widget(box)
            container.add_widget(card)
