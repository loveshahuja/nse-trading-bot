# ============================================================
# MIDDAY UPDATE v3.0 — 12:00 PM IST
# Full report: live market + open trades + updated signals
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

def get_current_price_live(symbol):
    try:
        ticker = symbol if ".NS" in symbol else symbol+".NS"
        df = yf.download(ticker, period="5d", interval="1d", progress=False)
        if not df.empty and len(df) >= 2:
            curr = float(df['Close'].iloc[-1])
            prev = float(df['Close'].iloc[-2])
            rsi = float(ta.momentum.RSIIndicator(df['Close'].squeeze()).rsi().iloc[-1])
            open_p = float(df['Open'].iloc[-1])
            high = float(df['High'].iloc[-1])
            low = float(df['Low'].iloc[-1])
            return {"current": curr, "prev": prev, "rsi": round(rsi,1),
                    "open": open_p, "high": high, "low": low,
                    "day_chg": round(((curr-prev)/prev)*100,2)}
    except:
        pass
    return None

def get_exit_signal(trade, price_data, nifty_direction):
    entry = float(trade.get('Entry Price', 0))
    target = float(trade.get('Target', entry*1.1))
    sl = float(trade.get('Stop Loss', entry*0.97))
    days = int(trade.get('Days Held', 0))
    curr = price_data['current']
    rsi = price_data['rsi']
    pnl_pct = ((curr - entry) / entry) * 100

    if curr <= sl:
        if nifty_direction == "BEARISH":
            return "🛑 EXIT NOW", "Stop loss hit AND market is bearish. Exit immediately — do not wait.", "red"
        else:
            return "🛑 EXIT NOW", f"Stop loss triggered at ₹{sl:.2f}. Market still mixed but protect capital. Exit now.", "red"
    if curr >= target:
        return "🎯 TARGET HIT", f"Target ₹{target:.2f} reached! Book profits now. Consider 75% exit, hold 25% for more upside.", "green"
    if rsi > 78:
        return "⚠️ PARTIAL EXIT", f"RSI {rsi:.0f} is very overbought. Book 50% profits at current price ₹{curr:.2f}. Hold rest.", "orange"
    if days > 10 and pnl_pct < 2:
        return "⚠️ REVIEW", f"Held {days} days, only {pnl_pct:.1f}% gain. If no catalyst — consider moving capital to stronger setup.", "orange"
    if pnl_pct > 12:
        return "✅ TRAIL SL", f"Good profit {pnl_pct:.1f}%. Move stop loss up to your entry price ₹{entry:.2f} — protect breakeven.", "green"
    if curr > entry * 1.05:
        return "✅ HOLD", f"Up {pnl_pct:.1f}%. Momentum positive. Hold. SL at ₹{sl:.2f}.", "green"
    if curr < entry * 0.98:
        return "⚠️ WATCH CLOSELY", f"Down {abs(pnl_pct):.1f}%. Approaching stop loss ₹{sl:.2f}. Watch carefully.", "orange"
    return "✅ HOLD", f"Position developing. P&L {pnl_pct:+.1f}%. Target ₹{target:.2f} | SL ₹{sl:.2f}.", "blue"

