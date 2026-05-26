# ============================================================
# EVENING UPDATE v3.0 — 8:00 PM IST
# Full closing report: P&L + tomorrow's preview + market wrap
# ============================================================
from utils import *
import pytz
IST = pytz.timezone("Asia/Kolkata")

def get_open_trades(sheet):
    try:
        ws = sheet.worksheet("Open Trades")
        return ws.get_all_records()
    except Exception as e:
        print(f"Trades error: {e}")
        return []

def get_closing_price(symbol):
    try:
        import math
        ticker = symbol if ".NS" in symbol else symbol + ".NS"
        df = yf.download(ticker, period="1mo", interval="1d",
                         progress=False, auto_adjust=True)
        if not df.empty and len(df) >= 2:
            close = df['Close'].squeeze()
            curr  = float(close.iloc[-1])
            prev  = float(close.iloc[-2])
            if math.isnan(curr) or math.isnan(prev):
                return None
            rsi_val = ta.momentum.RSIIndicator(close).rsi().iloc[-1]
            rsi     = round(float(rsi_val), 1) if not math.isnan(float(rsi_val)) else 50.0
            vol     = float(df['Volume'].squeeze().iloc[-1])
            avg_vol = float(df['Volume'].squeeze().tail(20).mean())
            ema20   = float(ta.trend.EMAIndicator(close, 20).ema_indicator().iloc[-1])
            ema50   = float(ta.trend.EMAIndicator(close, 50).ema_indicator().iloc[-1])
            macd_obj = ta.trend.MACD(close)
            ml      = float(macd_obj.macd().iloc[-1])
            sl_val  = float(macd_obj.macd_signal().iloc[-1])
            print(f"  ✅ {symbol}: ₹{curr:.2f} RSI:{rsi}")
            return {
                "current":  round(curr, 2),
                "prev":     round(prev, 2),
                "rsi":      rsi,
                "day_chg":  round(((curr - prev) / prev) * 100, 2),
                "vol":      int(vol),
                "avg_vol":  int(avg_vol),
                "vol_ratio": round(vol / avg_vol, 1) if avg_vol > 0 else 1.0,
                "trend":    "UP" if ema20 > ema50 else "DOWN",
                "macd":     "BULLISH" if ml > sl_val else "BEARISH",
            }
    except Exception as e:
        print(f"  ❌ Price error {symbol}: {e}")
    return None

def get_overnight_action(trade, price_data, nifty_direction):
    """Decide what to do overnight — hold, exit, or trail SL."""
    entry   = float(trade.get('Entry Price', 0))
    target  = float(trade.get('Target', entry * 1.1))
    sl      = float(trade.get('Stop Loss', entry * 0.97))
    days    = int(trade.get('Days Held', 0))
    curr    = price_data['current']
    rsi     = price_data['rsi']
    pnl_pct = ((curr - entry) / entry) * 100

    if curr <= sl:
        return "🛑 EXIT AT OPEN TOMORROW", \
               f"SL hit at ₹{sl:.2f}. Place sell order tonight for tomorrow open. Do not hold.", "red"
    if curr >= target:
        return "🎯 BOOK PROFITS TOMORROW", \
               f"Target ₹{target:.2f} hit! Sell 75% at open tomorrow. Move SL to entry for remaining 25%.", "green"
    if rsi > 80:
        return "⚠️ PARTIAL EXIT TOMORROW", \
               f"RSI {rsi:.0f} very overbought. Book 50% at tomorrow open. Set trailing SL on rest.", "orange"
    if pnl_pct > 15:
        return "✅ TRAIL SL TONIGHT", \
               f"Excellent gain {pnl_pct:.1f}%. Move SL up to entry ₹{entry:.2f} — protect profits overnight.", "green"
    if days > 12 and pnl_pct < 3:
        return "⚠️ REVIEW TONIGHT", \
               f"Held {days} days, only {pnl_pct:.1f}% gain. Consider exiting and deploying capital better.", "orange"
    if curr < entry * 0.97:
        return "🔴 CLOSE TO SL", \
               f"Down {abs(pnl_pct):.1f}%. SL at ₹{sl:.2f} is very close. Be ready to exit at open.", "red"
    if nifty_direction == "BEARISH" and pnl_pct > 5:
        return "⚠️ BOOK PARTIAL", \
               f"Market bearish overnight. Book 50% profits at ₹{curr:.2f}. Protect gains.", "orange"
    if pnl_pct > 5:
        return "✅ HOLD OVERNIGHT", \
               f"Good position +{pnl_pct:.1f}%. Hold overnight. SL at ₹{sl:.2f}. Target ₹{target:.2f}.", "green"
    return "✅ HOLD OVERNIGHT", \
           f"Position intact. P&L {pnl_pct:+.1f}%. SL ₹{sl:.2f} | Target ₹{target:.2f}. Hold for tomorrow.", "blue"

