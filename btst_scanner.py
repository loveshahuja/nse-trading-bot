# ============================================================
# BTST SCANNER — Buy Today Sell Tomorrow
# Runs at 2:45 PM IST (15 mins before close)
# Emails at ~3:00 PM after scan completes
#
# WHAT IT LOOKS FOR:
# 1. MOMENTUM — stocks surging into close (gap up tomorrow)
# 2. REVERSAL — stocks bouncing from key support into EOD
# 3. BREAKOUT — stocks breaking resistance in last hour
# 4. INSTITUTIONAL — heavy buying in power hour (2-3:30 PM)
#
# BTST LOGIC:
# - Entry: last 30 mins of today's session
# - Exit: tomorrow at open or within first hour
# - Target: 2-5% overnight/early morning
# - Stop: previous day low or -2% hard stop
# ============================================================

from utils import *
import pytz, math
IST = pytz.timezone("Asia/Kolkata")

# ── Config ────────────────────────────────────────────────────
MIN_PRICE     = 100    # BTST needs enough price movement in Rs
MAX_PRICE     = 5000
MIN_AVG_VOL   = 200000 # Higher liquidity for overnight hold
MAX_RSI_BTST  = 75     # Can be slightly overbought for momentum
MIN_BTST_SCORE = 60
MAX_RESULTS   = 5      # Top 5 BTST picks

BTST_SCAN_LIST_SIZE = 300  # Scan focused list, not all 2367


# ============================================================
# BTST SIGNAL 1: EOD MOMENTUM
# Stock surging in last hour with volume — likely to gap up
# ============================================================
def score_eod_momentum(df_daily, df_intraday, curr, avg_vol_20d):
    score = 0
    notes = []
    try:
        # Daily: price near day's high at close = bullish
        if df_intraday is not None and not df_intraday.empty:
            day_high = float(df_intraday["High"].squeeze().max())
            day_low  = float(df_intraday["Low"].squeeze().min())
            day_open = float(df_intraday["Open"].squeeze().iloc[0])
            day_range = day_high - day_low

            # Price closing near high of day
            if day_range > 0:
                close_pos = (curr - day_low) / day_range * 100
                if close_pos >= 75:
                    score += 15
                    notes.append(f"✅ Closing near day high ({close_pos:.0f}% of range) — bullish EOD")
                elif close_pos >= 55:
                    score += 8
                    notes.append(f"⚠️ Mid-upper range ({close_pos:.0f}%) — mild bullish")
                else:
                    score -= 5
                    notes.append(f"❌ Closing near day low ({close_pos:.0f}%) — bearish EOD")

            # Today's volume vs 20-day avg
            today_vol = float(df_intraday["Volume"].squeeze().sum()) if "Volume" in df_intraday.columns else 0
            if today_vol > 0 and avg_vol_20d > 0:
                vol_ratio = today_vol / avg_vol_20d
                if vol_ratio >= 2.5:
                    score += 12
                    notes.append(f"✅ Volume {vol_ratio:.1f}x avg — heavy buying today")
                elif vol_ratio >= 1.5:
                    score += 6
                    notes.append(f"⚠️ Volume {vol_ratio:.1f}x avg — above average")
                else:
                    notes.append(f"ℹ️ Volume {vol_ratio:.1f}x avg — normal")

            # Today up from open
            day_chg_from_open = (curr - day_open) / day_open * 100
            if day_chg_from_open >= 2:
                score += 8
                notes.append(f"✅ +{day_chg_from_open:.1f}% from open — strong intraday momentum")
            elif day_chg_from_open >= 0.5:
                score += 4
                notes.append(f"⚠️ +{day_chg_from_open:.1f}% from open — mild momentum")
            elif day_chg_from_open < -1:
                score -= 8
                notes.append(f"❌ {day_chg_from_open:.1f}% from open — intraday weakness")

    except Exception as e:
        print(f"EOD momentum error: {e}")
    return score, notes


