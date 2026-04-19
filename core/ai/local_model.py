"""
AI 分析引擎 - 本地 Gemma 3 4B + 云端 API 双轨推理
支持 Ollama / llama.cpp / OpenAI 兼容 API
"""
import asyncio
import json
import os
from typing import Optional, Dict
from dataclasses import dataclass
from core.utils.logger import logger
from core.utils.helpers import safe_execute
# config.settings 暂时未使用，直接使用环境变量


@dataclass
class AIAnalysis:
    """AI 分析结果"""
    symbol: str
    model: str
    signal: str
    confidence: float
    reasoning: str
    market_state: str
    risk_warning: str
    recommendation: str
    timestamp: int


class LocalModelClient:
    """本地模型客户端 (Ollama / llama.cpp server)"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.environ.get(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        )
        self.model = "gemma3:4b"
        self._available = None
    
    async def is_available(self) -> bool:
        """检测模型是否可用"""
        if self._available is not None:
            return self._available
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=3)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models = data.get('models', [])
                        model_names = [m.get('name', '') for m in models]
                        self._available = self.model in model_names
                        if self._available:
                            logger.info(f"✅ 本地模型可用: {self.model}")
                        else:
                            logger.warning(f"⚠️ Ollama运行中但未找到 {self.model}, 可用: {model_names}")
                    else:
                        self._available = False
        except Exception as e:
            self._available = False
            logger.debug(f"本地模型不可用: {e}")
        
        return self._available
    
    @safe_execute(default=None)
    async def chat(self, prompt: str, max_tokens: int = 512) -> Optional[str]:
        """发送聊天请求"""
        try:
            import aiohttp
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"num_predict": max_tokens, "temperature": 0.3},
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get('message', {}).get('content', '')
                    else:
                        text = await resp.text()
                        logger.error(f"模型响应错误 {resp.status}: {text[:200]}")
                        return None
        except Exception as e:
            logger.error(f"模型请求失败: {e}")
            return None


class AIAnalyzer:
    """
    AI 分析引擎
    优先级: 本地 Gemma 3 4B > 云端 API > 规则引擎
    """
    
    SYSTEM_PROMPT = """你是一位专业的数字货币量化分析师，专注于BTC、ETH等主流币种的技术和衍生品数据分析。
你的分析基于以下真实市场数据（来自Coinglass和Binance）：
- 资金费率 (Funding Rate): >0意味着多头支付给空头，<0意味着空头支付给多头
- 持仓量 (Open Interest): 双方总持仓金额，上升意味着趋势可能延续
- 爆仓 (Liquidation): 24h爆仓金额及多空比例
- 多空比 (Long/Short Ratio): >1意味着多头主导，<1意味着空头主导

请用JSON格式回复，包含以下字段：
- signal: STRONG_BUY / BUY / NEUTRAL / SELL / STRONG_SELL
- confidence: 0-100的置信度
- reasoning: 30字以内的中文推理过程
- market_state: 当前市场状态描述
- risk_warning: 风险提示（如有）
- recommendation: 具体操作建议"""

    def __init__(self):
        self.local_model = LocalModelClient()
        self._use_local = True  # 默认优先本地模型
    
    @safe_execute(default=None)
    async def analyze(self, analysis_result, btc_data: dict, deriv_data: dict) -> AIAnalysis:
        """
        AI 综合分析
        接收信号分析结果 + 原始数据
        """
        # 构建分析 prompt
        prompt = self._build_prompt(analysis_result, btc_data, deriv_data)
        
        # 尝试本地模型
        if await self.local_model.is_available():
            response = await self.local_model.chat(prompt)
            if response:
                return self._parse_response(response, "local_gemma3_4b")
        
        # 本地不可用 → 使用规则引擎（基于信号分析结果）
        logger.warning("本地模型不可用，使用规则引擎分析")
        return self._rule_based_analysis(analysis_result, btc_data, deriv_data)
    
    def _build_prompt(self, signal_result, btc_data: dict, deriv_data: dict) -> str:
        """构建分析 prompt"""
        
        fr = deriv_data.get('funding_rate', 0)
        annual = fr * 3 * 365
        oi = deriv_data.get('open_interest_usd', 0)
        liq = deriv_data.get('liquidation_24h', {})
        ls = deriv_data.get('long_short', {})
        
        # 爆仓多空比例
        short_ratio = 0
        if liq.get('total_usd', 0) > 0:
            short_ratio = liq.get('short_usd', 0) / liq.get('total_usd', 0)
        
        prompt = f"""{self.SYSTEM_PROMPT}

=== 当前市场数据 ===
BTC价格: ${btc_data.get('price', 0):,.2f}
1h涨跌: {btc_data.get('change_pct', 0):+.2f}%