def get_tomorrow_preview(sector_signals, nifty, fii_dii, global_data):
    """Build tomorrow's market preview based on today's close."""
    lines = []

    # Global cues
    dow  = global_data.get('US_DOW', {})
    vix  = global_data.get('VIX', {})
    crude = global_data.get('CRUDE_OIL', {})
    if dow.get('change_pct', 0) > 0.5:
        lines.append("🟢 US markets positive — expect gap-up opening tomorrow")
    elif dow.get('change_pct', 0) < -0.5:
        lines.append("🔴 US markets negative — expect gap-down opening tomorrow")
    else:
        lines.append("🟡 US markets flat — neutral opening expected tomorrow")

    if vix.get('price', 0) > 20:
        lines.append(f"⚠️ VIX at {vix.get('price',0):.1f} — high fear, volatile session expected")
    else:
        lines.append(f"✅ VIX at {vix.get('price',0):.1f} — calm market conditions")

    if crude.get('change_pct', 0) > 2:
        lines.append("⚠️ Crude oil rising — may pressure energy stocks and inflation")
    elif crude.get('change_pct', 0) < -2:
        lines.append("✅ Crude oil falling — positive for India markets")

    # FII signal
    fii = fii_dii.get('fii_net', 0) or 0
    if fii > 1000:
        lines.append(f"🟢 FII bought ₹{fii:,.0f} Cr today — bullish for tomorrow")
    elif fii < -1000:
        lines.append(f"🔴 FII sold ₹{abs(fii):,.0f} Cr today — cautious for tomorrow")

    # Nifty close
    if nifty:
        if nifty['direction'] == "BULLISH":
            lines.append(f"✅ Nifty closed bullish at {nifty['level']:,.0f} — uptrend intact")
        elif nifty['direction'] == "BEARISH":
            lines.append(f"🔴 Nifty closed bearish at {nifty['level']:,.0f} — avoid new buys tomorrow")
        else:
            lines.append(f"🟡 Nifty closed neutral at {nifty['level']:,.0f} — wait for direction")

    # Best sectors for tomorrow
    bull_sectors = [s for s, m in sector_signals.items() if "BULLISH" in m]
    bear_sectors = [s for s, m in sector_signals.items() if "BEARISH" in m]
    if bull_sectors:
        lines.append(f"🟢 Best sectors tomorrow: {', '.join(bull_sectors[:3])}")
    if bear_sectors:
        lines.append(f"🔴 Avoid sectors tomorrow: {', '.join(bear_sectors[:3])}")

    return lines