# ============================================================
# BTST SIGNAL 2: EOD REVERSAL
# Stock bouncing from support in last session — reversal play
# ============================================================
def score_eod_reversal(df_daily, curr):
    score = 0
    notes = []
    try:
        sr = pa_sr_zones(df_daily, curr)
        sup = sr.get("nearest_sup")

        if sup:
            dist = (curr - sup["price"]) / curr * 100
            if dist <= 2 and sup["touches"] >= 2:
                score += 18
                notes.append(f"✅ REVERSAL at {sup['touches']}x support ₹{sup['price']} — classic BTST bounce")
            elif dist <= 4 and sup["touches"] >= 2:
                score += 10
                notes.append(f"⚠️ Near {sup['touches']}x support ₹{sup['price']} ({dist:.1f}% away)")

        # Check last 3 candles for reversal pattern
        closes = df_daily["Close"].squeeze().values.astype(float)
        lows   = df_daily["Low"].squeeze().values.astype(float)
        opens  = df_daily["Open"].squeeze().values.astype(float)

        # Today closed up after being down intraday = reversal candle
        if closes[-1] > opens[-1]:  # bullish candle today
            lower_wick = opens[-1] - lows[-1]
            body = closes[-1] - opens[-1]
            if lower_wick > body * 1.5:
                score += 10
                notes.append("✅ Hammer/reversal candle today — buyers defended lows")

        # Yesterday closed down, today closing up = reversal
        if closes[-2] < opens[-2] and closes[-1] > opens[-1]:
            score += 6
            notes.append("✅ Yesterday down → today up — reversal in progress")

    except Exception as e:
        print(f"EOD reversal error: {e}")
    return score, notes


# ============================================================
# BTST SIGNAL 3: LATE SESSION BREAKOUT
# Breaking above resistance in power hour = strong for tomorrow
# ============================================================
def score_late_breakout(df_daily, curr):
    score = 0
    notes = []
    try:
        sr   = pa_sr_zones(df_daily, curr)
        ress = sr.get("resistances", [])

        if ress:
            res = ress[0]
            dist = (curr - res["price"]) / res["price"] * 100
            # Just broke above resistance (within 2%)
            if -1 <= dist <= 3 and res["touches"] >= 2:
                score += 20
                notes.append(f"🚀 BREAKOUT above {res['touches']}x resistance ₹{res['price']} — momentum play")
            elif 3 < dist <= 6 and res["touches"] >= 2:
                score += 10
                notes.append(f"⚠️ Recently broke ₹{res['price']} ({res['touches']}x) — continuation possible")

        # 52-week high breakout (very strong BTST)
        high_52w = float(df_daily["High"].squeeze().tail(252).max()) if len(df_daily) >= 252 else float(df_daily["High"].squeeze().max())
        if curr >= high_52w * 0.99:
            score += 15
            notes.append("🔥 Near 52-week HIGH — breakout with no overhead resistance")

    except Exception as e:
        print(f"Late breakout error: {e}")
    return score, notes


# ============================================================
# BTST SIGNAL 4: INSTITUTIONAL POWER HOUR ACTIVITY
# Heavy volume in 2-3:30 PM = institutions accumulating
# ============================================================
def score_institutional_eod(df_daily, avg_vol_20d):
    score = 0
    notes = []
    try:
        # Use daily volume as proxy
        lat_vol = float(df_daily["Volume"].squeeze().iloc[-1])
        if avg_vol_20d > 0:
            vol_ratio = lat_vol / avg_vol_20d
            if vol_ratio >= 3:
                score += 15
                notes.append(f"✅ {vol_ratio:.1f}x avg volume — strong institutional day")
            elif vol_ratio >= 2:
                score += 8
                notes.append(f"✅ {vol_ratio:.1f}x avg volume — above average institutional")

        # 5-day price trend
        closes = df_daily["Close"].squeeze().values.astype(float)
        if len(closes) >= 5:
            trend_5d = (closes[-1] - closes[-5]) / closes[-5] * 100
            if trend_5d >= 5:
                score += 8
                notes.append(f"✅ +{trend_5d:.1f}% in 5 days — sustained momentum")
            elif trend_5d >= 2:
                score += 4
                notes.append(f"⚠️ +{trend_5d:.1f}% in 5 days — mild momentum")
            elif trend_5d < -3:
                score -= 8
                notes.append(f"❌ {trend_5d:.1f}% in 5 days — weak trend, risky BTST")

    except Exception as e:
        print(f"Institutional EOD error: {e}")
    return score, notes


