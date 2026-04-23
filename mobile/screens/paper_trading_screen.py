"""Paper Trading 模拟交易屏幕"""
from kivy.uix.screenmanager import Screen
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.dialog import MDDialog
from kivymd.uix.snackbar import Snackbar
import requests
import json


# 模拟交易数据存储（内存中，实际应用应使用持久化存储）
_paper_trading_data = {
    "account": {
        "balance": 10000.0,
        "pnl": 0.0,
        "win_rate": 0.0,
        "total_trades": 0,
        "open_positions": 0,
    },
    "positions": [],
    "trade_history": [],
}


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

        # 账户信息区域
        pt_container = BoxLayout(
            orientation="vertical",
            spacing=8,
            size_hint_y=None,
            height=0,
        )
        pt_container.bind(minimum_height=pt_container.setter('height'))
        main.add_widget(pt_container)

        # 操作按钮区域
        action_box = BoxLayout(
            orientation="horizontal",
            spacing=8,
            size_hint_y=None,
            height="50dp",
            padding=[0, 8, 0, 8],
        )
        buy_btn = MDRaisedButton(
            text="买入",
            md_bg_color=(0.2, 0.73, 0.3, 1),
            on_release=self.show_buy_dialog,
        )
        sell_btn = MDRaisedButton(
            text="卖出",
            md_bg_color=(0.97, 0.32, 0.29, 1),
            on_release=self.show_sell_dialog,
        )
        action_box.add_widget(buy_btn)
        action_box.add_widget(sell_btn)
        main.add_widget(action_box)

        # 持仓区域
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
        self.dialog = None

    def go_back(self):
        """返回上一页"""
        if self.manager:
            self.manager.current = "home"

    def on_enter(self):
        self.load_account()
        self.load_positions()

    def get_server_url(self):
        from kivy.app import App
        app = App.get_running_app()
        return getattr(app, 'server_url', 'http://127.0.0.1:8000')

    def load_account(self):
        container = self.pt_container
        container.clear_widgets()

        # 尝试从服务器获取，失败则使用本地数据
        acct = _paper_trading_data["account"].copy()
        try:
            resp = requests.get(self.get_server_url() + "/api/trading/account", timeout=5)
            if resp.status_code == 200:
                server_acct = resp.json()
                if isinstance(server_acct, dict):
                    acct.update(server_acct)
        except Exception:
            pass

        balance = acct.get("balance", 0)
        pnl = acct.get("pnl", acct.get("total_pnl", 0))
        pnl_color = (0.2, 0.73, 0.3, 1) if pnl >= 0 else (0.97, 0.32, 0.29, 1)

        metrics = [
            ("账户余额", f"${balance:,.2f}"),
            ("总盈亏", f"${pnl:,.2f}"),
            ("胜率", f"{acct.get('win_rate', acct.get('winRate', 0)):.1f}%"),
            ("交易次数", str(acct.get("total_trades", 0))),
            ("当前持仓", str(acct.get("open_positions", 0))),
        ]

        for label, value in metrics:
            card = MDCard(
                padding="12dp",
                size_hint_y=None,
                height="60dp",
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
        container = self.pt_positions
        container.clear_widgets()

        # 添加持仓标题
        container.add_widget(MDLabel(
            text="当前持仓",
            font_style="H6",
            size_hint_y=None,
            height="40dp",
        ))

        positions = _paper_trading_data["positions"]

        # 尝试从服务器获取持仓
        try:
            resp = requests.get(self.get_server_url() + "/api/trading/positions", timeout=5)
            if resp.status_code == 200:
                server_positions = resp.json()
                if isinstance(server_positions, dict):
                    positions = server_positions.get("positions", [])
                elif isinstance(server_positions, list):
                    positions = server_positions
        except Exception:
            pass

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
                height="90dp",
                md_bg_color=(0.1, 0.11, 0.13, 1),
            )
            box = BoxLayout(orientation="vertical", spacing="4dp")
            # 第一行：币种和方向
            row1 = BoxLayout(orientation="horizontal")
            side = pos.get('side', 'LONG')
            side_color = (0.2, 0.73, 0.3, 1) if side == 'LONG' else (0.97, 0.32, 0.29, 1)
            side_label = MDLabel(
                text=f"{pos.get('symbol','BTC')} ",
                halign="left",
                theme_text_color="Primary",
                bold=True,
            )
            side_badge = MDLabel(
                text=side,
                halign="left",
                theme_text_color="Custom",
                text_color=side_color,
                font_size="12sp",
            )
            row1.add_widget(side_label)
            row1.add_widget(side_badge)
            row1.add_widget(MDLabel(
                text=f"{pnl:+.2f} USDT",
                halign="right",
                theme_text_color="Custom",
                text_color=pnl_color,
            ))
            box.add_widget(row1)
            # 第二行：数量和入场价
            row2 = BoxLayout(orientation="horizontal")
            row2.add_widget(MDLabel(
                text=f"数量: {pos.get('quantity', 0)}",
                halign="left",
                theme_text_color="Secondary",
                font_size="12sp",
            ))
            row2.add_widget(MDLabel(
                text=f"入场: ${pos.get('entry_price', 0):,.2f}",
                halign="right",
                theme_text_color="Secondary",
                font_size="12sp",
            ))
            box.add_widget(row2)
            card.add_widget(box)
            container.add_widget(card)

    def show_buy_dialog(self, *args):
        """显示买入对话框"""
        self._show_trade_dialog("买入", "LONG")

    def show_sell_dialog(self, *args):
        """显示卖出对话框"""
        self._show_trade_dialog("卖出", "SHORT")

    def _show_trade_dialog(self, action_name, side):
        """显示交易对话框"""
        content = BoxLayout(orientation="vertical", spacing="12dp", padding="12dp")

        symbol_input = MDTextField(
            hint_text="交易对 (如 BTCUSDT)",
            text="BTCUSDT",
        )
        quantity_input = MDTextField(
            hint_text="数量",
            text="0.01",
            input_filter="float",
        )
        price_input = MDTextField(
            hint_text="价格 (留空用市价)",
            input_filter="float",
        )

        content.add_widget(symbol_input)
        content.add_widget(quantity_input)
        content.add_widget(price_input)

        def on_confirm(*args):
            try:
                symbol = symbol_input.text.strip().upper()
                quantity = float(quantity_input.text or 0)
                price_str = price_input.text.strip()
                price = float(price_str) if price_str else None

                if not symbol:
                    Snackbar(text="请输入交易对").open()
                    return
                if quantity <= 0:
                    Snackbar(text="数量必须大于0").open()
                    return

                self.execute_trade(symbol, side, quantity, price)
                if self.dialog:
                    self.dialog.dismiss()
            except ValueError:
                Snackbar(text="请输入有效的数字").open()

        self.dialog = MDDialog(
            title=f"{action_name} {side}",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="取消", on_release=lambda x: self.dialog.dismiss()),
                MDRaisedButton(text=action_name, on_release=on_confirm),
            ],
        )
        self.dialog.open()

    def execute_trade(self, symbol, side, quantity, price=None):
        """执行模拟交易"""
        # 获取当前价格（如果未指定）
        if price is None:
            try:
                resp = requests.get(
                    f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}",
                    timeout=10,
                )
                if resp.status_code == 200:
                    price = float(resp.json().get("price", 0))
            except Exception:
                price = 0

        if price <= 0:
            Snackbar(text="无法获取价格，请手动输入").open()
            return

        # 计算成本
        cost = price * quantity

        # 检查余额
        acct = _paper_trading_data["account"]
        if side == "LONG" and cost > acct["balance"]:
            Snackbar(text=f"余额不足，需要 ${cost:,.2f}").open()
            return

        # 创建持仓
        position = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "entry_price": price,
            "current_price": price,
            "pnl": 0.0,
            "opened_at": json.dumps({"timestamp": "now"}),
        }

        # 更新账户
        if side == "LONG":
            acct["balance"] -= cost
        acct["total_trades"] += 1
        acct["open_positions"] = len(_paper_trading_data["positions"]) + 1

        # 添加持仓
        _paper_trading_data["positions"].append(position)

        # 记录交易历史
        _paper_trading_data["trade_history"].append({
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "cost": cost,
            "action": "OPEN",
        })

        Snackbar(text=f"{side} {symbol} {quantity} @ ${price:,.2f}").open()
        self.load_account()
        self.load_positions()
