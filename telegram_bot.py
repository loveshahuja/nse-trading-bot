# ============================================================
# TELEGRAM BOT v3.0 — 24/7 Command Listener
# ============================================================
from utils import *

def setup_sheets_bot():
    return setup_sheets()

def get_updates(offset=None):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
        r = requests.get(url, params={"timeout":30,"offset":offset}, timeout=35)
        if r.status_code == 200:
            return r.json().get('result', [])
    except:
        pass
    return []

def cmd_buy(args, sheet, chat_id):
    if len(args) < 3:
        return "❌ Format: /buy STOCK PRICE QTY\nExample: /buy BEL 435 50"
    try:
        stock = args[0].upper().replace(".NS","")
        price = float(args[1]); qty = int(args[2])
        target = round(price*1.10, 2); sl = round(price*0.97, 2)
        today = datetime.now().strftime('%d %b %Y')
        invested = price * qty
        lot = FON_LOT_SIZES.get(stock, 0)
        fno_note = f"\n\nF&O eligible ✅ Lot size: {lot} shares" if lot else "\n\nNot F&O eligible"
        if sheet:
            ws = sheet.worksheet("Open Trades")
            if not ws.row_values(1):
                ws.append_row(["Entry Date","Stock","Type","Entry Price","Qty",
                               "Target","Stop Loss","Days Held","Notes"])
            ws.append_row([today, stock, "STOCK", price, qty, target, sl, 0, ""])
        return f"""✅ <b>TRADE RECORDED — {stock}</b>

📋 <b>Trade Details</b>
Type      : STOCK BUY
Entry     : ₹{price}
Qty       : {qty} shares
Capital   : ₹{invested:,.0f}
Date      : {today}

🎯 <b>Targets</b>
Target    : ₹{target} (+10%)
Stop Loss : ₹{sl} (-3%)
Max loss  : ₹{round((price-sl)*qty):,.0f}
Max gain  : ₹{round((target-price)*qty):,.0f}

💡 <b>What to do</b>
Set price alert in Zerodha:
— Target alert at ₹{target}
— SL alert at ₹{sl}
Bot tracks this in all 3 daily updates.{fno_note}"""
    except Exception as e:
        return f"❌ Error: {e}\nFormat: /buy STOCK PRICE QTY"

def cmd_buyce(args, sheet, chat_id):
    if len(args) < 4:
        return "❌ Format: /buyce STOCK STRIKE PREMIUM LOTS\nExample: /buyce BEL 450 13.5 1"
    try:
        stock = args[0].upper().replace(".NS","")
        strike = float(args[1]); prem = float(args[2]); lots = int(args[3])
        lot_size = FON_LOT_SIZES.get(stock, 500)
        total_qty = lot_size * lots
        capital = round(prem * total_qty, 0)
        target_prem = round(prem * 2.2, 1)
        sl_prem = round(prem * 0.5, 1)
        today = datetime.now().strftime('%d %b %Y')
        if sheet:
            ws = sheet.worksheet("Open Trades")
            ws.append_row([today, stock, f"CE_{strike}", prem, total_qty,
                           target_prem, sl_prem, 0, f"{lots} lot(s)"])
        return f"""✅ <b>OPTIONS TRADE RECORDED — {stock}</b>

📋 <b>Trade Details</b>
Type      : CALL OPTION (CE)
Strike    : {strike}
Premium   : ₹{prem}
Lots      : {lots} × {lot_size} = {total_qty} shares
Capital   : ₹{capital:,.0f}
Date      : {today}

🎯 <b>Targets</b>
Target premium : ₹{target_prem} (+120%)
Stop loss prem : ₹{sl_prem} (-50%)
Max gain       : ₹{round((target_prem-prem)*total_qty):,.0f}
Max loss       : ₹{round((prem-sl_prem)*total_qty):,.0f}

💡 <b>What to do</b>
Exit when premium hits ₹{target_prem}
Exit if premium falls to ₹{sl_prem}
Never hold to expiry — exit before last 5 days"""
    except Exception as e:
        return f"❌ Error: {e}\nFormat: /buyce STOCK STRIKE PREMIUM LOTS"