# ============================================================
# BTST TARGETS
# Different from swing trades — tighter, overnight only
# ============================================================
def btst_targets(curr, df_daily):
    try:
        sr   = pa_sr_zones(df_daily, curr)
        ress = sr.get("resistances", [])
        sup  = sr.get("nearest_sup")

        # SL: previous day's low or 2% hard stop (whichever is closer)
        prev_low  = float(df_daily["Low"].squeeze().iloc[-2])
        hard_sl   = round(curr * 0.98, 2)
        sl        = round(max(prev_low * 0.995, hard_sl), 2)
        sl_pct    = round((curr - sl) / curr * 100, 1)
        sl_note   = f"Below prev day low ₹{prev_low:.2f} (2% hard cap)"

        # T1: 2-4% overnight gap target
        if ress:
            t1 = round(ress[0]["price"] * 0.99, 2)
            t1_pct = round((t1 - curr) / curr * 100, 1)
            if t1_pct < 1.5:  # too close
                t1 = round(curr * 1.025, 2)
                t1_pct = 2.5
            t1_note = f"Near resistance ₹{ress[0]['price']} or 2.5% gap target"
        else:
            t1 = round(curr * 1.03, 2)
            t1_pct = 3.0
            t1_note = "3% gap target (no resistance above)"

        # T2: if strong gap, ride to next resistance
        if len(ress) > 1:
            t2 = round(ress[1]["price"] * 0.99, 2)
            t2_pct = round((t2 - curr) / curr * 100, 1)
            t2_note = f"2nd resistance ₹{ress[1]['price']} (if strong gap)"
        else:
            t2 = round(curr * 1.05, 2)
            t2_pct = 5.0
            t2_note = "5% extended target"

        rr = round((t1 - curr) / (curr - sl), 1) if (curr - sl) > 0 else 0

        return {
            "sl": sl, "sl_pct": sl_pct, "sl_note": sl_note,
            "t1": t1, "t1_pct": t1_pct, "t1_note": t1_note,
            "t2": t2, "t2_pct": t2_pct, "t2_note": t2_note,
            "rr": rr
        }
    except Exception as e:
        print(f"BTST target error: {e}")
        return {
            "sl": round(curr*0.98,2), "sl_pct": 2.0, "sl_note": "2% hard stop",
            "t1": round(curr*1.03,2), "t1_pct": 3.0, "t1_note": "3% gap",
            "t2": round(curr*1.05,2), "t2_pct": 5.0, "t2_note": "5% extended",
            "rr": 1.5
        }


