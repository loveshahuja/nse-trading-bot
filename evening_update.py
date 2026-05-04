# ============================================================
# EVENING UPDATE v3.0 — 4:00 PM IST
# Position tracker + closing P&L + tomorrow preview
# NO repetitive scan — purely about YOUR trades
# ============================================================
from utils import *

def get_open_trades(sheet):
    try:
        ws = sheet.worksheet("Open Trades")
        return ws.get_all_records()
    except:
        return []

def update_days_held(sheet, trades):
    try:
        ws = sheet.worksheet("Open Trades")
        records = ws.get_all_records()
        for i, r in enumerate(records, 2):
            try:
                ed = datetime.strptime(r.get('Entry Date',''), '%d %b %Y')
                days = (datetime.now() - ed).days
                ws.update_cell(i, list(r.keys()).index('Days Held')+1, days)
            except:
                pass
    except:
        pass

def get_closing_price(symbol):
    try:
        ticker = symbol if ".NS" in symbol else symbol+".NS"
        df = yf.download(ticker, period="5d", interval="1d", progress=False)
        if not df.empty and len(df) >= 2:
            curr = float(df['Close'].iloc[-1])
            prev = float(df['Close'].iloc[-2])
            rsi = float(ta.momentum.RSIIndicator(df['Close'].squeeze()).rsi().iloc[-1])
            high = float(df['High'].iloc[-1])
            low = float(df['Low'].iloc[-1])
            vol = float(df['Volume'].iloc[-1])
            return {"close": curr, "prev_close": prev, "rsi": round(rsi,1),
                    "high": high, "low": low, "vol": vol,
                    "day_chg": round(((curr-prev)/prev)*100,2)}
    except:
        pass
    return None

def smart_exit_recommendation(trade, price_data, nifty_direction, news_sentiment):
    entry = float(trade.get('Entry Price', 0))
    target = float(trade.get('Target', entry*1.1))
    sl = float(trade.get('Stop Loss', entry*0.97))
    days = int(trade.get('Days Held', 0))
    curr = price_data['close']
    rsi = price_data['rsi']
    pnl_pct = ((curr - entry) / entry) * 100
    high = price_data['high']
    low = price_data['low']

    # SL hit
    if curr <= sl or low <= sl:
        if news_sentiment == "NEGATIVE" or nifty_direction == "BEARISH":
            return "🛑 EXIT TOMORROW OPEN", "Stop loss breached AND negative context. Exit at tomorrow's open. Don't hope for recovery.", "red", "HIGH"
        else:
            return "🛑 EXIT NOW", "Stop loss triggered. Market mixed — protect capital. Exit position.", "red", "HIGH"

    # Target hit
    if curr >= target or high >= target:
        return "🎯 BOOK PROFITS", f"Target ₹{target:.2f} hit today! Book 75% profits. Hold 25% with trailing SL at ₹{round(entry*1.05,2)}.", "green", "HIGH"

    # RSI overbought
    if rsi > 78:
        return "⚠️ PARTIAL EXIT", f"RSI {rsi:.0f} = very overbought. Book 50% at ₹{curr:.2f}. Hold rest with SL at ₹{round(curr*0.97,2)}.", "orange", "MEDIUM"

    # Long hold, no movement
    if days > 15 and pnl_pct < 2:
        return "⚠️ REVIEW POSITION", f"Held {days} days, only {pnl_pct:.1f}% gain. Consider if better opportunities exist. No urgency but review.", "orange", "LOW"

    # Approaching target
    if curr >= target * 0.95:
        return "🔔 NEAR TARGET", f"Only {((target-curr)/curr*100):.1f}% away from target ₹{target:.2f}. Set price alert. Watch closely tomorrow.", "green", "MEDIUM"

    # Approaching SL
    if curr <= sl * 1.03:
        return "⚠️ NEAR STOP LOSS", f"Only {((curr-sl)/sl*100):.1f}% above SL ₹{sl:.2f}. Stay alert tomorrow. Have exit order ready.", "orange", "HIGH"

    # Good profit
    if pnl_pct > 8:
        return "✅ TRAIL STOP LOSS", f"Strong {pnl_pct:.1f}% profit. Move SL up to ₹{round(entry*1.03,2)} (3% above entry). Lock in gains.", "green", "LOW"

    return "✅ HOLD", f"Developing well. {pnl_pct:+.1f}%. Target ₹{target:.2f} | SL ₹{sl:.2f}. No action needed tonight.", "blue", "LOW"

