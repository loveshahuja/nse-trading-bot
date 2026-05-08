# ============================================================
# CONFLUENCE SCANNER v2.0 — SMC EDITION
# ALL existing v1.0 logic preserved exactly
# SMC added as Force 7 bonus scoring (+0 to +6 points)
# New SMC factors: Stage, Order Block, FVG, BOS, Liquidity
# ============================================================
from utils import *
import pytz
IST = pytz.timezone("Asia/Kolkata")

# Import SMC Engine
try:
    from smc_engine import calculate_smc_score, get_killzone
    SMC_AVAILABLE = True
    print("✅ SMC Engine loaded")
except ImportError:
    SMC_AVAILABLE = False
    print("⚠️ SMC Engine not found — running original 6-force mode")

# ── Confluence thresholds (unchanged from v1.0) ───────────────
ULTRA_BUY_SCORE   = 18
STRONG_BUY_SCORE  = 14
MIN_PRICE         = 50
MIN_AVG_VOLUME    = 100000
MAX_RSI_ENTRY     = 68


# ============================================================
# ALL EXISTING v1.0 FORCE FUNCTIONS — UNCHANGED
# ============================================================

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
            score += 1; details.append(f"✅ RSI {rsi:.1f} — perfect entry zone (35–60)")
        elif rsi < 35:
            score += 1; details.append(f"✅ RSI {rsi:.1f} — oversold, high bounce probability")
        else:
            details.append(f"❌ RSI {rsi:.1f} — elevated, not ideal entry")
        if ema20 > ema50:
            score += 1; details.append("✅ EMA20 > EMA50 — confirmed uptrend")
        else:
            details.append("❌ EMA20 < EMA50 — downtrend, skip")
        if ml > sl:
            score += 1; details.append("✅ MACD bullish crossover — buying momentum")
        else:
            details.append("❌ MACD bearish — selling momentum")
        if vol_ratio >= 2.0:
            score += 1; details.append(f"✅ Volume {vol_ratio:.1f}x average — strong institutional buying")
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
        highs = [float(close.iloc[i]) for i in range(-10, -1)]
        hh = all(highs[i] >= highs[i-1]*0.995 for i in range(1, len(highs)))
        support = float(close.tail(20).min())
        resistance = float(close.tail(20).max())
        dist_from_support = ((curr - support) / support) * 100
        last_20_range = ((resistance - support) / support) * 100
        week_ago = float(close.iloc[-6])
        price_momentum = ((curr - week_ago) / week_ago) * 100
        high_52w = float(close.tail(252).max()) if len(close) >= 252 else float(close.max())
        near_52w_high = curr >= high_52w * 0.95
        if hh:
            score += 1; details.append("✅ Higher highs pattern — uptrend structure intact")
        else:
            details.append("❌ No clear higher highs — structure weak")
        if dist_from_support <= 5:
            score += 1; details.append(f"✅ Price near support ₹{support:.2f} — low risk entry zone")
        elif dist_from_support <= 10:
            details.append(f"⚠️ Price {dist_from_support:.1f}% above support ₹{support:.2f}")
        else:
            details.append(f"❌ Price {dist_from_support:.1f}% above support — risk/reward less ideal")
        if near_52w_high and price_momentum > 0:
            score += 1; details.append(f"✅ Near 52-week high — strong momentum breakout")
        elif price_momentum > 3:
            score += 1; details.append(f"✅ Strong weekly momentum +{price_momentum:.1f}% — buyers in control")
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
            score += 2; details.append(f"✅ Sector {sector} is BULLISH — tailwind for this stock")
        elif "NEUTRAL" in sector_mood:
            score += 1; details.append(f"⚠️ Sector {sector} is NEUTRAL — no headwind")
        else:
            details.append(f"❌ Sector {sector} is BEARISH — fighting headwind")
        if nifty_dir == "BULLISH" and nifty_rsi < 68:
            score += 1; details.append(f"✅ Nifty BULLISH — market supporting individual stocks")
        elif nifty_dir == "BEARISH":
            details.append("❌ Nifty BEARISH — market working against this trade")
        else:
            details.append("⚠️ Nifty NEUTRAL — mixed market conditions")
        if sector in ["BANKING","FINANCE"] and bn_dir == "BULLISH":
            score += 1; details.append("✅ Bank Nifty also bullish — double confirmation")
        return score, details, {"sector": sector, "sector_mood": sector_mood, "nifty_dir": nifty_dir}
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
        if vol_ratio_today >= 3.0:
            score += 2; details.append(f"✅ MASSIVE volume {vol_ratio_today:.1f}x average — clear institutional activity")
        elif vol_ratio_today >= 2.0:
            score += 1; details.append(f"✅ High volume {vol_ratio_today:.1f}x average — notable buying")
        else:
            details.append(f"❌ Volume {vol_ratio_today:.1f}x — no unusual institutional activity")
        if vol_trend >= 1.3:
            score += 1; details.append(f"✅ Volume trending UP last 5 days — accumulation pattern")
        else:
            details.append(f"⚠️ Volume flat/declining — no sustained accumulation")
        if price_5d_chg > 5 and vol_ratio_today > 1.5:
            score += 1; details.append(f"✅ Price +{price_5d_chg:.1f}% in 5 days with volume — institutional buying confirmed")
        elif price_20d_chg > 10:
            score += 1; details.append(f"✅ Price +{price_20d_chg:.1f}% in 20 days — sustained accumulation")
        else:
            details.append(f"⚠️ 20-day price change: {price_20d_chg:+.1f}% — below accumulation threshold")
        return score, details, {"vol_ratio": round(vol_ratio_today,1), "vol_trend": round(vol_trend,1),
                                "price_5d": round(price_5d_chg,1), "price_20d": round(price_20d_chg,1)}
    except Exception as e:
        return 0, [f"❌ Institutional calc error: {e}"], {}