# ============================================================
# MASTER BTST ANALYSER
# ============================================================
def analyse_btst(symbol, sector_signals, nifty_cond):
    try:
        sym       = symbol if ".NS" in symbol else symbol + ".NS"
        sym_clean = sym.replace(".NS", "")

        # Daily data (for S/R, trend, stage)
        df_d = yf.download(sym, period="12mo", interval="1d",
                           auto_adjust=True, progress=False)
        if df_d is None or df_d.empty or len(df_d) < 30:
            return None
        df_d.columns = [str(c[0]).capitalize() if isinstance(c, tuple)
                        else str(c).capitalize() for c in df_d.columns]

        close  = df_d["Close"].squeeze()
        volume = df_d["Volume"].squeeze()
        curr   = float(close.iloc[-1])
        prev   = float(close.iloc[-2])

        if curr < MIN_PRICE or curr > MAX_PRICE: return None
        avg_vol = float(volume.tail(20).mean())
        if avg_vol < MIN_AVG_VOL: return None
        rsi_now = float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
        if rsi_now > MAX_RSI_BTST: return None

        ema20 = float(ta.trend.EMAIndicator(close, 20).ema_indicator().iloc[-1])
        ema50 = float(ta.trend.EMAIndicator(close, 50).ema_indicator().iloc[-1])

        # Hard veto: downtrend — BTST doesn't work against trend
        if ema20 < ema50 * 0.97 and rsi_now < 40: return None

        # Try intraday data for today's action
        df_i = None
        try:
            df_i = yf.download(sym, period="1d", interval="5m",
                               auto_adjust=True, progress=False)
            if df_i is not None and not df_i.empty:
                df_i.columns = [str(c[0]).capitalize() if isinstance(c, tuple)
                                else str(c).capitalize() for c in df_i.columns]
        except:
            pass

        score = 0
        notes = []
        btst_type = "UNKNOWN"

        # Determine primary BTST type
        m_score, m_notes = score_eod_momentum(df_d, df_i, curr, avg_vol)
        r_score, r_notes = score_eod_reversal(df_d, curr)
        b_score, b_notes = score_late_breakout(df_d, curr)
        i_score, i_notes = score_institutional_eod(df_d, avg_vol)

        # Pick dominant type and add all scores
        scores_map = {"MOMENTUM": m_score, "REVERSAL": r_score, "BREAKOUT": b_score}
        btst_type  = max(scores_map, key=scores_map.get)
        if scores_map[btst_type] <= 0: return None

        score = m_score + r_score + b_score + i_score
        notes = m_notes + r_notes + b_notes + i_notes

        # Nifty alignment
        if nifty_cond == "BULLISH":     score += 8; notes.append("✅ Nifty BULLISH — supports BTST")
        elif nifty_cond == "BEARISH":   score -= 10; notes.append("🔴 Nifty BEARISH — risky BTST, avoid")
        elif nifty_cond == "OVERBOUGHT": score -= 3; notes.append("⚠️ Nifty OVERBOUGHT — gap may fade")
        else:                           score += 3; notes.append("⚠️ Nifty NEUTRAL")

        # Sector alignment
        sector   = get_stock_sector(sym)
        sec_mood = sector_signals.get(sector, "NEUTRAL 🟡")
        if "BULLISH" in sec_mood:   score += 5; notes.append(f"✅ Sector {sector} BULLISH")
        elif "BEARISH" in sec_mood: score -= 5; notes.append(f"⚠️ Sector {sector} BEARISH")

        score = min(100, max(0, score))
        if score < MIN_BTST_SCORE: return None

        # BTST targets (tighter than swing)
        lv = btst_targets(curr, df_d)
        if lv["rr"] < 1.5: return None

        day_chg = round((curr - prev) / prev * 100, 2)
        lot     = FON_LOT_SIZES.get(sym_clean, 0)

        if score >= 80:   signal = "STRONG BTST 🔥"
        elif score >= 68: signal = "BTST BUY ⭐"
        else:             signal = "BTST WATCH 👀"

        return {
            "symbol":    sym_clean,
            "price":     round(curr, 2),
            "day_chg":   day_chg,
            "signal":    signal,
            "score":     score,
            "btst_type": btst_type,
            "rsi":       round(rsi_now, 1),
            "sector":    sector,
            "is_fno":    lot > 0,
            "lot":       lot,
            "sl":        lv["sl"],  "sl_pct":  lv["sl_pct"],  "sl_note":  lv["sl_note"],
            "t1":        lv["t1"],  "t1_pct":  lv["t1_pct"],  "t1_note":  lv["t1_note"],
            "t2":        lv["t2"],  "t2_pct":  lv["t2_pct"],  "t2_note":  lv["t2_note"],
            "rr":        lv["rr"],
            "notes":     notes,
        }
    except Exception as e:
        return None