def get_tomorrow_preview(nifty, banknifty, news, portfolio_results, trades_data):
    preview = []

    # Check for near-target trades
    for t in trades_data:
        if t['current'] >= t['target'] * 0.93:
            preview.append({
                "type": "TARGET_NEAR", "priority": "HIGH",
                "msg": f"🎯 {t['symbol']} is {((t['target']-t['current'])/t['current']*100):.1f}% from target. Set price alert at ₹{t['target']:.2f}"
            })
        if t['current'] <= t['sl'] * 1.04:
            preview.append({
                "type": "SL_NEAR", "priority": "HIGH",
                "msg": f"⚠️ {t['symbol']} is {((t['current']-t['sl'])/t['sl']*100):.1f}% above stop loss. Watch closely tomorrow."
            })

    # Check RSI warnings in portfolio
    for r in portfolio_results:
        if r['rsi'] > 75:
            preview.append({
                "type": "RSI_WARN", "priority": "MEDIUM",
                "msg": f"📊 {r['symbol']} RSI is {r['rsi']} — overbought. Consider booking partial profits if you hold this."
            })

    # Nifty levels to watch
    if nifty:
        dist_to_res = ((nifty['resistance'] - nifty['level']) / nifty['level']) * 100
        dist_to_sup = ((nifty['level'] - nifty['support']) / nifty['level']) * 100
        if dist_to_res < 1.5:
            preview.append({
                "type": "INDEX_RESIST", "priority": "MEDIUM",
                "msg": f"📊 Nifty is {dist_to_res:.1f}% from resistance {nifty['resistance']:,.0f}. May face selling pressure at open tomorrow."
            })
        if dist_to_sup < 1.5:
            preview.append({
                "type": "INDEX_SUPPORT", "priority": "HIGH",
                "msg": f"📊 Nifty is {dist_to_sup:.1f}% above support {nifty['support']:,.0f}. Important level — if broken, market could fall sharply."
            })

    # Positive news
    for n in news[:3]:
        if "POSITIVE" in n['sentiment'] and n['stock'] != "MARKET":
            preview.append({
                "type": "NEWS_POS", "priority": "MEDIUM",
                "msg": f"📰 {n['stock']}: Positive news today may continue tomorrow. Watch for gap-up open."
            })

    # Sort by priority
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    preview.sort(key=lambda x: priority_order.get(x['priority'], 3))
    return preview[:8]