def score_force5_news_fii(symbol, news, fii_dii):
    """Force 5 — News + FII/DII sentiment (0-3 points)"""
    score = 0; details = []
    try:
        sym_clean = symbol.replace('.NS','').upper()
        stock_news = [n for n in news if n['stock'].upper() == sym_clean or sym_clean in n['headline'].upper()]
        if stock_news:
            positive = sum(1 for n in stock_news if "POSITIVE" in n['sentiment'])
            negative = sum(1 for n in stock_news if "NEGATIVE" in n['sentiment'])
            if positive > negative:
                score += 1; details.append(f"✅ Positive news: {stock_news[0]['headline'][:50]}...")
            elif negative > positive:
                details.append(f"❌ Negative news: {stock_news[0]['headline'][:50]}...")
            else:
                details.append(f"⚠️ Mixed news — proceed with caution")
        else:
            details.append(f"⚠️ No specific news — neutral factor")
        fii_net = fii_dii.get('fii_net')
        if fii_net is not None:
            if fii_net > 1000:
                score += 2; details.append(f"✅ FII buying ₹{fii_net:,.0f} Cr — strong market tailwind")
            elif fii_net > 0:
                score += 1; details.append(f"✅ FII net buyers ₹{fii_net:,.0f} Cr — mild tailwind")
            elif fii_net < -1000:
                details.append(f"❌ FII selling ₹{abs(fii_net):,.0f} Cr — strong headwind")
            else:
                details.append(f"⚠️ FII selling ₹{abs(fii_net):,.0f} Cr — mild headwind")
        else:
            details.append("⚠️ FII data unavailable — neutral")
        return score, details, {}
    except Exception as e:
        return 0, [f"❌ News/FII calc error: {e}"], {}


