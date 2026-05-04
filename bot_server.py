# ============================================================
# TELEGRAM WEBHOOK SERVER v1.0
# Runs 24/7 on Render.com
# Responds instantly to all Telegram commands
# ============================================================
from flask import Flask, request, jsonify
import yfinance as yf
import pandas as pd
import ta
import requests
import os
import json
import gspread
import warnings
from google.oauth2.service_account import Credentials
from datetime import datetime
import pytz
IST = pytz.timezone('Asia/Kolkata')
import time
warnings.filterwarnings('ignore')

app = Flask(__name__)

# ── Credentials ──────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
GOOGLE_SHEET_ID  = os.environ.get('GOOGLE_SHEET_ID')
GOOGLE_CREDS     = os.environ.get('GOOGLE_CREDENTIALS')

# ── F&O lot sizes ─────────────────────────────────────────────
FON_LOT_SIZES = {
    "RELIANCE":250,"TCS":150,"HDFCBANK":550,"ICICIBANK":700,
    "INFY":400,"SBIN":1500,"KOTAKBANK":400,"AXISBANK":1200,
    "BAJFINANCE":125,"MARUTI":100,"TITAN":375,"SUNPHARMA":700,
    "WIPRO":1500,"HCLTECH":700,"NTPC":2250,"TATAMOTORS":1425,
    "JSWSTEEL":675,"ADANIENT":250,"HINDALCO":1400,"TATASTEEL":5500,
    "CIPLA":650,"DRREDDY":125,"SUZLON":2900,"BEL":2950,
    "HAL":150,"BHEL":4350,"SAIL":6750,"TATAPOWER":1350,
    "IRFC":4800,"RVNL":2750,"PFC":1200,"RECLTD":975,
    "ZOMATO":2475,"IRCTC":875,"ADANIPORTS":1250,"COALINDIA":1350,
    "ONGC":1925,"BPCL":1800,"IOC":2250,"POWERGRID":2900,
    "LT":175,"BAJAJ-AUTO":250,"HEROMOTOCO":300,"EICHERMOT":200,
}
FON_STOCKS = set(k+".NS" for k in FON_LOT_SIZES)

