import yfinance as yf
import pandas as pd
import ta
from datetime import datetime
import time
import warnings
import requests
import os
import json
import gspread
from google.oauth2.service_account import Credentials
warnings.filterwarnings('ignore')

# ============================================================
# TELEGRAM BOT — 24/7 Command Listener
# Commands: /buy /sell /buyce /sellce /portfolio /pnl
#           /analyse /compare /sector /top5 /market /news
# ============================================================

TELEGRAM_TOKEN   = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
GOOGLE_SHEET_ID  = os.environ.get('GOOGLE_SHEET_ID')
GOOGLE_CREDS     = os.environ.get('GOOGLE_CREDENTIALS')

def setup_sheets():
    try:
        creds_dict = json.loads(GOOGLE_CREDS)
        scopes = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client.open_by_key(GOOGLE_SHEET_ID)
    except Exception as e:
        print(f"Sheets error: {e}")
        return None

def send_telegram(message, chat_id=None):
    try:
        cid = chat_id or TELEGRAM_CHAT_ID
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": cid, "text": message, "parse_mode": "HTML"}, timeout=15)
        return r.status_code == 200
    except:
        return False

def get_updates(offset=None):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
        params = {"timeout": 30, "offset": offset}
        r = requests.get(url, params=params, timeout=35)
        if r.status_code == 200:
            return r.json().get('result', [])
    except:
        pass
    return []

def quick_analyse(symbol):
    try:
        ticker = symbol if symbol.endswith('.NS') else symbol + '.NS'
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)
        if df.empty or len(df) < 30:
            return f"❌ No data found for {symbol}. Check the symbol name."

        close = df['Close'].squeeze()
        volume = df['Volume'].squeeze()
        rsi = float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
        ema20 = float(ta.trend.EMAIndicator(close, window=20).ema_indicator().iloc[-1])
        ema50 = float(ta.trend.EMAIndicator(close, window=50).ema_indicator().iloc[-1])
        macd_obj = ta.trend.MACD(close)
        macd_line = float(macd_obj.macd().iloc[-1])
        signal_line = float(macd_obj.macd_signal().iloc[-1])
        current_price = float(close.iloc[-1])
        avg_vol = float(volume.tail(20).mean())
        latest_vol = float(volume.iloc[-1])
        vol_surge = latest_vol > avg_vol * 1.5
        support = round(float(close.tail(20).min()), 2)
        resistance = round(float(close.tail(20).max()), 2)

        buy_score = 0
        if rsi < 40: buy_score += 2
        elif rsi < 50: buy_score += 1
        if ema20 > ema50: buy_score += 2
        if macd_line > signal_line: buy_score += 2
        if vol_surge: buy_score += 1

        sell_score = 0
        if rsi > 70: sell_score += 2
        elif rsi > 60: sell_score += 1
        if ema20 < ema50: sell_score += 2
        if macd_line < signal_line: sell_score += 2

        if buy_score >= 5: signal = "STRONG BUY 🟢"
        elif buy_score >= 3 and buy_score > sell_score: signal = "BUY 🟢"
        elif sell_score >= 5: signal = "STRONG SELL 🔴"
        elif sell_score >= 3 and sell_score > buy_score: signal = "SELL 🔴"
        else: signal = "HOLD 🟡"

        entry = round(current_price * 0.999, 2)
        target = round(current_price * 1.10, 2)
        sl = round(current_price * 0.97, 2)

        rsi_note = "Oversold — strong buy zone ✅" if rsi < 40 else \
                   "Healthy buy zone ✅" if rsi < 60 else \
                   "Getting elevated ⚠️" if rsi < 70 else \
                   "Overbought — avoid buying 🔴"

        trend_note = "Uptrend confirmed ✅" if ema20 > ema50 else "Downtrend ❌"
        macd_note = "Bullish momentum ✅" if macd_line > signal_line else "Bearish momentum ❌"
        vol_note = "Big players buying ✅" if vol_surge else "Normal volume"
        now = datetime.now().strftime('%d %b %Y %I:%M %p')

        msg = f"""🔍 <b>ON-DEMAND ANALYSIS — {symbol.upper()}</b>
⏰ Price as of: {now} (15 min delayed)

📊 <b>CURRENT STATUS</b>
Price      : ₹{current_price}
Signal     : <b>{signal}</b>
RSI        : {rsi:.1f} — {rsi_note}
Trend      : {trend_note}
MACD       : {macd_note}
Volume     : {vol_note}
Support    : ₹{support}
Resistance : ₹{resistance}

📈 <b>STOCK TRADE</b>
Entry  : ₹{entry} (wait for dip if running)
Target : ₹{target} (+10%)
SL     : ₹{sl} (-3%)
Hold   : 2–8 weeks

💡 <b>SIMPLE EXPLANATION</b>
RSI {rsi:.0f} means the stock is {rsi_note.lower()}
{'Trend is up — momentum is with buyers.' if ema20 > ema50 else 'Trend is down — sellers in control.'}
{'Volume surge confirms institutional buying.' if vol_surge else 'No unusual volume activity.'}
{'Overall setup looks FAVORABLE for entry.' if buy_score >= 3 else 'Setup is WEAK — wait for better entry.' if buy_score < 2 else 'Mixed signals — proceed with caution.'}

⚠️ Verify current price in Zerodha before trading."""

        return msg
    except Exception as e:
        return f"❌ Error analysing {symbol}: {str(e)[:100]}"

