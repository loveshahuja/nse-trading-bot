# ============================================================
# MORNING SCANNER v3.0 — 8:00 AM IST
# Full NSE scan + all 6 forces + detailed explanations
# ============================================================
from utils import *

def build_tg_message(today, global_data, fii_dii, news, nifty, banknifty,
                     sensex, sector_signals, portfolio_results, top20, total):
    # Global
    dow = global_data.get('US_DOW', {})
    nasdaq = global_data.get('US_NASDAQ', {})
    crude = global_data.get('CRUDE_OIL', {})
    usd = global_data.get('USD_INR', {})
    vix = global_data.get('VIX', {})

    def fmt(d, invert=False):
        if not d or d.get('price', 0) == 0:
            return "N/A"
        c = d.get('change_pct', 0)
        if invert: c = -c
        e = "🟢" if c > 0 else "🔴" if c < 0 else "🟡"
        return f"{d['price']:,.2f} ({c:+.2f}%) {e}"

    nifty_txt = f"{nifty['level']:,.0f} | RSI {nifty['rsi']} | {nifty['mood']}" if nifty else "N/A"
    bn_txt = f"{banknifty['level']:,.0f} | RSI {banknifty['rsi']} | {banknifty['mood']}" if banknifty else "N/A"

    fii = fii_dii.get('fii_net')
    dii = fii_dii.get('dii_net')
    fii_txt = f"₹{abs(fii):,.0f} Cr {'BOUGHT 🟢' if fii>0 else 'SOLD 🔴'}" if fii is not None else "Data unavailable"
    dii_txt = f"₹{abs(dii):,.0f} Cr {'BOUGHT 🟢' if dii>0 else 'SOLD 🔴'}" if dii is not None else "Data unavailable"

    news_txt = ""
    for n in news[:4]:
        news_txt += f"• <b>{n['stock']}</b>: {n['headline'][:70]}... {n['sentiment']}\n"
    if not news_txt:
        news_txt = "• No major news today\n"

    port_txt = ""
    for r in portfolio_results:
        e = "🟢" if "BUY" in r['signal'] else "🔴" if "SELL" in r['signal'] else "🟡"
        fno = " F&O✅" if r['is_fno'] else ""
        port_txt += f"{e} <b>{r['symbol']}</b> ₹{r['price']} | {r['signal']} | RSI:{r['rsi']} | {r['efficiency']}/5{fno}\n"

    top_txt = ""
    for i, r in enumerate(top20[:5], 1):
        fno = " F&O✅" if r['is_fno'] else ""
        top_txt += f"{i}. <b>{r['symbol']}</b> ₹{r['price']} | {r['signal']} | RSI:{r['rsi']} | Eff:{r['efficiency']}/5{fno}\n"
        top_txt += f"   Entry ₹{r['entry']} | Target ₹{r['target']} | SL ₹{r['sl']}\n"

    opt_txt = ""
    if nifty:
        o = get_nifty_options_rec(nifty['level'], nifty['rsi'], nifty['direction'])
        opt_txt = f"\n🎯 <b>NIFTY OPTION</b>: {o['action']} {o['strike']} {o['type']} ({o['expiry']})\nPremium ₹{o['prem_low']}–{o['prem_high']} | Target ₹{o['target']} | SL ₹{o['sl']} | Capital ₹{o['capital']:,}\n"

    sector_txt = ""
    for s, m in sector_signals.items():
        e = "🟢" if "BULL" in m else "🔴" if "BEAR" in m else "🟡"
        sector_txt += f"{e} {s}: {m}\n"

    return f"""📈 <b>MORNING SCAN — {today}</b>
⏰ Prices: Yesterday 3:30 PM NSE Close | Scanned: {total} stocks

━━━━━━━━━━━━━━━━━━━━
🌍 <b>GLOBAL MARKETS</b>
🇺🇸 Dow: {fmt(dow)} | Nasdaq: {fmt(nasdaq)}
🛢️ Crude: {fmt(crude)} | 💵 USD/INR: {fmt(usd, True)}
😨 VIX: {fmt(vix)}

💡 Rising US markets = positive opening for India today

━━━━━━━━━━━━━━━━━━━━
💰 <b>FII/DII ACTIVITY</b>
FII (Foreign funds): {fii_txt}
DII (Indian funds): {dii_txt}

💡 FII buying = big money flowing into India = bullish

━━━━━━━━━━━━━━━━━━━━
📰 <b>NEWS ALERTS</b>
{news_txt}
━━━━━━━━━━━━━━━━━━━━
📊 <b>INDEX DASHBOARD</b>
Nifty 50  : {nifty_txt}
BankNifty : {bn_txt}

💡 RSI below 40 = oversold = good to buy index
   RSI above 70 = overbought = be careful

━━━━━━━━━━━━━━━━━━━━
🗺️ <b>SECTOR MOMENTUM</b>
{sector_txt}
━━━━━━━━━━━━━━━━━━━━
{opt_txt}
━━━━━━━━━━━━━━━━━━━━
💼 <b>YOUR PORTFOLIO</b>
{port_txt}
━━━━━━━━━━━━━━━━━━━━
🏆 <b>TOP 5 TODAY (of {total} scanned)</b>
{top_txt}
━━━━━━━━━━━━━━━━━━━━
📧 Full detailed report + CSV sent to Gmail
⚠️ Verify all prices in Zerodha before trading
💬 Type /analyse STOCK for instant deep analysis"""