# ============================================================
# EMAIL BUILDER
# ============================================================
def build_btst_email(results, today, now_str, nifty_cond, nifty_rsi, fii_net):
    if not results:
        return "<p>No qualifying BTST setups found today.</p>"

    fii_color = "#27ae60" if fii_net and fii_net > 0 else "#e74c3c"
    fii_txt   = f"₹{abs(fii_net):,.0f} Cr {'BUYING 🟢' if fii_net > 0 else 'SELLING 🔴'}" if fii_net else "Data N/A"
    nifty_color = "#27ae60" if nifty_cond == "BULLISH" else "#e74c3c" if nifty_cond == "BEARISH" else "#f39c12"

    rows = ""
    for r in results:
        notes_html = "".join(f"<li style='font-size:12px;margin:3px 0'>{n}</li>" for n in r["notes"])
        color = "#1a5276" if r["score"] >= 80 else "#6c3483" if r["btst_type"] == "REVERSAL" else "#1e8449"
        badge_color = {"MOMENTUM":"#e67e22","REVERSAL":"#8e44ad","BREAKOUT":"#1a5276"}.get(r["btst_type"],"#27ae60")
        qty = int(200000*0.02/(r["price"]*r["sl_pct"]/100)) if r["price"]*r["sl_pct"]>0 else 0

        rows += f"""
        <div style='background:white;border:1px solid #ddd;border-radius:8px;margin:20px 0;overflow:hidden;box-shadow:0 2px 4px rgba(0,0,0,0.1)'>
        <div style='background:{color};color:white;padding:15px;display:flex;justify-content:space-between;align-items:center'>
        <div>
        <h2 style='margin:0'>{r['signal']} — {r['symbol']}</h2>
        <p style='margin:4px 0 0;opacity:.9'>Score: {r['score']}/100 | ₹{r['price']} ({r['day_chg']:+.2f}%) | RSI {r['rsi']} | {r['sector']}</p>
        </div>
        <div style='background:{badge_color};padding:6px 14px;border-radius:20px;font-weight:bold;font-size:14px'>
        {r['btst_type']}
        </div></div>

        <div style='padding:15px;background:#fafafa;border-bottom:1px solid #eee'>
        <h3 style='margin:0 0 10px;color:#2c3e50'>BTST Trade Plan — Enter today, exit tomorrow morning</h3>
        <table border='0' cellpadding='0' style='width:100%;font-size:14px'>
        <tr>
        <td style='padding:6px 12px;background:#eaf4fb;border-radius:6px;margin:4px'>
        <b>Entry (today 2:45-3:30 PM):</b><br>₹{r['price']} (current) — enter with limit order</td>
        <td style='padding:6px 12px;background:#fdf2f8;border-radius:6px;margin:4px'>
        <b>Stop Loss:</b><br>₹{r['sl']} (-{r['sl_pct']}%)<br><small style='color:#888'>{r['sl_note']}</small></td>
        <td style='padding:6px 12px;background:#eafaf1;border-radius:6px;margin:4px'>
        <b>Target 1 (tomorrow open/morning):</b><br>₹{r['t1']} (+{r['t1_pct']}%)<br><small style='color:#888'>{r['t1_note']}</small></td>
        <td style='padding:6px 12px;background:#e8f8f5;border-radius:6px;margin:4px'>
        <b>Target 2 (if strong gap up):</b><br>₹{r['t2']} (+{r['t2_pct']}%)<br><small style='color:#888'>{r['t2_note']}</small></td>
        </tr></table>
        <p style='margin:10px 0 0;font-size:13px'>
        <b>R/R:</b> 1:{r['rr']} | <b>Position (2% risk on ₹2L):</b> {qty} shares = ₹{qty*r['price']:,.0f} | <b>Max loss:</b> ₹{round(qty*r['price']*r['sl_pct']/100):,}
        {'| <b>F&O:</b> Lot '+str(r['lot']) if r['is_fno'] else ''}
        </p></div>

        <div style='padding:15px'>
        <b>Why this BTST setup:</b>
        <ul style='margin:8px 0;padding-left:18px'>{notes_html}</ul>
        <div style='background:#fff3cd;padding:12px;border-radius:6px;margin-top:10px;font-size:13px;border-left:4px solid #f39c12'>
        <b>⚡ BTST Rules:</b><br>
        1. Enter in last 30 mins of today (2:45–3:30 PM)<br>
        2. Set SL order immediately after entry<br>
        3. Tomorrow at open — if gap up ≥1.5%, book 50% immediately<br>
        4. If no gap or gap down → exit at open, don't hold<br>
        5. Max hold: tomorrow 11 AM. Don't convert to swing without fresh analysis.
        </div></div></div>"""

    html = f"""<html><body style='font-family:Arial,sans-serif;max-width:950px;margin:auto;padding:20px;color:#2c3e50'>
    <div style='background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);padding:20px;border-radius:12px;color:white;margin-bottom:25px'>
    <h1 style='margin:0'>⚡ BTST Scanner — Buy Today Sell Tomorrow</h1>
    <p style='margin:6px 0 0;opacity:.9'>{today} | {now_str} | {len(results)} setup(s) identified</p>
    <p style='margin:4px 0 0;opacity:.75;font-size:13px'>EOD Momentum + Reversal + Breakout + Institutional Power Hour Activity</p>
    <div style='margin-top:12px;display:flex;gap:15px'>
    <span style='background:rgba(255,255,255,.15);padding:6px 12px;border-radius:20px;font-size:13px'>
    Nifty: <b style='color:{nifty_color}'>{nifty_cond}</b> (RSI {nifty_rsi:.0f})</span>
    <span style='background:rgba(255,255,255,.15);padding:6px 12px;border-radius:20px;font-size:13px'>
    FII: <b style='color:{fii_color}'>{fii_txt}</b></span>
    </div></div>

    <div style='background:#fff3cd;padding:12px;border-radius:8px;border-left:4px solid #f39c12;margin-bottom:20px;font-size:13px'>
    <b>⚠️ BTST Risk Reminder:</b> Overnight trades carry gap risk from global events.
    Never risk more than 2% capital per BTST trade. Always place stop loss before market closes.
    Exit tomorrow morning regardless — don't hold as a swing trade without fresh analysis.
    </div>

    {rows}

    <p style='color:#999;font-size:12px;margin-top:25px;border-top:1px solid #eee;padding-top:15px'>
    Generated at {now_str} | Enter in last 30 mins of today's session (2:45–3:30 PM IST)<br>
    Technical analysis only. Past performance does not guarantee future results.
    </p></body></html>"""
    return html