def build_tg_evening(today, now, global_data, fii_dii, news, nifty, banknifty,
                     trades_data, portfolio_results, tomorrow_preview, total_pnl, total_pnl_pct):
    nifty_txt = f"{nifty['level']:,.0f} ({nifty['change_pct']:+.2f}%) | {nifty['mood']}" if nifty else "N/A"

    fii = fii_dii.get('fii_net')
    fii_txt = f"₹{abs(fii):,.0f} Cr {'BOUGHT 🟢' if fii>0 else 'SOLD 🔴'}" if fii is not None else "Data unavailable"

    news_txt = ""
    for n in news[:3]:
        news_txt += f"• <b>{n['stock']}</b>: {n['headline'][:60]}... {n['sentiment']}\n"
    if not news_txt:
        news_txt = "• No major news today\n"

    trades_txt = ""
    for t in trades_data:
        e = "🟢" if t['pnl'] >= 0 else "🔴"
        trades_txt += f"""
{e} <b>{t['symbol']}</b> (Day {t['days']})
Entry ₹{t['entry']} → Close ₹{t['close']} ({t['day_chg']:+.1f}% today)
P&L: ₹{t['pnl']:+,.0f} ({t['pnl_pct']:+.1f}%) | High ₹{t['high']} | Low ₹{t['low']}
{t['action']}: {t['reason'][:90]}
Priority: {t['priority']}
"""
    if not trades_txt:
        trades_txt = "No open trades recorded.\n"

    preview_txt = ""
    for p in tomorrow_preview:
        preview_txt += f"• {p['msg']}\n"
    if not preview_txt:
        preview_txt = "• No urgent alerts for tomorrow — continue holding your positions\n"

    total_e = "🟢" if total_pnl >= 0 else "🔴"

    return f"""🌆 <b>EVENING UPDATE — {today} {now}</b>
⏰ Prices: Today 3:30 PM NSE Official Close

━━━━━━━━━━━━━━━━━━━━
📊 <b>MARKET CLOSED TODAY</b>
Nifty 50  : {nifty_txt}
BankNifty : {f"{banknifty['level']:,.0f} ({banknifty['change_pct']:+.2f}%) | {banknifty['mood']}" if banknifty else "N/A"}

💡 {"Market closed positive — momentum may continue tomorrow" if nifty and nifty['change_pct'] > 0.3 else "Market closed negative — be cautious about new entries tomorrow" if nifty and nifty['change_pct'] < -0.3 else "Market closed flat — wait for direction tomorrow"}

━━━━━━━━━━━━━━━━━━━━
💰 <b>FII FINAL TODAY</b>
{fii_txt}

━━━━━━━━━━━━━━━━━━━━
📰 <b>NEWS TODAY</b>
{news_txt}
━━━━━━━━━━━━━━━━━━━━
💼 <b>YOUR CLOSING P&L</b>
{trades_txt}
{total_e} <b>Total P&L Today: ₹{total_pnl:+,.0f} ({total_pnl_pct:+.1f}%)</b>

━━━━━━━━━━━━━━━━━━━━
🔮 <b>TOMORROW PREVIEW</b>
{preview_txt}
━━━━━━━━━━━━━━━━━━━━
📧 Full detailed report sent to Gmail
💤 See you at 8 AM tomorrow with fresh opportunities"""

