import yfinance as yf
import pandas as pd
import ta
from datetime import datetime
import time
import warnings
import smtplib
import requests
import os
import json
import gspread
from google.oauth2.service_account import Credentials
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import feedparser
warnings.filterwarnings('ignore')

# ============================================================
# EVENING POSITION TRACKER v2.0
# Runs at 4:00 PM IST daily
# Tracks all open trades, calculates P&L, gives exit guidance
# ============================================================

GMAIL_ADDRESS    = os.environ.get('GMAIL_ADDRESS')
GMAIL_PASSWORD   = os.environ.get('GMAIL_PASSWORD')
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

def get_open_trades(sheet):
    try:
        ws = sheet.worksheet("Open Trades")
        data = ws.get_all_records()
        return data
    except Exception as e:
        print(f"Get trades error: {e}")
        return []

def get_current_price(symbol):
    try:
        ticker = symbol if symbol.endswith('.NS') else symbol + '.NS'
        df = yf.download(ticker, period="5d", interval="1d", progress=False)
        if not df.empty:
            price = float(df['Close'].iloc[-1])
            prev = float(df['Close'].iloc[-2]) if len(df) >= 2 else price
            rsi = float(ta.momentum.RSIIndicator(df['Close'].squeeze()).rsi().iloc[-1])
            return price, prev, rsi
    except:
        pass
    return None, None, None

def get_index_summary():
    indices = {"Nifty": "^NSEI", "BankNifty": "^NSEBANK", "Sensex": "^BSESN"}
    result = {}
    for name, ticker in indices.items():
        try:
            df = yf.download(ticker, period="5d", interval="1d", progress=False)
            if not df.empty and len(df) >= 2:
                curr = float(df['Close'].iloc[-1])
                prev = float(df['Close'].iloc[-2])
                chg = ((curr - prev) / prev) * 100
                result[name] = {"level": curr, "change_pct": round(chg, 2)}
        except:
            pass
    return result

def get_news_for_stock(stock):
    feeds = ["https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"]
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:30]:
                title = entry.get('title', '')
                if stock.upper() in title.upper():
                    sentiment = "POSITIVE 🟢" if any(w in title.upper() for w in ["SURGE","JUMP","GAIN","RISE","ORDER","PROFIT"]) \
                        else "NEGATIVE 🔴" if any(w in title.upper() for w in ["FALL","DROP","LOSS","CRASH","DECLINE"]) \
                        else "NEUTRAL 🟡"
                    return title[:100], sentiment
        except:
            pass
    return None, None

def get_exit_recommendation(trade, current_price, rsi):
    entry = float(trade.get('Entry Price', 0))
    target = float(trade.get('Target', 0))
    stop_loss = float(trade.get('Stop Loss', 0))
    days_held = int(trade.get('Days Held', 0))
    trade_type = trade.get('Type', 'STOCK')

    if current_price <= stop_loss:
        return "🛑 EXIT IMMEDIATELY", "Price hit stop loss. Capital protection is priority. Exit now.", "red"

    if current_price >= target:
        return "🎯 TARGET HIT — EXIT", "Target reached! Book profits. Consider exiting 75% now.", "green"

    pnl_pct = ((current_price - entry) / entry) * 100

    if rsi and rsi > 78:
        return "⚠️ CONSIDER PARTIAL EXIT", f"RSI {rsi:.0f} — stock is overbought. Book 50% profits now, hold rest.", "orange"

    if days_held > 60 and pnl_pct < 3:
        return "⚠️ REVIEW POSITION", f"Held {days_held} days with only {pnl_pct:.1f}% gain. Capital might be better deployed elsewhere.", "orange"

    if days_held > 90:
        return "⚠️ EXIT AND REVIEW", f"Held {days_held} days — exceeds maximum holding period. Consider exiting and reassessing.", "orange"

    if pnl_pct > 15:
        return "✅ TRAIL STOP LOSS", f"Good profit of {pnl_pct:.1f}%. Move stop loss to breakeven to protect gains.", "green"

    if current_price > entry * 1.05:
        return "✅ HOLD", f"Up {pnl_pct:.1f}%. Momentum positive. Hold with stop loss at ₹{stop_loss}.", "green"

    return "✅ HOLD", f"Position developing. {pnl_pct:.1f}% move. Target ₹{target} | SL ₹{stop_loss}.", "blue"

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=15)
        print(f"Telegram: {r.status_code}")
    except Exception as e:
        print(f"Telegram error: {e}")