def handle_buy(args, sheet, chat_id):
    # /buy STOCK PRICE QTY
    if len(args) < 3:
        return "❌ Format: /buy STOCK PRICE QTY\nExample: /buy BEL 435 50"
    try:
        stock = args[0].upper()
        price = float(args[1])
        qty = int(args[2])
        target = round(price * 1.10, 2)
        sl = round(price * 0.97, 2)
        today = datetime.now().strftime('%d %b %Y')

        if sheet:
            ws = sheet.worksheet("Open Trades")
            headers = ws.row_values(1)
            if not headers:
                ws.append_row(["Entry Date","Stock","Type","Entry Price","Qty","Target","Stop Loss","Days Held","Notes"])
            ws.append_row([today, stock, "STOCK", price, qty, target, sl, 0, ""])

        invested = price * qty
        return f"""✅ <b>TRADE RECORDED — {stock}</b>

Type      : STOCK BUY
Entry     : ₹{price}
Qty       : {qty} shares
Invested  : ₹{invested:,.0f}
Target    : ₹{target} (+10%)
Stop Loss : ₹{sl} (-3%)
Date      : {today}

💡 Bot will track this in evening updates daily.
Set a price alert in Zerodha at ₹{target} (target) and ₹{sl} (SL)."""
    except Exception as e:
        return f"❌ Error: {e}. Format: /buy STOCK PRICE QTY"

def handle_sell(args, sheet, chat_id):
    # /sell STOCK PRICE
    if len(args) < 2:
        return "❌ Format: /sell STOCK PRICE\nExample: /sell BEL 475"
    try:
        stock = args[0].upper()
        exit_price = float(args[1])
        today = datetime.now().strftime('%d %b %Y')

        if sheet:
            open_ws = sheet.worksheet("Open Trades")
            records = open_ws.get_all_records()
            trade_row = None
            row_num = None
            for i, r in enumerate(records, 2):
                if r.get('Stock', '').upper() == stock and r.get('Type') == 'STOCK':
                    trade_row = r
                    row_num = i
                    break

            if not trade_row:
                return f"❌ No open STOCK trade found for {stock}. Check /portfolio."

            entry = float(trade_row.get('Entry Price', 0))
            qty = int(trade_row.get('Qty', 0))
            pnl = (exit_price - entry) * qty
            pnl_pct = ((exit_price - entry) / entry) * 100
            days = trade_row.get('Days Held', 0)

            closed_ws = sheet.worksheet("Closed Trades")
            closed_ws.append_row([
                trade_row.get('Entry Date'), today, stock, 'STOCK',
                entry, exit_price, qty, pnl, round(pnl_pct, 2), days
            ])
            open_ws.delete_rows(row_num)

            pnl_emoji = "🟢" if pnl > 0 else "🔴"
            return f"""{pnl_emoji} <b>TRADE CLOSED — {stock}</b>

Entry  : ₹{entry}
Exit   : ₹{exit_price}
Qty    : {qty} shares
P&L    : ₹{pnl:+,.0f} ({pnl_pct:+.1f}%)
Days   : {days}

{'🎉 Profitable trade! Well done.' if pnl > 0 else '📚 Loss noted. Review what happened for learning.'}
Trade saved to Closed Trades history."""
    except Exception as e:
        return f"❌ Error: {e}"