def cmd_sell(args, sheet, chat_id):
    if len(args) < 2:
        return "❌ Format: /sell STOCK PRICE\nExample: /sell BEL 475"
    try:
        stock = args[0].upper().replace(".NS",""); exit_price = float(args[1])
        today = datetime.now().strftime('%d %b %Y')
        if not sheet:
            return "❌ Cannot connect to Google Sheets"
        open_ws = sheet.worksheet("Open Trades")
        records = open_ws.get_all_records()
        trade_row = None; row_num = None
        for i, r in enumerate(records, 2):
            if r.get('Stock','').upper() == stock and r.get('Type') == 'STOCK':
                trade_row = r; row_num = i; break
        if not trade_row:
            return f"❌ No open STOCK trade for {stock}.\nCheck /portfolio for open trades."
        entry = float(trade_row.get('Entry Price',0))
        qty = int(trade_row.get('Qty',0))
        pnl = (exit_price-entry)*qty
        pnl_pct = ((exit_price-entry)/entry)*100
        days = trade_row.get('Days Held',0)
        closed_ws = sheet.worksheet("Closed Trades")
        if not closed_ws.row_values(1):
            closed_ws.append_row(["Entry Date","Exit Date","Stock","Type",
                                  "Entry","Exit","Qty","P&L","P&L%","Days"])
        closed_ws.append_row([trade_row.get('Entry Date'), today, stock, 'STOCK',
                              entry, exit_price, qty, round(pnl,2), round(pnl_pct,2), days])
        open_ws.delete_rows(row_num)
        e = "🟢" if pnl > 0 else "🔴"
        lesson = "🎉 Profitable trade! Well done. Note what worked." if pnl > 0 else \
                 "📚 Loss. Review: Did stop loss trigger? What signal was wrong? Learn and improve." if pnl < 0 else \
                 "🟡 Breakeven trade."
        return f"""{e} <b>TRADE CLOSED — {stock}</b>

📋 <b>Summary</b>
Entry  : ₹{entry}
Exit   : ₹{exit_price}
Qty    : {qty} shares
Days   : {days}

💰 <b>Result</b>
P&L    : ₹{pnl:+,.0f}
Return : {pnl_pct:+.1f}%

{lesson}
Trade saved to Closed Trades history."""
    except Exception as e:
        return f"❌ Error: {e}"

def cmd_sellce(args, sheet, chat_id):
    if len(args) < 3:
        return "❌ Format: /sellce STOCK STRIKE EXIT_PREMIUM\nExample: /sellce BEL 450 28.5"
    try:
        stock = args[0].upper().replace(".NS","")
        strike = float(args[1]); exit_prem = float(args[2])
        today = datetime.now().strftime('%d %b %Y')
        if not sheet:
            return "❌ Cannot connect to Google Sheets"
        open_ws = sheet.worksheet("Open Trades")
        records = open_ws.get_all_records()
        trade_row = None; row_num = None
        for i, r in enumerate(records, 2):
            if r.get('Stock','').upper()==stock and str(strike) in str(r.get('Type','')):
                trade_row = r; row_num = i; break
        if not trade_row:
            return f"❌ No open CE trade for {stock} {strike}.\nCheck /portfolio."
        entry_prem = float(trade_row.get('Entry Price',0))
        qty = int(trade_row.get('Qty',0))
        pnl = (exit_prem-entry_prem)*qty
        pnl_pct = ((exit_prem-entry_prem)/entry_prem)*100
        days = trade_row.get('Days Held',0)
        closed_ws = sheet.worksheet("Closed Trades")
        closed_ws.append_row([trade_row.get('Entry Date'), today, stock,
                              f"CE_{strike}", entry_prem, exit_prem, qty,
                              round(pnl,2), round(pnl_pct,2), days])
        open_ws.delete_rows(row_num)
        return f"""{'🟢' if pnl>0 else '🔴'} <b>OPTIONS TRADE CLOSED — {stock} {strike} CE</b>

Entry premium : ₹{entry_prem}
Exit premium  : ₹{exit_prem}
Qty           : {qty} shares
P&L           : ₹{pnl:+,.0f} ({pnl_pct:+.1f}%)
Days held     : {days}

{'🎉 Great options trade!' if pnl>0 else '📚 Options loss. Review entry timing and strike selection.'}"""
    except Exception as e:
        return f"❌ Error: {e}"