def setup_sheets():
    try:
        creds_dict = json.loads(GOOGLE_CREDS)
        scopes = ['https://spreadsheets.google.com/feeds',
                  'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client.open_by_key(GOOGLE_SHEET_ID)
    except Exception as e:
        print(f"Sheets error: {e}")
        return None

def send_reply(chat_id, message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        for chunk in [message[i:i+4000] for i in range(0, len(message), 4000)]:
            requests.post(url, data={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "HTML"
            }, timeout=15)
            time.sleep(0.3)
    except Exception as e:
        print(f"Reply error: {e}")

def analyse_stock(sym):
    try:
        sym = sym.upper().replace(".NS","")
        ticker = sym + ".NS"
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)
        if df.empty or len(df) < 30:
            return f"❌ No data for {sym}. Check symbol name."
        close = df['Close'].squeeze()
        volume = df['Volume'].squeeze()
        curr = float(close.iloc[-1])
        prev = float(close.iloc[-2])
        rsi = float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
        ema20 = float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
        ema50 = float(ta.trend.EMAIndicator(close,50).ema_indicator().iloc[-1])
        macd_obj = ta.trend.MACD(close)
        ml = float(macd_obj.macd().iloc[-1])
        sl = float(macd_obj.macd_signal().iloc[-1])
        avg_vol = float(volume.tail(20).mean())
        lat_vol = float(volume.iloc[-1])
        vol_surge = lat_vol > avg_vol * 1.5
        support = round(float(close.tail(20).min()), 2)
        resistance = round(float(close.tail(20).max()), 2)
        day_chg = ((curr - prev) / prev) * 100
        is_fno = ticker in FON_STOCKS
        lot = FON_LOT_SIZES.get(sym, 0)

        bs = 0; ss = 0
        if rsi < 40: bs += 2
        elif rsi < 50: bs += 1
        if rsi > 70: ss += 2
        elif rsi > 60: ss += 1
        if ema20 > ema50: bs += 2
        else: ss += 2
        if ml > sl: bs += 2
        else: ss += 2
        if vol_surge: bs += 1

        if bs >= 6: signal = "STRONG BUY 🟢"
        elif bs >= 4 and bs > ss: signal = "BUY 🟢"
        elif ss >= 6: signal = "STRONG SELL 🔴"
        elif ss >= 4 and ss > bs: signal = "SELL 🔴"
        else: signal = "HOLD 🟡"

        score = sum([
            1 if (40<=rsi<=65 or rsi<40) else 0,
            1 if ema20>ema50 else 0,
            1 if ml>sl else 0,
            1 if vol_surge else 0,
        ])
        stars = "⭐" * score

        entry = round(curr*0.999,2)
        target = round(curr*1.10,2)
        sl_price = round(max(curr*0.97, support*0.98),2)

        rsi_note = "Oversold ✅ Strong buy zone" if rsi<40 else \
                   "Healthy ✅ Good entry zone" if rsi<60 else \
                   "Elevated ⚠️ Be careful" if rsi<70 else \
                   "Overbought 🔴 Avoid buying"
        trend_note = "Uptrend ✅" if ema20>ema50 else "Downtrend ❌"
        macd_note = "Bullish ✅" if ml>sl else "Bearish ❌"
        vol_note = "Surge ✅ Big players buying" if vol_surge else "Normal volume"

        opt_txt = ""
        if is_fno and "BUY" in signal and rsi < 72 and lot > 0:
            strike = round(curr*1.03/50)*50
            prem = round(curr*0.028,1)
            cap = round(prem*lot)
            opt_txt = f"""
🎯 <b>OPTIONS ROUTE</b>
Buy    : {sym} {strike} CE
Premium: ~₹{prem} (verify in Zerodha)
Lot    : {lot} shares
Capital: ~₹{cap:,}
Target : ₹{round(prem*2.2,1)} (+120%)
SL     : ₹{round(prem*0.5,1)}"""

        now = datetime.now(IST).strftime('%d %b %Y %I:%M %p IST')
        return f"""🔍 <b>ANALYSIS — {sym}</b>
⏰ {now} (15 min delayed)

💰 <b>Price</b>
Current    : ₹{curr} ({day_chg:+.2f}% today)
Support    : ₹{support}
Resistance : ₹{resistance}
Signal     : <b>{signal}</b>
Strength   : {score}/4 {stars}

📊 <b>Indicators</b>
RSI    : {rsi:.1f} — {rsi_note}
Trend  : {trend_note}
MACD   : {macd_note}
Volume : {vol_note}

📈 <b>Stock Trade</b>
Entry  : ₹{entry}
Target : ₹{target} (+10%)
SL     : ₹{sl_price} (-3%)
{"F&O ✅ Lot: "+str(lot) if is_fno else "Not F&O eligible"}
{opt_txt}
💡 {"✅ Good setup — multiple indicators aligned." if score>=3 else "⚠️ Mixed signals — wait for better entry." if score==2 else "❌ Weak setup — better opportunities available."}

⚠️ Verify price in Zerodha before trading"""
    except Exception as e:
        return f"❌ Error analysing {sym}: {str(e)[:100]}"

def cmd_market():
    try:
        msg = f"📊 <b>MARKET NOW</b>\n⏰ {datetime.now(IST).strftime('%d %b %Y %I:%M %p IST')} (15 min delayed)\n\n"
        for name, ticker in [("Nifty 50","^NSEI"),("Bank Nifty","^NSEBANK"),("Sensex","^BSESN")]:
            df = yf.download(ticker, period="5d", interval="1d", progress=False)
            if not df.empty and len(df) >= 2:
                curr = float(df['Close'].iloc[-1])
                prev = float(df['Close'].iloc[-2])
                chg = ((curr-prev)/prev)*100
                rsi = float(ta.momentum.RSIIndicator(df['Close'].squeeze()).rsi().iloc[-1])
                e = "🟢" if chg>0 else "🔴"
                msg += f"{e} <b>{name}</b>: {curr:,.0f} ({chg:+.2f}%) | RSI:{rsi:.0f}\n"
            time.sleep(0.3)
        msg += "\n💡 RSI <40 = oversold | RSI >70 = overbought"
        return msg
    except:
        return "❌ Could not fetch market data. Try again."

def cmd_buy(args, sheet, chat_id):
    if len(args) < 3:
        return "❌ Format: /buy STOCK PRICE QTY\nExample: /buy BEL 435 50"
    try:
        stock = args[0].upper().replace(".NS","")
        price = float(args[1]); qty = int(args[2])
        target = round(price*1.10,2); sl = round(price*0.97,2)
        today = datetime.now().strftime('%d %b %Y')
        invested = price * qty
        lot = FON_LOT_SIZES.get(stock,0)
        if sheet:
            ws = sheet.worksheet("Open Trades")
            if not ws.row_values(1):
                ws.append_row(["Entry Date","Stock","Type","Entry Price",
                               "Qty","Target","Stop Loss","Days Held","Notes"])
            ws.append_row([today,stock,"STOCK",price,qty,target,sl,0,""])
        return f"""✅ <b>TRADE RECORDED — {stock}</b>

Entry     : ₹{price}
Qty       : {qty} shares
Capital   : ₹{invested:,.0f}
Target    : ₹{target} (+10%)
Stop Loss : ₹{sl} (-3%)
Date      : {today}
{"F&O ✅ Lot: "+str(lot) if lot else ""}

💡 Set price alert in Zerodha:
Target → ₹{target} | SL → ₹{sl}
Bot tracks this in daily updates."""
    except Exception as e:
        return f"❌ Error: {e}\nFormat: /buy STOCK PRICE QTY"

def cmd_sell(args, sheet):
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
            if r.get('Stock','').upper()==stock and r.get('Type')=='STOCK':
                trade_row = r; row_num = i; break
        if not trade_row:
            return f"❌ No open trade for {stock}.\nCheck /portfolio."
        entry = float(trade_row.get('Entry Price',0))
        qty = int(trade_row.get('Qty',0))
        pnl = (exit_price-entry)*qty
        pnl_pct = ((exit_price-entry)/entry)*100
        days = trade_row.get('Days Held',0)
        closed_ws = sheet.worksheet("Closed Trades")
        if not closed_ws.row_values(1):
            closed_ws.append_row(["Entry Date","Exit Date","Stock","Type",
                                  "Entry","Exit","Qty","P&L","P&L%","Days"])
        closed_ws.append_row([trade_row.get('Entry Date'),today,stock,'STOCK',
                              entry,exit_price,qty,round(pnl,2),round(pnl_pct,2),days])
        open_ws.delete_rows(row_num)
        e = "🟢" if pnl>0 else "🔴"
        return f"""{e} <b>TRADE CLOSED — {stock}</b>

Entry  : ₹{entry} → Exit: ₹{exit_price}
Qty    : {qty} shares | Days: {days}
P&L    : ₹{pnl:+,.0f} ({pnl_pct:+.1f}%)

{'🎉 Profitable! Well done.' if pnl>0 else '📚 Loss. Review for learning.'}"""
    except Exception as e:
        return f"❌ Error: {e}"

def cmd_portfolio(sheet):
    if not sheet:
        return "❌ Cannot connect to Google Sheets"
    try:
        ws = sheet.worksheet("Open Trades")
        records = ws.get_all_records()
        if not records:
            return "📊 <b>No open trades</b>\n\nRecord a trade:\n/buy STOCK PRICE QTY\nExample: /buy BEL 435 50"
        msg = f"💼 <b>OPEN POSITIONS</b>\n⏰ {datetime.now(IST).strftime('%d %b %Y %I:%M %p IST')}\n\n"
        total = 0
        for r in records:
            stock = r.get('Stock',''); entry = float(r.get('Entry Price',0))
            qty = int(r.get('Qty',0)); target = float(r.get('Target',0))
            sl = float(r.get('Stop Loss',0)); days = r.get('Days Held',0)
            invested = entry*qty; total += invested
            msg += f"<b>{stock}</b> | Entry ₹{entry} × {qty} = ₹{invested:,.0f}\n"
            msg += f"Target ₹{target} | SL ₹{sl} | Day {days}\n\n"
        msg += f"💰 Total deployed: ₹{total:,.0f}"
        return msg
    except Exception as e:
        return f"❌ Error: {e}"

def cmd_compare(args):
    if len(args) < 2:
        return "❌ Format: /compare STOCK1 STOCK2\nExample: /compare BEL HAL"
    r1 = analyse_stock(args[0])
    r2 = analyse_stock(args[1])
    return f"⚖️ <b>{args[0].upper()} vs {args[1].upper()}</b>\n\n{r1}\n\n{'━'*30}\n\n{r2}"

def cmd_help():
    return """🤖 <b>TRADING BOT v3.0</b>
24/7 Active — Instant Response

📈 <b>RECORD TRADES</b>
/buy STOCK PRICE QTY
/buyce STOCK STRIKE PREMIUM LOTS
/sell STOCK EXIT_PRICE
/sellce STOCK STRIKE EXIT_PREMIUM

📊 <b>VIEW POSITIONS</b>
/portfolio — all open trades

🔍 <b>ANALYSIS</b>
/analyse STOCK
/compare STOCK1 STOCK2
/market — live index levels

⏰ <b>AUTO REPORTS</b>
8:00 AM — Morning scan
12:00 PM — Midday update
8:00 PM — Evening P&L

💡 Bot responds instantly 24/7"""

def process_message(text, chat_id):
    sheet = setup_sheets()
    parts = text.strip().split()
    if not parts: return None
    cmd = parts[0].lower(); args = parts[1:]

    if cmd == '/start' or cmd == '/help':
        return cmd_help()
    elif cmd == '/analyse' and args:
        return analyse_stock(args[0])
    elif cmd == '/market':
        return cmd_market()
    elif cmd == '/buy':
        return cmd_buy(args, sheet, chat_id)
    elif cmd == '/sell':
        return cmd_sell(args, sheet)
    elif cmd == '/portfolio' or cmd == '/pnl':
        return cmd_portfolio(sheet)
    elif cmd == '/compare':
        return cmd_compare(args)
    elif cmd == '/ping':
        return f"🟢 Bot is alive!\n⏰ {datetime.now(IST).strftime('%d %b %Y %I:%M %p IST')}"
    return None

# ── Webhook endpoint ──────────────────────────────────────────
@app.route(f'/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": True})
        message = data.get('message', {})
        text = message.get('text', '')
        chat_id = str(message.get('chat', {}).get('id', ''))
        if text and text.startswith('/'):
            print(f"Command: {text} from {chat_id}")
            response = process_message(text, chat_id)
            if response:
                send_reply(chat_id, response)
    except Exception as e:
        print(f"Webhook error: {e}")
    return jsonify({"ok": True})

# ── Health check — keeps Render awake ────────────────────────
@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "alive",
        "time": datetime.now(IST).strftime('%d %b %Y %I:%M %p IST'),
        "bot": "LoveshNSEBot"
    })

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "NSE Trading Bot — Running 24/7"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Bot server starting on port {port}")
    app.run(host='0.0.0.0', port=port)