def score_force6_risk_reward(close, symbol):
    """Force 6 — Risk/reward and entry quality (0-4 points)"""
    score = 0; details = []
    try:
        curr = float(close.iloc[-1])
        support_20 = float(close.tail(20).min())
        resistance_20 = float(close.tail(20).max())
        risk = curr - support_20
        reward = resistance_20 - curr
        rr_ratio = reward / risk if risk > 0 else 0
        target_pct = ((resistance_20 - curr) / curr) * 100
        sl_pct = ((curr - support_20) / curr) * 100
        if rr_ratio >= 3:
            score += 2; details.append(f"✅ R/R = {rr_ratio:.1f}:1 — excellent (aim for 3:1+)")
        elif rr_ratio >= 2:
            score += 1; details.append(f"✅ R/R = {rr_ratio:.1f}:1 — good (minimum 2:1)")
        else:
            details.append(f"❌ R/R = {rr_ratio:.1f}:1 — too low (<2:1), skip this trade")
        if target_pct >= 10:
            score += 1; details.append(f"✅ Upside potential {target_pct:.1f}% — room to run")
        elif target_pct >= 7:
            details.append(f"⚠️ Upside {target_pct:.1f}% — acceptable")
        else:
            details.append(f"❌ Upside only {target_pct:.1f}% — not enough room")
        if sl_pct <= 3:
            score += 1; details.append(f"✅ Stop loss {sl_pct:.1f}% away — tight, controlled risk")
        elif sl_pct <= 5:
            details.append(f"⚠️ Stop loss {sl_pct:.1f}% away — acceptable")
        else:
            details.append(f"❌ Stop loss {sl_pct:.1f}% away — too loose")
        entry = round(curr * 0.999, 2)
        smart_sl = round(max(curr * 0.97, support_20 * 0.99), 2)
        t1 = round(curr * 1.08, 2)
        t2 = round(curr * 1.15, 2)
        t3 = round(curr * 1.22, 2)
        return score, details, {"entry": entry, "sl": smart_sl, "target1": t1,
                                "target2": t2, "target3": t3,
                                "rr_ratio": round(rr_ratio, 1)}
    except Exception as e:
        return 0, [f"❌ R/R calc error: {e}"], {}


# ============================================================
# NEW: FORCE 7 — SMC BONUS SCORING (0-6 points)
# Does NOT replace any existing forces — purely additive
# ============================================================
def score_force7_smc(df, symbol):
    """
    Force 7 — Smart Money Concepts bonus (0-6 points)
    Each confirmed SMC factor adds 1-2 points on top of 22-point system.
    """
    if not SMC_AVAILABLE or df is None:
        return 0, [], {}
    score = 0; details = []
    try:
        smc = calculate_smc_score(df, symbol)

        # +2: Advancing stage (big filter — only trade with trend)
        if smc['stage'] == "Advancing":
            score += 2; details.append(f"✅ SMC Stage: Advancing (200MA up, HH+HL confirmed)")
        elif smc['stage'] == "Declining":
            score -= 2; details.append(f"🔴 SMC Stage: Declining — avoid longs")

        # +1: Discount zone (price is 'cheap' relative to range)
        pd_z = smc.get('premium_disc') or {}
        if pd_z.get('current_zone') == 'Discount':
            score += 1; details.append(f"✅ SMC: Discount zone ({pd_z.get('position_pct','?')}%)")
        if pd_z.get('in_ote'):
            score += 1; details.append(f"✅ SMC: OTE zone (62–79% retracement) — institutional entry")

        # +2: Price at bullish Order Block
        ob = smc.get('order_block')
        if ob and ob['type'] == 'bullish_ob':
            score += 2; details.append(f"✅ SMC: At Bullish OB ₹{ob['ob_low']}–₹{ob['ob_high']}")

        # +1: Bullish BOS confirmed
        bos = smc.get('bos_choch', {})
        if bos.get('bos') and 'Bullish' in bos['bos']['direction']:
            score += 1; details.append(f"✅ SMC: {bos['bos']['message']}")
        # -2 if CHoCH bearish (early reversal warning — very important)
        if bos.get('choch') and 'Bearish' in bos['choch']['direction']:
            score -= 2; details.append(f"🔴 SMC: {bos['choch']['message']}")

        # +1: SSL sweep (stop hunt complete — reversal likely)
        swept = smc.get('liquidity', {}).get('swept', [])
        for sw in swept:
            if 'UP' in sw['message']:
                score += 1; details.append(f"✅ SMC: {sw['message']}")

        # +1: Bullish candle pattern
        pats = smc.get('candle_patterns', [])
        bull_pats = [p for p in pats if p['bias']=='Bullish' and p['strength'] in ['Strong','Very Strong']]
        if bull_pats:
            score += 1; details.append(f"✅ SMC: {bull_pats[0]['pattern']} ({bull_pats[0]['strength']})")

        return score, details, {
            "stage": smc.get('stage','Unknown'),
            "smc_score": smc.get('smc_score',0),
            "order_block": ob,
            "fvg_below": smc.get('fvg_below'),
            "bos_choch": bos,
            "premium_disc": pd_z,
            "liquidity": smc.get('liquidity',{}),
            "candle_patterns": pats,
        }
    except Exception as e:
        print(f"Force7 SMC error {symbol}: {e}")
        return 0, [], {}