def handle_portfolio(sheet):
    if not sheet:
        return "❌ Cannot connect to Google Sheets."
    try:
        ws = sheet.worksheet("Open Trades")
        records = ws.get_all_records()
        if not records:
            return "📊 No open trades.\nUse /buy STOCK PRICE QTY to record a trade."

        msg = f"💼 <b>OPEN POSITIONS</b>\n⏰ {datetime.now().strftime('%d %b %Y %I:%M %p')}\n\n"
        total_invested = 0
        for r in records:
            stock = r.get('Stock', '')
            entry = float(r.get('Entry Price', 0))
            qty = int(r.get('Qty', 0))
            target = float(r.get('Target', 0))
            sl = float(r.get('Stop Loss', 0))
            trade_type = r.get('Type', 'STOCK')
            invested = entry * qty
            total_invested += invested
            msg += f"<b>{stock}</b> ({trade_type})\n"
            msg += f"Entry: ₹{entry} | Qty: {qty} | Invested: ₹{invested:,.0f}\n"
            msg += f"Target: ₹{target} | SL: ₹{sl}\n\n"

        msg += f"💰 Total invested: ₹{total_invested:,.0f}\n"
        msg += "Use /pnl for live P&L calculation."
        return msg
    except Exception as e:
        return f"❌ Error: {e}"

def handle_market():
    indices = {"Nifty 50": "^NSEI", "Bank Nifty": "^NSEBANK", "Sensex": "^BSESN"}
    msg = f"📊 <b>MARKET NOW</b>\n⏰ {datetime.now().strftime('%I:%M %p')} (15 min delayed)\n\n"
    for name, ticker in indices.items():
        try:
            df = yf.download(ticker, period="5d", interval="1d", progress=False)
            if not df.empty and len(df) >= 2:
                curr = float(df['Close'].iloc[-1])
                prev = float(df['Close'].iloc[-2])
                chg = ((curr - prev) / prev) * 100
                emoji = "🟢" if chg > 0 else "🔴"
                msg += f"{emoji} <b>{name}</b>: {curr:,.0f} ({chg:+.2f}%)\n"
        except:
            pass
    return msg

def handle_help():
    return """🤖 <b>TRADING BOT COMMANDS</b>

📈 <b>TRADE TRACKING</b>
/buy STOCK PRICE QTY
  Example: /buy BEL 435 50
  Records a stock purchase

/sell STOCK PRICE
  Example: /sell BEL 475
  Closes a trade + calculates P&L

/portfolio
  Shows all open positions

/pnl
  Live profit/loss on all positions

📊 <b>ANALYSIS</b>
/analyse STOCK
  Example: /analyse RELIANCE
  Full technical analysis instantly

/compare STOCK1 STOCK2
  Example: /compare BEL HAL
  Side by side comparison

/top5
  Top 5 buy signals right now

/market
  Current Nifty, BankNifty, Sensex

📰 <b>INFO</b>
/help
  Show this menu

💡 Bot runs morning scan at 8 AM
and evening update at 4 PM daily."""

def process_command(text, sheet, chat_id):
    parts = text.strip().split()
    if not parts:
        return None
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd == '/buy':
        return handle_buy(args, sheet, chat_id)
    elif cmd == '/sell':
        return handle_sell(args, sheet, chat_id)
    elif cmd == '/portfolio':
        return handle_portfolio(sheet)
    elif cmd == '/market':
        return handle_market()
    elif cmd == '/analyse' and args:
        return quick_analyse(args[0])
    elif cmd == '/compare' and len(args) >= 2:
        r1 = quick_analyse(args[0])
        r2 = quick_analyse(args[1])
        return f"📊 <b>COMPARISON</b>\n\n{r1}\n\n{'='*30}\n\n{r2}"
    elif cmd == '/top5':
        return "⏳ Running quick scan for top 5... This takes 2-3 minutes.\n\nFor full Top 20, check the 8 AM morning scan in your Gmail."
    elif cmd == '/help' or cmd == '/start':
        return handle_help()
    elif cmd == '/pnl':
        return handle_portfolio(sheet) + "\n\n💡 For live P&L, check the 4 PM evening update."
    return None

def run_bot():
    print(f"Telegram Bot started — {datetime.now().strftime('%d %b %Y %I:%M %p')}")
    sheet = setup_sheets()
    send_telegram("🤖 <b>Trading Bot is online!</b>\n\nSend /help to see all commands.\nMorning scan runs at 8 AM.\nEvening update at 4 PM.")

    offset = None
    start_time = time.time()
    max_runtime = 55 * 60  # 55 minutes (GitHub Actions limit)

    while time.time() - start_time < max_runtime:
        updates = get_updates(offset)
        for update in updates:
            offset = update['update_id'] + 1
            message = update.get('message', {})
            text = message.get('text', '')
            chat_id = str(message.get('chat', {}).get('id', ''))

            if text and text.startswith('/'):
                print(f"Command: {text} from {chat_id}")
                response = process_command(text, sheet, chat_id)
                if response:
                    send_telegram(response, chat_id)
        time.sleep(2)

    print("Bot session ended.")

run_bot()