def send_email(subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_ADDRESS
        msg['To'] = GMAIL_ADDRESS
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_ADDRESS, GMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Email sent!")
    except Exception as e:
        print(f"Email error: {e}")

def run_evening_update():
    today = datetime.now().strftime('%d %b %Y')
    now = datetime.now().strftime('%I:%M %p')
    print(f"Evening Update — {today} {now}")

    sheet = setup_sheets()
    if not sheet:
        print("Cannot connect to Google Sheets")
        return

    trades = get_open_trades(sheet)
    if not trades:
        msg = f"📊 <b>Evening Update — {today}</b>\n\nNo open trades to track.\nUse /buy STOCK PRICE QTY to record a trade."
        send_telegram(msg)
        return

    indices = get_index_summary()
    nifty = indices.get('Nifty', {})
    nifty_chg = nifty.get('change_pct', 0)
    nifty_mood = "BULLISH 🟢" if nifty_chg > 0.3 else "BEARISH 🔴" if nifty_chg < -0.3 else "NEUTRAL 🟡"

    position_updates = []
    total_invested = 0
    total_current = 0

    for trade in trades:
        symbol = trade.get('Stock', '')
        entry_price = float(trade.get('Entry Price', 0))
        qty = int(trade.get('Qty', 0))
        entry_date = trade.get('Entry Date', '')
        trade_type = trade.get('Type', 'STOCK')

        if not symbol or not entry_price or not qty:
            continue

        current_price, prev_price, rsi = get_current_price(symbol)
        if not current_price:
            continue

        pnl = (current_price - entry_price) * qty
        pnl_pct = ((current_price - entry_price) / entry_price) * 100
        day_change = ((current_price - prev_price) / prev_price * 100) if prev_price else 0

        try:
            entry_dt = datetime.strptime(entry_date, '%d %b %Y')
            days_held = (datetime.now() - entry_dt).days
        except:
            days_held = int(trade.get('Days Held', 0))

        trade['Days Held'] = days_held
        news_headline, news_sentiment = get_news_for_stock(symbol)
        action, reason, color = get_exit_recommendation(trade, current_price, rsi)

        invested = entry_price * qty
        current_value = current_price * qty
        total_invested += invested
        total_current += current_value

        position_updates.append({
            "symbol": symbol,
            "entry": entry_price,
            "current": current_price,
            "qty": qty,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "day_change": day_change,
            "days_held": days_held,
            "rsi": rsi,
            "action": action,
            "reason": reason,
            "color": color,
            "news": news_headline,
            "news_sentiment": news_sentiment,
            "target": float(trade.get('Target', current_price * 1.1)),
            "stop_loss": float(trade.get('Stop Loss', current_price * 0.97)),
            "price_timestamp": f"Today {now} NSE Close",
        })
        time.sleep(0.5)

    total_pnl = total_current - total_invested
    total_pnl_pct = ((total_current - total_invested) / total_invested * 100) if total_invested > 0 else 0

    # Build Telegram message
    port_txt = ""
    for p in position_updates:
        pnl_emoji = "🟢" if p['pnl'] > 0 else "🔴"
        port_txt += f"""
{pnl_emoji} <b>{p['symbol']}</b> (Day {p['days_held']})
Entry ₹{p['entry']} → Today ₹{p['current']} ({p['day_change']:+.1f}% today)
P&L: ₹{p['pnl']:+.0f} ({p['pnl_pct']:+.1f}%) | RSI: {p['rsi']:.0f if p['rsi'] else 'N/A'}
Target: ₹{p['target']} | SL: ₹{p['stop_loss']}
{p['action']}: {p['reason'][:80]}
"""
        if p['news']:
            port_txt += f"📰 News: {p['news'][:60]}... {p['news_sentiment']}\n"

    total_emoji = "🟢" if total_pnl > 0 else "🔴"
    tg_msg = f"""📊 <b>EVENING UPDATE — {today} {now}</b>
⏰ Prices as of: Today {now} NSE Close

━━━━━━━━━━━━━━━━━━━━
📈 <b>MARKET TODAY</b>
Nifty: {nifty.get('level', 0):,.0f} ({nifty_chg:+.2f}%) {nifty_mood}

━━━━━━━━━━━━━━━━━━━━
💼 <b>YOUR POSITIONS</b>
{port_txt}
━━━━━━━━━━━━━━━━━━━━
{total_emoji} <b>TOTAL P&L: ₹{total_pnl:+,.0f} ({total_pnl_pct:+.1f}%)</b>
Invested: ₹{total_invested:,.0f} | Current: ₹{total_current:,.0f}

📧 Detailed report sent to Gmail
💬 Use /analyse STOCK for deep analysis"""

    send_telegram(tg_msg)

    # Build email
    position_rows = ""
    for p in position_updates:
        pnl_color = "#27ae60" if p['pnl'] > 0 else "#e74c3c"
        action_color = {"red": "#e74c3c", "green": "#27ae60", "orange": "#f39c12", "blue": "#3498db"}.get(p['color'], "#333")
        news_row = f"<tr style='background:#fffde7'><td colspan='10' style='font-size:12px;padding:6px 12px'>📰 <b>News:</b> {p['news']} — <span style='color:{\"#27ae60\" if \"POSITIVE\" in str(p[\"news_sentiment\"]) else \"#e74c3c\"}'>{p['news_sentiment']}</span></td></tr>" if p['news'] else ""

        position_rows += f"""
        <tr>
            <td><b>{p['symbol']}</b></td>
            <td>₹{p['entry']}</td>
            <td>₹{p['current']}</td>
            <td style='color:{"#27ae60" if p["day_change"] > 0 else "#e74c3c"}'>{p['day_change']:+.1f}%</td>
            <td style='color:{pnl_color}'><b>₹{p['pnl']:+,.0f}</b></td>
            <td style='color:{pnl_color}'><b>{p['pnl_pct']:+.1f}%</b></td>
            <td>{p['days_held']} days</td>
            <td>{p['rsi']:.0f if p['rsi'] else 'N/A'}</td>
            <td>₹{p['target']} | ₹{p['stop_loss']}</td>
            <td style='font-size:11px;color:#7f8c8d'>{p['price_timestamp']}</td>
        </tr>
        <tr style='background:#f8f9fa'><td colspan='10' style='padding:6px 12px'>
            <span style='color:{action_color}'><b>{p['action']}</b></span> — {p['reason']}
        </td></tr>
        {news_row}"""

    total_color = "#27ae60" if total_pnl > 0 else "#e74c3c"
    nifty_color = "#27ae60" if nifty_chg > 0 else "#e74c3c"

    email_body = f"""<html><body style='font-family:Arial,sans-serif;max-width:1000px;margin:auto;padding:20px'>
<div style='background:linear-gradient(135deg,#2c3e50,#27ae60);padding:20px;border-radius:12px;color:white;margin-bottom:20px'>
<h1 style='margin:0'>📊 Evening Position Update</h1>
<p style='margin:5px 0 0;opacity:0.9'>{today} | {now} | {len(position_updates)} open positions</p>
<p style='margin:5px 0 0;opacity:0.8;font-size:13px'>⏰ All prices as of: Today {now} NSE Official Close</p>
</div>

<div style='background:#eaf4fb;padding:15px;border-radius:8px;margin-bottom:20px'>
<h3 style='margin:0'>📈 Market Today</h3>
<p style='margin:5px 0 0'>Nifty: <b>{nifty.get('level',0):,.0f}</b> <span style='color:{nifty_color}'>({nifty_chg:+.2f}%)</span> — {nifty_mood}</p>
</div>

<div style='background:#{'eafaf1' if total_pnl >= 0 else 'fdf2f2'};padding:15px;border-radius:8px;border-left:4px solid {total_color};margin-bottom:20px'>
<h3 style='margin:0;color:{total_color}'>💰 Total Portfolio P&L: ₹{total_pnl:+,.0f} ({total_pnl_pct:+.1f}%)</h3>
<p style='margin:5px 0 0;font-size:13px'>Total Invested: ₹{total_invested:,.0f} | Current Value: ₹{total_current:,.0f}</p>
</div>

<h2 style='border-bottom:2px solid #3498db;padding-bottom:8px'>💼 Your Open Positions</h2>
<div style='background:#f8f9fa;padding:12px;border-radius:8px;margin-bottom:10px;font-size:13px;color:#555'>
💡 <b>How to read this:</b> Each row shows your trade performance today.
Day change = how much the stock moved today only. P&L = total profit/loss since you bought.
Action tells you what to do. Follow stop loss strictly — it protects your capital.
</div>
<table border='1' cellpadding='8' cellspacing='0' style='width:100%;border-collapse:collapse;font-size:13px'>
<tr style='background:#2c3e50;color:white'>
<th>Stock</th><th>Entry</th><th>Today</th><th>Day Chg</th><th>P&L ₹</th><th>P&L %</th><th>Days</th><th>RSI</th><th>Target | SL</th><th>Price as of</th>
</tr>
{position_rows}
</table>

<p style='color:#7f8c8d;font-size:12px;margin-top:20px;border-top:1px solid #eee;padding-top:10px'>
⚠️ Prices are NSE closing prices for today.<br>
Always verify in Zerodha before taking any action.<br>
Use /analyse STOCKNAME in Telegram for instant deep analysis.
</p>
</body></html>"""

    total_emoji_txt = "🟢" if total_pnl >= 0 else "🔴"
    send_email(
        subject=f"📊 Evening Update {today} | P&L: {total_emoji_txt} ₹{total_pnl:+,.0f} ({total_pnl_pct:+.1f}%)",
        body=email_body
    )
    print(f"\n✅ Evening update complete! P&L: ₹{total_pnl:+,.0f}")

run_evening_update()
