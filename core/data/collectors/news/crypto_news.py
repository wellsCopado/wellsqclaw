"""
加密货币新闻数据采集器
支持：RSS订阅源 + 新闻API + 关键词监控

免费数据源：
1. CryptoCompare News API
2. CoinGecko News
3. RSS 订阅源 (多个)
4. Twitter/X 关键词搜索 (可选)
"""
import asyncio
import aiohttp
import feedparser
import time
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass
from core.utils.logger import logger
from core.utils.helpers import safe_execute


@dataclass
class NewsItem:
    """新闻条目"""
    id: str
    title: str
    source: str
    url: str
    published: int        # unix timestamp
    summary: str
    sentiment: str        # positive / negative / neutral
    sentiment_score: float  # -1.0 to 1.0
    related_coins: list    # ["BTC", "ETH"]
    categories: list
    fetched_at: int = 0


class CryptoNewsCollector:
    """
    加密货币新闻采集器
    
    支持：
    - RSS 订阅源 (多个来源)
    - CryptoCompare API
    - 关键词过滤
    - 情感分析 (规则引擎)
    """
    
    # RSS 订阅源
    RSS_FEEDS = {
        "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "cointelegraph": "https://cointelegraph.com/rss",
        "theblock": "https://www.theblock.co/rss.xml",
        "decrypt": "https://decrypt.co/feed",
        "cryptonews": "https://cryptonews.com/news/feed/",
    }
    
    # 关键词映射
    SENTIMENT_KEYWORDS = {
        "positive": [
            "bullish", "buy", "surge", "rally", "soar", "gain", "growth",
            "partnership", "adoption", "upgrade", "approval", "launch",
            "positive", "breakout", "high", "record", "million", "billion",
            "上涨", "突破", "利好", "合作", "采用", "批准"
        ],
        "negative": [
            "bearish", "sell", "crash", "plunge", "drop", "fall", "loss",
            "hack", "scam", "ban", "regulation", "investigation",
            "collapse", "fraud", "warning", "risk", "selloff",
            "下跌", "暴跌", "利空", "监管", "黑客", "风险"
        ],
    }
    
    # 币种关键词
    COIN_KEYWORDS = {
        "BTC": ["bitcoin", "btc", "比特币", "satoshi"],
        "ETH": ["ethereum", "eth", "以太坊", "ether", "vitalik"],
        "BNB": ["binance coin", "bnb", "binance"],
        "SOL": ["solana", "sol"],
        "XRP": ["ripple", "xrp"],
        "ADA": ["cardano", "ada"],
        "DOGE": ["dogecoin", "doge", "马斯克", "musk", "elon"],
        "DOT": ["polkadot", "dot", "gavin wood"],
        "AVAX": ["avalanche", "avax"],
        "LINK": ["chainlink", "link"],
    }
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: dict[str, NewsItem] = {}
        self._last_fetch: dict[str, float] = {}
        self._cache_ttl = 300  # 5分钟缓存
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=20)
            )
        return self._session
    
    # ── 情感分析 ──
    def analyze_sentiment(self, text: str) -> tuple[str, float]:
        """
        规则引擎情感分析
        返回: (sentiment, score)
        """
        text_lower = text.lower()
        pos_count = sum(1 for kw in self.SENTIMENT_KEYWORDS["positive"] if kw in text_lower)
        neg_count = sum(1 for kw in self.SENTIMENT_KEYWORDS["negative"] if kw in text_lower)
        
        total = pos_count + neg_count
        if total == 0:
            return "neutral", 0.0
        
        score = (pos_count - neg_count) / total
        
        if score > 0.2:
            return "positive", round(score, 2)
        elif score < -0.2:
            return "negative", round(score, 2)
        else:
            return "neutral", round(score, 2)
    
    def detect_coins(self, text: str) -> list[str]:
        """从文本中检测相关币种"""
        text_lower = text.lower()
        detected = []
        for coin, keywords in self.COIN_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                detected.append(coin)
        return detected if detected else ["CRYPTO"]  # 通用加密货币
    
    # ── RSS 采集 ──
    async def _fetch_rss(self, name: str, url: str) -> list[NewsItem]:
        """采集单个 RSS 源"""
        try:
            session = await self._get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return []
                
                text = await resp.text()
            
            # 解析 RSS
            feed = feedparser.parse(text)
            items = []
            
            for entry in feed.entries[:20]:  # 每源最多20条
                try:
                    # 解析时间
                    published_ts = 0
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        published_ts = int(time.mktime(entry.published_parsed))
                    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                        published_ts = int(time.mktime(entry.updated_parsed))
                    
                    title = getattr(entry, "title", "")
                    summary = getattr(entry, "summary", "")[:200]
                    link = getattr(entry, "link", "")
                    
                    # 唯一ID
                    item_id = hashlib.md5(f"{link}{title}".encode()).hexdigest()[:16]
                    
                    # 情感分析
                    sentiment, score = self.analyze_sentiment(f"{title} {summary}")
                    
                    # 币种检测
                    coins = self.detect_coins(f"{title} {summary}")
                    
                    item = NewsItem(
                        id=item_id,
                        title=title[:200],
                        source=name,
                        url=link,
                        published=published_ts,
                        summary=summary,
                        sentiment=sentiment,
                        sentiment_score=score,
                        related_coins=coins,
                        categories=getattr(entry, "tags", []),
                        fetched_at=int(time.time()),
                    )
                    items.append(item)
                    
                except Exception as e:
                    logger.warning(f"解析 RSS 条目失败: {e}")
                    continue
            
            return items
            
        except Exception as e:
            logger.warning(f"RSS 采集失败 [{name}]: {e}")
            return []
    
    async def fetch_all_rss(self) -> list[NewsItem]:
        """采集所有 RSS 源"""
        logger.info(f"采集 {len(self.RSS_FEEDS)} 个 RSS 源...")
        
        tasks = [
            self._fetch_rss(name, url)
            for name, url in self.RSS_FEEDS.items()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_items = []
        for result in results:
            if isinstance(result, list):
                all_items.extend(result)
        
        # 去重
        seen_ids = set()
        unique_items = []
        for item in all_items:
            if item.id not in seen_ids:
                seen_ids.add(item.id)
                unique_items.append(item)
        
        # 按时间排序
        unique_items.sort(key=lambda x: x.published, reverse=True)
        
        logger.info(f"RSS 采集完成: {len(unique_items)} 条新闻")
        return unique_items
    
    # ── CryptoCompare 新闻 ──
    async def fetch_cryptocompare(self, categories: list = None, lang: str = "EN") -> list[NewsItem]:
        """
        使用 CryptoCompare 免费新闻 API
        https://min-api.cryptocompare.com/
        免费额度: 暂无 Key 限制
        """
        try:
            session = await self._get_session()
            
            if categories is None:
                categories = ["BTC", "ETH", " blockchain"]
            
            items = []
            for cat in categories[:5]:  # 最多5个分类
                url = f"https://min-api.cryptocompare.com/data/v2/news/?lang={lang}&categories={cat}"
                
                async with session.get(url) as resp:
                    if resp.status != 200:
                        continue
                    
                    data = await resp.json()
                    news_list = data.get("Data", [])
                    
                    for n in news_list[:10]:
                        published_ts = n.get("published_on", 0)
                        title = n.get("title", "")[:200]
                        summary = n.get("body", "")[:200]
                        
                        item_id = hashlib.md5(f"{n.get('id', '')}{title}".encode()).hexdigest()[:16]
                        
                        sentiment, score = self.analyze_sentiment(f"{title} {summary}")
                        coins = self.detect_coins(f"{title} {summary}")
                        
                        items.append(NewsItem(
                            id=item_id,
                            title=title,
                            source=n.get("source", ""),
                            url=n.get("url", ""),
                            published=published_ts,
                            summary=summary,
                            sentiment=sentiment,
                            sentiment_score=score,
                            related_coins=coins,
                            categories=[cat],
                            fetched_at=int(time.time()),
                        ))
            
            return items
            
        except Exception as e:
            logger.warning(f"CryptoCompare 采集失败: {e}")
            return []
    
    # ── 综合采集 ──
    async def get_latest_news(self, max_items: int = 50) -> list[NewsItem]:
        """
        综合采集最新新闻
        合并 RSS + CryptoCompare
        """
        logger.info("开始采集最新加密货币新闻...")
        
        rss_task = self.fetch_all_rss()
        cc_task = self.fetch_cryptocompare()
        
        rss_items, cc_items = await asyncio.gather(rss_task, cc_task)
        
        # 合并
        all_items = rss_items + cc_items
        
        # 去重
        seen_ids = set()
        unique_items = []
        for item in all_items:
            if item.id not in seen_ids:
                seen_ids.add(item.id)
                unique_items.append(item)
        
        # 排序
        unique_items.sort(key=lambda x: x.published, reverse=True)
        
        logger.info(f"新闻采集完成: {len(unique_items)} 条 (去重后)")
        return unique_items[:max_items]
    
    # ── 情感统计 ──
    def get_sentiment_summary(self, items: list[NewsItem]) -> dict:
        """获取情感统计摘要"""
        if not items:
            return {"positive": 0, "neutral": 0, "negative": 0, "total": 0}
        
        counts = {"positive": 0, "neutral": 0, "negative": 0}
        for item in items:
            counts[item.sentiment] = counts.get(item.sentiment, 0) + 1
        
        total = len(items)
        scores = [item.sentiment_score for item in items]
        
        return {
            "total": total,
            "positive": counts["positive"],
            "neutral": counts["neutral"],
            "negative": counts["negative"],
            "positive_pct": round(counts["positive"] / total * 100, 1),
            "negative_pct": round(counts["negative"] / total * 100, 1),
            "avg_sentiment_score": round(sum(scores) / len(scores), 3) if scores else 0,
            "bullish_articles": counts["positive"],
            "bearish_articles": counts["negative"],
        }
    
    # ── 按币种过滤 ──
    def filter_by_coin(self, items: list[NewsItem], coin: str) -> list[NewsItem]:
        """过滤指定币种相关新闻"""
        return [item for item in items if coin.upper() in item.related_coins]
    
    # ── 关键词搜索 ──
    @safe_execute(default=None)
    def search(self, items: list[NewsItem], keyword: str) -> list[NewsItem]:
        """关键词搜索新闻"""
        kw_lower = keyword.lower()
        return [
            item for item in items
            if kw_lower in item.title.lower() or kw_lower in item.summary.lower()
        ]
    
    async def get_market_sentiment(self) -> dict:
        """
        获取市场情绪数据
        综合新闻情感 + 币种分布
        """
        news = await self.get_latest_news(30)
        summary = self.get_sentiment_summary(news)
        
        # 币种分布
        coin_counts = {}
        for item in news:
            for coin in item.related_coins:
                coin_counts[coin] = coin_counts.get(coin, 0) + 1
        
        # 热门币种
        hot_coins = sorted(coin_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "summary": summary,
            "hot_coins": [{"coin": c, "count": n} for c, n in hot_coins],
            "latest_news": [
                {"title": n.title[:80], "source": n.source, "sentiment": n.sentiment, "coins": n.related_coins}
                for n in news[:10]
            ],
            "timestamp": int(time.time() * 1000),
        }
    
    @safe_execute(default=None)
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


def get_news_collector() -> CryptoNewsCollector:
    return CryptoNewsCollector()