def build_tg_evening(today, now, global_data, fii_dii, nifty, banknifty,
                     sector_signals, trades_data, tomorrow_lines, total_pnl):
    nifty_txt = f"{nifty['level']:,.0f} ({nifty['change_pct']:+.2f}%) | {nifty['mood']}" if nifty else "N/A"
    bn_txt    = f"{banknifty['level']:,.0f} ({banknifty['change_pct']:+.2f}%) | {banknifty['mood']}" if banknifty else "N/A"

    fii = fii_dii.get('fii_net')
    fii_txt = f"₹{abs(fii):,.0f} Cr {'BOUGHT 🟢' if fii > 0 else 'SOLD 🔴'}" if fii is not None else "N/A"
    dii = fii_dii.get('dii_net')
    dii_txt = f"₹{abs(dii):,.0f} Cr {'BOUGHT 🟢' if dii > 0 else 'SOLD 🔴'}" if dii is not None else "N/A"

    trades_txt = ""
    for t in trades_data:
        e = "🟢" if t['pnl'] >= 0 else "🔴"
        trades_txt += f"""
{e} <b>{t['symbol']}</b> (Day {t['days']})
Entry ₹{t['entry']} → Close ₹{t['current']} ({t['day_chg']:+.1f}% today)
P&L: ₹{t['pnl']:+,.0f} ({t['pnl_pct']:+.1f}%) | RSI: {t['rsi']}
{t['action']}: {t['reason'][:80]}
"""
    if not trades_txt:
        trades_txt = "No open trades.\n"

    tomorrow_txt = "\n".join(f"• {l}" for l in tomorrow_lines)
    total_e = "🟢" if total_pnl >= 0 else "🔴"

    return f"""🌙 <b>EVENING UPDATE — {today} {now}</b>
⏰ NSE Closing Prices

━━━━━━━━━━━━━━━━━━━━
📊 <b>TODAY'S CLOSING</b>
Nifty 50  : {nifty_txt}
BankNifty : {bn_txt}
FII Today : {fii_txt}
DII Today : {dii_txt}

━━━━━━━━━━━━━━━━━━━━
💼 <b>YOUR TRADES — CLOSING P&L</b>
{trades_txt}
{total_e} <b>Total P&L Today: ₹{total_pnl:+,.0f}</b>

━━━━━━━━━━━━━━━━━━━━
🔭 <b>TOMORROW'S PREVIEW</b>
{tomorrow_txt}

━━━━━━━━━━━━━━━━━━━━
📧 Full report sent to Gmail
⏰ Next scan: Tomorrow 8:00 AM IST"""