def cmd_portfolio(sheet):
    if not sheet:
        return "❌ Cannot connect to Google Sheets"
    try:
        ws = sheet.worksheet("Open Trades")
        records = ws.get_all_records()
        if not records:
            return "📊 <b>No open trades</b>\n\nRecord your first trade:\n/buy STOCK PRICE QTY\nExample: /buy BEL 435 50"
        msg = f"💼 <b>OPEN POSITIONS</b>\n⏰ {datetime.now().strftime('%d %b %Y %I:%M %p')}\n\n"
        total = 0
        for r in records:
            stock = r.get('Stock',''); entry = float(r.get('Entry Price',0))
            qty = int(r.get('Qty',0)); target = float(r.get('Target',0))
            sl = float(r.get('Stop Loss',0)); days = r.get('Days Held',0)
            trade_type = r.get('Type','STOCK'); invested = entry*qty; total += invested
            progress = f"Target ₹{target} | SL ₹{sl}" if trade_type=='STOCK' else f"Exit ₹{target} | SL ₹{sl}"
            msg += f"<b>{stock}</b> ({trade_type})\n"
            msg += f"Entry ₹{entry} × {qty} = ₹{invested:,.0f} | Day {days}\n"
            msg += f"{progress}\n\n"
        msg += f"💰 Total deployed: ₹{total:,.0f}\n\n"
        msg += "For live P&L → wait for 12 PM or 4 PM update\nOr use /analyse STOCK for current price"
        return msg
    except Exception as e:
        return f"❌ Error: {e}"

def cmd_analyse(args, chat_id):
    if not args:
        return "❌ Format: /analyse STOCK\nExample: /analyse BEL"
    sym = args[0].upper().replace(".NS","")
    try:
        ticker = sym+".NS"
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)
        if df.empty or len(df) < 30:
            return f"❌ No data for {sym}. Check symbol name."
        close = df['Close'].squeeze(); volume = df['Volume'].squeeze()
        curr = float(close.iloc[-1]); prev = float(close.iloc[-2])
        rsi = float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
        ema20 = float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
        ema50 = float(ta.trend.EMAIndicator(close,50).ema_indicator().iloc[-1])
        macd_obj = ta.trend.MACD(close)
        ml = float(macd_obj.macd().iloc[-1]); sl = float(macd_obj.macd_signal().iloc[-1])
        avg_vol = float(volume.tail(20).mean()); lat_vol = float(volume.iloc[-1])
        vol_surge = lat_vol > avg_vol*1.5
        support = round(float(close.tail(20).min()),2)
        resistance = round(float(close.tail(20).max()),2)
        day_chg = ((curr-prev)/prev)*100
        is_fno = ticker in FON_STOCKS
        lot = FON_LOT_SIZES.get(sym,0)

        bs = 0
        if rsi < 40: bs += 2
        elif rsi < 50: bs += 1
        if ema20 > ema50: bs += 2
        if ml > sl: bs += 2
        if vol_surge: bs += 1
        ss = 0
        if rsi > 70: ss += 2
        elif rsi > 60: ss += 1
        if ema20 < ema50: ss += 2
        if ml < sl: ss += 2

        if bs >= 6: signal = "STRONG BUY 🟢"
        elif bs >= 4 and bs > ss: signal = "BUY 🟢"
        elif ss >= 6: signal = "STRONG SELL 🔴"
        elif ss >= 4 and ss > bs: signal = "SELL 🔴"
        else: signal = "HOLD 🟡"

        score = sum([
            1 if 40<=rsi<=65 or rsi<40 else 0,
            1 if ema20>ema50 else 0,
            1 if ml>sl else 0,
            1 if vol_surge else 0,
        ])

        entry = round(curr*0.999,2); target = round(curr*1.10,2); sl_p = round(curr*0.97,2)

        rsi_note = "Oversold ✅ Strong buy zone" if rsi<40 else "Healthy ✅ Good to buy" if rsi<60 else "Elevated ⚠️ Be careful" if rsi<70 else "Overbought 🔴 Avoid buying"
        trend_note = "Uptrend ✅ Price rising consistently" if ema20>ema50 else "Downtrend ❌ Price falling"
        macd_note = "Bullish ✅ Buying momentum building" if ml>sl else "Bearish ❌ Selling momentum"
        vol_note = "Surge ✅ Big players buying" if vol_surge else "Normal — no unusual activity"

        opt_note = ""
        if is_fno and "BUY" in signal and rsi < 68:
            strike = round(curr*1.03/50)*50
            prem_est = round(curr*0.028,1)
            cap = round(prem_est*lot)
            opt_note = f"""
🎯 <b>OPTIONS ROUTE (F&O eligible)</b>
Buy    : {sym} {strike} CE
Expiry : Current monthly
Premium: ~₹{prem_est} (estimate only)
Lot    : {lot} shares
Capital: ~₹{cap:,}
⚠️ Check actual premium in Zerodha"""

        now = datetime.now().strftime('%d %b %Y %I:%M %p')
        return f"""🔍 <b>ANALYSIS — {sym}</b>
⏰ {now} (15 min delayed)

💰 <b>Price Action</b>
Current : ₹{curr} ({day_chg:+.2f}% today)
Support : ₹{support} | Resistance: ₹{resistance}
Signal  : <b>{signal}</b>
Strength: {score}/4 {'⭐'*score}

📊 <b>Technical Indicators</b>
RSI   : {rsi:.1f} — {rsi_note}
Trend : {trend_note}
MACD  : {macd_note}
Volume: {vol_note}

📈 <b>STOCK ROUTE</b>
Entry  : ₹{entry}
Target : ₹{target} (+10%)
SL     : ₹{sl_p} (-3%)
Hold   : 2–8 weeks
{"F&O: ✅ Lot size "+str(lot) if is_fno else "F&O: ❌ Not eligible"}

💡 <b>Simple summary</b>
{"✅ Good setup for entry. All indicators aligned." if score>=3 else "⚠️ Mixed signals. Wait for clearer entry." if score==2 else "❌ Weak setup. Better opportunities available."}
{opt_note}
⚠️ Verify price in Zerodha before trading"""
    except Exception as e:
        return f"❌ Error analysing {sym}: {str(e)[:100]}"