# ============================================================
# TELEGRAM SUMMARY
# ============================================================
def build_btst_telegram(results, today, now_str, nifty_cond, nifty_rsi):
    if not results:
        return f"""⚡ <b>BTST Scanner — {today} {now_str}</b>

No qualifying BTST setups found today.
Market: {nifty_cond} (RSI {nifty_rsi:.0f})

✅ No trade = valid decision for BTST.
📧 Email sent with market context."""

    badge_map = {"MOMENTUM":"📈 MOMENTUM","REVERSAL":"🔄 REVERSAL","BREAKOUT":"🚀 BREAKOUT"}
    msg = f"""⚡ <b>BTST SCANNER — {today} {now_str}</b>
━━━━━━━━━━━━━━━━━━━━
{len(results)} setup(s) | Enter 2:45–3:30 PM
Market: {nifty_cond} (RSI {nifty_rsi:.0f})
📧 Full details sent to Gmail
━━━━━━━━━━━━━━━━━━━━\n"""

    for i, r in enumerate(results, 1):
        badge = badge_map.get(r["btst_type"], r["btst_type"])
        msg += f"""
{i}. <b>{r['symbol']}</b> — {badge}
   Score: {r['score']}/100 | ₹{r['price']} ({r['day_chg']:+.2f}%) | RSI {r['rsi']}
   Entry: ₹{r['price']} | SL: ₹{r['sl']} (-{r['sl_pct']}%)
   T1: ₹{r['t1']} (+{r['t1_pct']}%) | T2: ₹{r['t2']} (+{r['t2_pct']}%)
   R/R: 1:{r['rr']} | {r['sector']}{'| F&O ✅' if r['is_fno'] else ''}
"""
    msg += "\n⚠️ Enter last 30 mins today | Exit tomorrow open/morning"
    return msg