def build_tg_midday(today, now, global_data, fii_dii, news, nifty, banknifty,
                    sector_signals, trades_data, top5_new):
    nifty_txt = f"{nifty['level']:,.0f} ({nifty['change_pct']:+.2f}%) | {nifty['mood']}" if nifty else "N/A"
    bn_txt = f"{banknifty['level']:,.0f} ({banknifty['change_pct']:+.2f}%) | {banknifty['mood']}" if banknifty else "N/A"

    dow = global_data.get('US_DOW',{})
    dow_txt = f"{dow.get('price',0):,.0f} ({dow.get('change_pct',0):+.2f}%)" if dow.get('price',0) > 0 else "N/A"

    news_txt = ""
    for n in news[:3]:
        news_txt += f"• <b>{n['stock']}</b>: {n['headline'][:70]}... {n['sentiment']}\n"
    if not news_txt:
        news_txt = "• No major news since morning\n"

    trades_txt = ""
    total_pnl = 0
    total_invested = 0
    for t in trades_data:
        pnl_e = "🟢" if t['pnl'] >= 0 else "🔴"
        trades_txt += f"""
{pnl_e} <b>{t['symbol']}</b> (Day {t['days']})
Entry ₹{t['entry']} → Now ₹{t['current']} ({t['day_chg']:+.1f}% today)
P&L: ₹{t['pnl']:+,.0f} ({t['pnl_pct']:+.1f}%) | RSI: {t['rsi']}
{t['action']}: {t['reason'][:80]}
"""
        total_pnl += t['pnl']
        total_invested += t['entry'] * t['qty']

    if not trades_txt:
        trades_txt = "No open trades. Use /buy STOCK PRICE QTY to record trades.\n"

    top5_txt = ""
    for i, r in enumerate(top5_new[:5], 1):
        top5_txt += f"{i}. <b>{r['symbol']}</b> ₹{r['price']} | {r['signal']} | RSI:{r['rsi']} | {r['efficiency']}/5\n"
        top5_txt += f"   Entry ₹{r['entry']} | Target ₹{r['target']} | SL ₹{r['sl']}\n"
    if not top5_txt:
        top5_txt = "No new signals since morning scan\n"

    total_e = "🟢" if total_pnl >= 0 else "🔴"

    return f"""☀️ <b>MIDDAY UPDATE — {today} {now}</b>
⏰ Prices: Live (15 min delayed)

━━━━━━━━━━━━━━━━━━━━
📊 <b>MARKET MID-SESSION</b>
Nifty 50  : {nifty_txt}
BankNifty : {bn_txt}
US Futures: {dow_txt}

💡 {"Market trending up mid-session — momentum with buyers" if nifty and nifty['change_pct'] > 0.3 else "Market weak mid-session — sellers in control" if nifty and nifty['change_pct'] < -0.3 else "Market flat mid-session — wait for direction"}

━━━━━━━━━━━━━━━━━━━━
💰 <b>FII ACTIVITY TODAY</b>
{f"FII: ₹{abs(fii_dii['fii_net']):,.0f} Cr {'BOUGHT 🟢' if fii_dii['fii_net']>0 else 'SOLD 🔴'}" if fii_dii.get('fii_net') is not None else "FII data updating..."}

━━━━━━━━━━━━━━━━━━━━
📰 <b>NEWS SINCE MORNING</b>
{news_txt}
━━━━━━━━━━━━━━━━━━━━
💼 <b>YOUR TRADES MIDDAY</b>
{trades_txt}
{total_e} <b>Total P&L: ₹{total_pnl:+,.0f}</b>

━━━━━━━━━━━━━━━━━━━━
🔔 <b>NEW SIGNALS SINCE 8 AM</b>
{top5_txt}
━━━━━━━━━━━━━━━━━━━━
📧 Full report sent to Gmail
⚠️ Prices are 15 min delayed — verify in Zerodha"""

