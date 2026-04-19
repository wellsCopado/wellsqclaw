"""
CryptoMind Pro Plus AI - 实时数据仪表盘
真实 API 数据展示，无任何模拟数据
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import flet as ft
from datetime import datetime

from core.utils.logger import logger
from core.data.collectors.spot.binance import BinanceSpotCollector
from core.data.collectors.derivatives import get_coinglass_collector
from core.data.storage import get_db


# ==================== 配色主题 ====================
class Theme:
    BG = "#0D1117"
    CARD_BG = "#161B22"
    BORDER = "#30363D"
    GREEN = "#3FB950"
    RED = "#F85149"
    YELLOW = "#D29922"
    BLUE = "#58A6FF"
    PURPLE = "#BC8CFF"
    TEXT = "#E6EDF3"
    TEXT_DIM = "#8B949E"
    ACCENT = "#7C3AED"


# ==================== 数据服务 ====================
class DataService:
    """数据服务 - 全部来自真实 API"""
    
    def __init__(self):
        self.binance = BinanceSpotCollector()
        self.coinglass = get_coinglass_collector()
        self.db = get_db()
        self._cache = {}
        self._cache_time = {}
        self._cache_ttl = 60  # 60秒缓存
    
    async def close(self):
        await self.binance.close()
        await self.coinglass.close()
    
    async def get_btc_price(self) -> dict:
        """获取 BTC 最新价格"""
        try:
            klines = await self.binance.get_klines("BTCUSDT", "1m", 5)
            if klines:
                latest = klines[-1]
                prev = klines[-2] if len(klines) > 1 else latest
                price = latest['close']
                prev_price = prev['close']
                change_pct = ((price - prev_price) / prev_price) * 100
                return {
                    "price": price,
                    "change_pct": change_pct,
                    "high": latest['high'],
                    "low": latest['low'],
                    "volume": latest['volume'],
                    "timestamp": latest['open_time'],
                }
        except Exception as e:
            logger.error(f"BTC价格获取失败: {e}")
        return {"price": 0, "change_pct": 0}
    
    async def get_derivatives_summary(self) -> dict:
        """获取衍生品综合数据"""
        try:
            # 并行请求
            funding_task = self.coinglass.get_funding_rate("BTC", "4h", 1)
            oi_task = self.coinglass.get_open_interest("BTC", "4h", 1)
            liq_task = self.coinglass.get_liquidation("BTC", 1)
            ls_task = self.coinglass.get_long_short_ratio("BTC", 1)
            
            funding_data, _ = await funding_task
            oi_data, _ = await oi_task
            liq_data = await liq_task
            ls_data = await ls_task
            
            result = {}
            
            if funding_data:
                fr = float(funding_data[-1].get('close', 0))
                result["funding_rate"] = fr
                result["funding_rate_str"] = f"{fr:.4f}%"
                result["funding_annual"] = fr * 3 * 365
            
            if oi_data:
                oi_usd = float(oi_data[-1].get('close', 0))
                result["open_interest"] = oi_usd
                result["open_interest_str"] = f"${oi_usd / 1e9:.2f}B"
            
            if liq_data:
                result["liq_total"] = liq_data.get('total_24h_usd', 0)
                result["liq_long"] = liq_data.get('long_24h_usd', 0)
                result["liq_short"] = liq_data.get('short_24h_usd', 0)
                result["liq_total_str"] = f"${liq_data.get('total_24h_usd', 0) / 1e6:.2f}M"
            
            if ls_data:
                result["long_pct"] = ls_data.get('long_percent', 0)
                result["short_pct"] = ls_data.get('short_percent', 0)
                result["ls_ratio"] = ls_data.get('long_short_ratio', 0)
            
            return result
        except Exception as e:
            logger.error(f"衍生品数据获取失败: {e}")
            return {}
    
    async def get_top_coins(self) -> list:
        """获取主流币种数据"""
        symbols = ["BTC", "ETH", "SOL", "BNB", "XRP"]
        results = []
        
        for sym in symbols:
            try:
                klines = await self.binance.get_klines(f"{sym}USDT", "1h", 2)
                if klines and len(klines) >= 2:
                    curr = klines[-1]['close']
                    prev = klines[-2]['close']
                    chg = ((curr - prev) / prev) * 100
                    results.append({
                        "symbol": sym,
                        "price": curr,
                        "change_pct": chg,
                    })
                await asyncio.sleep(0.2)
            except Exception as e:
                logger.error(f"{sym} 数据获取失败: {e}")
        
        return results
    
    async def get_funding_rate_history(self, days: int = 7) -> list:
        """获取资金费率历史"""
        data, _ = await self.coinglass.get_funding_rate("BTC", "4h", days)
        return data
    
    async def get_oi_history(self, days: int = 7) -> list:
        """获取持仓量历史"""
        data, _ = await self.coinglass.get_open_interest("BTC", "4h", days)
        return data


# ==================== UI 组件 ====================
def fmt_usd(val: float) -> str:
    if val >= 1e9:
        return f"${val / 1e9:.2f}B"
    elif val >= 1e6:
        return f"${val / 1e6:.2f}M"
    elif val >= 1e3:
        return f"${val / 1e3:.2f}K"
    return f"${val:.2f}"


def fmt_price(val: float) -> str:
    if val >= 1000:
        return f"${val:,.2f}"
    elif val >= 1:
        return f"${val:.4f}"
    else:
        return f"${val:.6f}"


def fmt_pct(val: float, show_sign: bool = True) -> str:
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.2f}%"


def make_card(content, width=None):
    return ft.Container(
        content=content,
        bgcolor=Theme.CARD_BG,
        border=ft.border.all(1, Theme.BORDER),
        border_radius=12,
        padding=16,
        width=width,
    )


def make_label(title, value, color=Theme.TEXT, size="titleMedium"):
    return ft.Column([
        ft.Text(title, color=Theme.TEXT_DIM, size="labelSmall"),
        ft.Text(value, color=color, size=size, weight=ft.FontWeight.BOLD),
    ])


# ==================== 主应用 ====================
async def main(page: ft.Page):
    page.title = "CryptoMind Pro Plus AI - 实时数据"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = Theme.BG
    page.padding = 20
    
    # 设置页面宽度
    page.window_width = 1400
    page.window_height = 900
    page.min_width = 1000
    page.min_height = 700
    
    # 数据服务
    ds = DataService()
    
    # ==================== 全局状态 ====================
    btc_price_ref = ft.Ref[ft.Text]()
    btc_change_ref = ft.Ref[ft.Text]()
    btc_high_ref = ft.Ref[ft.Text]()
    btc_low_ref = ft.Ref[ft.Text]()
    btc_volume_ref = ft.Ref[ft.Text]()
    
    fr_value_ref = ft.Ref[ft.Text]()
    fr_annual_ref = ft.Ref[ft.Text]()
    oi_value_ref = ft.Ref[ft.Text]()
    
    liq_total_ref = ft.Ref[ft.Text]()
    liq_long_ref = ft.Ref[ft.Text]()
    liq_short_ref = ft.Ref[ft.Text]()
    
    ls_long_ref = ft.Ref[ft.Text]()
    ls_short_ref = ft.Ref[ft.Text]()
    ls_ratio_ref = ft.Ref[ft.Text]()
    
    top_coins_ref = ft.Ref[ft.Column]()
    status_ref = ft.Ref[ft.Text]()
    refresh_btn_ref = ft.Ref[ft.ElevatedButton]()
    
    # 刷新指示器
    spinner_ref = ft.Ref[ft.ProgressRing]()
    
    # ==================== 数据刷新 ====================
    async def refresh_all(e=None):
        """刷新所有数据"""
        spinner_ref.current.visible = True
        refresh_btn_ref.current.disabled = True
        page.update()
        
        try:
            # BTC 价格
            btc = await ds.get_btc_price()
            if btc.get('price', 0) > 0:
                btc_price_ref.current.value = fmt_price(btc['price'])
                color = Theme.GREEN if btc['change_pct'] >= 0 else Theme.RED
                btc_change_ref.current.value = fmt_pct(btc['change_pct'])
                btc_change_ref.current.color = color
                btc_high_ref.current.value = fmt_price(btc['high'])
                btc_low_ref.current.value = fmt_price(btc['low'])
                btc_volume_ref.current.value = f"{btc['volume']:,.0f} BTC"
            
            # 衍生品数据
            deriv = await ds.get_derivatives_summary()
            
            if 'funding_rate' in deriv:
                fr = deriv['funding_rate']
                fr_value_ref.current.value = deriv.get('funding_rate_str', f"{fr:.4f}%")
                fr_value_ref.current.color = Theme.RED if fr > 0 else Theme.GREEN
                fr_annual_ref.current.value = fmt_pct(deriv.get('funding_annual', 0))
            
            if 'open_interest' in deriv:
                oi_ref = deriv['open_interest']
                oi_value_ref.current.value = deriv.get('open_interest_str', fmt_usd(oi_ref))
            
            if 'liq_total' in deriv:
                liq_total_ref.current.value = deriv.get('liq_total_str', fmt_usd(deriv['liq_total']))
                liq_long_ref.current.value = fmt_usd(deriv.get('liq_long', 0))
                liq_short_ref.current.value = fmt_usd(deriv.get('liq_short', 0))
            
            if 'long_pct' in deriv:
                ls_long_ref.current.value = f"{deriv['long_pct']:.1f}%"
                ls_short_ref.current.value = f"{deriv['short_pct']:.1f}%"
                ls_ratio_ref.current.value = f"{deriv['ls_ratio']:.2f}"
            
            # 主流币种
            coins = await ds.get_top_coins()
            top_coins_ref.current.controls.clear()
            for c in coins:
                color = Theme.GREEN if c['change_pct'] >= 0 else Theme.RED
                top_coins_ref.current.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Text(c['symbol'], width=60, color=Theme.TEXT, weight=ft.FontWeight.BOLD),
                            ft.Text(fmt_price(c['price']), expand=True, color=Theme.TEXT),
                            ft.Text(fmt_pct(c['change_pct']), color=color, weight=ft.FontWeight.BOLD),
                        ], spacing=10),
                        bgcolor=Theme.BG,
                        border_radius=8,
                        padding=10,
                    )
                )
            
            status_ref.current.value = f"✅ 数据更新: {datetime.now().strftime('%H:%M:%S')}"
            status_ref.current.color = Theme.GREEN
            
        except Exception as e:
            status_ref.current.value = f"❌ 错误: {str(e)[:50]}"
            status_ref.current.color = Theme.RED
            logger.error(f"刷新失败: {e}")
        
        finally:
            spinner_ref.current.visible = False
            refresh_btn_ref.current.disabled = False
            page.update()
    
    # ==================== 布局 ====================
    
    # 顶部标题栏
    header = ft.Container(
        content=ft.Row([
            ft.Column([
                ft.Text("CryptoMind Pro Plus AI", size=22, weight=ft.FontWeight.BOLD, color=Theme.TEXT),
                ft.Text("全维度智能自进化数字货币分析系统", size=12, color=Theme.TEXT_DIM),
            ]),
            ft.Container(expand=True),
            ft.ProgressRing(ref=spinner_ref, width=20, height=20, visible=False),
            ft.ElevatedButton(
                ref=refresh_btn_ref,
                text="🔄 刷新数据",
                on_click=refresh_all,
                bgcolor=Theme.ACCENT,
                color=ft.WHITE,
            ),
            ft.Container(width=10),
            ft.Text(ref=status_ref, value="⏳ 准备就绪", color=Theme.TEXT_DIM, size=12),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        padding=15,
        bgcolor=Theme.CARD_BG,
        border_radius=12,
        margin=ft.margin.only(bottom=15),
    )
    
    # ==================== 第一行: BTC 价格卡片 ====================
    btc_card = make_card(ft.Column([
        ft.Row([
            ft.Text("BTC/USDT", size=20, weight=ft.FontWeight.BOLD, color=Theme.YELLOW),
            ft.Container(expand=True),
            ft.Text("Binance 现货", color=Theme.TEXT_DIM, size=11),
        ]),
        ft.Container(height=8),
        ft.Row([
            ft.Text(ref=btc_price_ref, value="加载中...", size=36, weight=ft.FontWeight.BOLD, color=Theme.TEXT),
            ft.Container(width=15),
            ft.Container(
                content=ft.Text(ref=btc_change_ref, value="--", size=20, weight=ft.FontWeight.BOLD),
                bgcolor=Theme.BG,
                border_radius=8,
                padding=ft.padding.only(left=10, right=10, top=5, bottom=5),
            ),
        ], alignment=ft.MainAxisAlignment.START),
        ft.Container(height=12),
        ft.Row([
            make_label("24h 高", "", color=Theme.GREEN),
            ft.Container(width=40),
            make_label("24h 低", "", color=Theme.RED),
            ft.Container(width=40),
            make_label("24h 成交量", ""),
        ]),
        ft.Container(height=5),
        ft.Row([
            ft.Text(ref=btc_high_ref, value="--", size=14, color=Theme.GREEN),
            ft.Container(width=40),
            ft.Text(ref=btc_low_ref, value="--", size=14, color=Theme.RED),
            ft.Container(width=40),
            ft.Text(ref=btc_volume_ref, value="--", size=14, color=Theme.TEXT_DIM),
        ]),
    ]))
    
    # ==================== 资金费率卡片 ====================
    fr_card = make_card(ft.Column([
        ft.Row([
            ft.Text("💰 资金费率", size=16, weight=ft.FontWeight.BOLD, color=Theme.TEXT),
            ft.Container(expand=True),
            ft.Text("Binance 永续", color=Theme.TEXT_DIM, size=11),
        ]),
        ft.Container(height=10),
        ft.Text(ref=fr_value_ref, value="--", size=32, weight=ft.FontWeight.BOLD, color=Theme.TEXT),
        ft.Text("当前费率", color=Theme.TEXT_DIM, size=11),
        ft.Container(height=15),
        ft.Row([
            ft.Column([
                ft.Text("年化估算", color=Theme.TEXT_DIM, size=11),
                ft.Text(ref=fr_annual_ref, value="--", size=18, weight=ft.FontWeight.BOLD, color=Theme.TEXT_DIM),
            ]),
        ]),
        ft.Container(height=10),
        ft.Container(
            content=ft.Text(
                "费率 > 0 → 多头支付资金费（偏多）\n费率 < 0 → 空头支付资金费（偏空）",
                size=10, color=Theme.TEXT_DIM
            ),
            bgcolor=Theme.BG,
            border_radius=8,
            padding=10,
        ),
    ]))
    
    # ==================== 持仓量卡片 ====================
    oi_card = make_card(ft.Column([
        ft.Row([
            ft.Text("📊 持仓量", size=16, weight=ft.FontWeight.BOLD, color=Theme.TEXT),
            ft.Container(expand=True),
            ft.Text("全市场 BTC", color=Theme.TEXT_DIM, size=11),
        ]),
        ft.Container(height=10),
        ft.Text(ref=oi_value_ref, value="--", size=32, weight=ft.FontWeight.BOLD, color=Theme.BLUE),
        ft.Text("总持仓量 USD", color=Theme.TEXT_DIM, size=11),
        ft.Container(height=10),
        ft.Container(
            content=ft.Text(
                "持仓量创历史新高 → 多空双方都在加仓\n持仓量下降 → 趋势可能反转",
                size=10, color=Theme.TEXT_DIM
            ),
            bgcolor=Theme.BG,
            border_radius=8,
            padding=10,
        ),
    ]))
    
    # ==================== 爆仓卡片 ====================
    liq_card = make_card(ft.Column([
        ft.Row([
            ft.Text("💥 24h 爆仓", size=16, weight=ft.FontWeight.BOLD, color=Theme.TEXT),
            ft.Container(expand=True),
        ]),
        ft.Container(height=8),
        ft.Text(ref=liq_total_ref, value="--", size=28, weight=ft.FontWeight.BOLD, color=Theme.RED),
        ft.Text("总爆仓金额", color=Theme.TEXT_DIM, size=11),
        ft.Container(height=12),
        ft.Row([
            ft.Column([
                ft.Text("多头爆仓", color=Theme.TEXT_DIM, size=11),
                ft.Text(ref=liq_long_ref, value="--", size=16, weight=ft.FontWeight.BOLD, color=Theme.GREEN),
            ], expand=True),
            ft.Column([
                ft.Text("空头爆仓", color=Theme.TEXT_DIM, size=11),
                ft.Text(ref=liq_short_ref, value="--", size=16, weight=ft.FontWeight.BOLD, color=Theme.RED),
            ], expand=True),
        ]),
    ]))
    
    # ==================== 多空比卡片 ====================
    ls_card = make_card(ft.Column([
        ft.Row([
            ft.Text("📈 多空比", size=16, weight=ft.FontWeight.BOLD, color=Theme.TEXT),
            ft.Container(expand=True),
            ft.Text("账户级别", color=Theme.TEXT_DIM, size=11),
        ]),
        ft.Container(height=10),
        ft.Text(ref=ls_ratio_ref, value="--", size=32, weight=ft.FontWeight.BOLD, color=Theme.PURPLE),
        ft.Text("多空比", color=Theme.TEXT_DIM, size=11),
        ft.Container(height=12),
        # 多空比例条
        ft.Column([
            ft.Row([
                ft.Text("多头", color=Theme.TEXT_DIM, size=11),
                ft.Container(expand=True),
                ft.Text(ref=ls_long_ref, value="--", size=12, color=Theme.GREEN, weight=ft.FontWeight.BOLD),
            ]),
            ft.Container(height=5),
            ft.Row([
                ft.Text("空头", color=Theme.TEXT_DIM, size=11),
                ft.Container(expand=True),
                ft.Text(ref=ls_short_ref, value="--", size=12, color=Theme.RED, weight=ft.FontWeight.BOLD),
            ]),
            ft.Container(height=5),
            ft.Container(
                content=ft.Row([
                    ft.Container(width=100, height=8, bgcolor=Theme.GREEN, border_radius=4),
                    ft.Container(width=100, height=8, bgcolor=Theme.RED, border_radius=4),
                ]),
            ),
        ]),
    ]))
    
    # ==================== 主流币种列表 ====================
    coins_card = make_card(ft.Column([
        ft.Text("主流币种行情", size=16, weight=ft.FontWeight.BOLD, color=Theme.TEXT),
        ft.Container(height=10),
        ft.Column(ref=top_coins_ref, spacing=5),
        ft.Container(height=5),
        ft.Text("每15分钟自动刷新", size=10, color=Theme.TEXT_DIM),
    ]))
    
    # ==================== 数据来源说明 ====================
    source_card = make_card(ft.Column([
        ft.Text("📡 数据来源", size=16, weight=ft.FontWeight.BOLD, color=Theme.TEXT),
        ft.Container(height=8),
        ft.Text("• Binance API - 现货K线、价格、成交量", size=11, color=Theme.TEXT_DIM),
        ft.Text("• Coinglass V4 API - 资金费率、持仓量、爆仓、多空比", size=11, color=Theme.TEXT_DIM),
        ft.Text("• OKX API - 备用数据源", size=11, color=Theme.TEXT_DIM),
        ft.Container(height=8),
        ft.Text("所有数据均为实时真实数据，无模拟。", size=11, color=Theme.GREEN),
        ft.Text(f"Coinglass Hobby Plan ($29/月) - 1118个币种 · 30个交易所", size=10, color=Theme.TEXT_DIM),
    ]))
    
    # ==================== 组装页面 ====================
    page.add(header)
    
    # 第一行: BTC 价格 + 衍生品指标
    page.add(
        ft.Row([
            ft.Container(content=btc_card, expand=2),
            ft.Container(width=12),
            ft.Container(content=fr_card, expand=1),
            ft.Container(width=12),
            ft.Container(content=oi_card, expand=1),
        ], spacing=0)
    )
    
    page.add(ft.Container(height=12))
    
    # 第二行: 爆仓 + 多空比 + 来源
    page.add(
        ft.Row([
            ft.Container(content=liq_card, expand=1),
            ft.Container(width=12),
            ft.Container(content=ls_card, expand=1),
            ft.Container(width=12),
            ft.Container(content=ft.Column([coins_card, ft.Container(height=12), source_card], spacing=0), expand=1),
        ], spacing=0)
    )
    
    # 首次加载
    page.on_mount = refresh_all
    
    # 自动刷新 - 每60秒
    def auto_refresh(e):
        asyncio.run(refresh_all())
    
    page.run_auto_refresh(interval=60, callback=auto_refresh)
    
    page.on_disconnect = lambda e: asyncio.run(ds.close())


ft.app(target=main)