# ============================================================
# MAIN
# ============================================================
def run():
    today   = datetime.now(IST).strftime('%d %b %Y')
    now_str = datetime.now(IST).strftime('%I:%M %p IST')
    print(f"\n{'='*60}\nBTST Scanner — {today} {now_str}\n{'='*60}")

    # Market condition
    nifty_cond, nifty_rsi = pa_nifty_condition()
    fii_dii = get_fii_dii()
    fii_net = fii_dii.get("fii_net", 0) or 0
    print(f"Nifty: {nifty_cond} | RSI: {nifty_rsi:.1f} | FII: {fii_net:+,.0f} Cr")

    # Hard stop — no BTST in bearish market
    if nifty_cond == "BEARISH":
        msg = f"""⚡ <b>BTST Scanner — {today} {now_str}</b>

🔴 Nifty BEARISH — no BTST setups recommended
Gap-down risk is high in bearish market.
Protect existing positions instead.

Next BTST scan tomorrow 2:45 PM."""
        send_telegram(msg)
        send_email(
            subject=f"BTST Scanner {today} — No trades (Nifty BEARISH)",
            body=f"<html><body><h2>BTST Scanner — {today}</h2><p>Nifty is BEARISH (RSI {nifty_rsi:.0f}). No BTST recommendations today. Gap-down risk too high.</p></body></html>"
        )
        return

    sector_signals = get_sector_momentum()

    # Build focused scan list
    # Priority: bullish sector stocks + high volume stocks + NSE 500
    sector_stocks = []
    for sector, mood in sector_signals.items():
        if "BULLISH" in mood:
            sector_stocks.extend(SECTOR_MAP.get(sector, [])[:8])

    # Add portfolio stocks
    portfolio = get_portfolio_symbols()
    scan_list = list(set(portfolio + sector_stocks))[:BTST_SCAN_LIST_SIZE]

    # If still small, add fallback popular stocks
    if len(scan_list) < 100:
        fallback = get_fallback_symbols()[:200]
        scan_list = list(set(scan_list + fallback))[:BTST_SCAN_LIST_SIZE]

    print(f"Scanning {len(scan_list)} stocks for BTST setups...")
    results = []
    for i, sym in enumerate(scan_list):
        try:
            r = analyse_btst(sym, sector_signals, nifty_cond)
            if r:
                results.append(r)
                print(f"  BTST: {r['symbol']} {r['score']}/100 | {r['btst_type']} | "
                      f"T1:+{r['t1_pct']}% | R/R:{r['rr']}")
            if (i+1) % 50 == 0:
                print(f"  Progress: {i+1}/{len(scan_list)} | Found: {len(results)}")
            time.sleep(0.4)
        except: pass

    results.sort(key=lambda x: x["score"], reverse=True)
    top = results[:MAX_RESULTS]
    print(f"\nDone. Found:{len(results)} | Top:{len(top)}")

    # Send Telegram
    tg_msg = build_btst_telegram(top, today, now_str, nifty_cond, nifty_rsi)
    send_telegram(tg_msg)

    # Send Email
    email_html = build_btst_email(top, today, now_str, nifty_cond, nifty_rsi, fii_net)
    subject_tag = f"{top[0]['symbol']} {top[0]['score']}/100 {top[0]['btst_type']}" if top else "No setups"
    send_email(
        subject=f"⚡ BTST Scanner {today} | {subject_tag} | {len(top)} setup(s)",
        body=email_html
    )
    print("✅ BTST scan complete!")

run()
