import streamlit as st
import asyncio
import os  # <--- 新增
import pandas as pd
from datetime import datetime, date
from ib_logic import IBKR_Strategy_Analyzer

# ==========================================
# 🛡️ 安全验证 (新增模块)
# ==========================================
def check_password():
    """密码验证组件"""
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    def password_entered():
        # 从环境变量获取密码，默认 admin123 (部署时请修改docker-compose)
        correct_password = os.environ.get("APP_PASSWORD", "admin123")
        if st.session_state["password"] == correct_password:
            st.session_state.password_correct = True
            del st.session_state["password"]
        else:
            st.session_state.password_correct = False

    if st.session_state.password_correct:
        return True

    st.text_input("🔒 请输入访问密码", type="password", on_change=password_entered, key="password")
    return False

if not check_password():
    st.stop()  # ⛔ 如果密码不对，直接停止运行下面的代码

# ==========================================
# 下面是你原本的代码
# ==========================================
st.set_page_config(page_title="FG策略 - 狙击镜", layout="centered")

st.title("🎯 异动期权狙击镜")
st.caption("IBKR 实时数据连接 | 智能 IV 分析 | 趋势共振确认")

# 初始化 Session State
if 'report' not in st.session_state:
    st.session_state.report = None
if 'analyzed_expiry' not in st.session_state:
    st.session_state.analyzed_expiry = None

with st.container(border=True):
    st.subheader("🛠️ 参数设置")

    col1, col2 = st.columns(2)
    with col1:
        ticker = st.text_input("标的代码 (Symbol)", value="NVDA", help="输入美股代码，如 NVDA, TSLA").upper()
    with col2:
        expiry_date = st.date_input("行权日期 (Expiry)", min_value=datetime.today())

    col3, col4 = st.columns(2)
    with col3:
        direction = st.radio("方向 (Direction)", ["Call (看涨)", "Put (看跌)"], horizontal=True)
    with col4:
        strike = st.number_input("行权价 (Strike Price)", min_value=1.0, value=190.0, step=0.5, format="%.1f")

    expiry_str = expiry_date.strftime("%Y%m%d")
    right_code = "C" if "Call" in direction else "P"

    btn_col1, btn_col2 = st.columns([1, 3])
    with btn_col2:
        start_btn = st.button("🚀 立即分析 (Analyze)", type="primary", use_container_width=True)

    if start_btn:
        st.info(f"正在连接 TWS 并锁定合约: {ticker} {expiry_str} {right_code}{strike}...")
        st.session_state.analyzed_expiry = expiry_date
        analyzer = IBKR_Strategy_Analyzer()

        try:
            result, error = asyncio.run(analyzer.analyze_single_target(ticker, right_code, expiry_str, strike))
            analyzer.disconnect()

            if error:
                st.error(error)
                st.session_state.report = None
            else:
                st.session_state.report = result
                st.balloons()

        except Exception as e:
            st.error(f"系统错误: {e}")

if st.session_state.report:
    r = st.session_state.report
    target_date = st.session_state.analyzed_expiry
    today = date.today()
    dte = (target_date - today).days

    if dte < 0:
        dte_badge_color = "#9e9e9e"
        dte_text = "⚠️ 已过期"
    elif dte <= 5:
        dte_badge_color = "#ff5252"
        dte_text = f"⏳ 仅剩 {dte} 天 (末日轮风险)"
    elif dte <= 14:
        dte_badge_color = "#ffa726"
        dte_text = f"⏳ 剩 {dte} 天"
    else:
        dte_badge_color = "#66bb6a"
        dte_text = f"🗓️ 剩 {dte} 天"

    st.divider()

    st.markdown(f"""
    ### 📊 分析报告: {ticker} {right_code}{strike} 
    <span style='font-size:16px; color:#aaa; margin-left:10px;'>到期日: {target_date.strftime('%Y-%m-%d')}</span>
    <span style='background-color:{dte_badge_color}; color:white; padding:2px 8px; border-radius:4px; font-size:14px; margin-left:10px;'>{dte_text}</span>
    """, unsafe_allow_html=True)

    decision_bg = "rgba(0,255,0,0.1)" if "推荐" in r['决策建议'] or "关注" in r['决策建议'] else "rgba(128,128,128,0.1)"
    decision_color = "#00c853" if "推荐" in r['决策建议'] or "关注" in r['决策建议'] else "#757575"

    st.markdown(f"""
    <div style="padding:20px; border-radius:10px; background-color:{decision_bg}; border:2px solid {decision_color}; text-align:center; margin-bottom: 20px;">
        <h2 style="color:{decision_color}; margin:0; font-size: 32px;">{r['决策建议']}</h2>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1.2, 1, 1])

    def lbl(text):
        return f"<p style='font-size:14px; color:#888; margin-bottom:0px;'>{text}</p>"

    def val(text, color="white", size="20px"):
        return f"<p style='font-size:{size}; color:{color}; font-weight:bold; margin-top:0px;'>{text}</p>"

    with c1:
        st.markdown("#### 🏢 正股环境")
        st.markdown(lbl("正股现价") + val(r['正股现价']), unsafe_allow_html=True)
        st.write("")

        trend_color = "#00e676" if "✅" in r['正股趋势'] else "#ff5252"
        st.markdown(lbl("趋势状态"), unsafe_allow_html=True)
        st.markdown(f"""
        <div style="border-left: 3px solid {trend_color}; padding-left: 10px; margin-top: 5px;">
            <span style="color: {trend_color}; font-weight: bold; font-size: 16px;">{r['正股趋势']}</span>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        st.markdown(lbl("成交量比") + val(r['成交量比']), unsafe_allow_html=True)

    with c2:
        st.markdown("#### ⚡ 期权数据")
        st.metric("IV (隐含波动率)", r['隐含波动率(IV)'])
        st.metric("Delta (对冲值)", r['Delta'])
        st.metric("Gamma (加速值)", r['Gamma'])

    with c3:
        st.markdown("#### 💰 盘口状态")
        st.markdown(lbl("当前报价") + val(r['期权价格'], size="16px"), unsafe_allow_html=True)

        spread_color = "orange" if "宽" in r['流动性'] else "#29b6f6"
        st.markdown(f"""
        <div style="margin-top:10px; padding:5px; background-color:rgba(255,255,255,0.05); border-radius:5px; text-align:center; border:1px solid {spread_color}">
            <small style="color:{spread_color}">{r['流动性']}</small>
        </div>
        """, unsafe_allow_html=True)

    st.caption("注：IV 和 Greeks 数据由 IBKR 实时计算，盘前盘后可能稍有延迟。")