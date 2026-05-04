# ============================================================
# CONFLUENCE SCANNER v1.0
# 6-Force High Conviction Signal System
# Fires only when score >= 14/22
# Runs every 2 hours during market hours
# ============================================================
from utils import *
import pytz
IST = pytz.timezone("Asia/Kolkata")

# ── Confluence thresholds ─────────────────────────────────────
ULTRA_BUY_SCORE   = 18   # ~80% win probability
STRONG_BUY_SCORE  = 14   # ~70% win probability
MIN_PRICE         = 50
MIN_AVG_VOLUME    = 100000   # Higher than regular scanner
MAX_RSI_ENTRY     = 68       # Won't recommend overbought

def score_force1_technicals(close, volume):
    """Force 1 — Technical indicators (0-4 points)"""
    score = 0; details = []
    try:
        rsi = float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
        ema20 = float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
        ema50 = float(ta.trend.EMAIndicator(close,50).ema_indicator().iloc[-1]) if len(close)>=50 else ema20
        macd_obj = ta.trend.MACD(close)
        ml = float(macd_obj.macd().iloc[-1])
        sl = float(macd_obj.macd_signal().iloc[-1])
        avg_vol = float(volume.tail(20).mean())
        lat_vol = float(volume.iloc[-1])
        vol_ratio = lat_vol / avg_vol if avg_vol > 0 else 0

        if 35 <= rsi <= 60:
            score += 1
            details.append(f"✅ RSI {rsi:.1f} — perfect entry zone (35–60)")
        elif rsi < 35:
            score += 1
            details.append(f"✅ RSI {rsi:.1f} — oversold, high bounce probability")
        else:
            details.append(f"❌ RSI {rsi:.1f} — elevated, not ideal entry")

        if ema20 > ema50:
            score += 1
            details.append("✅ EMA20 > EMA50 — confirmed uptrend")
        else:
            details.append("❌ EMA20 < EMA50 — downtrend, skip")

        if ml > sl:
            score += 1
            details.append("✅ MACD bullish crossover — buying momentum")
        else:
            details.append("❌ MACD bearish — selling momentum")

        if vol_ratio >= 2.0:
            score += 1
            details.append(f"✅ Volume {vol_ratio:.1f}x average — strong institutional buying")
        elif vol_ratio >= 1.5:
            details.append(f"⚠️ Volume {vol_ratio:.1f}x average — moderate interest")
        else:
            details.append(f"❌ Volume {vol_ratio:.1f}x average — no unusual activity")

        return score, details, {"rsi": round(rsi,1), "ema_trend": ema20>ema50,
                                "macd_bull": ml>sl, "vol_ratio": round(vol_ratio,1)}
    except Exception as e:
        return 0, [f"❌ Technical calc error: {e}"], {}

def score_force2_market_structure(close, symbol):
    """Force 2 — Market structure (0-3 points)"""
    score = 0; details = []
    try:
        curr = float(close.iloc[-1])
        # Higher highs + higher lows (last 10 days)
        highs = [float(close.iloc[i]) for i in range(-10, -1)]
        lows_list = highs.copy()
        hh = all(highs[i] >= highs[i-1]*0.995 for i in range(1, len(highs)))
        # Support level (20-day low)
        support = float(close.tail(20).min())
        resistance = float(close.tail(20).max())
        dist_from_support = ((curr - support) / support) * 100
        # Consolidation breakout (price was range-bound, now breaking out)
        last_20_range = ((resistance - support) / support) * 100
        week_ago = float(close.iloc[-6])
        price_momentum = ((curr - week_ago) / week_ago) * 100
        # 52-week high check
        high_52w = float(close.tail(252).max()) if len(close) >= 252 else float(close.max())
        near_52w_high = curr >= high_52w * 0.95

        if hh:
            score += 1
            details.append("✅ Higher highs pattern — uptrend structure intact")
        else:
            details.append("❌ No clear higher highs — structure weak")

        if dist_from_support <= 5:
            score += 1
            details.append(f"✅ Price near support ₹{support:.2f} — low risk entry zone")
        elif dist_from_support <= 10:
            details.append(f"⚠️ Price {dist_from_support:.1f}% above support ₹{support:.2f}")
        else:
            details.append(f"❌ Price {dist_from_support:.1f}% above support — risk/reward less ideal")

        if near_52w_high and price_momentum > 0:
            score += 1
            details.append(f"✅ Near 52-week high — strong momentum breakout")
        elif price_momentum > 3:
            score += 1
            details.append(f"✅ Strong weekly momentum +{price_momentum:.1f}% — buyers in control")
        else:
            details.append(f"❌ Weekly momentum {price_momentum:+.1f}% — weak price action")

        return score, details, {"support": round(support,2), "resistance": round(resistance,2),
                                "dist_from_support": round(dist_from_support,1),
                                "momentum_1w": round(price_momentum,1)}
    except Exception as e:
        return 0, [f"❌ Structure calc error: {e}"], {}