def cmd_market():
    try:
        msg = f"📊 <b>MARKET NOW</b>\n⏰ {datetime.now().strftime('%d %b %Y %I:%M %p')} (15 min delayed)\n\n"
        for name, ticker in [("Nifty 50","^NSEI"),("Bank Nifty","^NSEBANK"),("Sensex","^BSESN")]:
            df = yf.download(ticker, period="5d", interval="1d", progress=False)
            if not df.empty and len(df)>=2:
                curr = float(df['Close'].iloc[-1]); prev = float(df['Close'].iloc[-2])
                chg = ((curr-prev)/prev)*100; e = "🟢" if chg>0 else "🔴"
                rsi = float(ta.momentum.RSIIndicator(df['Close'].squeeze()).rsi().iloc[-1])
                msg += f"{e} <b>{name}</b>: {curr:,.0f} ({chg:+.2f}%) | RSI:{rsi:.0f}\n"
            time.sleep(0.3)
        msg += "\n💡 RSI <40 = oversold (good to buy index)\nRSI >70 = overbought (be careful)"
        return msg
    except:
        return "❌ Could not fetch market data. Try again."

def cmd_compare(args):
    if len(args) < 2:
        return "❌ Format: /compare STOCK1 STOCK2\nExample: /compare BEL HAL"
    r1 = cmd_analyse([args[0]], None)
    r2 = cmd_analyse([args[1]], None)
    return f"⚖️ <b>COMPARISON: {args[0].upper()} vs {args[1].upper()}</b>\n\n{r1}\n\n{'━'*30}\n\n{r2}"

