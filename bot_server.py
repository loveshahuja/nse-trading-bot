# ============================================================
# NSE TRADING BOT v5.0 — RENDER SERVER
# Lightweight — only handles:
# 1. Telegram webhook (instant 24/7 responses)
# 2. APScheduler triggers GitHub Actions at right times
# 3. Health check
# NO heavy scanning — GitHub Actions does that
# ============================================================
from flask import Flask, request, jsonify
import requests
import os
import json
import gzip
import zlib
import time
import math
import gspread
import yfinance as yf
import ta
import warnings
import threading
from google.oauth2.service_account import Credentials
from datetime import datetime
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

warnings.filterwarnings('ignore')
app = Flask(__name__)
IST = pytz.timezone('Asia/Kolkata')

# ── Credentials ───────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
GOOGLE_SHEET_ID  = os.environ.get('GOOGLE_SHEET_ID')
GOOGLE_CREDS     = os.environ.get('GOOGLE_CREDENTIALS')
GITHUB_TOKEN     = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO      = os.environ.get('GITHUB_REPO', 'loveshahuja/nse-trading-bot')

# ── F&O Lot Sizes ─────────────────────────────────────────────
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
    "ASIANPAINT":300,"BRITANNIA":250,"NESTLEIND":100,
    "DIVISLAB":200,"APOLLOHOSP":125,"BAJAJFINSV":500,
    "HINDUNILVR":300,"ITC":3200,"SBILIFE":750,"HDFCLIFE":1100,
    "INDUSINDBK":525,"GRASIM":475,"TATACONSUM":1100,
    "ULTRACEMCO":100,"BHARTIARTL":950,"TECHM":600,
}
FON_STOCKS = set(k+".NS" for k in FON_LOT_SIZES)

def now_ist(): return datetime.now(IST)
def ist_str(fmt='%d %b %Y %I:%M %p IST'): return now_ist().strftime(fmt)
def today_str(): return now_ist().strftime('%d %b %Y')

# ── Telegram ──────────────────────────────────────────────────
def send_telegram(message, chat_id=None):
    try:
        cid = chat_id or TELEGRAM_CHAT_ID
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        for chunk in [message[i:i+4000] for i in range(0, len(message), 4000)]:
            requests.post(url, data={"chat_id":cid,"text":chunk,"parse_mode":"HTML"}, timeout=15)
            time.sleep(0.3)
    except Exception as e:
        print(f"Telegram error: {e}")

# ── Google Sheets ─────────────────────────────────────────────
def setup_sheets():
    try:
        creds_dict = json.loads(GOOGLE_CREDS)
        scopes = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client.open_by_key(GOOGLE_SHEET_ID)
    except Exception as e:
        print(f"Sheets error: {e}"); return None

# ── GitHub Actions Trigger ────────────────────────────────────
def trigger_github_workflow(workflow_name):
    """Trigger a GitHub Actions workflow via API"""
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{workflow_name}/dispatches"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        }
        payload = {"ref": "main"}
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        if r.status_code == 204:
            print(f"✅ Triggered {workflow_name}")
            return True
        else:
            print(f"❌ Failed to trigger {workflow_name}: {r.status_code} {r.text}")
            return False
    except Exception as e:
        print(f"❌ GitHub trigger error: {e}")
        return False

# ── Scheduled Triggers ────────────────────────────────────────
def trigger_morning_scan():
    print(f"Triggering morning scan — {ist_str()}")
    if trigger_github_workflow("morning_scan.yml"):
        send_telegram(f"⏳ <b>Morning Scan triggered</b>\n{ist_str()}\nGitHub Actions running scan. Report in ~25 mins.")
    else:
        send_telegram(f"⚠️ Morning scan trigger failed at {ist_str()}\nTry manually: /run_morning")

def trigger_midday():
    print(f"Triggering midday — {ist_str()}")
    trigger_github_workflow("midday_update.yml")

def trigger_evening():
    print(f"Triggering evening — {ist_str()}")
    trigger_github_workflow("evening_update.yml")

def trigger_confluence():
    print(f"Triggering confluence — {ist_str()}")
    trigger_github_workflow("confluence_scan.yml")

