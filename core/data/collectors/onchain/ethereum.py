"""
Ethereum 链上数据采集器
使用公共 RPC 节点，无需 API Key

数据采集：
1. Gas 价格 (快/中/慢)
2. 大额转账 (鲸鱼追踪)
3. DEX 交易数据 (Uniswap)
4. 链上活跃度指标
"""
import asyncio
import aiohttp
import time
from typing import Optional, Any
from core.utils.logger import logger
from core.utils.helpers import safe_execute


# ─────────────────────────────────────────────────────────────
# 公共 RPC 节点 (免费，无需 API Key)
# ─────────────────────────────────────────────────────────────
ETHEREUM_RPC_ENDPOINTS = [
    "https://rpc.ankr.com/eth",
    "https://eth.llamarpc.com",
    "https://ethereum.publicnode.com",
    "https://eth.drpc.org",
]

# 备用 Bitcoin API
BITCOIN_API_ENDPOINTS = [
    "https://blockstream.info/api",
    "https://mempool.space/api",
]


# ─────────────────────────────────────────────────────────────
# Ethereum RPC 采集器
# ─────────────────────────────────────────────────────────────
class EthereumRPCCollector:
    """
    Ethereum 链上数据采集器
    
    使用免费公共 RPC 节点，支持：
    - Gas 价格实时监控
    - 大额 ETH 转账追踪
    - DEX 交易数据
    - 链上活跃度
    """
    
    def __init__(self, rpc_endpoints: list = None):
        self.endpoints = rpc_endpoints or ETHEREUM_RPC_ENDPOINTS
        self._active_endpoint: Optional[str] = None
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"Content-Type": "application/json"},
            )
        return self._session
    
    async def _find_working_endpoint(self) -> str:
        """找到可用的 RPC 节点"""
        for endpoint in self.endpoints:
            try:
                session = await self._get_session()
                payload = {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}
                async with session.post(endpoint, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("result"):
                            block = int(data["result"], 16)
                            self._active_endpoint = endpoint
                            logger.info(f"Ethereum RPC: {endpoint[:40]}... (区块 #{block})")
                            return endpoint
            except Exception:
                continue
        raise RuntimeError("所有 Ethereum RPC 节点均不可用")
    
    async def _rpc_call(self, method: str, params: list = None) -> Any:
        """通用 RPC 调用，支持限流降级"""
        errors = []
        for endpoint in self.endpoints:
            try:
                session = await self._get_session()
                payload = {"jsonrpc": "2.0", "method": method, "params": params or [], "id": 1}
                async with session.post(endpoint, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 429:
                        errors.append(f"429 on {endpoint[:30]}...")
                        continue  # 限流，尝试下一个节点
                    if resp.status != 200:
                        errors.append(f"HTTP {resp.status} on {endpoint[:30]}")
                        continue
                    data = await resp.json()
                    if "error" in data:
                        errors.append(str(data["error"]))
                        continue
                    self._active_endpoint = endpoint
                    return data.get("result")
            except asyncio.TimeoutError:
                errors.append(f"Timeout on {endpoint[:30]}")
                continue
            except Exception as e:
                errors.append(f"{type(e).__name__} on {endpoint[:30]}: {e}")
                continue
        raise RuntimeError(f"所有 RPC 节点均失败: {errors[-1] if errors else 'unknown'}")
    
    async def get_latest_block(self) -> dict:
        """获取最新区块信息"""
        try:
            block_number_hex = await self._rpc_call("eth_blockNumber")
            block_number = int(block_number_hex, 16)
            block_data = await self._rpc_call("eth_getBlockByNumber", [block_number_hex, False])
            return {
                "block_number": block_number,
                "hash": block_data.get("hash", ""),
                "timestamp": int(block_data.get("timestamp", "0x0"), 16),
                "tx_count": len(block_data.get("transactions", [])),
                "gas_limit": int(block_data.get("gasLimit", "0x0"), 16),
                "gas_used": int(block_data.get("gasUsed", "0x0"), 16),
                "gas_utilization_pct": round(
                    int(block_data.get("gasUsed", "0x0"), 16) /
                    int(block_data.get("gasLimit", "0x1"), 16) * 100, 1
                ),
            }
        except Exception as e:
            logger.error(f"获取区块信息失败: {e}")
            return {}
    
    async def get_gas_price(self) -> dict:
        """
        获取实时 Gas 价格
        Low/Medium/High 三档 + 网络利用率
        """
        try:
            gas_hex = await self._rpc_call("eth_gasPrice")
            current_gas = int(gas_hex, 16)  # wei
            current_gwei = current_gas / 1e9
            
            block_number_hex = await self._rpc_call("eth_blockNumber")
            block_data = await self._rpc_call("eth_getBlockByNumber", [block_number_hex, False])
            gas_limit = int(block_data.get("gasLimit", "0x1"), 16)
            gas_used = int(block_data.get("gasUsed", "0x0"), 16)
            utilization = gas_used / gas_limit if gas_limit > 0 else 0
            
            # 三档估算
            return {
                "low_gwei": round(current_gwei * 0.8, 2),
                "medium_gwei": round(current_gwei * (1 + utilization * 0.5), 2),
                "high_gwei": round(current_gwei * (1 + utilization) * 1.2, 2),
                "current_gwei": round(current_gwei, 2),
                "gas_utilization_pct": round(utilization * 100, 1),
                "time_low": "~10分钟" if current_gwei > 30 else "~5分钟",
                "time_medium": "~3分钟",
                "time_high": "~30秒",
                "timestamp": int(time.time() * 1000),
            }
        except Exception as e:
            logger.error(f"获取 Gas 价格失败: {e}")
            return {}
    
    async def get_network_stats(self) -> dict:
        """获取网络活跃度统计"""
        try:
            block_number_hex = await self._rpc_call("eth_blockNumber")
            block_number = int(block_number_hex, 16)
            block_data = await self._rpc_call("eth_getBlockByNumber", [block_number_hex, False])
            
            recent_txs = 0
            for i in range(10):
                try:
                    past = await self._rpc_call("eth_getBlockByNumber", [hex(block_number - i), False])
                    recent_txs += len(past.get("transactions", []))
                except Exception:
                    pass
            
            gas_price = int((await self._rpc_call("eth_gasPrice") or "0x0"), 16)
            gas_used = int(block_data.get("gasUsed", "0x0"), 16)
            gas_limit = int(block_data.get("gasLimit", "0x1"), 16)
            
            return {
                "latest_block": block_number,
                "block_timestamp": int(block_data.get("timestamp", "0x0"), 16),
                "txs_in_block": len(block_data.get("transactions", [])),
                "avg_txs_per_block_10": round(recent_txs / 10, 1),
                "current_gas_gwei": round(gas_price / 1e9, 2),
                "network_utilization_pct": round(gas_used / gas_limit * 100, 1) if gas_limit > 0 else 0,
            }
        except Exception as e:
            logger.error(f"获取网络统计失败: {e}")
            return {}
    
    async def get_balance(self, address: str) -> dict:
        """获取 ETH 地址余额"""
        try:
            balance_hex = await self._rpc_call("eth_getBalance", [address, "latest"])
            balance_wei = int(balance_hex or "0x0", 16)
            balance_eth = balance_wei / 1e18
            return {
                "address": address,
                "balance_wei": balance_wei,
                "balance_eth": round(balance_eth, 6),
                "balance_usd_approx": round(balance_eth * 3200, 2),
            }
        except Exception as e:
            logger.error(f"获取余额失败: {e}")
            return {}
    
    async def get_large_transfers(self, min_value_eth: float = 1000) -> list:
        """追踪大额 ETH 转账（鲸鱼追踪）"""
        WHALE_ADDRESSES = {
            "0x28C6c06298d514Db089934071355E5743bf21d60": "Binance Hot",
            "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance Cold",
            "0x56EDdb7aa8756c09E9Fd78350C47b2E3706dE56b": "Binance",
            "0xA9D1e08C7793af67e9d92fe308d5697FB81d3E43": "Coinbase",
            "0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8": "Binance",
        }
        
        large_transfers = []
        for addr, label in WHALE_ADDRESSES.items():
            try:
                balance = await self.get_balance(addr)
                balance_eth = balance.get("balance_eth", 0)
                if balance_eth >= min_value_eth:
                    large_transfers.append({
                        "address": addr,
                        "label": label,
                        "balance_eth": round(balance_eth, 2),
                        "balance_usd": balance.get("balance_usd_approx", 0),
                    })
            except Exception:
                pass
        
        return sorted(large_transfers, key=lambda x: x["balance_eth"], reverse=True)
    
    async def get_uniswap_stats(self) -> dict:
        """获取 Uniswap V3 概览数据（The Graph）"""
        try:
            session = await self._get_session()
            query = {
                "query": """
                {
                    uniswapDayDatas(first: 1, orderBy: date, orderDirection: desc) {
                        date
                        volumeUSD
                        tvlUSD
                        txCount
                    }
                    factory(id: "0x1F98431c8aD98523631AE4a59f267346ea31F984") {
                        totalVolumeUSD
                        totalLiquidityUSD
                    }
                }
                """
            }
            async with session.post(
                "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3",
                json=query,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if "data" in data:
                        day = (data["data"].get("uniswapDayDatas") or [{}])[0]
                        fac = data["data"].get("factory") or {}
                        return {
                            "volume_24h_usd": float(day.get("volumeUSD") or 0),
                            "tvl_usd": float(day.get("tvlUSD") or 0),
                            "tx_count_24h": int(day.get("txCount") or 0),
                            "total_volume_usd": float(fac.get("totalVolumeUSD") or 0),
                            "total_tvl_usd": float(fac.get("totalLiquidityUSD") or 0),
                        }
            return {}
        except Exception as e:
            logger.warning(f"Uniswap 数据失败: {e}")
            return {}
    
    async def get_full_onchain_data(self) -> dict:
        """获取综合 Ethereum 链上数据"""
        logger.info("开始采集 Ethereum 链上数据...")
        gas, stats, whales, dex = await asyncio.gather(
            self.get_gas_price(),
            self.get_network_stats(),
            self.get_large_transfers(1000),
            self.get_uniswap_stats(),
            return_exceptions=True
        )
        results = {
            "gas": gas if not isinstance(gas, Exception) else {},
            "network": stats if not isinstance(stats, Exception) else {},
            "whales": whales if not isinstance(whales, Exception) else [],
            "dex": dex if not isinstance(dex, Exception) else {},
            "timestamp": int(time.time() * 1000),
        }
        success = sum(1 for v in [gas, stats, whales, dex] if not isinstance(v, Exception))
        logger.info(f"Ethereum 链上完成: {success}/4")
        return results
    
    @safe_execute(default=None)
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


# ─────────────────────────────────────────────────────────────
# Bitcoin 链上采集器
# ─────────────────────────────────────────────────────────────
class BitcoinRPCCollector:
    """
    Bitcoin 链上数据采集器
    
    使用 Blockstream 公共 API (免费)
    """
    
    def __init__(self, api_base: str = "https://blockstream.info/api"):
        self.api_base = api_base
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20))
        return self._session
    
    async def get_latest_blocks(self, count: int = 10) -> list:
        try:
            session = await self._get_session()
            async with session.get(f"{self.api_base}/blocks", params={"limit": count}) as resp:
                if resp.status == 200:
                    return await resp.json()
                return []
        except Exception as e:
            logger.error(f"获取 BTC 区块失败: {e}")
            return []
    
    async def get_mempool_stats(self) -> dict:
        try:
            session = await self._get_session()
            async with session.get(f"{self.api_base}/mempool") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "tx_count": data.get("count", 0),
                        "vsize_mb": round(data.get("vsize", 0) / 1e6, 2),
                        "total_fee_btc": round(data.get("total_fee", 0) / 1e8, 4),
                    }
                return {}
        except Exception as e:
            logger.error(f"获取 Mempool 失败: {e}")
            return {}
    
    async def get_large_btc_transfers(self, min_btc: float = 500) -> list:
        """追踪大额 BTC 转账"""
        try:
            session = await self._get_session()
            blocks = await self.get_latest_blocks(2)
            large_txs = []
            
            for block in blocks[:2]:
                block_hash = block.get("id", "")
                async with session.get(f"{self.api_base}/block/{block_hash}/txids") as resp:
                    if resp.status == 200:
                        txids = await resp.json()
                        for txid in txids[:15]:
                            async with session.get(f"{self.api_base}/tx/{txid}") as tx_resp:
                                if tx_resp.status == 200:
                                    tx = await tx_resp.json()
                                    total_out = sum(o.get("value", 0) for o in tx.get("vout", [])) / 1e8
                                    if total_out >= min_btc:
                                        large_txs.append({
                                            "txid": txid,
                                            "total_btc": round(total_out, 2),
                                            "fee_btc": round(tx.get("fee", 0) / 1e8, 6),
                                            "block_height": block.get("height"),
                                        })
            
            return sorted(large_txs, key=lambda x: x["total_btc"], reverse=True)
        except Exception as e:
            logger.error(f"追踪 BTC 大额转账失败: {e}")
            return []
    
    async def get_network_difficulty(self) -> dict:
        try:
            blocks = await self.get_latest_blocks(1)
            if not blocks:
                return {}
            latest = blocks[0]
            return {
                "difficulty": latest.get("difficulty", 0),
                "timestamp": latest.get("timestamp"),
                "block_height": latest.get("height"),
                "tx_count": latest.get("tx_count", 0),
            }
        except Exception as e:
            logger.error(f"获取 BTC 网络数据失败: {e}")
            return {}
    
    async def get_full_onchain_data(self) -> dict:
        """获取综合 Bitcoin 链上数据"""
        logger.info("开始采集 Bitcoin 链上数据...")
        mempool, difficulty, large_txs = await asyncio.gather(
            self.get_mempool_stats(),
            self.get_network_difficulty(),
            self.get_large_btc_transfers(500),
            return_exceptions=True
        )
        results = {
            "mempool": mempool if not isinstance(mempool, Exception) else {},
            "network": difficulty if not isinstance(difficulty, Exception) else {},
            "large_transfers": large_txs if not isinstance(large_txs, Exception) else [],
            "timestamp": int(time.time() * 1000),
        }
        success = sum(1 for v in [mempool, difficulty, large_txs] if not isinstance(v, Exception))
        logger.info(f"Bitcoin 链上完成: {success}/3")
        return results
    
    @safe_execute(default=None)
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


# ─────────────────────────────────────────────────────────────
# 工厂函数
# ─────────────────────────────────────────────────────────────
def get_ethereum_collector() -> EthereumRPCCollector:
    return EthereumRPCCollector()


def get_bitcoin_collector() -> BitcoinRPCCollector:
    return BitcoinRPCCollector()


def get_onchain_collector(chain: str) -> Any:
    collectors = {
        "ethereum": EthereumRPCCollector,
        "eth": EthereumRPCCollector,
        "bitcoin": BitcoinRPCCollector,
        "btc": BitcoinRPCCollector,
    }
    cls = collectors.get(chain.lower())
    if cls:
        return cls()
    raise ValueError(f"不支持的链: {chain}")