# ============================================================
# MAIN CONFLUENCE CALCULATOR — enhanced with Force 7
# ============================================================
def calculate_confluence_score(symbol, sector_signals, nifty, banknifty, news, fii_dii):
    try:
        sym = symbol if ".NS" in symbol else symbol + ".NS"
        sym_clean = sym.replace('.NS','')
        df = yf.download(sym, period="12mo", interval="1d",
                         auto_adjust=True, progress=False)
        if df is None or df.empty or len(df) < 50:
            return None
        # Standardize columns
        df.columns = [str(c[0]).capitalize() if isinstance(c, tuple) else str(c).capitalize()
                      for c in df.columns]

        close  = df["Close"].squeeze()
        volume = df["Volume"].squeeze()
        curr   = float(close.iloc[-1])

        # Basic filters (unchanged)
        if curr < MIN_PRICE: return None
        avg_vol = float(volume.tail(20).mean())
        if avg_vol < MIN_AVG_VOLUME: return None

        rsi_val = float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
        if rsi_val > MAX_RSI_ENTRY: return None

        # ── All 6 original forces ──────────────────────────────
        f1_score, f1_det, f1_dat = score_force1_technicals(close, volume)
        f2_score, f2_det, f2_dat = score_force2_market_structure(close, sym_clean)
        f3_score, f3_det, f3_dat = score_force3_alignment(sym, sector_signals, nifty, banknifty)
        f4_score, f4_det, f4_dat = score_force4_institutional(close, volume, sym_clean)
        f5_score, f5_det, f5_dat = score_force5_news_fii(sym, news, fii_dii)
        f6_score, f6_det, f6_dat = score_force6_risk_reward(close, sym_clean)
        base_score = f1_score + f2_score + f3_score + f4_score + f5_score + f6_score

        # ── Force 7: SMC bonus ─────────────────────────────────
        f7_score, f7_det, f7_dat = score_force7_smc(df, sym_clean)
        total_score = base_score + f7_score

        # Filter — must meet original threshold (14/22 base)
        if base_score < STRONG_BUY_SCORE:
            return None

        sector = get_stock_sector(sym)

        entry = f6_dat.get('entry', round(curr*0.999, 2))
        smart_sl = f6_dat.get('sl', round(curr*0.97, 2))
        t1 = f6_dat.get('target1', round(curr*1.08, 2))
        t2 = f6_dat.get('target2', round(curr*1.15, 2))
        t3 = f6_dat.get('target3', round(curr*1.22, 2))

        all_details = (
            ["━━━ FORCE 1: Technicals ━━━"] + f1_det +
            ["━━━ FORCE 2: Market Structure ━━━"] + f2_det +
            ["━━━ FORCE 3: Sector Alignment ━━━"] + f3_det +
            ["━━━ FORCE 4: Institutional ━━━"] + f4_det +
            ["━━━ FORCE 5: News/FII ━━━"] + f5_det +
            ["━━━ FORCE 6: Risk/Reward ━━━"] + f6_det +
            (["━━━ FORCE 7: SMC (Bonus) ━━━"] + f7_det if f7_det else [])
        )

        signal = "ULTRA BUY 🔥" if total_score >= ULTRA_BUY_SCORE else "STRONG BUY ⭐"

        result = {
            "symbol": sym_clean, "price": round(curr,2),
            "signal": signal,
            "total_score": total_score, "base_score": base_score, "smc_bonus": f7_score,
            "f1":f1_score,"f2":f2_score,"f3":f3_score,"f4":f4_score,"f5":f5_score,"f6":f6_score,"f7":f7_score,
            "rsi": round(rsi_val,1), "sector": sector,
            "efficiency": min(5, int(base_score/22*5)),
            "entry": entry, "sl": smart_sl,
            "target1": t1, "target2": t2, "target3": t3,
            "details": all_details,
            # SMC fields
            "stage":          f7_dat.get('stage','Unknown'),
            "order_block":    f7_dat.get('order_block'),
            "fvg_below":      f7_dat.get('fvg_below'),
            "bos_choch":      f7_dat.get('bos_choch',{}),
            "premium_disc":   f7_dat.get('premium_disc'),
            "liquidity":      f7_dat.get('liquidity',{}),
            "candle_patterns":f7_dat.get('candle_patterns',[]),
        }

        # Add F&O info
        lot = FON_LOT_SIZES.get(sym_clean, 0)
        result['is_fno'] = lot > 0
        result['lot'] = lot

        return result
    except Exception as e:
        return None