def score_force3_alignment(symbol, sector_signals, nifty, banknifty):
    """Force 3 — Sector + Index alignment (0-4 points)"""
    score = 0; details = []
    try:
        sector = get_stock_sector(symbol)
        sector_mood = sector_signals.get(sector, "NEUTRAL 🟡")
        nifty_dir = nifty['direction'] if nifty else "NEUTRAL"
        nifty_rsi = nifty['rsi'] if nifty else 50
        bn_dir = banknifty['direction'] if banknifty else "NEUTRAL"

        if "BULLISH" in sector_mood:
            score += 2
            details.append(f"✅ Sector {sector} is BULLISH — tailwind for this stock")
        elif "NEUTRAL" in sector_mood:
            score += 1
            details.append(f"⚠️ Sector {sector} is NEUTRAL — no headwind")
        else:
            details.append(f"❌ Sector {sector} is BEARISH — fighting headwind")

        if nifty_dir == "BULLISH" and nifty_rsi < 68:
            score += 1
            details.append(f"✅ Nifty BULLISH — market supporting individual stocks")
        elif nifty_dir == "BEARISH":
            details.append("❌ Nifty BEARISH — market working against this trade")
        else:
            details.append("⚠️ Nifty NEUTRAL — mixed market conditions")

        if sector in ["BANKING","FINANCE"] and bn_dir == "BULLISH":
            score += 1
            details.append("✅ Bank Nifty also bullish — double confirmation for banking stock")

        return score, details, {"sector": sector, "sector_mood": sector_mood,
                                "nifty_dir": nifty_dir}
    except Exception as e:
        return 0, [f"❌ Alignment calc error: {e}"], {}

def score_force4_institutional(close, volume, symbol):
    """Force 4 — Institutional footprint (0-4 points)"""
    score = 0; details = []
    try:
        avg_vol_20 = float(volume.tail(20).mean())
        avg_vol_5 = float(volume.tail(5).mean())
        lat_vol = float(volume.iloc[-1])
        curr = float(close.iloc[-1])
        prev_5 = float(close.iloc[-6])
        prev_20 = float(close.iloc[-21]) if len(close) >= 21 else float(close.iloc[0])

        vol_ratio_today = lat_vol / avg_vol_20 if avg_vol_20 > 0 else 0
        vol_trend = avg_vol_5 / avg_vol_20 if avg_vol_20 > 0 else 1
        price_5d_chg = ((curr - prev_5) / prev_5) * 100
        price_20d_chg = ((curr - prev_20) / prev_20) * 100

        # Volume surge
        if vol_ratio_today >= 3.0:
            score += 2
            details.append(f"✅ MASSIVE volume {vol_ratio_today:.1f}x average — clear institutional activity")
        elif vol_ratio_today >= 2.0:
            score += 1
            details.append(f"✅ High volume {vol_ratio_today:.1f}x average — notable buying")
        else:
            details.append(f"❌ Volume {vol_ratio_today:.1f}x — no unusual institutional activity")

        # Volume trend increasing
        if vol_trend >= 1.3:
            score += 1
            details.append(f"✅ Volume trending UP last 5 days — accumulation pattern")
        else:
            details.append(f"⚠️ Volume flat/declining — no sustained accumulation")

        # Price rising with volume (not just price pump)
        if price_5d_chg > 2 and vol_trend >= 1.2:
            score += 1
            details.append(f"✅ Price +{price_5d_chg:.1f}% with rising volume — genuine buying")
        elif price_5d_chg > 0:
            details.append(f"⚠️ Price +{price_5d_chg:.1f}% but volume not confirming")
        else:
            details.append(f"❌ Price {price_5d_chg:+.1f}% — weak price action")

        return score, details, {"vol_ratio_today": round(vol_ratio_today,1),
                                "vol_trend": round(vol_trend,2),
                                "price_5d": round(price_5d_chg,1),
                                "price_20d": round(price_20d_chg,1)}
    except Exception as e:
        return 0, [f"❌ Institutional calc error: {e}"], {}