def build_email_evening(today, now, global_data, fii_dii, news, nifty,
                        banknifty, sensex, sector_signals, trades_data,
                        tomorrow_lines, top5_tomorrow):
    # Index rows
    i_rows = ""
    for idx in [nifty, banknifty, sensex]:
        if not idx: continue
        mc = mood_color(idx['mood'])
        cc = "#27ae60" if idx['change_pct'] > 0 else "#e74c3c"
        close_note = "Closed positive ✅" if idx['change_pct'] > 0.3 \
                     else "Closed negative ⚠️" if idx['change_pct'] < -0.3 \
                     else "Closed flat 🟡"
        i_rows += f"""<tr>
            <td><b>{idx['name']}</b></td><td><b>{idx['level']:,.2f}</b></td>
            <td style='color:{cc}'>{idx['change_pct']:+.2f}%</td>
            <td>{idx['rsi']}</td><td>{idx['trend']}</td><td>{idx['macd']}</td>
            <td>₹{idx['support']:,.0f}</td><td>₹{idx['resistance']:,.0f}</td>
            <td style='color:{mc}'><b>{idx['mood']}</b></td>
            <td style='font-size:12px;color:#555'>{close_note}</td>
        </tr>"""

    # Trades rows
    t_rows = ""
    total_pnl = 0; total_invested = 0; total_current = 0
    for t in trades_data:
        pc = "#27ae60" if t['pnl'] >= 0 else "#e74c3c"
        dc = "#27ae60" if t['day_chg'] >= 0 else "#e74c3c"
        ac = {"red": "#e74c3c", "green": "#27ae60",
              "orange": "#f39c12", "blue": "#3498db"}.get(t['color'], "#333")
        total_pnl      += t['pnl']
        total_invested += t['entry'] * t['qty']
        total_current  += t['current'] * t['qty']
        progress_pct = min(100, max(0,
            ((t['current'] - t['entry']) / (t['target'] - t['entry']) * 100)
        )) if t['target'] != t['entry'] else 0
        t_rows += f"""<tr>
            <td><b>{t['symbol']}</b><br><span style='font-size:11px;color:#888'>Day {t['days']}</span></td>
            <td>₹{t['entry']}</td><td>₹{t['current']}</td>
            <td style='color:{dc}'>{t['day_chg']:+.2f}%</td>
            <td style='color:{pc}'><b>₹{t['pnl']:+,.0f}</b></td>
            <td style='color:{pc}'><b>{t['pnl_pct']:+.1f}%</b></td>
            <td>{t['rsi']}</td>
            <td>{t['trend']} | {t['macd']}</td>
            <td>₹{t['target']} | ₹{t['sl']}</td>
            <td style='font-size:11px'><div style='background:#eee;border-radius:4px;height:8px'>
            <div style='background:#27ae60;width:{progress_pct:.0f}%;height:8px;border-radius:4px'></div></div>
            {progress_pct:.0f}% to target</td>
            <td style='color:{ac};font-size:12px'><b>{t['action']}</b><br>{t['reason'][:80]}</td>
        </tr>"""
    if not t_rows:
        t_rows = "<tr><td colspan='11' style='color:#888'>No open trades.</td></tr>"

    total_pnl_pct = ((total_current - total_invested) / total_invested * 100) \
                    if total_invested > 0 else 0
    total_color = "#27ae60" if total_pnl >= 0 else "#e74c3c"

    # Tomorrow preview rows
    tmrw_rows = "".join(
        f"<tr><td style='font-size:13px;padding:8px'>{l}</td></tr>"
        for l in tomorrow_lines
    )

    # Top 5 for tomorrow
    new_rows = ""
    for i, r in enumerate(top5_tomorrow[:5], 1):
        sc    = sig_color(r['signal'])
        stars = "⭐" * r['efficiency']
        new_rows += f"""<tr>
            <td>{i}</td><td><b>{r['symbol']}</b></td><td>₹{r['price']}</td>
            <td style='color:{sc}'><b>{r['signal']}</b></td>
            <td>{r['efficiency']}/5 {stars}</td><td>{r['rsi']}</td>
            <td>{r['sector']}</td>
            <td>₹{r['entry']} | ₹{r['target']} | ₹{r['sl']}</td>
        </tr>"""
    if not new_rows:
        new_rows = "<tr><td colspan='8'>No qualifying signals for tomorrow — no forced trades</td></tr>"

    # Sector rows
    s_rows = "".join(
        f"<tr><td><b>{s}</b></td><td style='color:{mood_color(m)}'>{m}</td>"
        f"<td style='font-size:12px;color:#555'>{'Watch for longs' if 'BULL' in m else 'Avoid new buys' if 'BEAR' in m else 'Neutral'}</td></tr>"
        for s, m in sector_signals.items()
    )

    # FII/DII
    fii = fii_dii.get('fii_net', 0) or 0
    dii = fii_dii.get('dii_net', 0) or 0
    fii_color = "#27ae60" if fii > 0 else "#e74c3c"
    dii_color = "#27ae60" if dii > 0 else "#e74c3c"

    nifty_mood = nifty['mood'] if nifty else "NEUTRAL 🟡"

    html = f"""<html><body style='font-family:Arial,sans-serif;max-width:1000px;margin:auto;padding:20px;color:#2c3e50'>
{html_header('🌙 Evening Position Update v3.0',
             f'{today} | {now} | NSE Closing Prices', '#1a3a4a', '#2c5f7a')}

<div style='background:#eaf4fb;padding:15px;border-radius:8px;border-left:4px solid {mood_color(nifty_mood)};margin-bottom:20px'>
<h3 style='margin:0'>📊 Market Closed: <span style='color:{mood_color(nifty_mood)}'>{nifty_mood}</span></h3>
<p style='margin:5px 0 0;font-size:13px'>
{"✅ Positive close — momentum intact heading into tomorrow." if nifty and nifty['change_pct'] > 0.3 else
 "⚠️ Negative close — review positions and tighten SLs for tomorrow." if nifty and nifty['change_pct'] < -0.3 else
 "🟡 Flat close — consolidation day. Watch for breakout tomorrow."}</p>
</div>

<h2 style='border-bottom:2px solid #2c5f7a;padding-bottom:8px'>📊 Section 1 — Today's Closing</h2>
{section_tip("Final closing numbers for all major indices. This is the official record for today.")}
{table_start(["Index","Close","Change","RSI","Trend","MACD","Support","Resistance","Mood","Close note"])}
{i_rows}{table_end()}

<h2 style='border-bottom:2px solid #2c5f7a;padding-bottom:8px;margin-top:25px'>💰 Section 2 — FII/DII Final Tally</h2>
{section_tip("Final FII/DII data for today. This is the most important number — where big money went today.")}
<div style='background:#eaf4fb;padding:15px;border-radius:8px'>
<table style='width:100%;font-size:14px'>
<tr>
  <td style='padding:8px'><b>FII (Foreign Funds):</b>
    <span style='color:{fii_color};font-size:16px;font-weight:bold'>
      {f"BOUGHT ₹{abs(fii):,.0f} Cr 🟢" if fii > 0 else f"SOLD ₹{abs(fii):,.0f} Cr 🔴" if fii else "Data N/A"}
    </span>
  </td>
  <td style='padding:8px'><b>DII (Indian Funds):</b>
    <span style='color:{dii_color};font-size:16px;font-weight:bold'>
      {f"BOUGHT ₹{abs(dii):,.0f} Cr 🟢" if dii > 0 else f"SOLD ₹{abs(dii):,.0f} Cr 🔴" if dii else "Data N/A"}
    </span>
  </td>
</tr>
<tr>
  <td colspan='2' style='padding:8px;font-size:13px;color:#555'>
    {
      "Both FII and DII buying = strong institutional support 🟢" if fii > 0 and dii > 0 else
      "FII buying, DII selling = foreign confidence, local caution 🟡" if fii > 0 and dii < 0 else
      "FII selling, DII buying = foreigners exiting, locals supporting 🟡" if fii < 0 and dii > 0 else
      "Both selling = weak institutional environment — be cautious 🔴" if fii < 0 and dii < 0 else
      "Data unavailable"
    }
  </td>
</tr>
</table>
</div>

<h2 style='border-bottom:2px solid #2c5f7a;padding-bottom:8px;margin-top:25px'>💼 Section 3 — Your Positions — Closing P&L</h2>
{section_tip("Final P&L for all your positions today. Action column tells you exactly what to do tonight before tomorrow's open.")}
<div style='background:{"#eafaf1" if total_pnl >= 0 else "#fdf2f2"};padding:15px;border-radius:8px;border-left:4px solid {total_color};margin-bottom:15px'>
<h3 style='margin:0;color:{total_color}'>💰 Closing P&L: ₹{total_pnl:+,.0f} ({total_pnl_pct:+.1f}%)</h3>
<p style='margin:5px 0 0;font-size:13px'>Invested: ₹{total_invested:,.0f} | Closing value: ₹{total_current:,.0f}</p>
</div>
{table_start(["Stock","Entry","Close","Day Chg","P&L ₹","P&L %","RSI","Trend|MACD","Target|SL","Progress","Tonight's action"])}
{t_rows}{table_end()}

<h2 style='border-bottom:2px solid #2c5f7a;padding-bottom:8px;margin-top:25px'>🗺️ Section 4 — Sector Closing Momentum</h2>
{section_tip("How each sector closed today. Bullish sectors closing strong = good candidates for tomorrow.")}
<table border='1' cellpadding='8' cellspacing='0' style='width:70%;border-collapse:collapse;font-size:13px'>
<tr style='background:#2c3e50;color:white'><th>Sector</th><th>Closing Momentum</th><th>Tomorrow outlook</th></tr>
{s_rows}</table>

<h2 style='border-bottom:2px solid #2c5f7a;padding-bottom:8px;margin-top:25px'>🔭 Section 5 — Tomorrow's Preview</h2>
{section_tip("Key factors that will influence tomorrow's market. Read this tonight to plan your strategy for tomorrow morning.")}
<table border='1' cellpadding='0' cellspacing='0' style='width:100%;border-collapse:collapse'>
{tmrw_rows}</table>

<h2 style='border-bottom:2px solid #2c5f7a;padding-bottom:8px;margin-top:25px'>🎯 Section 6 — Watchlist for Tomorrow</h2>
{section_tip("Stocks that passed quality filters today and are worth watching tomorrow morning. Verify on TradingView before trading.")}
{table_start(["#","Stock","Price","Signal","Quality","RSI","Sector","Entry/Target/SL"])}
{new_rows}{table_end()}

<p style='color:#7f8c8d;font-size:12px;margin-top:25px;border-top:1px solid #eee;padding-top:10px'>
⚠️ Closing prices shown. Always verify in Zerodha before placing orders.<br>
Actions are based on technical signals only — use your own judgment.<br>
Next update: Tomorrow 8:00 AM IST Morning Scan.
</p></body></html>"""
    return html