def build_email_evening(today, now, global_data, fii_dii, news, nifty, banknifty,
                        sensex, trades_data, portfolio_results, tomorrow_preview,
                        total_pnl, total_pnl_pct, total_invested, total_current):

    # Index rows
    i_rows = ""
    for idx in [nifty, banknifty, sensex]:
        if not idx: continue
        mc = mood_color(idx['mood']); cc = "#27ae60" if idx['change_pct'] > 0 else "#e74c3c"
        tomorrow_bias = "Likely positive opening tomorrow" if idx['change_pct'] > 0.5 else \
                       "May open weak tomorrow" if idx['change_pct'] < -0.5 else \
                       "Flat opening expected tomorrow"
        i_rows += f"""<tr>
            <td><b>{idx['name']}</b></td><td><b>{idx['level']:,.2f}</b></td>
            <td style='color:{cc}'><b>{idx['change_pct']:+.2f}%</b></td>
            <td>{idx['rsi']}</td><td>{idx['trend']}</td><td>{idx['macd']}</td>
            <td>₹{idx['support']:,.0f}</td><td>₹{idx['resistance']:,.0f}</td>
            <td style='color:{mc}'><b>{idx['mood']}</b></td>
            <td style='font-size:12px;color:#555'>{tomorrow_bias}</td>
        </tr>"""

    # News rows
    n_rows = ""
    for n in news:
        sc = "#27ae60" if "POSITIVE" in n['sentiment'] else "#e74c3c" if "NEGATIVE" in n['sentiment'] else "#f39c12"
        n_rows += f"<tr><td><b>{n['stock']}</b></td><td>{n['headline']}</td><td style='color:{sc}'>{n['sentiment']}</td><td style='font-size:12px'>{n['impact']}</td></tr>"
    if not n_rows:
        n_rows = "<tr><td colspan='4'>No major news today</td></tr>"

    # Portfolio signals
    p_rows = ""
    for r in portfolio_results:
        sc = sig_color(r['signal']); stars = "⭐"*r['efficiency']
        rsi_note = "Overbought ⚠️" if r['rsi'] > 70 else "Oversold ✅" if r['rsi'] < 40 else "Healthy ✅"
        p_rows += f"""<tr>
            <td><b>{r['symbol']}</b></td><td>₹{r['price']}</td>
            <td style='color:{sig_color(r["signal"])}'><b>{r['signal']}</b></td>
            <td>{r['rsi']} — {rsi_note}</td><td>{r['trend']}</td>
            <td>{r['efficiency']}/5 {stars}</td>
        </tr>"""

    # Trades rows
    t_rows = ""
    for t in trades_data:
        pc = "#27ae60" if t['pnl'] >= 0 else "#e74c3c"
        dc = "#27ae60" if t['day_chg'] >= 0 else "#e74c3c"
        ac = {"red":"#e74c3c","green":"#27ae60","orange":"#f39c12","blue":"#3498db"}.get(t['color'],"#333")
        pri_color = "#e74c3c" if t['priority']=="HIGH" else "#f39c12" if t['priority']=="MEDIUM" else "#27ae60"
        days_remaining = max(0, 90 - t['days'])
        t_rows += f"""<tr>
            <td><b>{t['symbol']}</b><br><span style='font-size:11px;color:#888'>Day {t['days']} | {days_remaining}d left</span></td>
            <td>₹{t['entry']}</td><td>₹{t['close']}</td>
            <td style='color:{dc}'>{t['day_chg']:+.2f}%</td>
            <td>₹{t['high']} / ₹{t['low']}</td>
            <td style='color:{pc}'><b>₹{t['pnl']:+,.0f}</b></td>
            <td style='color:{pc}'><b>{t['pnl_pct']:+.1f}%</b></td>
            <td>{t['rsi']}</td>
            <td>₹{t['target']} | ₹{t['sl']}</td>
            <td style='color:{ac};font-size:12px'><b>{t['action']}</b><br>{t['reason'][:100]}</td>
            <td style='color:{pri_color};font-size:12px'><b>{t['priority']}</b></td>
        </tr>"""
    if not t_rows:
        t_rows = "<tr><td colspan='11' style='color:#888'>No open trades. Record your first trade using /buy STOCK PRICE QTY in Telegram.</td></tr>"

    # Tomorrow preview
    prev_rows = ""
    for p in tomorrow_preview:
        pri_color = "#e74c3c" if p['priority']=="HIGH" else "#f39c12" if p['priority']=="MEDIUM" else "#27ae60"
        prev_rows += f"<tr><td style='color:{pri_color}'><b>{p['priority']}</b></td><td>{p['msg']}</td></tr>"
    if not prev_rows:
        prev_rows = "<tr><td>LOW</td><td>✅ No urgent alerts — positions are safe. Continue holding.</td></tr>"

    total_color = "#27ae60" if total_pnl >= 0 else "#e74c3c"
    nifty_mood = nifty['mood'] if nifty else "NEUTRAL 🟡"

    html = f"""<html><body style='font-family:Arial,sans-serif;max-width:1000px;margin:auto;padding:20px;color:#2c3e50'>
{html_header('🌆 Evening Position Update v3.0', f'{today} | {now} IST | ⏰ All prices: Today 3:30 PM NSE Official Close', '#1a3a4a', '#2ecc71')}

<div style='background:{"#eafaf1" if total_pnl>=0 else "#fdf2f2"};padding:15px;border-radius:8px;border-left:4px solid {total_color};margin-bottom:20px'>
<h3 style='margin:0;color:{total_color}'>💰 Today's Closing P&L: ₹{total_pnl:+,.0f} ({total_pnl_pct:+.1f}%)</h3>
<p style='margin:5px 0 0;font-size:13px'>Total invested: ₹{total_invested:,.0f} | Current value: ₹{total_current:,.0f}</p>
<p style='margin:5px 0 0;font-size:13px'>Overall market today: <span style='color:{mood_color(nifty_mood)}'><b>{nifty_mood}</b></span></p>
</div>

<h2 style='border-bottom:2px solid #2ecc71;padding-bottom:8px'>📊 Section 1 — How Market Closed Today</h2>
{section_tip("Today's closing levels. Support and resistance carry over to tomorrow. If Nifty closed near resistance = may face selling pressure at open. If near support = buyers may step in tomorrow.")}
{table_start(["Index","Close","Today","RSI","Trend","MACD","Support","Resistance","Mood","Tomorrow bias"])}
{i_rows}{table_end()}

<h2 style='border-bottom:2px solid #2ecc71;padding-bottom:8px;margin-top:25px'>💰 Section 2 — FII Activity Today</h2>
{section_tip("Final FII/DII figures for the day. If FII bought heavily today = market likely to open positive tomorrow. If FII sold = be cautious at tomorrow's open.")}
<div style='background:#eaf4fb;padding:15px;border-radius:8px'>
<table style='width:100%;font-size:14px'><tr>
<td><b>FII (Foreign funds):</b></td>
<td style='color:{"#27ae60" if fii_dii.get("fii_net",0) and fii_dii["fii_net"]>0 else "#e74c3c"}'>
<b>{f"BOUGHT ₹{abs(fii_dii['fii_net']):,.0f} Cr 🟢" if fii_dii.get('fii_net') and fii_dii['fii_net']>0 else f"SOLD ₹{abs(fii_dii.get('fii_net',0)):,.0f} Cr 🔴" if fii_dii.get('fii_net') else "Data unavailable"}</b></td>
<td style='font-size:12px;color:#555'>{"Foreign investors bullish on India today — positive for tomorrow" if fii_dii.get('fii_net') and fii_dii['fii_net']>0 else "Foreign investors reduced exposure today — watch tomorrow open carefully" if fii_dii.get('fii_net') else ""}</td>
</tr><tr>
<td><b>DII (Indian funds):</b></td>
<td style='color:{"#27ae60" if fii_dii.get("dii_net",0) and fii_dii["dii_net"]>0 else "#e74c3c"}'>
<b>{f"BOUGHT ₹{abs(fii_dii['dii_net']):,.0f} Cr 🟢" if fii_dii.get('dii_net') and fii_dii['dii_net']>0 else f"SOLD ₹{abs(fii_dii.get('dii_net',0)):,.0f} Cr 🔴" if fii_dii.get('dii_net') else "Data unavailable"}</b></td>
<td style='font-size:12px;color:#555'>{"Indian mutual funds supporting market — cushion for any FII selling" if fii_dii.get('dii_net') and fii_dii['dii_net']>0 else ""}</td>
</tr></table></div>

<h2 style='border-bottom:2px solid #2ecc71;padding-bottom:8px;margin-top:25px'>📰 Section 3 — News That Moved Stocks Today</h2>
{section_tip("News that came out today and may continue impacting stocks tomorrow. Positive news stocks often gap-up next morning. Negative news stocks may continue falling.")}
{table_start(["Stock","Headline","Sentiment","Impact"])}
{n_rows}{table_end()}

<h2 style='border-bottom:2px solid #2ecc71;padding-bottom:8px;margin-top:25px'>📊 Section 4 — Your Portfolio Closing Signals</h2>
{section_tip("End of day technical reading for your holdings. RSI above 70 = stock ran up a lot today, may cool off tomorrow. RSI below 40 = stock fell a lot, may bounce tomorrow.")}
{table_start(["Stock","Close","Signal","RSI","Trend","Efficiency"])}
{p_rows}{table_end()}

<h2 style='border-bottom:2px solid #2ecc71;padding-bottom:8px;margin-top:25px'>💼 Section 5 — Your Open Trades — Closing P&L</h2>
{section_tip("Complete P&L for each open trade based on today's closing price. High/Low shows the range today — if SL was touched during the day it's shown. Priority column tells urgency of action needed.")}
{table_start(["Stock","Entry","Close","Day Chg","High/Low","P&L ₹","P&L %","RSI","Target|SL","What to do","Priority"])}
{t_rows}{table_end()}

<h2 style='border-bottom:2px solid #2ecc71;padding-bottom:8px;margin-top:25px'>🔮 Section 6 — Tomorrow Preview</h2>
{section_tip("Key things to watch at tomorrow's 9:15 AM open. HIGH priority = take action first thing. MEDIUM = watch and decide. LOW = nothing urgent.")}
{table_start(["Priority","What to watch tomorrow"])}
{prev_rows}{table_end()}

<div style='background:#f8f9fa;padding:15px;border-radius:8px;margin-top:20px'>
<h4 style='margin:0 0 8px'>📋 Morning Checklist for Tomorrow</h4>
<p style='margin:0;font-size:13px;color:#555'>
1. Check 8 AM morning scan for fresh opportunities<br>
2. Verify your stop losses are still valid<br>
3. Check global markets before 9:15 AM open<br>
4. Any HIGH priority items above — act first thing<br>
5. Use /market in Telegram for live index levels at open
</p></div>

<p style='color:#7f8c8d;font-size:12px;margin-top:20px;border-top:1px solid #eee;padding-top:10px'>
⚠️ All prices are NSE official closing prices for today {today}.<br>
Tomorrow preview is based on technical analysis — news can change everything overnight.<br>
Use /analyse STOCKNAME in Telegram for instant analysis of any stock.<br>
Morning scan arrives at 8:00 AM tomorrow with fresh Top 20 opportunities.
</p></body></html>"""
    return html

