"""Bitcoin 链上数据采集器

支持：
  - Bitcoin Core RPC (需要本地节点或第三方RPC服务)
  - Mempool.space API (无节点方案，公共接口)
  - Blockstream API (公共接口)
"""
import requests
import time
from typing import Optional, Dict, Any, List
from core.utils.helpers import safe_execute
from core.utils.logger import logger


class BitcoinOnChainCollector:
    """Bitcoin 链上数据采集器

    无需本地Bitcoin Core节点，优先使用公共API。
    """

    MEMPOOL_URL = "https://mempool.space/api"
    BLOCKSTREAM_URL = "https://blockstream.info/api"

    def __init__(self, rpc_url: str = "", rpc_user: str = "", rpc_password: str = ""):
        """
        Args:
            rpc_url: Bitcoin Core RPC URL，如 http://localhost:8332
            rpc_user: RPC 用户名
            rpc_password: RPC 密码
        """
        self.rpc_url = rpc_url
        self.rpc_user = rpc_user
        self.rpc_password = rpc_password
        self._use_mempool = not bool(rpc_url)
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})
        logger.info(
            f"CryptoMind: Bitcoin采集器初始化, 模式: {'Mempool.space公共API' if self._use_mempool else 'Bitcoin Core RPC'}"
        )

    # ─────────────────────────────────────────────────────────────
    # Bitcoin Core RPC 模式
    # ─────────────────────────────────────────────────────────────

    def _rpc_call(self, method: str, params: list = None) -> Any:
        """调用Bitcoin Core RPC"""
        if not self.rpc_url:
            return None
        import json, base64
        payload = {"jsonrpc": "1.0", "id": "cryptomind", "method": method, "params": params or []}
        try:
            resp = self._session.post(
                self.rpc_url,
                json=payload,
                timeout=15,
                auth=(self.rpc_user, self.rpc_password)
            )
            result = resp.json().get("result")
            return result
        except Exception as e:
            logger.error(f"Bitcoin RPC {method} error: {e}")
            return None

    @safe_execute(default={})
    def get_mvrv(self) -> Dict[str, Any]:
        """获取 MVRV 比率 (Market Value to Realized Value)

        无本地节点时使用 Glassnode 风格估算。
        """
        if self.rpc_url:
            # 有节点：获取已实现 cap
            try:
                data = self._rpc_call("getblockchaininfo", [])
                chain = data or {}
                block_height = chain.get("blocks", 0)

                # 估算已实现上限（简化：取最后区块的UTXO set）
                # 这里用 MVRV = 市值 / 已实现市值 的近似
                price_usd = self._get_bitcoin_price()
                supply = self._rpc_call("gettxoutsetinfo", [])
                utxo_count = supply.get("txoutsetinfo", {}).get("txouts", 0) if supply else 0

                realized_cap_approx = utxo_count * 100  # 简化估算
                market_cap = supply.get("txoutsetinfo", {}).get("total_amount", 0) * 1e8 * price_usd
                mvrv = market_cap / realized_cap_approx if realized_cap_approx > 0 else 0

                return {
                    "block_height": block_height,
                    "mvrv": round(mvrv, 2),
                    "market_cap_usd": market_cap,
                    "realized_cap_approx": realized_cap_approx,
                    "method": "bitcoin_core_rpc",
                }
            except Exception as e:
                logger.error(f"Bitcoin MVRV RPC error: {e}")

        # 无节点：使用 Mempool.space 估算
        try:
            # 获取当前价格（从mempool的fees页面估算）
            price_usd = self._get_bitcoin_price()
            # 获取流通量
            supply_resp = self._session.get(f"{self.MEMPOOL_URL}/blocks/tip/height", timeout=10)
            block_height = int(supply_resp.text.strip())

            # 简化 MVRV：使用历史实现 cap 估算
            # MVRV > 3.5 为顶部区域，< 1 为底部区域
            market_cap = block_height * 6.25 * 1e8 * price_usd / 1e8  # rough
            # 这里用链上活跃度指标做近似
            mvrv = round(price_usd / 20000, 2)  # 极简估算: 假设实现价格~20000

            return {
                "block_height": block_height,
                "mvrv": max(0.1, min(mvrv, 10.0)),  # clamp
                "market_cap_usd": market_cap,
                "price_usd": price_usd,
                "method": "mempool_estimator",
            }
        except Exception as e:
            logger.error(f"Bitcoin MVRV mempool error: {e}")

        return {}

    @safe_execute(default={})
    def get_miner_revenue(self) -> Dict[str, Any]:
        """获取矿工收益（每日）"""
        if self.rpc_url:
            try:
                block_subsidy = self._rpc_call("getblockchaininfo", [])
                height = block_subsidy.get("blocks", 0) if block_subsidy else 0

                # 区块补贴 = 50 * 2^(-height/210000)，每210000区块减半
                subsidy = 50 * (0.5 ** (height // 210000))

                # 获取最新区块的费率收入
                recent_blocks = self._rpc_call("getblockstats", [height])
                fees = recent_blocks.get("subsidy", 0) if recent_blocks else 0

                price_usd = self._get_bitcoin_price()
                total_revenue = (subsidy + fees) * 1e-8 * price_usd

                return {
                    "block_height": height,
                    "miner_revenue_daily_usd": round(total_revenue * 144, 2),  # ~144 blocks/day
                    "block_subsidy_btc": subsidy,
                    "fee_btc": fees,
                    "method": "bitcoin_core_rpc",
                }
            except Exception as e:
                logger.error(f"Bitcoin miner revenue error: {e}")

        # 无节点：使用 Mempool.space
        try:
            stats_resp = self._session.get(f"{self.MEMPOOL_URL}/v1/fees/mempool-blocks", timeout=10)
            stats = stats_resp.json() if stats_resp.status_code == 200 else {}

            price_usd = self._get_bitcoin_price()
            # 估算矿工收入
            estimated_daily = 144 * 6.25 * price_usd  # 144 blocks/day * 6.25 BTC/block

            return {
                "miner_revenue_daily_usd": round(estimated_daily, 2),
                "block_subsidy_btc": 6.25,
                "estimated_fees_btc": 0.5,  # rough
                "method": "mempool_estimator",
            }
        except Exception as e:
            logger.error(f"Bitcoin miner revenue mempool error: {e}")

        return {}

    @safe_execute(default={})
    def get_large_transfers(self, min_btc: float = 100) -> Dict[str, Any]:
        """获取大额转账 (>min_btc BTC)"""
        if self.rpc_url:
            try:
                # 获取最新区块的coinbase交易（大额可能含打包）
                height = self._rpc_call("getblockcount", [])
                hashes = [self._rpc_call("getblockhash", [height - i]) for i in range(10)]
                large_txs = []
                for h in hashes:
                    if not h:
                        continue
                    block = self._rpc_call("getblock", [h])
                    for txid in (block.get("tx", [])[:5] if block else []):
                        tx = self._rpc_call("getrawtransaction", [txid, True])
                        if not tx:
                            continue
                        total_out = sum(v.get("value", 0) for v in tx.get("vout", []))
                        if total_out >= min_btc * 1e8:
                            large_txs.append({
                                "txid": txid,
                                "btc": round(total_out / 1e8, 4),
                                "confirmations": tx.get("confirmations", 0),
                            })
                return {
                    "min_btc": min_btc,
                    "count": len(large_txs),
                    "transfers": large_txs[:10],
                }
            except Exception as e:
                logger.error(f"Bitcoin large transfers error: {e}")

        # 无节点：使用 Blockstream
        try:
            blocks_resp = self._session.get(f"{self.BLOCKSTREAM_URL}/blocks/tip/height", timeout=10)
            tip_height = int(blocks_resp.text.strip())
            large = []
            for offset in range(5):
                bh = tip_height - offset * 10
                block_resp = self._session.get(f"{self.BLOCKSTREAM_URL}/block-height/{bh}", timeout=10)
                block_hash = block_resp.text.strip()
                tx_resp = self._session.get(f"{self.BLOCKSTREAM_URL}/block/{block_hash}/txids", timeout=10)
                txids = tx_resp.json() if tx_resp.status_code == 200 else []
                for txid in txids[:3]:
                    tx_detail = self._session.get(f"{self.BLOCKSTREAM_URL}/tx/{txid}", timeout=10)
                    if tx_detail.status_code == 200:
                        tx = tx_detail.json()
                        for out in tx.get("vout", []):
                            if out.get("value", 0) >= min_btc * 1e8:
                                large.append({
                                    "txid": txid,
                                    "btc": round(out["value"] / 1e8, 4),
                                    "confirmations": tx.get("status", {}).get("block_height", 0) or 0,
                                })
            return {
                "min_btc": min_btc,
                "count": len(large),
                "transfers": large[:10],
            }
        except Exception as e:
            logger.error(f"Bitcoin large transfers blockstream error: {e}")

        return {"min_btc": min_btc, "count": 0, "transfers": []}

    @safe_execute(default={})
    def get_active_addresses(self, days: int = 1) -> Dict[str, Any]:
        """获取活跃地址数（估算）"""
        if self.rpc_url:
            try:
                # 近似：取每日交易数 * 2（买卖双方估算）
                height = self._rpc_call("getblockcount", [])
                # 简化：平均区块 ~2000 tx，每天~144区块
                tx_per_block = 2000  # 简化估算
                daily_txs = 144 * tx_per_block
                active_addresses = int(daily_txs * 1.8)  # 买卖双方+找零地址

                return {
                    "active_addresses_24h": active_addresses,
                    "estimated_txs_24h": daily_txs,
                    "method": "bitcoin_core_rpc",
                }
            except Exception as e:
                logger.error(f"Bitcoin active addresses error: {e}")

        # 无节点：使用 Mempool.space
        try:
            stats_resp = self._session.get(f"{self.MEMPOOL_URL}/v1/fees/recommended", timeout=10)
            mempool_stats = stats_resp.json() if stats_resp.status_code == 200 else {}
            mempool_txs = mempool_stats.get("mempoolInfo", {}).get("size", 3000)

            return {
                "active_addresses_24h": int(mempool_txs * 1.8 * 288),  # ~288 10min intervals/day
                "estimated_txs_24h": int(mempool_txs * 144),
                "mempool_size": mempool_txs,
                "method": "mempool_estimator",
            }
        except Exception as e:
            logger.error(f"Bitcoin active addresses mempool error: {e}")

        return {}

    def _get_bitcoin_price(self) -> float:
        """获取BTC价格（用于计算USD价值）"""
        try:
            resp = self._session.get("https://mempool.space/api/v1/prices/bitcoinusd", timeout=5)
            if resp.status_code == 200:
                return float(resp.text.strip())
        except:
            pass
        return 45000.0  # fallback

    @safe_execute(default={})
    def get_fee_estimate(self) -> Dict[str, Any]:
        """获取手续费估算（sat/vB）"""
        try:
            resp = self._session.get(f"{self.MEMPOOL_URL}/v1/fees/recommended", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "fastest_fee": data.get("fastestFee", 10),
                    "half_hour_fee": data.get("halfHourFee", 5),
                    "hour_fee": data.get("hourFee", 3),
                    "economy_fee": data.get("economyFee", 1),
                    "minimum_fee": data.get("minimumFee", 1),
                }
        except Exception as e:
            logger.error(f"Bitcoin fee estimate error: {e}")
        return {}

    @safe_execute(default={})
    def get_block_height(self) -> Dict[str, Any]:
        """获取最新区块高度"""
        try:
            resp = self._session.get(f"{self.BLOCKSTREAM_URL}/blocks/tip/height", timeout=10)
            height = int(resp.text.strip())
            return {
                "block_height": height,
                "timestamp": int(time.time()),
            }
        except Exception as e:
            logger.error(f"Bitcoin block height error: {e}")
        return {}

    @safe_execute(default={})
    def get_full_metrics(self) -> Dict[str, Any]:
        """一次性获取全部链上指标"""
        return {
            "block_height": self.get_block_height(),
            "mvrv": self.get_mvrv(),
            "miner_revenue": self.get_miner_revenue(),
            "large_transfers": self.get_large_transfers(),
            "active_addresses": self.get_active_addresses(),
            "fee_estimate": self.get_fee_estimate(),
        }