# ============================================================
# TELEGRAM ALERT BUILDER — enhanced with SMC section
# ============================================================
def build_tg_alert(r, rank):
    score = r['total_score']
    base  = r['base_score']
    smc_b = r.get('smc_bonus', 0)
    signal = r['signal']
    emoji = "🔥" if "ULTRA" in signal else "⭐"
    smc_line = ""
    if r.get('stage') and r['stage'] != "Unknown":
        smc_line += f"\nSMC Stage : {r['stage']}"
    if r.get('order_block'):
        ob = r['order_block']
        smc_line += f"\nOrder Block: ₹{ob['ob_low']}–₹{ob['ob_high']}"
    if r.get('fvg_below'):
        fvg = r['fvg_below']
        smc_line += f"\nFVG Support: ₹{fvg['fvg_low']}–₹{fvg['fvg_high']}"
    bos = r.get('bos_choch', {})
    if bos.get('bos'):
        smc_line += f"\nBOS        : {bos['bos']['message']}"
    if bos.get('choch'):
        smc_line += f"\nCHoCH      : {bos['choch']['message']}"
    swept = r.get('liquidity',{}).get('swept',[])
    if swept:
        smc_line += f"\nLiquidity  : {swept[-1]['message']}"
    pats = r.get('candle_patterns',[])
    if pats:
        smc_line += f"\nCandles    : {', '.join([p['pattern'] for p in pats[:2]])}"
    kz = get_killzone() if SMC_AVAILABLE else {"zone":"N/A","quality":"N/A","note":""}
    smc_block = f"""
━━━━━━━━━━━━━━━━━━━━
🧠 <b>SMC Analysis (Force 7)</b>
Base score: {base}/22 | SMC bonus: +{smc_b} | Total: {score}{smc_line}
Killzone: {kz['zone']} ({kz['quality']}) — {kz['note']}
━━━━━━━━━━━━━━━━━━━━""" if smc_line or smc_b != 0 else ""
    return f"""{emoji} <b>#{rank} CONFLUENCE ALERT — {r['symbol']}</b>
━━━━━━━━━━━━━━━━━━━━
Signal  : <b>{signal}</b>
Score   : <b>{score}</b> (Base:{base}/22 + SMC:+{smc_b})
Price   : ₹{r['price']}
RSI     : {r['rsi']}
Sector  : {r['sector']}

📊 <b>Force Breakdown</b>
F1 Technicals : {r['f1']}/4
F2 Structure  : {r['f2']}/3
F3 Alignment  : {r['f3']}/4
F4 Institutional:{r['f4']}/4
F5 News/FII   : {r['f5']}/3
F6 Risk/Reward: {r['f6']}/4
F7 SMC Bonus  : +{r['f7']}{smc_block}
📌 <b>Trade Setup</b>
Entry   : ₹{r['entry']}
Stop Loss: ₹{r['sl']}
Target 1: ₹{r['target1']} (+8%)
Target 2: ₹{r['target2']} (+15%)
Target 3: ₹{r['target3']} (+22%)

💡 Exit 33% at each target. Move SL to entry after T1.
⚠️ Verify in Zerodha before entering."""


