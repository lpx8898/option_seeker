import asyncio
import sys
import datetime
import random
import pandas as pd
import nest_asyncio
import os  # <--- 新增: 用于读取环境变量

# ==========================================
# 🛑 核心修复补丁
# ==========================================
try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ==========================================
# 📦 导入 ib_async
# ==========================================
from ib_async import *

nest_asyncio.apply()

# ==========================================
# ⚙️ 配置区域 (动态获取)
# ==========================================
# 如果环境变量里有设置 IB_HOST (Docker环境)，就用设置的；否则默认 127.0.0.1 (本地环境)
IB_HOST = os.environ.get('IB_HOST', '127.0.0.1')

# 如果环境变量里有设置 IB_PORT，就用设置的；否则默认 7497
# 注意：Docker 里的 IB Gateway 默认端口通常是 4001 (Live) 或 4002 (Paper)
IB_PORT = int(os.environ.get('IB_PORT', 7497))

class IBKR_Strategy_Analyzer:
    def __init__(self):
        self.ib = IB()
        self.client_id = random.randint(1000, 9999)

    async def analyze_single_target(self, ticker, rights, expiry, strike):
        """深度分析单个期权标的"""

        # --- 1. 连接 TWS/Gateway ---
        if not self.ib.isConnected():
            try:
                nest_asyncio.apply()
                # 使用动态获取的 HOST 和 PORT
                print(f"正在连接 {IB_HOST}:{IB_PORT} (ID:{self.client_id})...")
                await self.ib.connectAsync(IB_HOST, IB_PORT, clientId=self.client_id)
            except Exception as e:
                return None, f"连接失败: {str(e)}\n目标: {IB_HOST}:{IB_PORT}"

        self.ib.reqMarketDataType(1)

        # =================================
        # 第一步：获取正股数据
        # =================================
        stock = Stock(ticker, 'SMART', 'USD')

        try:
            details = await self.ib.reqContractDetailsAsync(stock)
            if not details: return None, f"找不到股票代码: {ticker}"
            stock = details[0].contract
        except:
            return None, f"股票代码查询错误: {ticker}"

        bars = await self.ib.reqHistoricalDataAsync(stock, '', '1 M', '1 day', 'TRADES', True)
        if not bars: return None, "无法获取正股历史数据"

        df = util.df(bars)
        ma_20 = df['close'].rolling(20).mean().iloc[-1]
        avg_vol = df['volume'].mean()

        self.ib.reqMktData(stock, '', False, False)

        # =================================
        # 第二步：获取期权合约
        # =================================
        right_str = 'C' if rights.upper().startswith('C') else 'P'
        try:
            strike_float = float(strike)
        except:
            return None, "行权价必须是数字"

        option = Option(ticker, expiry, strike_float, right_str, 'SMART')

        try:
            opt_details = await self.ib.reqContractDetailsAsync(option)
            if not opt_details: return None, f"找不到该期权合约: {ticker} {expiry} {strike}"
            option = opt_details[0].contract
        except Exception as e:
            return None, f"期权合约查找失败: {e}"

        self.ib.reqMktData(option, '100,101,106,221', False, False)

        # =================================
        # 第三步：智能等待数据
        # =================================
        stk_data = self.ib.ticker(stock)
        opt_data = self.ib.ticker(option)

        print(f"正在等待 {ticker} 期权数据回传...")

        for i in range(16):
            await asyncio.sleep(0.5)
            has_iv = opt_data.modelGreeks and opt_data.modelGreeks.impliedVol
            has_bid_ask = (opt_data.bid > 0 and opt_data.ask > 0)

            if has_iv or has_bid_ask:
                await asyncio.sleep(0.5)
                break

        # =================================
        # 第四步：数据提取与计算
        # =================================
        curr_price = stk_data.last if (stk_data.last and stk_data.last > 0) else stk_data.close
        if pd.isna(curr_price): curr_price = df['close'].iloc[-1]

        curr_vol = stk_data.volume if (stk_data.volume and stk_data.volume > 0) else 0
        vol_ratio = curr_vol / avg_vol if avg_vol else 0

        if right_str == 'C':
            trend_ok = curr_price > ma_20
            trend_txt = "✅股价>MA20 (多头)" if trend_ok else "⚠️股价<MA20 (逆势)"
        else:
            trend_ok = curr_price < ma_20
            trend_txt = "✅股价<MA20 (空头)" if trend_ok else "⚠️股价>MA20 (逆势)"

        iv, delta, gamma = None, None, None
        if opt_data.modelGreeks:
            iv = opt_data.modelGreeks.impliedVol
            delta = opt_data.modelGreeks.delta
            gamma = opt_data.modelGreeks.gamma

        bid = opt_data.bid if (opt_data.bid and opt_data.bid > 0) else 0.0
        ask = opt_data.ask if (opt_data.ask and opt_data.ask > 0) else 0.0

        spread_txt = "无买盘(流动性差)"
        if bid > 0 and ask > 0:
            spread = (ask - bid) / bid
            spread_txt = f"价差 {spread:.1%}"
            if spread > 0.15: spread_txt += " (宽)"

        # =================================
        # 第五步：生成决策建议
        # =================================
        decision = "👀 观望"
        score = 0

        if vol_ratio > 1.2: score += 1
        if trend_ok: score += 1
        if iv and 0.1 < iv < 0.6: score += 0.5

        if score >= 2.5:
            decision = "🚀 强力推荐"
        elif score >= 1.5:
            decision = "✅ 值得关注"

        result = {
            "正股现价": f"${curr_price:.2f}",
            "正股趋势": trend_txt,
            "成交量比": f"{vol_ratio:.1%}",
            "期权价格": f"Bid:{bid:.2f} / Ask:{ask:.2f}",
            "隐含波动率(IV)": f"{iv:.1%}" if iv else "⚠️无数据",
            "Delta": f"{delta:.2f}" if delta else "-",
            "Gamma": f"{gamma:.3f}" if gamma else "-",
            "流动性": spread_txt,
            "决策建议": decision
        }

        return result, None

    def disconnect(self):
        if self.ib.isConnected():
            self.ib.disconnect()