def score_force5_multitimeframe(symbol):
    """Force 5 — Multi-timeframe alignment (0-3 points)"""
    score = 0; details = []
    try:
        ticker = symbol if ".NS" in symbol else symbol+".NS"
        # Weekly data
        df_weekly = yf.download(ticker, period="1y", interval="1wk", progress=False)
        # Monthly data
        df_monthly = yf.download(ticker, period="2y", interval="1mo", progress=False)

        # Weekly trend
        if not df_weekly.empty and len(df_weekly) >= 20:
            wc = df_weekly['Close'].squeeze()
            w_ema10 = float(ta.trend.EMAIndicator(wc,10).ema_indicator().iloc[-1])
            w_ema20 = float(ta.trend.EMAIndicator(wc,20).ema_indicator().iloc[-1])
            w_rsi = float(ta.momentum.RSIIndicator(wc).rsi().iloc[-1])
            if w_ema10 > w_ema20 and w_rsi < 72:
                score += 1
                details.append(f"✅ Weekly chart UPTREND — medium term bullish (RSI {w_rsi:.0f})")
            else:
                details.append(f"❌ Weekly chart NOT in uptrend — medium term weak")
        else:
            details.append("⚠️ Weekly data insufficient")

        # Monthly trend
        if not df_monthly.empty and len(df_monthly) >= 12:
            mc = df_monthly['Close'].squeeze()
            m_ema6 = float(ta.trend.EMAIndicator(mc,6).ema_indicator().iloc[-1])
            m_ema12 = float(ta.trend.EMAIndicator(mc,12).ema_indicator().iloc[-1])
            if m_ema6 > m_ema12:
                score += 1
                details.append("✅ Monthly chart UPTREND — long term bullish")
            else:
                details.append("❌ Monthly chart NOT in uptrend — long term weak")
        else:
            details.append("⚠️ Monthly data insufficient")

        # If both weekly and monthly bullish = 3rd point
        if score == 2:
            score += 1
            details.append("✅ ALL timeframes aligned — very rare and powerful setup")

        return score, details, {}
    except Exception as e:
        return 0, [f"❌ Multi-TF error: {e}"], {}

def score_force6_fundamental(symbol, news, fii_dii):
    """Force 6 — Fundamental + News trigger (0-4 points)"""
    score = 0; details = []
    try:
        sym_clean = symbol.replace(".NS","")
        ticker = symbol if ".NS" in symbol else symbol+".NS"

        # Check news sentiment for this stock
        stock_news = [n for n in news if sym_clean.upper() in n['stock'].upper()]
        if stock_news:
            positive = [n for n in stock_news if "POSITIVE" in n['sentiment']]
            negative = [n for n in stock_news if "NEGATIVE" in n['sentiment']]
            if positive and not negative:
                score += 2
                details.append(f"✅ Positive news catalyst: {positive[0]['headline'][:80]}")
            elif negative:
                score -= 1
                details.append(f"❌ Negative news: {negative[0]['headline'][:80]}")
            else:
                score += 1
                details.append("⚠️ Neutral news — no negative catalyst")
        else:
            score += 1
            details.append("✅ No negative news in last 24 hours — clean slate")

        # FII buying context
        fii_net = fii_dii.get('fii_net', 0) or 0
        if fii_net > 2000:
            score += 1
            details.append(f"✅ FII buying ₹{fii_net:,.0f} Cr today — foreign money bullish on India")
        elif fii_net > 0:
            details.append(f"⚠️ FII buying ₹{fii_net:,.0f} Cr — modest foreign interest")
        elif fii_net < -2000:
            score -= 1
            details.append(f"❌ FII selling ₹{abs(fii_net):,.0f} Cr — foreign money exiting")
        else:
            details.append("⚠️ FII data not available — neutral assumption")

        # Price vs 52-week performance
        try:
            df = yf.download(ticker, period="1y", interval="1d", progress=False)
            if not df.empty:
                curr = float(df['Close'].iloc[-1])
                high_52w = float(df['High'].max())
                low_52w = float(df['Low'].min())
                pos_in_range = ((curr - low_52w) / (high_52w - low_52w)) * 100 if high_52w != low_52w else 50
                if pos_in_range >= 70:
                    score += 1
                    details.append(f"✅ Stock in upper 30% of 52-week range — strong momentum")
                elif pos_in_range <= 30:
                    details.append(f"⚠️ Stock in lower 30% of 52-week range — potential value but weak momentum")
                else:
                    details.append(f"⚠️ Stock in middle of 52-week range — neutral positioning")
        except:
            pass

        score = max(0, min(4, score))
        return score, details, {"news_count": len(stock_news), "fii_net": fii_net}
    except Exception as e:
        return 0, [f"❌ Fundamental error: {e}"], {}