# ── Stock Analysis (lightweight — for /analyse command) ───────
def analyse_stock(sym):
    try:
        sym = sym.upper().replace('.NS','')
        n = now_ist()
        if 1 <= n.hour <= 6:
            return f"⏰ Market data unavailable at {ist_str('%I:%M %p IST')}. Try after 6 AM IST."
        df = yf.download(sym+'.NS', period="3mo", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df)<30:
            return f"❌ No data for {sym}. Check symbol name."
        close=df['Close'].squeeze(); volume=df['Volume'].squeeze()
        curr=float(close.iloc[-1]); prev=float(close.iloc[-2])
        if math.isnan(curr) or math.isnan(prev):
            return f"⏰ {sym} data unavailable. Try after 9 AM IST."
        rsi=float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
        ema20=float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
        ema50=float(ta.trend.EMAIndicator(close,50).ema_indicator().iloc[-1])
        macd=ta.trend.MACD(close); ml=float(macd.macd().iloc[-1]); sl_v=float(macd.macd_signal().iloc[-1])
        avg_vol=float(volume.tail(20).mean()); lat_vol=float(volume.iloc[-1])
        vol_surge=lat_vol>avg_vol*1.5
        support=round(float(close.tail(20).min()),2)
        resistance=round(float(close.tail(20).max()),2)
        day_chg=((curr-prev)/prev)*100
        is_fno=sym+'.NS' in FON_STOCKS; lot=FON_LOT_SIZES.get(sym,0)
        bs=0; ss=0
        if rsi<40: bs+=2
        elif rsi<50: bs+=1
        if rsi>70: ss+=2
        elif rsi>60: ss+=1
        if ema20>ema50: bs+=2
        else: ss+=2
        if ml>sl_v: bs+=2
        else: ss+=2
        if vol_surge: bs+=1
        if bs>=6: signal="STRONG BUY 🟢"
        elif bs>=4 and bs>ss: signal="BUY 🟢"
        elif ss>=6: signal="STRONG SELL 🔴"
        elif ss>=4 and ss>bs: signal="SELL 🔴"
        else: signal="HOLD 🟡"
        score=sum([1 if (40<=rsi<=65 or rsi<40) else 0,
                   1 if ema20>ema50 else 0,
                   1 if ml>sl_v else 0,
                   1 if vol_surge else 0])
        entry=round(curr*0.999,2); target=round(curr*1.10,2)
        sl_p=round(max(curr*0.97,support*0.98),2)
        sl_dist=curr-sl_p; max_shares=int((200000*0.02)/sl_dist) if sl_dist>0 else 0
        opt_txt=""
        if is_fno and "BUY" in signal and rsi<72 and lot>0:
            strike=round(curr*1.03/50)*50; prem=round(curr*0.028,1); cap=round(prem*lot)
            opt_txt=f"\n🎯 <b>OPTIONS:</b> {sym} {strike} CE | Prem ~₹{prem} | Lot {lot} | Capital ~₹{cap:,}\n⚠️ Verify in Zerodha Options Chain"
        return f"""🔍 <b>ANALYSIS — {sym}</b>
⏰ {ist_str()} (15 min delayed)

💰 ₹{curr:.2f} ({day_chg:+.2f}% today)
Signal   : <b>{signal}</b> ({score}/4 {"⭐"*score})
Support  : ₹{support} | Resistance: ₹{resistance}

📊 RSI: {rsi:.1f} {'✅ Healthy' if rsi<65 else '⚠️ Elevated'}
Trend  : {'UP ✅' if ema20>ema50 else 'DOWN ❌'}
MACD   : {'Bullish ✅' if ml>sl_v else 'Bearish ❌'}
Volume : {'Surge ✅' if vol_surge else 'Normal'}

📈 <b>Trade Plan</b>
Entry    : ₹{entry}
Target   : ₹{target} (+10%)
Stop Loss: ₹{sl_p} (-3%)
Position : {max_shares} shares = ₹{max_shares*curr:,.0f} (2% risk on ₹2L)
{"F&O ✅ Lot: "+str(lot) if is_fno else "Not F&O"}{opt_txt}

⚠️ Verify price in Zerodha before trading"""
    except Exception as e:
        return f"❌ Error: {str(e)[:100]}"