=== 衍生品数据 ===
资金费率: {fr*100:+.4f}% (年化 {annual*100:+.2f}%)
持仓量: ${oi/1e9:.2f}B
24h爆仓: ${liq.get('total_usd', 0)/1e6:.2f}M
  - 多头爆仓: ${liq.get('long_usd', 0)/1e6:.2f}M
  - 空头爆仓: ${liq.get('short_usd', 0)/1e6:.2f}M ({short_ratio*100:.1f}%)
多空比: {ls.get('ratio', 1.0):.2f}
  - 多头: {ls.get('long_pct', 50):.1f}%
  - 空头: {ls.get('short_pct', 50):.1f}%

=== 量化信号分析 ===
综合评分: {signal_result.overall_score:+.1f}
信号: {signal_result.signal_label}
置信度: {signal_result.confidence}%
风险等级: {signal_result.risk_level}
因子分析:
{chr(10).join(f"- {f.name}: {f.label} (权重{f.weight:.0%}, 分数{f.score:+.0f})" for f in signal_result.factors)}
总结: {signal_result.summary}

请输出JSON格式分析结果:"""
        return prompt
    
    def _parse_response(self, response: str, model: str) -> AIAnalysis:
        """解析模型响应"""
        try:
            # 尝试提取 JSON
            text = response.strip()
            
            # 尝试解析整个响应为 JSON
            try:
                data = json.loads(text)
            except Exception as e:
                logger.warning(f"本地模型异常: {e}")
                # 尝试从文本中提取 JSON
                import re
                json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    raise ValueError("无法解析模型响应")
            
            return AIAnalysis(
                symbol="BTC",
                model=model,
                signal=data.get('signal', 'NEUTRAL'),
                confidence=float(data.get('confidence', 50)),
                reasoning=data.get('reasoning', '模型未提供推理'),
                market_state=data.get('market_state', '未知'),
                risk_warning=data.get('risk_warning', ''),
                recommendation=data.get('recommendation', '观望'),
                timestamp=int(asyncio.get_event_loop().time() * 1000),
            )
        except Exception as e:
            logger.error(f"解析模型响应失败: {e}, 原始响应: {response[:200]}")
            return AIAnalysis(
                symbol="BTC",
                model=model,
                signal="NEUTRAL",
                confidence=0,
                reasoning="解析失败",
                market_state="未知",
                risk_warning="",
                recommendation="观望",
                timestamp=int(asyncio.get_event_loop().time() * 1000),
            )
    
    def _rule_based_analysis(self, signal_result, btc_data: dict, deriv_data: dict) -> AIAnalysis:
        """规则引擎分析（本地模型不可用时的备用）"""
        signal = signal_result.signal.value
        confidence = signal_result.confidence
        overall = signal_result.overall_score
        
        # 基于量化信号生成 AI 风格回复
        if signal == "STRONG_BUY":
            reasoning = f"综合评分{overall:.0f}，{signal_result.risk_level}风险，量化信号极度看多"
            market_state = "强势上涨趋势，空头被迫平仓"
            risk = "追高风险，注意止损"
            rec = "可考虑分批建仓做多，止损设在近期支撑位"
        elif signal == "BUY":
            reasoning = f"综合评分{overall:.0f}，偏多信号，{signal_result.risk_level}风险"
            market_state = "偏多趋势，多头占优"
            risk = "注意回调风险"
            rec = "轻仓做多，关注资金费率变化"
        elif signal == "STRONG_SELL":
            reasoning = f"综合评分{overall:.0f}，{signal_result.risk_level}风险，量化信号极度看空"
            market_state = "弱势下跌趋势，多头被清洗"
            risk = "空头主导，趋势可能延续"
            rec = "观望或做空，注意空头陷阱"
        elif signal == "SELL":
            reasoning = f"综合评分{overall:.0f}，偏空信号，{signal_result.risk_level}风险"
            market_state = "偏空趋势，空头占优"
            risk = "警惕反弹"
            rec = "观望为主，不盲目追空"
        else:
            reasoning = f"综合评分{overall:.0f}，多空均衡，建议观望"
            market_state = "震荡整理，多空双方观望"
            risk = "方向不明"
            rec = "等待信号明确，暂不操作"
        
        return AIAnalysis(
            symbol="BTC",
            model="rule_engine",
            signal=signal,
            confidence=confidence,
            reasoning=reasoning,
            market_state=market_state,
            risk_warning=risk,
            recommendation=rec,
            timestamp=int(asyncio.get_event_loop().time() * 1000),
        )


# 全局单例
_ai_analyzer = None

def get_ai_analyzer() -> AIAnalyzer:
    global _ai_analyzer
    if _ai_analyzer is None:
        _ai_analyzer = AIAnalyzer()
    return _ai_analyzer