def build_email(today, now, global_data, fii_dii, news, nifty, banknifty,
                sensex, sector_signals, portfolio_results, top20, total):

    # ── Section 1: Global ─────────────────────────────────────
    global_items = [
        ("🇺🇸 US Dow Jones","US_DOW",
         "If US markets rose overnight → India opens positive. If US fell → India opens cautious."),
        ("🇺🇸 US Nasdaq","US_NASDAQ",
         "Nasdaq = tech stocks. Rises here = positive for Indian IT stocks like TCS, Infosys."),
        ("🛢️ Crude Oil","CRUDE_OIL",
         "Oil rising = fuel costs go up = bad for aviation (IndiGo), paints (Asian Paints), tyres (MRF). Oil falling = good."),
        ("💵 USD/INR","USD_INR",
         "Rupee weakening (higher number) = FII may pull money out = negative. Rupee stable = positive."),
        ("😨 VIX Fear Index","VIX",
         "VIX below 15 = calm market, safe to buy. VIX 15-20 = some nervousness. VIX above 25 = panic — avoid new trades."),
        ("🥇 Gold","GOLD",
         "Gold rising = investors seeking safety = they fear stock market may fall. Caution signal."),
    ]
    g_rows = ""
    opening_verdict = "POSITIVE 🟢"
    pos_count = 0; neg_count = 0
    for label, key, meaning in global_items:
        d = global_data.get(key, {})
        p = d.get('price', 0); c = d.get('change_pct', 0)
        if p == 0:
            g_rows += f"<tr><td><b>{label}</b></td><td>Fetching...</td><td>N/A</td><td style='font-size:12px;color:#7f8c8d'>{meaning}</td></tr>"
            continue
        color = "#27ae60" if c > 0 else "#e74c3c" if c < 0 else "#888"
        arrow = "▲" if c > 0 else "▼" if c < 0 else "●"
        if key in ["US_DOW","US_NASDAQ","US_SP500"] and c > 0: pos_count += 1
        elif key in ["US_DOW","US_NASDAQ","US_SP500"] and c < 0: neg_count += 1
        g_rows += f"<tr><td><b>{label}</b></td><td>{p:,.2f}</td><td style='color:{color}'><b>{arrow} {abs(c):.2f}%</b></td><td style='font-size:12px;color:#7f8c8d'>{meaning}</td></tr>"
    if pos_count >= 2: opening_verdict = "POSITIVE 🟢 — Good day to take fresh entries"
    elif neg_count >= 2: opening_verdict = "CAUTIOUS 🔴 — Global weakness, trade carefully today"
    else: opening_verdict = "MIXED 🟡 — Watch first 30 minutes before entering"

    # ── Section 2: FII/DII ─────────────────────────────────────
    fii = fii_dii.get('fii_net'); dii = fii_dii.get('dii_net')
    fii_avail = fii is not None
    fii_color = "#27ae60" if fii_avail and fii > 0 else "#e74c3c"
    dii_color = "#27ae60" if fii_avail and dii and dii > 0 else "#e74c3c"
    fii_activity = f"BUYING ₹{abs(fii):,.0f} Cr 🟢" if fii_avail and fii > 0 else f"SELLING ₹{abs(fii):,.0f} Cr 🔴" if fii_avail else "Data unavailable today"
    dii_activity = f"BUYING ₹{abs(dii):,.0f} Cr 🟢" if fii_avail and dii and dii > 0 else f"SELLING ₹{abs(dii):,.0f} Cr 🔴" if fii_avail else "Data unavailable today"
    net = (fii or 0) + (dii or 0)
    net_txt = f"Net flow: ₹{net:+,.0f} Cr — {'Money flowing IN 🟢' if net > 0 else 'Money flowing OUT 🔴' if net < 0 else 'Balanced'}" if fii_avail else ""

    # ── Section 3: News ────────────────────────────────────────
    n_rows = ""
    if news:
        for n in news:
            sc = "#27ae60" if "POSITIVE" in n['sentiment'] else "#e74c3c" if "NEGATIVE" in n['sentiment'] else "#f39c12"
            n_rows += f"<tr><td><b>{n['stock']}</b></td><td>{n['headline']}</td><td style='color:{sc}'>{n['sentiment']}</td><td style='font-size:12px;color:#7f8c8d'>{n['impact']}</td></tr>"
    else:
        n_rows = "<tr><td colspan='4' style='color:#7f8c8d'>No major news affecting your stocks today — technicals drive the market today</td></tr>"

    # ── Section 4: Indices ─────────────────────────────────────
    i_rows = ""
    overall_mood = "NEUTRAL 🟡"
    for idx in [nifty, banknifty, sensex]:
        if not idx: continue
        mc = mood_color(idx['mood']); cc = "#27ae60" if idx['change_pct'] > 0 else "#e74c3c"
        rsi_note = "Oversold ✅" if idx['rsi'] < 40 else "Overbought ⚠️" if idx['rsi'] > 70 else "Healthy ✅"
        i_rows += f"""<tr>
            <td><b>{idx['name']}</b></td>
            <td><b>{idx['level']:,.2f}</b></td>
            <td style='color:{cc}'>{idx['change_pct']:+.2f}%</td>
            <td>{idx['rsi']} — {rsi_note}</td>
            <td>{idx['trend']}</td>
            <td>{idx['macd']}</td>
            <td>₹{idx['support']:,.0f}</td>
            <td>₹{idx['resistance']:,.0f}</td>
            <td style='color:{mc}'><b>{idx['mood']}</b></td>
        </tr>"""
    if nifty: overall_mood = nifty['mood']

    # ── Section 5: Index Options ───────────────────────────────
    opt_html = "<p style='color:#888'>Index data unavailable for options calculation</p>"
    if nifty:
        o = get_nifty_options_rec(nifty['level'], nifty['rsi'], nifty['direction'])
        why = "Nifty is bullish — buying CALL means you profit when Nifty rises" if "CALL" in o['type'] else "Nifty is bearish — buying PUT means you profit when Nifty falls"
        opt_html = f"""<div style='background:#eaf4fb;padding:15px;border-radius:8px;border-left:4px solid #3498db;margin:10px 0'>
        <h4 style='margin:0 0 8px'>🎯 NIFTY {o['type']} — {o['action']}</h4>
        <table style='width:100%;font-size:13px'><tr>
        <td><b>Strike:</b> {o['strike']}</td>
        <td><b>Expiry:</b> {o['expiry']}</td>
        <td><b>Buy premium:</b> ₹{o['prem_low']}–{o['prem_high']}</td>
        <td><b>Target premium:</b> ₹{o['target']} (+100%)</td>
        <td><b>Stop loss:</b> ₹{o['sl']}</td>
        <td><b>1 lot capital:</b> ₹{o['capital']:,} ({o['lot']} shares)</td>
        </tr></table>
        <p style='font-size:13px;color:#2c3e50;margin:10px 0 0'>
        💡 <b>Simple explanation:</b> {why}. Nifty is at {nifty['level']:,.0f}.
        You pay ₹{o['prem_low']}–{o['prem_high']} per share × {o['lot']} shares = ₹{o['capital']:,} total investment.
        If Nifty moves in your direction, the premium doubles to ₹{o['target']} → you make 100% profit.
        If wrong, you exit at ₹{o['sl']} and lose only half your investment.
        Maximum loss = ₹{o['capital']:,}. Cannot lose more than that.
        ⚠️ Check actual premium in Zerodha Options Chain before buying.</p></div>"""

    # ── Section 6: Portfolio ───────────────────────────────────
    p_rows = ""
    for r in portfolio_results:
        sc = sig_color(r['signal']); dc = "#27ae60" if r['day_chg'] > 0 else "#e74c3c"
        stars = "⭐" * r['efficiency']
        hold_note = ""
        if r['rsi'] > 75: hold_note = "⚠️ Overbought — consider booking partial profits"
        elif r['rsi'] < 40: hold_note = "✅ Oversold — consider adding more"
        elif "BUY" in r['signal'] and r['efficiency'] >= 4: hold_note = "✅ Strong setup — good to hold/add"
        elif "SELL" in r['signal']: hold_note = "🔴 Review position — consider reducing"
        else: hold_note = "🟡 Hold — no action needed today"
        fno_badge = "<span style='background:#27ae60;color:white;padding:1px 5px;border-radius:3px;font-size:11px'>F&O</span>" if r['is_fno'] else ""
        p_rows += f"""<tr>
            <td><b>{r['symbol']}</b> {fno_badge}</td>
            <td>₹{r['price']}</td>
            <td style='color:{dc}'>{r['day_chg']:+.2f}%</td>
            <td style='color:{sc}'><b>{r['signal']}</b></td>
            <td>{r['rsi']}</td>
            <td>{r['trend']}</td>
            <td>{r['vol_surge']}</td>
            <td>{r['efficiency']}/5 {stars}</td>
            <td style='font-size:11px;color:#2c3e50'>{hold_note}</td>
            <td style='font-size:11px;color:#888'>{r['timestamp']}</td>
        </tr>"""

    # ── Section 7: Top 20 ──────────────────────────────────────
    s_rows = "".join(
        f"<tr><td><b>{s}</b></td><td style='color:{mood_color(m)}'>{m}</td></tr>"
        for s, m in sector_signals.items()
    )
    t_rows = ""
    for i, r in enumerate(top20, 1):
        sc = sig_color(r['signal']); stars = "⭐" * r['efficiency']
        fno_badge = "<span style='background:#27ae60;color:white;padding:1px 5px;border-radius:3px;font-size:11px'>F&O</span>" if r['is_fno'] else ""
        details_html = "<br>".join(r['details'])
        opt_row = ""
        if r['options']:
            o = r['options']
            opt_row = f"""<tr style='background:#f0faf0'><td colspan='10' style='padding:8px 12px;font-size:12px'>
            <b>🎯 OPTIONS ROUTE:</b> Buy {r['symbol']} <b>{o['strike']} {o['type']}</b> ({o['expiry']}) |
            Pay premium: ₹{o['prem_low']}–{o['prem_high']} | Target premium: ₹{o['tgt_prem']} (+120%) |
            Stop loss: ₹{o['sl_prem']} | Lot: {o['lot_size']} shares | Capital: ₹{o['cap_low']:,}–{o['cap_high']:,}<br>
            <span style='color:#555'>💡 You pay max ₹{o['cap_high']:,}. If {r['symbol']} hits ₹{r['target']:.0f},
            option premium doubles. Your maximum loss = premium paid only. Cannot lose more.</span>
            </td></tr>"""
        t_rows += f"""<tr>
            <td>{i}</td>
            <td><b>{r['symbol']}</b> {fno_badge}</td>
            <td>₹{r['price']}</td>
            <td style='color:{sc}'><b>{r['signal']}</b></td>
            <td>{r['efficiency']}/5 {stars}</td>
            <td>{r['rsi']}</td>
            <td>{r['sector']}</td>
            <td>Entry ₹{r['entry']}<br>Target ₹{r['target']}<br>SL ₹{r['sl']}</td>
            <td style='font-size:11px;color:#888'>{r['timestamp']}</td>
        </tr>
        <tr style='background:#f8f9fa'><td colspan='9' style='padding:5px 12px;font-size:12px;color:#555'>{details_html}</td></tr>
        {opt_row}"""

    html = f"""<html><body style='font-family:Arial,sans-serif;max-width:1000px;margin:auto;padding:20px;color:#2c3e50'>
{html_header('📈 NSE Morning Scanner v3.0', f'{today} | Scan time: {now} | Stocks scanned: {total} | ⏰ Prices: Yesterday 3:30 PM NSE Close')}

<div style='background:#eaf4fb;padding:15px;border-radius:8px;border-left:4px solid {mood_color(overall_mood)};margin-bottom:20px'>
<h3 style='margin:0'>🌡️ Overall Market Mood: <span style='color:{mood_color(overall_mood)}'>{overall_mood}</span></h3>
<p style='margin:5px 0;font-size:13px'>Global Opening Verdict: <b>{opening_verdict}</b></p>
<p style='margin:0;font-size:13px'>Buy signals: <b>{len([r for r in top20 if 'BUY' in r['signal']])}</b> strong setups found from {total} stocks scanned today</p>
</div>

<h2 style='border-bottom:2px solid #3498db;padding-bottom:8px'>🌍 Section 1 — Global Markets</h2>
{section_tip("Before Indian market opens at 9:15 AM, check what happened globally overnight. US markets, oil prices and currency all affect how Indian stocks will move today. Green = positive for India. Red = be cautious today.")}
{table_start(["Market","Level","Change","What it means for YOU today"])}
{g_rows}{table_end()}
<div style='background:#e8f8f5;padding:10px;border-radius:6px;margin:8px 0;font-size:13px'>
✅ <b>Opening Verdict:</b> {opening_verdict}</div>

<h2 style='border-bottom:2px solid #3498db;padding-bottom:8px;margin-top:25px'>💰 Section 2 — FII/DII Activity</h2>
{section_tip("FII = Big foreign funds like Goldman Sachs, JP Morgan, Deutsche Bank. DII = Indian mutual funds like SBI MF, HDFC MF. When FII buys in large quantity = market goes up. Think of them as the tide — when tide comes in, all boats rise.")}
{table_start(["Type","Who they are","Activity","Amount","What it means"])}
<tr><td><b>FII (Foreign)</b></td><td style='font-size:12px'>Goldman Sachs, JP Morgan, foreign funds</td>
<td style='color:{fii_color}'><b>{fii_activity}</b></td>
<td style='color:{fii_color}'>{"₹"+f"{abs(fii):,.0f} Cr" if fii_avail else "N/A"}</td>
<td>{"Foreign money flowing INTO India — very bullish signal 🟢" if fii_avail and fii and fii>0 else "Foreign money flowing OUT — be cautious 🔴" if fii_avail else "NSE data unavailable — check NSE website manually"}</td></tr>
<tr><td><b>DII (Domestic)</b></td><td style='font-size:12px'>SBI MF, HDFC MF, LIC, Indian funds</td>
<td style='color:{dii_color}'><b>{dii_activity}</b></td>
<td style='color:{dii_color}'>{"₹"+f"{abs(dii):,.0f} Cr" if fii_avail and dii else "N/A"}</td>
<td>{"Indian funds supporting the market — positive 🟢" if fii_avail and dii and dii>0 else "Indian funds reducing exposure — neutral 🟡" if fii_avail else "NSE data unavailable"}</td></tr>
{table_end()}
{"<div style='background:#eaf4fb;padding:8px;border-radius:6px;margin:8px 0;font-size:13px'><b>"+net_txt+"</b></div>" if net_txt else ""}

<h2 style='border-bottom:2px solid #3498db;padding-bottom:8px;margin-top:25px'>📰 Section 3 — News Alerts</h2>
{section_tip("Latest news filtered for YOUR portfolio stocks and major market events. Positive news = stock likely to rise today. Negative = stock may face selling. Always news + technicals together make a stronger case.")}
{table_start(["Stock/Topic","Headline","Sentiment","What to do"])}
{n_rows}{table_end()}

<h2 style='border-bottom:2px solid #3498db;padding-bottom:8px;margin-top:25px'>📊 Section 4 — Index Dashboard</h2>
{section_tip("Think of Nifty as the heartbeat of the market. Support = price floor (buyers come here). Resistance = price ceiling (sellers come here). If Nifty breaks resistance = big rally. RSI below 40 = oversold = good to buy. RSI above 70 = overbought = careful.")}
{table_start(["Index","Level","Today","RSI","Trend","MACD","Support","Resistance","Mood"])}
{i_rows}{table_end()}

<h2 style='border-bottom:2px solid #3498db;padding-bottom:8px;margin-top:25px'>🗺️ Section 5 — Sector Momentum</h2>
{section_tip("Sectors that are bullish = stocks in that sector have tailwind. Trade WITH the sector — buy stocks in bullish sectors, avoid stocks in bearish sectors. Individual stock can fight the sector for a while but not forever.")}
<table border='1' cellpadding='8' cellspacing='0' style='width:60%;border-collapse:collapse;font-size:13px'>
<tr style='background:#2c3e50;color:white'><th>Sector</th><th>Momentum Today</th></tr>
{s_rows}</table>

<h2 style='border-bottom:2px solid #3498db;padding-bottom:8px;margin-top:25px'>🎯 Section 6 — Index Options Recommendation</h2>
{section_tip("Instead of buying individual stocks, you can trade Nifty directly. CALL = bet Nifty will rise. PUT = bet Nifty will fall. Small capital, big potential return. Maximum loss = only the premium you paid. Always check actual premium in Zerodha Options Chain before buying.")}
{opt_html}

<h2 style='border-bottom:2px solid #3498db;padding-bottom:8px;margin-top:25px'>💼 Section 7 — Your Portfolio Signals</h2>
{section_tip("Fresh analysis of YOUR holdings every morning. What happened overnight. Whether to add more, hold, or reduce. Efficiency stars (⭐) = how many indicators are aligned. 5/5 = all green lights. 2/5 = mixed — proceed carefully.")}
{table_start(["Stock","Price","Day Chg","Signal","RSI","Trend","Volume","Efficiency","What to do today","Price as of"])}
{p_rows}{table_end()}

<h2 style='border-bottom:2px solid #3498db;padding-bottom:8px;margin-top:25px'>🏆 Section 8 — Top 20 Opportunities Today</h2>
{section_tip(f"Best buy setups from {total} NSE stocks scanned today. Stocks with price > ₹50, daily volume > 50,000 shares, and highest efficiency score. Each shows STOCK ROUTE (buy shares) and OPTIONS ROUTE (buy CE) so you choose. Always verify entry price in Zerodha — prices shown are yesterday's close.")}
{table_start(["#","Stock","Price","Signal","Efficiency","RSI","Sector","Entry / Target / SL","Price as of"])}
{t_rows}{table_end()}

<p style='color:#7f8c8d;font-size:12px;margin-top:25px;border-top:1px solid #eee;padding-top:10px'>
⚠️ These are technical signals only. Always do your own research before investing.<br>
All prices based on NSE official closing prices from previous trading day 3:30 PM.<br>
Option premiums are estimated — check actual premiums in Zerodha Options Chain before trading.<br>
Stocks filtered: Price > ₹50, Volume > 50,000/day, All NSE main board stocks.<br>
Use /analyse STOCKNAME in Telegram anytime for instant deep analysis.<br>
Full scan data attached as CSV.
</p></body></html>"""
    return html