def cmd_sector(args):
    if not args:
        return "❌ Format: /sector SECTORNAME\nAvailable: IT, BANKING, PHARMA, DEFENCE, POWER, AUTO, FMCG, METALS, INFRA, CHEMICALS, CEMENT, FINANCE, REALTY"
    sector = args[0].upper()
    stocks = SECTOR_MAP.get(sector, [])
    if not stocks:
        return f"❌ Sector {sector} not found.\nAvailable: {', '.join(SECTOR_MAP.keys())}"
    msg = f"🏭 <b>SECTOR: {sector}</b>\n⏰ {datetime.now().strftime('%I:%M %p')}\n\n"
    results = []
    for sym in stocks[:8]:
        df = yf.download(sym, period="2mo", interval="1d", progress=False)
        if df.empty or len(df) < 20: continue
        close = df['Close'].squeeze()
        rsi = float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
        ema20 = float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
        ema50 = float(ta.trend.EMAIndicator(close,50).ema_indicator().iloc[-1]) if len(close)>=50 else ema20
        curr = float(close.iloc[-1])
        bs = (2 if rsi<40 else 1 if rsi<50 else 0) + (2 if ema20>ema50 else 0)
        sig = "STRONG BUY 🟢" if bs>=4 else "BUY 🟢" if bs>=3 else "HOLD 🟡"
        results.append({"sym":sym.replace(".NS",""),"price":curr,"rsi":round(rsi,1),"signal":sig,"score":bs})
        time.sleep(0.3)
    results.sort(key=lambda x: x['score'], reverse=True)
    for r in results:
        msg += f"{'🟢' if 'BUY' in r['signal'] else '🟡'} <b>{r['sym']}</b> ₹{r['price']:.2f} | {r['signal']} | RSI:{r['rsi']}\n"
    return msg

def cmd_help():
    return """🤖 <b>TRADING BOT v3.0 — COMMANDS</b>

📈 <b>RECORD TRADES</b>
/buy STOCK PRICE QTY
  Example: /buy BEL 435 50

/buyce STOCK STRIKE PREMIUM LOTS
  Example: /buyce BEL 450 13.5 1

/sell STOCK EXIT_PRICE
  Example: /sell BEL 475

/sellce STOCK STRIKE EXIT_PREMIUM
  Example: /sellce BEL 450 28.5

📊 <b>VIEW POSITIONS</b>
/portfolio — all open trades
/pnl — same as portfolio

🔍 <b>ANALYSIS</b>
/analyse STOCK
/compare STOCK1 STOCK2
/sector SECTORNAME
/market — live index levels

📋 <b>INFO</b>
/help — this menu

⏰ <b>AUTO REPORTS</b>
8:00 AM — Morning scan (2100+ stocks)
12:00 PM — Midday update
4:00 PM — Evening P&L + tomorrow preview

💡 All reports → Telegram + Gmail"""

def process_command(text, sheet, chat_id):
    parts = text.strip().split()
    if not parts: return None
    cmd = parts[0].lower(); args = parts[1:]
    if cmd == '/buy': return cmd_buy(args, sheet, chat_id)
    elif cmd == '/buyce': return cmd_buyce(args, sheet, chat_id)
    elif cmd == '/sell': return cmd_sell(args, sheet, chat_id)
    elif cmd == '/sellce': return cmd_sellce(args, sheet, chat_id)
    elif cmd in ['/portfolio','/pnl']: return cmd_portfolio(sheet)
    elif cmd == '/market': return cmd_market()
    elif cmd == '/analyse' and args: return cmd_analyse(args, chat_id)
    elif cmd == '/compare': return cmd_compare(args)
    elif cmd == '/sector': return cmd_sector(args)
    elif cmd in ['/help','/start']: return cmd_help()
    return None

def run():
    print(f"Telegram Bot v3.0 started — {datetime.now().strftime('%d %b %Y %I:%M %p')}")
    sheet = setup_sheets_bot()
    send_telegram(f"🤖 <b>Trading Bot v3.0 Online!</b>\n\n✅ All systems ready\nSend /help to see all commands\n\n⏰ Reports: 8 AM | 12 PM | 4 PM daily")
    offset = None
    start_time = time.time()
    max_runtime = 55 * 60
    while time.time() - start_time < max_runtime:
        updates = get_updates(offset)
        for update in updates:
            offset = update['update_id'] + 1
            msg = update.get('message', {})
            text = msg.get('text', '')
            chat_id = str(msg.get('chat', {}).get('id', ''))
            if text and text.startswith('/'):
                print(f"CMD: {text}")
                resp = process_command(text, sheet, chat_id)
                if resp:
                    send_telegram(resp, chat_id)
        time.sleep(2)
    print("Bot session ended.")

run()