def run():
    today = datetime.now().strftime('%d %b %Y')
    now = datetime.now().strftime('%I:%M %p')
    print(f"\n{'='*60}\nEvening Update v3.0 — {today} {now}\n{'='*60}")

    sheet = setup_sheets()
    global_data = get_global_markets()
    fii_dii = get_fii_dii()
    news = get_news()
    nifty = analyze_index("^NSEI","Nifty 50")
    banknifty = analyze_index("^NSEBANK","Bank Nifty")
    sensex = analyze_index("^BSESN","Sensex")
    nifty_dir = nifty['direction'] if nifty else "NEUTRAL"
    sector_signals = get_sector_momentum()

    # Portfolio fresh signals
    portfolio_results = []
    for sym in MY_PORTFOLIO:
        r = calculate_signal(sym, sector_signals, nifty_dir)
        if r: portfolio_results.append(r)
        time.sleep(0.5)

    # Open trades P&L
    trades_data = []
    total_invested = 0; total_current = 0
    if sheet:
        trades = get_open_trades(sheet)
        for t in trades:
            sym = t.get('Stock','')
            entry = float(t.get('Entry Price', 0))
            qty = int(t.get('Qty', 0))
            if not sym or not entry or not qty: continue
            pd_data = get_closing_price(sym)
            if not pd_data: continue
            try:
                ed = datetime.strptime(t.get('Entry Date',''), '%d %b %Y')
                days = (datetime.now() - ed).days
            except:
                days = int(t.get('Days Held', 0))
            pnl = (pd_data['close'] - entry) * qty
            pnl_pct = ((pd_data['close'] - entry) / entry) * 100
            news_s = next((n['sentiment'] for n in news if sym.upper() in n['stock'].upper()), None)
            action, reason, color, priority = smart_exit_recommendation(
                {**t, 'Days Held': days}, pd_data, nifty_dir, news_s or "")
            total_invested += entry * qty
            total_current += pd_data['close'] * qty
            trades_data.append({
                "symbol": sym, "entry": entry, "qty": qty,
                "close": pd_data['close'], "day_chg": pd_data['day_chg'],
                "high": pd_data['high'], "low": pd_data['low'],
                "rsi": pd_data['rsi'], "pnl": pnl, "pnl_pct": pnl_pct,
                "days": days,
                "target": float(t.get('Target', entry*1.1)),
                "sl": float(t.get('Stop Loss', entry*0.97)),
                "action": action, "reason": reason,
                "color": color, "priority": priority,
            })
            time.sleep(0.5)

    total_pnl = total_current - total_invested
    total_pnl_pct = ((total_current-total_invested)/total_invested*100) if total_invested > 0 else 0
    tomorrow_preview = get_tomorrow_preview(nifty, banknifty, news, portfolio_results, trades_data)

    # Send
    tg = build_tg_evening(today, now, global_data, fii_dii, news, nifty,
                          banknifty, trades_data, portfolio_results,
                          tomorrow_preview, total_pnl, total_pnl_pct)
    send_telegram(tg)

    email_body = build_email_evening(today, now, global_data, fii_dii, news,
                                     nifty, banknifty, sensex, trades_data,
                                     portfolio_results, tomorrow_preview,
                                     total_pnl, total_pnl_pct,
                                     total_invested, total_current)
    mood = nifty['mood'] if nifty else 'N/A'
    send_email(
        subject=f"🌆 Evening Update {today} | {mood} | P&L: ₹{total_pnl:+,.0f} ({total_pnl_pct:+.1f}%)",
        body=email_body
    )
    print(f"\n✅ Evening update complete! P&L: ₹{total_pnl:+,.0f}")

run()