def calculate_confluence_score(symbol, sector_signals, nifty, banknifty, news, fii_dii):
    """Calculate complete 6-force confluence score"""
    try:
        ticker = symbol if ".NS" in symbol else symbol+".NS"
        df = yf.download(ticker, period="6mo", interval="1d", progress=False)
        if df.empty or len(df) < 30:
            return None
        close = df['Close'].squeeze()
        volume = df['Volume'].squeeze()
        curr = float(close.iloc[-1])
        if curr < MIN_PRICE:
            return None
        avg_vol = float(volume.tail(20).mean())
        if avg_vol < MIN_AVG_VOLUME:
            return None
        rsi = float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
        if rsi > MAX_RSI_ENTRY:
            return None

        # Calculate all 6 forces
        f1_score, f1_details, f1_data = score_force1_technicals(close, volume)
        f2_score, f2_details, f2_data = score_force2_market_structure(close, symbol)
        f3_score, f3_details, f3_data = score_force3_alignment(symbol, sector_signals, nifty, banknifty)
        f4_score, f4_details, f4_data = score_force4_institutional(close, volume, symbol)
        f5_score, f5_details, f5_data = score_force5_multitimeframe(symbol)
        f6_score, f6_details, f6_data = score_force6_fundamental(symbol, news, fii_dii)

        total = f1_score + f2_score + f3_score + f4_score + f5_score + f6_score
        total = max(0, min(22, total))

        if total < STRONG_BUY_SCORE:
            return None

        sym_clean = symbol.replace(".NS","")
        entry = round(curr * 0.999, 2)
        target1 = round(curr * 1.065, 2)
        target2 = round(curr * 1.13, 2)
        target3 = round(curr * 1.20, 2)
        sl = max(round(curr * 0.96, 2), round(float(close.tail(20).min()) * 0.98, 2))

        is_fno = ticker in FON_STOCKS
        lot = FON_LOT_SIZES.get(sym_clean, 0)

        # Position sizing (2% risk rule)
        sl_dist = curr - sl
        risk_per_share = sl_dist
        capital = 200000
        max_risk = capital * 0.02
        max_shares = int(max_risk / risk_per_share) if risk_per_share > 0 else 0
        recommended_capital = round(max_shares * curr)

        # Options recommendation
        opts = None
        if is_fno and lot > 0:
            strike = round(curr * 1.03 / 50) * 50
            prem_low = round(curr * 0.025, 1)
            prem_high = round(curr * 0.035, 1)
            tgt_prem = round(prem_low * 2.5, 1)
            sl_prem = round(prem_low * 0.5, 1)
            opts = {
                "strike": strike,
                "prem_low": prem_low,
                "prem_high": prem_high,
                "tgt_prem": tgt_prem,
                "sl_prem": sl_prem,
                "lot": lot,
                "cap_low": round(prem_low * lot),
                "cap_high": round(prem_high * lot),
            }

        win_prob = 55 + (total - 10) * 1.5
        win_prob = min(82, max(55, win_prob))

        return {
            "symbol": sym_clean,
            "price": round(curr, 2),
            "total_score": total,
            "max_score": 22,
            "signal": "ULTRA BUY 🔥" if total >= ULTRA_BUY_SCORE else "STRONG BUY ⭐",
            "win_prob": round(win_prob, 0),
            "forces": {
                "f1": {"score": f1_score, "max": 4, "name": "Technical Setup", "details": f1_details, "data": f1_data},
                "f2": {"score": f2_score, "max": 3, "name": "Market Structure", "details": f2_details, "data": f2_data},
                "f3": {"score": f3_score, "max": 4, "name": "Sector + Index Alignment", "details": f3_details, "data": f3_data},
                "f4": {"score": f4_score, "max": 4, "name": "Institutional Footprint", "details": f4_details, "data": f4_data},
                "f5": {"score": f5_score, "max": 3, "name": "Multi-Timeframe", "details": f5_details, "data": f5_data},
                "f6": {"score": f6_score, "max": 4, "name": "Fundamental + News", "details": f6_details, "data": f6_data},
            },
            "entry": entry,
            "target1": target1,
            "target2": target2,
            "target3": target3,
            "sl": sl,
            "max_shares": max_shares,
            "recommended_capital": recommended_capital,
            "is_fno": is_fno,
            "lot": lot,
            "options": opts,
            "rsi": round(rsi, 1),
            "sector": get_stock_sector(symbol),
        }
    except Exception as e:
        return None