def build_email_confluence(results, today, now, scan_count):
    if not results:
        return "<p>No confluence signals found this scan.</p>"
    results_html = ""
    for r in results:
        score = r['total_score']
        color = "#27ae60" if score >= ULTRA_BUY_SCORE else "#2980b9"
        smc_row = ""
        if r.get('stage') and r['stage'] != 'Unknown':
            smc_parts = [f"Stage: <b>{r['stage']}</b>"]
            if r.get('order_block'):
                ob = r['order_block']
                smc_parts.append(f"OB: ₹{ob['ob_low']}–₹{ob['ob_high']}")
            if r.get('fvg_below'):
                fvg = r['fvg_below']
                smc_parts.append(f"FVG: ₹{fvg['fvg_low']}–₹{fvg['fvg_high']}")
            bos = r.get('bos_choch',{})
            if bos.get('bos'):
                smc_parts.append(bos['bos']['message'])
            smc_row = f"""<tr style='background:#e8f8f5'>
                <td colspan='5' style='padding:8px 12px;font-size:12px;color:#1a5276'>
                🧠 <b>SMC:</b> {' | '.join(smc_parts)} | SMC Bonus: +{r.get('smc_bonus',0)} points
                </td></tr>"""
        details_html = "".join([f"<li style='font-size:12px;margin:2px 0'>{d}</li>" for d in r['details']])
        results_html += f"""
        <div style='background:white;border:1px solid #ddd;border-radius:8px;margin:15px 0;overflow:hidden'>
        <div style='background:{color};color:white;padding:12px 15px'>
        <h3 style='margin:0'>{r['signal']} — {r['symbol']}</h3>
        <p style='margin:4px 0 0;opacity:0.9'>Score: {score} (Base:{r['base_score']}/22 + SMC:+{r.get('smc_bonus',0)}) | ₹{r['price']} | RSI: {r['rsi']} | {r['sector']}</p>
        </div>
        <table border='1' cellpadding='8' style='width:100%;border-collapse:collapse;font-size:13px'>
        <tr style='background:#f8f9fa'>
        <td><b>Entry:</b> ₹{r['entry']}</td><td><b>Stop Loss:</b> ₹{r['sl']}</td>
        <td><b>Target 1:</b> ₹{r['target1']} (+8%)</td>
        <td><b>Target 2:</b> ₹{r['target2']} (+15%)</td>
        <td><b>Target 3:</b> ₹{r['target3']} (+22%)</td>
        </tr>
        {smc_row}
        </table>
        <div style='padding:10px 15px'>
        <b>All 7 Force Details:</b>
        <ul style='margin:8px 0;padding-left:20px'>{details_html}</ul>
        <div style='background:#fff3cd;padding:10px;border-radius:8px;margin-top:10px;font-size:13px'>
        💡 <b>Action plan:</b> Wait for ₹{r['entry']} → Enter → SL at ₹{r['sl']} →
        Book 33% at ₹{r['target1']} → Trail to entry → Hold for ₹{r['target2']} and ₹{r['target3']}
        </div></div></div>"""

    html = f"""<html><body style='font-family:Arial,sans-serif;max-width:900px;margin:auto;padding:20px;color:#2c3e50'>
    <div style='background:linear-gradient(135deg,#1a1a2e,#16213e);padding:20px;border-radius:12px;color:white;margin-bottom:20px'>
    <h1 style='margin:0'>🔥 Confluence Scanner Alert — SMC Edition</h1>
    <p style='margin:5px 0 0;opacity:0.9'>{today} | {now} | {len(results)} signal(s) | {scan_count} stocks scanned</p>
    <p style='margin:5px 0 0;opacity:0.7;font-size:13px'>7-Force System: Technical + Structure + Alignment + Institutional + News + Risk/Reward + SMC Bonus</p>
    </div>
    {results_html}
    <p style='color:#7f8c8d;font-size:12px;margin-top:20px;border-top:1px solid #eee;padding-top:10px'>
    ⚠️ Technical signals only. SMC Force 7 is bonus scoring — base 14/22 threshold still required.<br>
    Total score = base (max 22) + SMC bonus (typically 0–6).<br>
    Position sizing based on ₹2L capital with 2% risk rule.
    </p></body></html>"""
    return html


def log_confluence_to_sheets(signals):
    try:
        sheet = setup_sheets()
        if not sheet: return
        try:
            ws = sheet.worksheet("Signal Log")
        except:
            ws = sheet.add_worksheet(title="Signal Log", rows=5000, cols=20)
            ws.append_row(["Date","Time","Stock","Signal Type","Entry Price",
                           "Target 1 (8%)","Target 2 (15%)","Stop Loss","RSI",
                           "Sector","Efficiency","Scan Type","Outcome",
                           "Exit Price","Return %","Days Held","SMC Stage","SMC Score","Notes"])
        today = datetime.now(IST).strftime('%d %b %Y')
        now_t = datetime.now(IST).strftime('%I:%M %p')
        for r in signals:
            t1 = round(r['entry'] * 1.08, 2)
            t2 = round(r['entry'] * 1.15, 2)
            ws.append_row([
                today, now_t, r['symbol'],
                f"CONFLUENCE {r['total_score']} (SMC:+{r.get('smc_bonus',0)})",
                r['entry'], t1, t2, r['sl'],
                r['rsi'], r['sector'], f"{r['efficiency']}/5",
                "CONFLUENCE", "OPEN", "", "", "",
                r.get('stage',''), r.get('smc_bonus',0), ""
            ])
        print(f"✅ Logged {len(signals)} confluence signals to Signal Log")
    except Exception as e:
        print(f"Confluence signal log error: {e}")