def build_email_midday(today, now, global_data, fii_dii, news, nifty, banknifty,
                       sensex, sector_signals, trades_data, top5_new):

    # Index rows
    i_rows = ""
    for idx in [nifty, banknifty, sensex]:
        if not idx: continue
        mc = mood_color(idx['mood']); cc = "#27ae60" if idx['change_pct'] > 0 else "#e74c3c"
        morning_vs = "Rising since open ✅" if idx['change_pct'] > 0.3 else "Falling since open ⚠️" if idx['change_pct'] < -0.3 else "Flat — waiting for direction 🟡"
        i_rows += f"""<tr>
            <td><b>{idx['name']}</b></td><td><b>{idx['level']:,.2f}</b></td>
            <td style='color:{cc}'>{idx['change_pct']:+.2f}%</td>
            <td>{idx['rsi']}</td><td>{idx['trend']}</td><td>{idx['macd']}</td>
            <td>₹{idx['support']:,.0f}</td><td>₹{idx['resistance']:,.0f}</td>
            <td style='color:{mc}'><b>{idx['mood']}</b></td>
            <td style='font-size:12px;color:#555'>{morning_vs}</td>
        </tr>"""

    # News rows
    n_rows = ""
    for n in news:
        sc = "#27ae60" if "POSITIVE" in n['sentiment'] else "#e74c3c" if "NEGATIVE" in n['sentiment'] else "#f39c12"
        n_rows += f"<tr><td><b>{n['stock']}</b></td><td>{n['headline']}</td><td style='color:{sc}'>{n['sentiment']}</td><td style='font-size:12px;color:#555'>{n['impact']}</td></tr>"
    if not n_rows:
        n_rows = "<tr><td colspan='4'>No major news since morning</td></tr>"

    # Trades rows
    t_rows = ""
    total_pnl = 0; total_invested = 0; total_current = 0
    for t in trades_data:
        pc = "#27ae60" if t['pnl'] >= 0 else "#e74c3c"
        dc = "#27ae60" if t['day_chg'] >= 0 else "#e74c3c"
        ac = {"red":"#e74c3c","green":"#27ae60","orange":"#f39c12","blue":"#3498db"}.get(t['color'],"#333")
        total_pnl += t['pnl']; total_invested += t['entry']*t['qty']
        total_current += t['current']*t['qty']
        progress_pct = min(100, max(0, ((t['current']-t['entry'])/(t['target']-t['entry'])*100))) if t['target'] != t['entry'] else 0
        t_rows += f"""<tr>
            <td><b>{t['symbol']}</b><br><span style='font-size:11px;color:#888'>Day {t['days']}</span></td>
            <td>₹{t['entry']}</td><td>₹{t['current']}</td>
            <td style='color:{dc}'>{t['day_chg']:+.2f}%</td>
            <td style='color:{pc}'><b>₹{t['pnl']:+,.0f}</b></td>
            <td style='color:{pc}'><b>{t['pnl_pct']:+.1f}%</b></td>
            <td>{t['rsi']}</td>
            <td>₹{t['target']} | ₹{t['sl']}</td>
            <td style='font-size:11px'><div style='background:#eee;border-radius:4px;height:8px'>
            <div style='background:#27ae60;width:{progress_pct:.0f}%;height:8px;border-radius:4px'></div></div>
            {progress_pct:.0f}% to target</td>
            <td style='color:{ac};font-size:12px'><b>{t['action']}</b><br>{t['reason'][:80]}</td>
        </tr>"""

    if not t_rows:
        t_rows = "<tr><td colspan='10' style='color:#888'>No open trades. Use /buy STOCK PRICE QTY in Telegram to record trades.</td></tr>"

    total_pnl_pct = ((total_current-total_invested)/total_invested*100) if total_invested > 0 else 0
    total_color = "#27ae60" if total_pnl >= 0 else "#e74c3c"

    # Top 5 new signals
    new_rows = ""
    for i, r in enumerate(top5_new[:5], 1):
        sc = sig_color(r['signal']); stars = "⭐"*r['efficiency']
        new_rows += f"""<tr>
            <td>{i}</td><td><b>{r['symbol']}</b></td><td>₹{r['price']}</td>
            <td style='color:{sc}'><b>{r['signal']}</b></td>
            <td>{r['efficiency']}/5 {stars}</td><td>{r['rsi']}</td>
            <td>₹{r['entry']} | ₹{r['target']} | ₹{r['sl']}</td>
            <td style='font-size:11px;color:#888'>{r['timestamp']}</td>
        </tr>"""
    if not new_rows:
        new_rows = "<tr><td colspan='8'>No new signals since morning — morning Top 20 remains valid</td></tr>"

    # Sector
    s_rows = "".join(
        f"<tr><td><b>{s}</b></td><td style='color:{mood_color(m)}'>{m}</td></tr>"
        for s,m in sector_signals.items()
    )
    nifty_mood = nifty['mood'] if nifty else "NEUTRAL 🟡"

    html = f"""<html><body style='font-family:Arial,sans-serif;max-width:1000px;margin:auto;padding:20px;color:#2c3e50'>
{html_header('☀️ Midday Market Update v3.0', f'{today} | {now} | ⏰ Prices: Live (15 min delayed)', '#1a5276', '#2980b9')}

<div style='background:#eaf4fb;padding:15px;border-radius:8px;border-left:4px solid {mood_color(nifty_mood)};margin-bottom:20px'>
<h3 style='margin:0'>🌡️ Mid-Session Market Mood: <span style='color:{mood_color(nifty_mood)}'>{nifty_mood}</span></h3>
<p style='margin:5px 0 0;font-size:13px'>
{"✅ Market is rising mid-session — momentum with buyers. Morning bullish signals remain valid." if nifty and nifty['change_pct'] > 0.3 else
 "⚠️ Market is falling mid-session — exercise caution. Review any open trades near SL." if nifty and nifty['change_pct'] < -0.3 else
 "🟡 Market is flat mid-session — consolidating. Wait for breakout direction before new entries."}</p>
</div>

<h2 style='border-bottom:2px solid #2980b9;padding-bottom:8px'>📊 Section 1 — Market Mid-Session</h2>
{section_tip("How are indices performing right now vs morning open. Are they rising, falling or flat? This tells you if the morning signals are playing out as expected.")}
{table_start(["Index","Level","Change","RSI","Trend","MACD","Support","Resistance","Mood","Mid-session trend"])}
{i_rows}{table_end()}

<h2 style='border-bottom:2px solid #2980b9;padding-bottom:8px;margin-top:25px'>💰 Section 2 — FII Activity Today</h2>
{section_tip("FII data updates during the day. Shows how much foreign money is flowing in or out RIGHT NOW. Heavy FII buying mid-session = market likely to close positive.")}
<div style='background:#eaf4fb;padding:15px;border-radius:8px'>
<p style='margin:0;font-size:14px'>
FII (Foreign funds): <b style='color:{"#27ae60" if fii_dii.get("fii_net",0) and fii_dii["fii_net"]>0 else "#e74c3c"}'>
{f"BUYING ₹{abs(fii_dii['fii_net']):,.0f} Cr 🟢" if fii_dii.get('fii_net') and fii_dii['fii_net']>0 else
 f"SELLING ₹{abs(fii_dii['fii_net']):,.0f} Cr 🔴" if fii_dii.get('fii_net') else "Data updating..."}</b><br>
DII (Indian funds): <b>
{f"BUYING ₹{abs(fii_dii['dii_net']):,.0f} Cr 🟢" if fii_dii.get('dii_net') and fii_dii['dii_net']>0 else
 f"SELLING ₹{abs(fii_dii['dii_net']):,.0f} Cr 🔴" if fii_dii.get('dii_net') else "Data updating..."}</b>
</p></div>

<h2 style='border-bottom:2px solid #2980b9;padding-bottom:8px;margin-top:25px'>📰 Section 3 — News Since Morning</h2>
{section_tip("Any new developments since the 8 AM morning scan. Breaking news can change the direction of a stock instantly.")}
{table_start(["Stock","Headline","Sentiment","What to do"])}
{n_rows}{table_end()}

<h2 style='border-bottom:2px solid #2980b9;padding-bottom:8px;margin-top:25px'>🗺️ Section 4 — Sector Momentum Mid-Session</h2>
{section_tip("Has sector momentum changed since morning? A sector turning bearish mid-session is a warning for stocks in that sector.")}
<table border='1' cellpadding='8' cellspacing='0' style='width:60%;border-collapse:collapse;font-size:13px'>
<tr style='background:#2c3e50;color:white'><th>Sector</th><th>Mid-Session Momentum</th></tr>
{s_rows}</table>

<h2 style='border-bottom:2px solid #2980b9;padding-bottom:8px;margin-top:25px'>💼 Section 5 — Your Open Trades Mid-Session</h2>
{section_tip("Live P&L on all your open positions. Progress bar shows how far you are from your target. Action column tells you exactly what to do RIGHT NOW. Prices are 15 min delayed — verify exact price in Zerodha before acting.")}
<div style='background:{"#eafaf1" if total_pnl>=0 else "#fdf2f2"};padding:15px;border-radius:8px;border-left:4px solid {total_color};margin-bottom:15px'>
<h3 style='margin:0;color:{total_color}'>💰 Total P&L Mid-Session: ₹{total_pnl:+,.0f} ({total_pnl_pct:+.1f}%)</h3>
<p style='margin:5px 0 0;font-size:13px'>Invested: ₹{total_invested:,.0f} | Current value: ₹{total_current:,.0f}</p>
</div>
{table_start(["Stock","Entry","Current","Day Chg","P&L ₹","P&L %","RSI","Target|SL","Progress","Action now"])}
{t_rows}{table_end()}

<h2 style='border-bottom:2px solid #2980b9;padding-bottom:8px;margin-top:25px'>🔔 Section 6 — New Signals Since 8 AM</h2>
{section_tip("Any new strong buy signals that appeared after the morning scan. These are fresh opportunities you may have missed in the morning report.")}
{table_start(["#","Stock","Price","Signal","Efficiency","RSI","Entry/Target/SL","Price as of"])}
{new_rows}{table_end()}

<p style='color:#7f8c8d;font-size:12px;margin-top:25px;border-top:1px solid #eee;padding-top:10px'>
⚠️ All prices are 15 minutes delayed. Always verify exact price in Zerodha before placing any order.<br>
Actions recommended are based on technical signals only — use your own judgment.<br>
Use /analyse STOCKNAME in Telegram for instant analysis of any stock.
</p></body></html>"""
    return html