# ── Telegram Commands ─────────────────────────────────────────
def process_command(text, chat_id):
    sheet = setup_sheets()
    parts = text.strip().split(); cmd=parts[0].lower(); args=parts[1:]

    if cmd in ['/start','/help']:
        return """🤖 <b>NSE Trading Bot v5.0</b>
24/7 Active | Instant Response

📈 <b>RECORD TRADES</b>
/buy STOCK PRICE QTY
/buyce STOCK STRIKE PREMIUM LOTS
/sell STOCK EXIT_PRICE
/sellce STOCK STRIKE EXIT_PREMIUM

📊 <b>VIEW</b>
/portfolio — open trades

🔍 <b>ANALYSIS</b>
/analyse STOCK
/compare STOCK1 STOCK2
/market — live indices

🔄 <b>MANUAL TRIGGERS</b>
/run_morning — trigger morning scan now
/run_midday — trigger midday now
/run_evening — trigger evening now

⏰ <b>AUTO REPORTS</b>
8:00 AM — Morning scan
12:00 PM — Midday update
8:00 PM — Evening update
Confluence — 4x daily"""

    elif cmd == '/ping':
        return f"🟢 Bot alive!\n⏰ {ist_str()}"

    elif cmd == '/market':
        try:
            msg = f"📊 <b>LIVE MARKET</b>\n⏰ {ist_str()} (15 min delayed)\n\n"
            for name,ticker in [("Nifty 50","^NSEI"),("Bank Nifty","^NSEBANK"),("Sensex","^BSESN")]:
                df=yf.download(ticker,period="5d",interval="1d",progress=False,auto_adjust=True)
                if not df.empty and len(df)>=2:
                    curr=float(df['Close'].iloc[-1]); prev=float(df['Close'].iloc[-2])
                    if not math.isnan(curr):
                        chg=((curr-prev)/prev)*100
                        rsi=float(ta.momentum.RSIIndicator(df['Close'].squeeze()).rsi().iloc[-1])
                        msg+=f"{'🟢' if chg>0 else '🔴'} <b>{name}</b>: {curr:,.0f} ({chg:+.2f}%) | RSI:{rsi:.0f}\n"
                time.sleep(0.3)
            msg+="\n💡 RSI<40=oversold | RSI>70=overbought"
            return msg
        except: return "❌ Market data unavailable. Try again."

    elif cmd == '/analyse' and args:
        return analyse_stock(args[0])

    elif cmd == '/compare' and len(args)>=2:
        return f"⚖️ <b>{args[0].upper()} vs {args[1].upper()}</b>\n\n{analyse_stock(args[0])}\n\n{'━'*30}\n\n{analyse_stock(args[1])}"

    elif cmd == '/run_morning':
        if trigger_github_workflow("morning_scan.yml"):
            return f"✅ Morning scan triggered!\nGitHub Actions running. Report in ~25 mins.\n⏰ {ist_str()}"
        return "❌ Failed to trigger. Check GitHub token."

    elif cmd == '/run_midday':
        if trigger_github_workflow("midday_update.yml"):
            return f"✅ Midday update triggered!\n⏰ {ist_str()}"
        return "❌ Failed to trigger."

    elif cmd == '/run_evening':
        if trigger_github_workflow("evening_update.yml"):
            return f"✅ Evening update triggered!\n⏰ {ist_str()}"
        return "❌ Failed to trigger."

    elif cmd == '/run_confluence':
        if trigger_github_workflow("confluence_scan.yml"):
            return f"✅ Confluence scan triggered!\n⏰ {ist_str()}"
        return "❌ Failed to trigger."

    elif cmd == '/buy':
        if len(args)<3: return "❌ Format: /buy STOCK PRICE QTY\nExample: /buy BEL 435 50"
        try:
            stock=args[0].upper().replace('.NS',''); price=float(args[1]); qty=int(args[2])
            target=round(price*1.10,2); sl=round(price*0.97,2); today=today_str()
            invested=price*qty
            if sheet:
                ws=sheet.worksheet("Open Trades")
                if not ws.row_values(1):
                    ws.append_row(["Entry Date","Stock","Type","Entry Price","Qty","Target","Stop Loss","Days Held","Notes"])
                ws.append_row([today,stock,"STOCK",price,qty,target,sl,0,""])
            lot=FON_LOT_SIZES.get(stock,0)
            return f"""✅ <b>TRADE RECORDED — {stock}</b>
Entry     : ₹{price} × {qty} = ₹{invested:,.0f}
Target    : ₹{target} (+10%)
Stop Loss : ₹{sl} (-3%)
Date      : {today}
{"F&O ✅ Lot: "+str(lot) if lot else ""}
💡 Set alerts in Zerodha: Target ₹{target} | SL ₹{sl}"""
        except Exception as e: return f"❌ Error: {e}"

    elif cmd == '/buyce':
        if len(args)<4: return "❌ Format: /buyce STOCK STRIKE PREMIUM LOTS"
        try:
            stock=args[0].upper().replace('.NS',''); strike=float(args[1])
            prem=float(args[2]); lots=int(args[3])
            lot_size=FON_LOT_SIZES.get(stock,500); total_qty=lot_size*lots
            capital=round(prem*total_qty); today=today_str()
            if sheet:
                ws=sheet.worksheet("Open Trades")
                ws.append_row([today,stock,f"CE_{strike}",prem,total_qty,
                               round(prem*2.2,1),round(prem*0.5,1),0,f"{lots} lots"])
            return f"""✅ <b>OPTIONS TRADE — {stock} {strike} CE</b>
Premium   : ₹{prem} × {total_qty} = ₹{capital:,}
Target    : ₹{round(prem*2.2,1)} (+120%)
Stop Loss : ₹{round(prem*0.5,1)} (-50%)
Lots      : {lots} × {lot_size} = {total_qty} shares"""
        except Exception as e: return f"❌ Error: {e}"

    elif cmd == '/sell':
        if len(args)<2: return "❌ Format: /sell STOCK PRICE"
        try:
            stock=args[0].upper().replace('.NS',''); exit_price=float(args[1]); today=today_str()
            if not sheet: return "❌ Sheets unavailable"
            open_ws=sheet.worksheet("Open Trades"); records=open_ws.get_all_records()
            trade_row=None; row_num=None
            for i,r in enumerate(records,2):
                if r.get('Stock','').upper()==stock and r.get('Type')=='STOCK':
                    trade_row=r; row_num=i; break
            if not trade_row: return f"❌ No open trade for {stock}."
            entry=float(trade_row.get('Entry Price',0)); qty=int(trade_row.get('Qty',0))
            pnl=(exit_price-entry)*qty; pnl_pct=((exit_price-entry)/entry)*100
            days=trade_row.get('Days Held',0)
            closed_ws=sheet.worksheet("Closed Trades")
            if not closed_ws.row_values(1):
                closed_ws.append_row(["Entry Date","Exit Date","Stock","Type","Entry","Exit","Qty","P&L","P&L%","Days"])
            closed_ws.append_row([trade_row.get('Entry Date'),today,stock,'STOCK',
                                  entry,exit_price,qty,round(pnl,2),round(pnl_pct,2),days])
            open_ws.delete_rows(row_num)
            return f"""{'🟢' if pnl>0 else '🔴'} <b>CLOSED — {stock}</b>
Entry → Exit : ₹{entry} → ₹{exit_price}
P&L : ₹{pnl:+,.0f} ({pnl_pct:+.1f}%) | Days: {days}
{'🎉 Profitable!' if pnl>0 else '📚 Loss — review for learning.'}"""
        except Exception as e: return f"❌ Error: {e}"

    elif cmd == '/sellce':
        if len(args)<3: return "❌ Format: /sellce STOCK STRIKE EXIT_PREMIUM"
        try:
            stock=args[0].upper().replace('.NS',''); strike=float(args[1]); exit_prem=float(args[2])
            today=today_str()
            if not sheet: return "❌ Sheets unavailable"
            open_ws=sheet.worksheet("Open Trades"); records=open_ws.get_all_records()
            trade_row=None; row_num=None
            for i,r in enumerate(records,2):
                if r.get('Stock','').upper()==stock and str(strike) in str(r.get('Type','')):
                    trade_row=r; row_num=i; break
            if not trade_row: return f"❌ No open CE trade for {stock} {strike}."
            entry_prem=float(trade_row.get('Entry Price',0)); qty=int(trade_row.get('Qty',0))
            pnl=(exit_prem-entry_prem)*qty; pnl_pct=((exit_prem-entry_prem)/entry_prem)*100
            days=trade_row.get('Days Held',0)
            closed_ws=sheet.worksheet("Closed Trades")
            closed_ws.append_row([trade_row.get('Entry Date'),today,stock,f"CE_{strike}",
                                  entry_prem,exit_prem,qty,round(pnl,2),round(pnl_pct,2),days])
            open_ws.delete_rows(row_num)
            return f"""{'🟢' if pnl>0 else '🔴'} <b>OPTIONS CLOSED — {stock} {strike} CE</b>
Entry → Exit : ₹{entry_prem} → ₹{exit_prem}
P&L : ₹{pnl:+,.0f} ({pnl_pct:+.1f}%)"""
        except Exception as e: return f"❌ Error: {e}"

    elif cmd in ['/portfolio','/pnl']:
        if not sheet: return "❌ Sheets unavailable"
        try:
            ws=sheet.worksheet("Open Trades"); records=ws.get_all_records()
            if not records: return "📊 <b>No open trades</b>\nUse /buy STOCK PRICE QTY"
            msg=f"💼 <b>OPEN POSITIONS</b>\n⏰ {ist_str()}\n\n"; total=0
            for r in records:
                stock=r.get('Stock',''); entry=float(r.get('Entry Price',0))
                qty=int(r.get('Qty',0)); target=float(r.get('Target',0))
                sl=float(r.get('Stop Loss',0)); days=r.get('Days Held',0)
                invested=entry*qty; total+=invested
                msg+=f"<b>{stock}</b> ({r.get('Type','STOCK')})\n₹{entry} × {qty} = ₹{invested:,.0f} | Day {days}\nT:₹{target} | SL:₹{sl}\n\n"
            msg+=f"💰 Total: ₹{total:,.0f}"
            return msg
        except Exception as e: return f"❌ Error: {e}"

    return None