def run():
    today = datetime.now(IST).strftime('%d %b %Y')
    now = datetime.now(IST).strftime('%I:%M %p IST')
    print(f"\n{'='*60}\nConfluence Scanner v2.0 SMC — {today} {now}\n{'='*60}")

    # Killzone check (new)
    if SMC_AVAILABLE:
        kz = get_killzone()
        print(f"Killzone: {kz['zone']} ({kz['quality']}) — {kz['note']}")

    print("Loading market context...")
    sector_signals = get_sector_momentum()
    nifty = analyze_index("^NSEI","Nifty 50")
    banknifty = analyze_index("^NSEBANK","Bank Nifty")
    news = get_news()
    fii_dii = get_fii_dii()
    nifty_dir = nifty['direction'] if nifty else "NEUTRAL"

    if nifty and nifty['direction'] == "BEARISH" and nifty['rsi'] > 65:
        msg = f"⚠️ <b>Confluence Scanner — {today} {now}</b>\n\nMarket is BEARISH today.\nNo buy signals generated.\nProtect existing positions.\n\nNext scan in 2 hours."
        send_telegram(msg)
        print("Market bearish — skipping scan")
        return

    nse_symbols = get_nse_symbols()
    print(f"Scanning {len(nse_symbols)} stocks for 7-force confluence...")

    results = []
    scanned = 0
    for i, symbol in enumerate(nse_symbols):
        try:
            result = calculate_confluence_score(symbol, sector_signals, nifty, banknifty, news, fii_dii)
            if result:
                results.append(result)
                smc_tag = f" | SMC:+{result.get('smc_bonus',0)} | Stage:{result.get('stage','?')}"
                print(f"  ✅ FOUND: {result['symbol']} — {result['total_score']} ({result['base_score']}/22{smc_tag}) — {result['signal']}")
            scanned += 1
            if (i+1) % 300 == 0:
                print(f"  Progress: {i+1}/{len(nse_symbols)} | Qualified: {len(results)}")
            time.sleep(0.4)
        except:
            pass

    results.sort(key=lambda x: x['total_score'], reverse=True)
    top_results = results[:5]

    print(f"\nScan complete! Scanned: {scanned} | Qualified: {len(results)} | Showing top: {len(top_results)}")

    if not top_results:
        kz_note = f"\nKillzone: {kz['zone']} — {kz['note']}" if SMC_AVAILABLE else ""
        msg = f"""🔍 <b>Confluence Scanner v2.0 — {today} {now}</b>

Scanned: {scanned} stocks
Qualified signals: 0

No stock met the 14/22 minimum threshold today.
This is intentional — the filter is strict.

✅ Better to wait than force a trade.{kz_note}
   
Next scan in 2 hours."""
        send_telegram(msg)
        return

    header = f"""🔥 <b>CONFLUENCE ALERT v2.0 SMC — {today} {now}</b>
━━━━━━━━━━━━━━━━━━━━
{len(top_results)} high-conviction signal(s)
from {scanned} stocks | 7-Force system

Score required: 14/22 base minimum
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

    email_body = build_email_confluence(top_results, today, now, scanned)
    ultra_count = len([r for r in top_results if r['total_score'] >= ULTRA_BUY_SCORE])
    subject_prefix = "🔥 ULTRA BUY" if ultra_count > 0 else "⭐ STRONG BUY"
    top_symbol = top_results[0]['symbol'] if top_results else "N/A"
    top_score  = top_results[0]['total_score'] if top_results else 0

    log_confluence_to_sheets(top_results)

    send_email(
        subject=f"{subject_prefix} Confluence SMC Alert {today} | {top_symbol} {top_score} | {len(top_results)} signals",
        body=email_body
    )
    print("\n✅ Confluence scan v2.0 SMC complete!")

run()