def run():
    today = datetime.now(IST).strftime('%d %b %Y')
    now = datetime.now(IST).strftime('%I:%M %p IST')
    print(f"\n{'='*60}\nMidday Update v3.0 — {today} {now}\n{'='*60}")

    sheet = setup_sheets()

    # Get market data
    global_data = get_global_markets()
    fii_dii = get_fii_dii()
    news = get_news()
    sector_signals = get_sector_momentum()
    nifty = analyze_index("^NSEI","Nifty 50")
    banknifty = analyze_index("^NSEBANK","Bank Nifty")
    sensex = analyze_index("^BSESN","Sensex")
    nifty_dir = nifty['direction'] if nifty else "NEUTRAL"

    # Get open trades
    trades_data = []
    if sheet:
        trades = get_open_trades(sheet)
        for t in trades:
            sym = t.get('Stock','')
            entry = float(t.get('Entry Price', 0))
            qty = int(t.get('Qty', 0))
            if not sym or not entry or not qty:
                continue
            pd_data = get_current_price_live(sym)
            if not pd_data:
                continue
            try:
                ed = datetime.strptime(t.get('Entry Date',''), '%d %b %Y')
                days = (datetime.now(IST).replace(tzinfo=None) - ed).days
            except:
                days = int(t.get('Days Held', 0))
            pnl = (pd_data['current'] - entry) * qty
            pnl_pct = ((pd_data['current'] - entry) / entry) * 100
            action, reason, color = get_exit_signal(
                {**t, 'Days Held': days}, pd_data, nifty_dir)
            news_h, news_s = None, None
            for n in news:
                if sym.upper() in n['stock'].upper():
                    news_h = n['headline'][:80]; news_s = n['sentiment']; break
            trades_data.append({
                "symbol": sym, "entry": entry, "qty": qty,
                "current": pd_data['current'],
                "day_chg": pd_data['day_chg'],
                "rsi": pd_data['rsi'],
                "pnl": pnl, "pnl_pct": pnl_pct, "days": days,
                "target": float(t.get('Target', entry*1.1)),
                "sl": float(t.get('Stop Loss', entry*0.97)),
                "action": action, "reason": reason, "color": color,
                "news": news_h, "news_sentiment": news_s,
            })
            time.sleep(0.5)

    # Quick scan for new signals (portfolio + top sectors)
    sector_stocks = []
    for sector, mood in sector_signals.items():
        if "BULLISH" in mood:
            sector_stocks.extend(SECTOR_MAP.get(sector, [])[:5])
    scan_list = list(set(get_portfolio_symbols() + sector_stocks))[:80]
    new_signals = []
    for sym in scan_list:
        r = calculate_signal(sym, sector_signals, nifty_dir)
        if r and r['signal'] in ["STRONG BUY","BUY"] and r['efficiency'] >= 3:
            new_signals.append(r)
        time.sleep(0.3)
    top5_new = sorted(new_signals, key=lambda x: x['efficiency'], reverse=True)[:5]

    # Send
    tg = build_tg_midday(today, now, global_data, fii_dii, news, nifty,
                         banknifty, sector_signals, trades_data, top5_new)
    send_telegram(tg)

    email_body = build_email_midday(today, now, global_data, fii_dii, news,
                                    nifty, banknifty, sensex, sector_signals,
                                    trades_data, top5_new)
    total_pnl = sum(t['pnl'] for t in trades_data)
    total_pnl_pct = 0
    if trades_data:
        invested = sum(t['entry']*t['qty'] for t in trades_data)
        curr_val = sum(t['current']*t['qty'] for t in trades_data)
        total_pnl_pct = ((curr_val-invested)/invested*100) if invested > 0 else 0
    mood = nifty['mood'] if nifty else 'N/A'
    send_email(
        subject=f"☀️ Midday Update {today} | {mood} | P&L: ₹{total_pnl:+,.0f} ({total_pnl_pct:+.1f}%)",
        body=email_body
    )
    print("\n✅ Midday update complete!")

run()