# ── Flask Routes ──────────────────────────────────────────────
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data=request.get_json()
        if not data: return jsonify({"ok":True})
        msg=data.get('message',{}); text=msg.get('text','')
        chat_id=str(msg.get('chat',{}).get('id',''))
        if text and text.startswith('/'):
            print(f"CMD: {text}")
            resp=process_command(text,chat_id)
            if resp: send_telegram(resp,chat_id)
    except Exception as e:
        print(f"Webhook error: {e}")
    return jsonify({"ok":True})

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status":"alive","time":ist_str(),"version":"5.0"})

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status":"NSE Bot v5.0 — Render (Telegram) + GitHub Actions (Scans)"})

# Manual trigger routes
@app.route('/run_morning', methods=['GET'])
def manual_morning():
    ok=trigger_github_workflow("morning_scan.yml")
    if ok: send_telegram(f"⏳ <b>Morning scan triggered manually</b>\n{ist_str()}\nReport in ~25 mins.")
    return jsonify({"status":"triggered" if ok else "failed","time":ist_str()})

@app.route('/run_midday', methods=['GET'])
def manual_midday():
    ok=trigger_github_workflow("midday_update.yml")
    return jsonify({"status":"triggered" if ok else "failed","time":ist_str()})

@app.route('/run_evening', methods=['GET'])
def manual_evening():
    ok=trigger_github_workflow("evening_update.yml")
    return jsonify({"status":"triggered" if ok else "failed","time":ist_str()})