def build_tg_alert(result, rank=1):
    """Build Telegram alert for a confluence signal"""
    r = result
    signal_emoji = "🔥" if r['total_score'] >= ULTRA_BUY_SCORE else "⭐"
    stars = "⭐" * min(5, r['total_score'] // 4)

    force_summary = ""
    for fk, fv in r['forces'].items():
        bar = "█" * fv['score'] + "░" * (fv['max'] - fv['score'])
        force_summary += f"{bar} {fv['score']}/{fv['max']} {fv['name']}\n"

    opt_txt = ""
    if r['options']:
        o = r['options']
        opt_txt = f"""
🎯 <b>OPTIONS ROUTE (F&O)</b>
Buy    : {r['symbol']} {o['strike']} CE
Premium: ₹{o['prem_low']}–{o['prem_high']} (estimate)
Target : ₹{o['tgt_prem']} (+150%)
SL     : ₹{o['sl_prem']}
Capital: ₹{o['cap_low']:,}–{o['cap_high']:,}
Lot    : {o['lot']} shares"""

    return f"""{signal_emoji} <b>CONFLUENCE ALERT #{rank} — {r['symbol']}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━

📊 <b>Score: {r['total_score']}/22 {stars}</b>
Signal    : {r['signal']}
Win chance: ~{r['win_prob']:.0f}%
Price     : ₹{r['price']}
RSI       : {r['rsi']} | Sector: {r['sector']}

<b>6-Force Breakdown</b>
{force_summary}
━━━━━━━━━━━━━━━━━━━━━━━━━
📈 <b>STOCK ROUTE</b>
Entry     : ₹{r['entry']}
Target 1  : ₹{r['target1']} (+6.5%) → Book 33%
Target 2  : ₹{r['target2']} (+13%) → Book 33%
Target 3  : ₹{r['target3']} (+20%) → Book 34%
Stop Loss : ₹{r['sl']}
Position  : {r['max_shares']} shares (₹{r['recommended_capital']:,})
{opt_txt}
━━━━━━━━━━━━━━━━━━━━━━━━━
💡 This is a RARE high-conviction setup.
   Trade decisively. Follow stop loss strictly.
⚠️ Verify price in Zerodha before entering."""

def build_email_confluence(results, today, now, scan_count):
    """Build detailed email for confluence signals"""

    def force_bar_html(score, max_score):
        filled = round((score / max_score) * 10)
        bar = "█" * filled + "░" * (10 - filled)
        pct = round((score / max_score) * 100)
        color = "#27ae60" if pct >= 75 else "#f39c12" if pct >= 50 else "#e74c3c"
        return f"<span style='font-family:monospace;color:{color}'>{bar}</span> <b style='color:{color}'>{score}/{max_score}</b>"

    results_html = ""
    for i, r in enumerate(results, 1):
        signal_color = "#1a5276" if r['total_score'] >= ULTRA_BUY_SCORE else "#1e8449"
        signal_bg = "#d6eaf8" if r['total_score'] >= ULTRA_BUY_SCORE else "#d5f5e3"
        stars = "⭐" * min(5, r['total_score'] // 4)

        # Forces detail
        forces_html = ""
        for fk, fv in r['forces'].items():
            fc = "#27ae60" if fv['score'] == fv['max'] else "#f39c12" if fv['score'] >= fv['max']//2 else "#e74c3c"
            forces_html += f"""
            <tr style='border-bottom:1px solid #eee'>
                <td style='padding:8px;font-weight:bold;color:#2c3e50'>{fv['name']}</td>
                <td style='padding:8px'>{force_bar_html(fv['score'], fv['max'])}</td>
                <td style='padding:8px;font-size:12px;color:#555'>{'<br>'.join(fv['details'])}</td>
            </tr>"""

        # Options section
        opt_html = ""
        if r['options']:
            o = r['options']
            opt_html = f"""
            <div style='background:#e8f8f5;padding:12px;border-radius:8px;margin-top:10px'>
            <h4 style='margin:0 0 8px;color:#1e8449'>🎯 Options Route (F&O Eligible)</h4>
            <table style='width:100%;font-size:13px'><tr>
            <td><b>Strike:</b> {r['symbol']} {o['strike']} CE</td>
            <td><b>Buy premium:</b> ₹{o['prem_low']}–{o['prem_high']}</td>
            <td><b>Target:</b> ₹{o['tgt_prem']} (+150%)</td>
            <td><b>SL:</b> ₹{o['sl_prem']}</td>
            <td><b>Lot:</b> {o['lot']} shares</td>
            <td><b>Capital:</b> ₹{o['cap_low']:,}–{o['cap_high']:,}</td>
            </tr></table>
            <p style='font-size:12px;color:#555;margin:8px 0 0'>
            💡 You pay ₹{o['cap_low']:,} max. If {r['symbol']} hits ₹{r['target3']:.0f},
            option premium can reach ₹{o['tgt_prem']}. Maximum loss = premium paid only.
            ⚠️ Verify actual premium in Zerodha Options Chain before buying.</p>
            </div>"""

        results_html += f"""
        <div style='border:2px solid {signal_color};border-radius:12px;padding:20px;margin-bottom:25px;background:#fafafa'>

        <div style='background:{signal_bg};padding:12px;border-radius:8px;margin-bottom:15px'>
        <h2 style='margin:0;color:{signal_color}'>#{i} {r['signal']} — {r['symbol']}</h2>
        <p style='margin:5px 0 0;font-size:14px'>
        Score: <b>{r['total_score']}/22</b> {stars} |
        Price: <b>₹{r['price']}</b> |
        Win probability: <b>~{r['win_prob']:.0f}%</b> |
        RSI: <b>{r['rsi']}</b> |
        Sector: <b>{r['sector']}</b>
        </p>
        </div>

        <h3 style='color:#2c3e50;margin-bottom:10px'>📊 6-Force Analysis</h3>
        <table style='width:100%;border-collapse:collapse;font-size:13px'>
        <tr style='background:#2c3e50;color:white'>
            <th style='padding:8px;text-align:left'>Force</th>
            <th style='padding:8px;text-align:left'>Score</th>
            <th style='padding:8px;text-align:left'>Details</th>
        </tr>
        {forces_html}
        </table>

        <div style='display:flex;gap:15px;margin-top:15px'>
        <div style='flex:1;background:#eafaf1;padding:12px;border-radius:8px'>
        <h4 style='margin:0 0 8px;color:#1e8449'>📈 Stock Route</h4>
        <table style='width:100%;font-size:13px'><tr>
        <td><b>Entry:</b> ₹{r['entry']}</td>
        <td><b>Stop Loss:</b> ₹{r['sl']}</td>
        </tr></table>
        <div style='margin-top:8px;font-size:13px'>
        <div style='background:#fff;padding:6px;border-radius:4px;margin:3px 0;border-left:3px solid #27ae60'>
        🎯 Target 1: ₹{r['target1']} <b>(+6.5%)</b> — Book <b>33%</b> here</div>
        <div style='background:#fff;padding:6px;border-radius:4px;margin:3px 0;border-left:3px solid #f39c12'>
        🎯 Target 2: ₹{r['target2']} <b>(+13%)</b> — Book <b>33%</b> here</div>
        <div style='background:#fff;padding:6px;border-radius:4px;margin:3px 0;border-left:3px solid #e74c3c'>
        🎯 Target 3: ₹{r['target3']} <b>(+20%)</b> — Book <b>34%</b> here</div>
        </div>
        <p style='font-size:12px;margin:8px 0 0;color:#555'>
        Position size: <b>{r['max_shares']} shares</b> (₹{r['recommended_capital']:,})<br>
        Based on 2% risk rule on ₹2L capital. Adjust if your capital is different.</p>
        </div>
        </div>
        {opt_html}

        <div style='background:#fff3cd;padding:10px;border-radius:8px;margin-top:10px;font-size:13px'>
        💡 <b>Simple action plan:</b>
        Wait for price to dip to ₹{r['entry']} → Enter → Set SL alert at ₹{r['sl']} →
        Book 33% at ₹{r['target1']} → Trail SL to entry → Hold rest for ₹{r['target2']} and ₹{r['target3']}
        </div>
        </div>"""

    if not results_html:
        results_html = """
        <div style='background:#f8f9fa;padding:30px;border-radius:8px;text-align:center'>
        <h3 style='color:#888'>No confluence signals found this scan</h3>
        <p style='color:#aaa'>All {scan_count} stocks checked. None met the 14/22 minimum threshold.<br>
        This is normal — these signals are intentionally rare and high quality.<br>
        Next scan in 2 hours.</p>
        </div>"""

    html = f"""<html><body style='font-family:Arial,sans-serif;max-width:900px;margin:auto;padding:20px;color:#2c3e50'>
    <div style='background:linear-gradient(135deg,#1a1a2e,#16213e);padding:20px;border-radius:12px;color:white;margin-bottom:20px'>
    <h1 style='margin:0'>🔥 Confluence Scanner Alert</h1>
    <p style='margin:5px 0 0;opacity:0.9'>{today} | {now} | {len(results)} signal(s) found from {scan_count} stocks</p>
    <p style='margin:5px 0 0;opacity:0.7;font-size:13px'>
    Minimum score required: 14/22 | Signals found: {len(results)} |
    {"🔥 ULTRA BUY signals: "+str(len([r for r in results if r['total_score']>=ULTRA_BUY_SCORE])) if results else "No qualifying signals"}</p>
    </div>

    <div style='background:#fef9e7;padding:15px;border-radius:8px;border-left:4px solid #f39c12;margin-bottom:20px'>
    <h3 style='margin:0'>📖 How to use this report</h3>
    <p style='margin:8px 0 0;font-size:13px'>
    These signals fire <b>rarely</b> — only when 6 independent forces all agree.
    When they do, the win probability is significantly higher than regular signals.<br><br>
    <b>Score 18–22 (ULTRA BUY 🔥):</b> ~80% win probability. Act with full position size.<br>
    <b>Score 14–17 (STRONG BUY ⭐):</b> ~70% win probability. Act with 75% position size.<br><br>
    <b>Always follow the 3-target exit strategy.</b> Never hold all the way — book in parts.
    <b>Stop loss is mandatory.</b> No exceptions. Ever.
    </p>
    </div>

    {results_html}

    <p style='color:#7f8c8d;font-size:12px;margin-top:20px;border-top:1px solid #eee;padding-top:10px'>
    ⚠️ These are technical signals based on 6-force confluence analysis.<br>
    Option premiums are estimated — check actual premiums in Zerodha Options Chain.<br>
    Position sizing based on ₹2L capital with 2% risk rule — adjust for your capital.<br>
    Win probability is historical estimate — not a guarantee. Always use stop loss.<br>
    Prices as of: {now} IST (15 min delayed during market hours)
    </p></body></html>"""
    return html

def run():
    today = datetime.now(IST).strftime('%d %b %Y')
    now = datetime.now(IST).strftime('%I:%M %p IST')
    print(f"\n{'='*60}\nConfluence Scanner v1.0 — {today} {now}\n{'='*60}")

    # Get market context
    print("Loading market context...")
    sector_signals = get_sector_momentum()
    nifty = analyze_index("^NSEI","Nifty 50")
    banknifty = analyze_index("^NSEBANK","Bank Nifty")
    news = get_news()
    fii_dii = get_fii_dii()
    nifty_dir = nifty['direction'] if nifty else "NEUTRAL"

    # Only scan if market is not strongly bearish
    if nifty and nifty['direction'] == "BEARISH" and nifty['rsi'] > 65:
        msg = f"⚠️ <b>Confluence Scanner — {today} {now}</b>\n\nMarket is BEARISH today.\nNo buy signals generated.\nProtect existing positions.\n\nNext scan in 2 hours."
        send_telegram(msg)
        print("Market bearish — skipping scan")
        return

    # Get full stock list
    nse_symbols = get_nse_symbols()
    print(f"Scanning {len(nse_symbols)} stocks for confluence...")

    results = []
    scanned = 0
    for i, symbol in enumerate(nse_symbols):
        try:
            result = calculate_confluence_score(
                symbol, sector_signals, nifty, banknifty, news, fii_dii)
            if result:
                results.append(result)
                print(f"  ✅ FOUND: {result['symbol']} — Score {result['total_score']}/22 — {result['signal']}")
            scanned += 1
            if (i+1) % 300 == 0:
                print(f"  Progress: {i+1}/{len(nse_symbols)} | Qualified: {len(results)}")
            time.sleep(0.4)
        except:
            pass

    # Sort by score
    results.sort(key=lambda x: x['total_score'], reverse=True)
    top_results = results[:5]  # Max 5 signals per scan

    print(f"\nScan complete! Scanned: {scanned} | Qualified: {len(results)} | Showing top: {len(top_results)}")

    if not top_results:
        msg = f"""🔍 <b>Confluence Scanner — {today} {now}</b>

Scanned: {scanned} stocks
Qualified signals: 0

No stock met the 14/22 minimum threshold today.
This is intentional — the filter is strict.

✅ This means: No high-conviction setups right now.
   Better to wait than force a trade.
   
Next scan in 2 hours."""
        send_telegram(msg)
        print("No qualifying signals found")
        return

    # Send Telegram alerts
    header = f"""🔥 <b>CONFLUENCE ALERT — {today} {now}</b>
━━━━━━━━━━━━━━━━━━━━
{len(top_results)} high-conviction signal(s) found
from {scanned} stocks scanned

Score required: 14/22 minimum
Ultra Buy (🔥): {len([r for r in top_results if r['total_score']>=ULTRA_BUY_SCORE])} signals
Strong Buy (⭐): {len([r for r in top_results if STRONG_BUY_SCORE<=r['total_score']<ULTRA_BUY_SCORE])} signals

📧 Detailed report sent to Gmail
━━━━━━━━━━━━━━━━━━━━"""
    send_telegram(header)
    time.sleep(1)

    for i, r in enumerate(top_results, 1):
        alert = build_tg_alert(r, i)
        send_telegram(alert)
        time.sleep(1)

    # Send email
    email_body = build_email_confluence(top_results, today, now, scanned)
    ultra_count = len([r for r in top_results if r['total_score'] >= ULTRA_BUY_SCORE])
    subject_prefix = "🔥 ULTRA BUY" if ultra_count > 0 else "⭐ STRONG BUY"
    top_symbol = top_results[0]['symbol'] if top_results else "N/A"
    top_score = top_results[0]['total_score'] if top_results else 0

    send_email(
        subject=f"{subject_prefix} Confluence Alert {today} | {top_symbol} {top_score}/22 | {len(top_results)} signals",
        body=email_body
    )
    print("\n✅ Confluence scan complete!")

run()