def run():
    today = datetime.now(IST).strftime('%d %b %Y')
    now   = datetime.now(IST).strftime('%I:%M %p IST')
    print(f"\n{'='*60}\nEvening Update v3.0 — {today} {now}\n{'='*60}")

    sheet = setup_sheets()

    # Market data
    global_data    = get_global_markets()
    fii_dii        = get_fii_dii()
    news           = get_news()
    sector_signals = get_sector_momentum()
    nifty          = analyze_index("^NSEI",   "Nifty 50")
    banknifty      = analyze_index("^NSEBANK", "Bank Nifty")
    sensex         = analyze_index("^BSESN",  "Sensex")
    nifty_dir      = nifty['direction'] if nifty else "NEUTRAL"

    # Open trades closing P&L
    trades_data = []
    if sheet:
        trades = get_open_trades(sheet)
        for t in trades:
            sym   = t.get('Stock', '')
            entry = float(t.get('Entry Price', 0))
            qty   = int(t.get('Qty', 0))
            if not sym or not entry or not qty:
                continue
            pd_data = get_closing_price(sym)
            if not pd_data:
                continue
            try:
                ed   = datetime.strptime(t.get('Entry Date', ''), '%d %b %Y')
                days = (datetime.now(IST).replace(tzinfo=None) - ed).days
            except:
                days = int(t.get('Days Held', 0))
            pnl     = (pd_data['current'] - entry) * qty
            pnl_pct = ((pd_data['current'] - entry) / entry) * 100
            action, reason, color = get_overnight_action(
                {**t, 'Days Held': days}, pd_data, nifty_dir)
            trades_data.append({
                "symbol":   sym,
                "entry":    entry,
                "qty":      qty,
                "current":  pd_data['current'],
                "day_chg":  pd_data['day_chg'],
                "rsi":      pd_data['rsi'],
                "trend":    pd_data['trend'],
                "macd":     pd_data['macd'],
                "vol_ratio": pd_data['vol_ratio'],
                "pnl":      pnl,
                "pnl_pct":  pnl_pct,
                "days":     days,
                "target":   float(t.get('Target', entry * 1.1)),
                "sl":       float(t.get('Stop Loss', entry * 0.97)),
                "action":   action,
                "reason":   reason,
                "color":    color,
            })
            time.sleep(0.5)

    total_pnl = sum(t['pnl'] for t in trades_data)

    # Tomorrow's preview
    tomorrow_lines = get_tomorrow_preview(sector_signals, nifty, fii_dii, global_data)

    # Tomorrow's watchlist — scan bullish sectors
    sector_stocks = []
    for sector, mood in sector_signals.items():
        if "BULLISH" in mood:
            sector_stocks.extend(SECTOR_MAP.get(sector, [])[:5])
    scan_list = list(set(get_portfolio_symbols() + sector_stocks))[:80]
    tmrw_signals = []
    for sym in scan_list:
        r = calculate_signal(sym, sector_signals, nifty_dir)
        if r and r['signal'] in ["STRONG BUY", "BUY"] and r['efficiency'] >= 3:
            tmrw_signals.append(r)
        time.sleep(0.3)
    top5_tomorrow = sorted(tmrw_signals, key=lambda x: x['efficiency'], reverse=True)[:5]

    # Telegram
    tg = build_tg_evening(today, now, global_data, fii_dii, nifty, banknifty,
                          sector_signals, trades_data, tomorrow_lines, total_pnl)
    send_telegram(tg)

    # Email
    email_body = build_email_evening(today, now, global_data, fii_dii, news,
                                     nifty, banknifty, sensex, sector_signals,
                                     trades_data, tomorrow_lines, top5_tomorrow)
    mood = nifty['mood'] if nifty else 'N/A'
    total_pnl_pct = 0
    if trades_data:
        invested = sum(t['entry'] * t['qty'] for t in trades_data)
        curr_val = sum(t['current'] * t['qty'] for t in trades_data)
        total_pnl_pct = ((curr_val - invested) / invested * 100) if invested > 0 else 0
    send_email(
        subject=f"🌙 Evening Update {today} | {mood} | P&L: ₹{total_pnl:+,.0f} ({total_pnl_pct:+.1f}%)",
        body=email_body
    )
    print("\n✅ Evening update v3.0 complete!")

run()