@app.route('/run_confluence', methods=['GET'])
def manual_confluence():
    ok=trigger_github_workflow("confluence_scan.yml")
    return jsonify({"status":"triggered" if ok else "failed","time":ist_str()})

# ── Scheduler ─────────────────────────────────────────────────
def start_scheduler():
    scheduler = BackgroundScheduler(timezone=IST)
    # Trigger GitHub Actions at the right times
    scheduler.add_job(trigger_morning_scan, CronTrigger(
        hour=8, minute=0, day_of_week='mon-fri', timezone=IST))
    scheduler.add_job(trigger_midday, CronTrigger(
        hour=12, minute=0, day_of_week='mon-fri', timezone=IST))
    scheduler.add_job(trigger_evening, CronTrigger(
        hour=20, minute=0, day_of_week='mon-fri', timezone=IST))
    scheduler.add_job(trigger_confluence, CronTrigger(
        hour=9, minute=15, day_of_week='mon-fri', timezone=IST))
    scheduler.add_job(trigger_confluence, CronTrigger(
        hour=11, minute=0, day_of_week='mon-fri', timezone=IST))
    scheduler.add_job(trigger_confluence, CronTrigger(
        hour=13, minute=0, day_of_week='mon-fri', timezone=IST))
    scheduler.add_job(trigger_confluence, CronTrigger(
        hour=14, minute=30, day_of_week='mon-fri', timezone=IST))
    scheduler.start()
    print("✅ Scheduler started — triggers GitHub Actions at right times")
    print("   8:00 AM → morning_scan.yml")
    print("   12:00 PM → midday_update.yml")
    print("   8:00 PM → evening_update.yml")
    print("   9:15, 11:00, 13:00, 14:30 → confluence_scan.yml")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"NSE Bot v5.0 starting on port {port} — {ist_str()}")
    start_scheduler()
    send_telegram(f"🚀 <b>NSE Bot v5.0 Online!</b>\n⏰ {ist_str()}\n\n✅ Telegram bot active 24/7\n✅ Scheduler triggers GitHub Actions\n✅ Morning: 8 AM | Midday: 12 PM | Evening: 8 PM\n\nSend /help for commands")
    app.run(host='0.0.0.0', port=port)