def save_scan_to_sheets(sheet, top20, portfolio_results, today):
    try:
        ws = sheet.worksheet("Daily Scan")
        try:
            if ws.row_count == 0 or not ws.row_values(1):
                ws.append_row(["Date","Rank","Stock","Price","Signal","Efficiency",
                               "RSI","Trend","MACD","Volume","Sector","Entry","Target","SL","F&O"])
        except:
            ws.append_row(["Date","Rank","Stock","Price","Signal","Efficiency",
                           "RSI","Trend","MACD","Volume","Sector","Entry","Target","SL","F&O"])
        for i, r in enumerate(top20, 1):
            ws.append_row([today, i, r['symbol'], r['price'], r['signal'],
                          f"{r['efficiency']}/5", r['rsi'], r['trend'], r['macd'],
                          r['vol_surge'], r['sector'], r['entry'], r['target'],
                          r['sl'], "YES" if r['is_fno'] else "NO"])
        print("Saved to Daily Scan sheet!")
    except Exception as e:
        print(f"Sheets save error: {e}")

def run():
    today = datetime.now().strftime('%d %b %Y')
    now = datetime.now().strftime('%I:%M %p')
    print(f"\n{'='*60}\nNSE Morning Scanner v3.0 — {today} {now}\n{'='*60}")

    sheet = setup_sheets()

    # Step 1: Sector momentum first (before main scan)
    sector_signals = get_sector_momentum()

    # Step 2: Global + FII + News simultaneously
    global_data = get_global_markets()
    fii_dii = get_fii_dii()
    news = get_news()

    # Step 3: Indices
    nifty = analyze_index("^NSEI", "Nifty 50")
    banknifty = analyze_index("^NSEBANK", "Bank Nifty")
    sensex = analyze_index("^BSESN", "Sensex")
    nifty_dir = nifty['direction'] if nifty else "NEUTRAL"
    print(f"Nifty: {nifty['level'] if nifty else 'N/A'} | {nifty['mood'] if nifty else 'N/A'}")

    # Step 4: Portfolio
    print("Scanning portfolio...")
    portfolio_results = []
    for sym in MY_PORTFOLIO:
        r = calculate_signal(sym, sector_signals, nifty_dir)
        if r:
            portfolio_results.append(r)
        time.sleep(0.5)

    # Step 5: Full NSE scan
    nse_syms = get_nse_symbols()
    print(f"Scanning {len(nse_syms)} stocks...")
    all_results = []
    for i, sym in enumerate(nse_syms):
        r = calculate_signal(sym, sector_signals, nifty_dir)
        if r:
            all_results.append(r)
        if (i+1) % 300 == 0:
            print(f"  Progress: {i+1}/{len(nse_syms)} | Valid: {len(all_results)}")
        time.sleep(0.25)

    # Step 6: Rank — FIX 5: Filter stocks where target < 7% away
    def has_good_target(r):
        target_gap = ((r['target'] - r['price']) / r['price']) * 100
        return target_gap >= 7.0

    strong = sorted([r for r in all_results if r['signal']=="STRONG BUY" and has_good_target(r)],
                    key=lambda x: (x['efficiency'], x['buy_score']), reverse=True)
    buys = sorted([r for r in all_results if r['signal']=="BUY" and has_good_target(r)],
                  key=lambda x: (x['efficiency'], x['buy_score']), reverse=True)
    top20 = (strong + buys)[:20]
    total = len(all_results)
    print(f"\nScan complete! Valid: {total} | Strong Buy: {len(strong)} | Buy: {len(buys)}")

    # Step 7: Save + send
    if sheet:
        save_scan_to_sheets(sheet, top20, portfolio_results, today)

    csv_file = f"scan_{datetime.now().strftime('%Y%m%d')}.csv"
    if all_results:
        pd.DataFrame(all_results).to_csv(csv_file, index=False)

    tg = build_tg_message(today, global_data, fii_dii, news, nifty, banknifty,
                          sensex, sector_signals, portfolio_results, top20, total)
    send_telegram(tg)

    email_body = build_email(today, now, global_data, fii_dii, news, nifty,
                             banknifty, sensex, sector_signals, portfolio_results, top20, total)
    top_pick = top20[0]['symbol'] if top20 else 'N/A'
    mood = nifty['mood'] if nifty else 'N/A'
    send_email(
        subject=f"📈 Morning Scan {today} | {mood} | Top: {top_pick} | {total} scanned",
        body=email_body, csv_file=csv_file
    )
    print("\n✅ Morning scan complete!")

run()
