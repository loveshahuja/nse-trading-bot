# ============================================================
# NSE TRADING BOT v4.0 — Complete System
# Runs 24/7 on Render.com
# - Telegram webhook (instant 24/7 responses)
# - Morning scan 8:00 AM IST
# - Midday update 12:00 PM IST  
# - Evening update 8:00 PM IST
# - Confluence scanner 9AM, 11AM, 1PM, 2:30PM IST
# ============================================================
from flask import Flask, request, jsonify
import yfinance as yf
import pandas as pd
import ta
import requests
import os
import json
import gzip
import zlib
import time
import smtplib
import warnings
import feedparser
import gspread
import math
import threading
from google.oauth2.service_account import Credentials
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
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
GMAIL_ADDRESS    = os.environ.get('GMAIL_ADDRESS')
GMAIL_PASSWORD   = os.environ.get('GMAIL_PASSWORD')

# ── Portfolio ─────────────────────────────────────────────────
MY_PORTFOLIO = [
    "BLS.NS","ENGINERSIN.NS","HDFCBANK.NS","JIOFIN.NS",
    "PARADEEP.NS","SUZLON.NS","SYNGENE.NS","VMM.NS","BEL.NS"
]

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

# ── Sector Map ────────────────────────────────────────────────
SECTOR_REP = {
    "IT":        ["TCS.NS","INFY.NS","HCLTECH.NS"],
    "BANKING":   ["HDFCBANK.NS","ICICIBANK.NS","SBIN.NS"],
    "PHARMA":    ["SUNPHARMA.NS","DRREDDY.NS","CIPLA.NS"],
    "DEFENCE":   ["HAL.NS","BEL.NS","BEML.NS"],
    "POWER":     ["NTPC.NS","TATAPOWER.NS","ADANIGREEN.NS"],
    "AUTO":      ["MARUTI.NS","TATAMOTORS.NS","BAJAJ-AUTO.NS"],
    "FMCG":      ["HINDUNILVR.NS","ITC.NS","NESTLEIND.NS"],
    "INFRA":     ["LT.NS","RVNL.NS","IRFC.NS"],
    "METALS":    ["TATASTEEL.NS","JSWSTEEL.NS","HINDALCO.NS"],
    "ENERGY":    ["RELIANCE.NS","ONGC.NS","BPCL.NS"],
    "REALTY":    ["DLF.NS","GODREJPROP.NS","PRESTIGE.NS"],
    "FINANCE":   ["BAJFINANCE.NS","BAJAJFINSV.NS","MUTHOOTFIN.NS"],
    "CHEMICALS": ["DEEPAKNTR.NS","ATUL.NS","TATACHEM.NS"],
    "CEMENT":    ["ULTRACEMCO.NS","AMBUJACEM.NS","ACC.NS"],
    "INSURANCE": ["SBILIFE.NS","HDFCLIFE.NS","ICICIPRULI.NS"],
    "CONSUMER":  ["TITAN.NS","ASIANPAINT.NS","HAVELLS.NS"],
    "TELECOM":   ["BHARTIARTL.NS","TATACOMM.NS","HFCL.NS"],
}

SECTOR_STOCKS = {}
for s, stocks in SECTOR_REP.items():
    for sym in stocks:
        SECTOR_STOCKS[sym] = s

def get_sector(symbol):
    return SECTOR_STOCKS.get(symbol, "GENERAL")

# ── Helpers ───────────────────────────────────────────────────
def now_ist():
    return datetime.now(IST)

def ist_str(fmt='%d %b %Y %I:%M %p IST'):
    return now_ist().strftime(fmt)

def today_str():
    return now_ist().strftime('%d %b %Y')

def is_market_hours():
    n = now_ist()
    return n.weekday() < 5 and 9 <= n.hour < 16

def send_telegram(message, chat_id=None):
    try:
        cid = chat_id or TELEGRAM_CHAT_ID
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        for chunk in [message[i:i+4000] for i in range(0, len(message), 4000)]:
            requests.post(url, data={"chat_id":cid,"text":chunk,"parse_mode":"HTML"}, timeout=15)
            time.sleep(0.3)
    except Exception as e:
        print(f"Telegram error: {e}")

def send_email(subject, body, csv_file=None):
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_ADDRESS
        msg['To'] = GMAIL_ADDRESS
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        if csv_file and os.path.exists(csv_file):
            with open(csv_file,"rb") as f:
                part = MIMEBase('application','octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition',
                    f'attachment; filename="{os.path.basename(csv_file)}"')
                msg.attach(part)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_ADDRESS, GMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"Email sent: {subject}")
    except Exception as e:
        print(f"Email error: {e}")

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

# ── HTML Helpers ──────────────────────────────────────────────
def mood_color(m):
    if "BULLISH" in m: return "#27ae60"
    if "BEARISH" in m: return "#e74c3c"
    return "#f39c12"

def sig_color(s):
    if "STRONG BUY" in s: return "#1e8449"
    if "BUY" in s: return "#27ae60"
    if "STRONG SELL" in s: return "#922b21"
    if "SELL" in s: return "#e74c3c"
    return "#f39c12"

def html_header(title, subtitle, c1="#2c3e50", c2="#3498db"):
    return f"""<div style='background:linear-gradient(135deg,{c1},{c2});padding:20px;border-radius:12px;color:white;margin-bottom:20px'>
<h1 style='margin:0'>{title}</h1><p style='margin:5px 0 0;opacity:0.9'>{subtitle}</p></div>"""

def tip(text):
    return f"<div style='background:#f8f9fa;padding:10px;border-radius:8px;margin-bottom:10px;font-size:13px;color:#555'>💡 {text}</div>"

def tbl(headers):
    ths = "".join(f"<th style='padding:8px'>{h}</th>" for h in headers)
    return f"<table border='1' cellpadding='6' cellspacing='0' style='width:100%;border-collapse:collapse;font-size:13px'><tr style='background:#2c3e50;color:white'>{ths}</tr>"

# ── Data Fetchers ─────────────────────────────────────────────
def get_global_markets():
    print("Fetching global markets...")
    # Use Yahoo Finance with proper tickers
    tickers = {
        "US_DOW": "^DJI", "US_NASDAQ": "^IXIC",
        "CRUDE_OIL": "CL=F", "GOLD": "GC=F",
        "USD_INR": "INR=X", "VIX": "^VIX",
    }
    result = {}
    for name, ticker in tickers.items():
        for attempt in range(3):
            try:
                df = yf.download(ticker, period="5d", interval="1d", progress=False, auto_adjust=True)
                if not df.empty and len(df) >= 2:
                    curr = float(df['Close'].iloc[-1])
                    prev = float(df['Close'].iloc[-2])
                    if not math.isnan(curr) and not math.isnan(prev) and prev > 0:
                        chg = ((curr-prev)/prev)*100
                        result[name] = {"price": round(curr,2), "change_pct": round(chg,2)}
                        break
            except:
                pass
            time.sleep(1)
        time.sleep(0.5)
    return result

def get_fii_dii():
    print("Fetching FII/DII...")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.nseindia.com/',
        }
        session = requests.Session()
        session.headers.update(headers)
        try:
            session.get('https://www.nseindia.com/', timeout=15)
        except:
            pass
        time.sleep(3)
        r = session.get('https://www.nseindia.com/api/fiidiiTradeReact', timeout=20)
        if r.status_code == 200 and r.content:
            text = None
            try:
                text = r.text
                if not text or not text.strip().startswith('['):
                    text = None
            except: pass
            if not text:
                try: text = gzip.decompress(r.content).decode('utf-8')
                except: pass
            if not text:
                try: text = zlib.decompress(r.content, 16+zlib.MAX_WBITS).decode('utf-8')
                except: pass
            if text and '[' in text:
                data = json.loads(text)
                fii_net = dii_net = None
                date = ""
                for item in data:
                    cat = item.get('category','').upper()
                    try: net = float(str(item.get('netValue','0')).replace(',',''))
                    except: net = 0
                    if 'FII' in cat or 'FPI' in cat:
                        fii_net = net; date = item.get('date','')
                    elif 'DII' in cat:
                        dii_net = net
                if fii_net is not None:
                    print(f"  FII: ₹{fii_net:,.0f}Cr | DII: ₹{dii_net:,.0f}Cr ({date})")
                    return {"date":date,"fii_net":fii_net,"dii_net":dii_net,"source":"NSE"}
    except Exception as e:
        print(f"FII error: {e}")
    return {"date":today_str(),"fii_net":None,"dii_net":None,"source":"unavailable"}

def get_news():
    feeds = [
        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "https://www.moneycontrol.com/rss/business.xml",
    ]
    stocks = ["BLS","ENGINERSIN","HDFCBANK","JIOFIN","PARADEEP","SUZLON",
              "SYNGENE","VMM","BEL","NIFTY","SENSEX","MARKET","INDIA","TATA","RELIANCE"]
    items = []; seen = set()
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:20]:
                title = e.get('title',''); text = title.upper()
                matched = next((s for s in stocks if s in text), "MARKET")
                pos = sum(1 for w in ["SURGE","GAIN","RISE","PROFIT","BULLISH","RECORD","UP","BEAT","BUY"] if w in text)
                neg = sum(1 for w in ["FALL","LOSS","CRASH","BEARISH","DOWN","DECLINE","WEAK","SELL"] if w in text)
                sent = "POSITIVE 🟢" if pos>neg else "NEGATIVE 🔴" if neg>pos else "NEUTRAL 🟡"
                key = title[:60]
                if key not in seen:
                    seen.add(key)
                    items.append({"stock":matched,"headline":title[:150],"sentiment":sent})
        except: pass
    return items[:12]

def analyze_index(ticker, name):
    try:
        df = yf.download(ticker, period="3mo", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < 20: return None
        close = df['Close'].squeeze()
        curr = float(close.iloc[-1]); prev = float(close.iloc[-2])
        if math.isnan(curr): return None
        rsi = float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
        ema20 = float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
        ema50 = float(ta.trend.EMAIndicator(close,50).ema_indicator().iloc[-1])
        macd = ta.trend.MACD(close)
        ml = float(macd.macd().iloc[-1]); sl = float(macd.macd_signal().iloc[-1])
        chg = ((curr-prev)/prev)*100
        sup = round(float(close.tail(20).min()),2)
        res = round(float(close.tail(20).max()),2)
        if ema20>ema50 and ml>sl and rsi<70: direction="BULLISH"; mood="BULLISH 🟢"
        elif ema20<ema50 and ml<sl: direction="BEARISH"; mood="BEARISH 🔴"
        elif rsi>70: direction="OVERBOUGHT"; mood="OVERBOUGHT ⚠️"
        else: direction="NEUTRAL"; mood="NEUTRAL 🟡"
        return {"name":name,"level":round(curr,2),"change_pct":round(chg,2),
                "rsi":round(rsi,1),"trend":"UP" if ema20>ema50 else "DOWN",
                "macd":"BULLISH" if ml>sl else "BEARISH","support":sup,"resistance":res,
                "direction":direction,"mood":mood}
    except Exception as e:
        print(f"Index error {name}: {e}"); return None

def get_sector_momentum():
    print("Calculating sector momentum...")
    result = {}
    for sector, stocks in SECTOR_REP.items():
        bull = 0; total = 0
        for sym in stocks:
            try:
                df = yf.download(sym, period="3mo", interval="1d", progress=False, auto_adjust=True)
                if df.empty or len(df) < 20: continue
                close = df['Close'].squeeze()
                ema20 = float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
                ema50 = float(ta.trend.EMAIndicator(close,50).ema_indicator().iloc[-1])
                macd = ta.trend.MACD(close)
                ml = float(macd.macd().iloc[-1]); sl = float(macd.macd_signal().iloc[-1])
                rsi = float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
                if ema20>ema50 and ml>sl and rsi<75: bull+=1
                total+=1; time.sleep(0.2)
            except: pass
        if total>0:
            score = bull/total
            result[sector] = "BULLISH 🟢" if score>=0.67 else "NEUTRAL 🟡" if score>=0.34 else "BEARISH 🔴"
    return result

def calculate_signal(symbol, sector_signals=None, nifty_dir="NEUTRAL"):
    try:
        df = yf.download(symbol, period="6mo", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < 30: return None
        close = df['Close'].squeeze(); volume = df['Volume'].squeeze()
        curr = float(close.iloc[-1])
        if math.isnan(curr) or curr < 50: return None
        avg_vol = float(volume.tail(20).mean())
        if avg_vol < 50000: return None
        prev = float(close.iloc[-2])
        if math.isnan(prev): return None
        rsi = float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
        ema20 = float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
        ema50 = float(ta.trend.EMAIndicator(close,50).ema_indicator().iloc[-1]) if len(close)>=50 else ema20
        macd = ta.trend.MACD(close)
        ml = float(macd.macd().iloc[-1]); sl_val = float(macd.macd_signal().iloc[-1])
        lat_vol = float(volume.iloc[-1])
        vol_surge = lat_vol > avg_vol*1.5
        support = round(float(close.tail(20).min()),2)
        resistance = round(float(close.tail(20).max()),2)
        sector = get_sector(symbol)
        sector_mood = sector_signals.get(sector,"NEUTRAL 🟡") if sector_signals else "NEUTRAL 🟡"
        sym_clean = symbol.replace(".NS","")
        is_fno = symbol in FON_STOCKS
        lot = FON_LOT_SIZES.get(sym_clean, 0)

        # Score
        score = 0; details = []
        if rsi < 40: score+=1; details.append(f"RSI {rsi:.1f} ✅ Oversold — strong bounce expected")
        elif rsi <= 65: score+=1; details.append(f"RSI {rsi:.1f} ✅ Healthy buy zone")
        else: details.append(f"RSI {rsi:.1f} ⚠️ Elevated — stock may be overheated")
        if ema20>ema50: score+=1; details.append("Trend UP ✅ Uptrend confirmed")
        else: details.append("Trend DOWN ❌ Downtrend")
        if ml>sl_val: score+=1; details.append("MACD Bullish ✅ Buying momentum")
        else: details.append("MACD Bearish ❌ Selling momentum")
        if vol_surge: score+=1; details.append("Volume Surge ✅ Institutional buying")
        else: details.append("Volume normal")
        if "BULLISH" in sector_mood: score+=1; details.append(f"Sector {sector} ✅ Bullish")
        else: details.append(f"Sector {sector} — {sector_mood}")

        bs=0; ss=0
        if rsi<40: bs+=2
        elif rsi<50: bs+=1
        if rsi>70: ss+=2
        elif rsi>60: ss+=1
        if ema20>ema50: bs+=2
        else: ss+=2
        if ml>sl_val: bs+=2
        else: ss+=2
        if vol_surge: bs+=1
        if nifty_dir=="BULLISH": bs+=1
        elif nifty_dir=="BEARISH": ss+=1

        if bs>=6: sig="STRONG BUY"
        elif bs>=4 and bs>ss: sig="BUY"
        elif ss>=6: sig="STRONG SELL"
        elif ss>=4 and ss>bs: sig="SELL"
        else: sig="HOLD"

        entry = round(curr*0.999,2)
        dist_res = ((resistance-curr)/curr)*100
        target = round(curr*1.10,2) if dist_res>=7 else round(resistance*1.02,2)
        sl_p = round(max(curr*0.97, support*0.98),2)
        target_gap = ((target-curr)/curr)*100

        opts = None
        if is_fno and lot>0 and "BUY" in sig and rsi<72:
            mult = 1.02 if rsi<45 else 1.03 if rsi<55 else 1.05
            exp = "Current monthly" if rsi<55 else "Next monthly"
            strike = round(curr*mult/50)*50
            prem_low = round(curr*0.025,1); prem_high = round(curr*0.035,1)
            opts = {"strike":strike,"expiry":exp,"prem_low":prem_low,
                    "prem_high":prem_high,"tgt_prem":round(prem_low*2.2,1),
                    "sl_prem":round(prem_low*0.5,1),"lot":lot,
                    "cap_low":round(prem_low*lot),"cap_high":round(prem_high*lot)}

        ts = f"NSE Close — {(now_ist()-timedelta(days=1)).strftime('%d %b %Y')}"
        return {"symbol":sym_clean,"price":round(curr,2),"prev":round(prev,2),
                "day_chg":round(((curr-prev)/prev)*100,2),"signal":sig,
                "buy_score":bs,"sell_score":ss,"efficiency":score,"details":details,
                "rsi":round(rsi,1),"trend":"UP" if ema20>ema50 else "DOWN",
                "macd":"BULLISH" if ml>sl_val else "BEARISH",
                "vol_surge":"YES" if vol_surge else "no",
                "support":support,"resistance":resistance,"dist_res":round(dist_res,1),
                "sector":sector,"sector_mood":sector_mood,"is_fno":is_fno,"lot":lot,
                "entry":entry,"target":target,"sl":sl_p,"target_gap":round(target_gap,1),
                "options":opts,"timestamp":ts,"avg_vol":round(avg_vol)}
    except Exception as e:
        return None

def get_nse_symbols():
    try:
        import io
        headers = {'User-Agent':'Mozilla/5.0','Referer':'https://www.nseindia.com/'}
        session = requests.Session()
        session.get('https://www.nseindia.com', headers=headers, timeout=15)
        time.sleep(2)
        r = session.get('https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv',
                        headers=headers, timeout=30)
        if r.status_code == 200:
            df = pd.read_csv(io.StringIO(r.text))
            syms = [s.strip()+'.NS' for s in df['SYMBOL'].tolist()]
            print(f"Downloaded {len(syms)} NSE symbols")
            return syms
    except Exception as e:
        print(f"NSE download failed: {e}")
    # Fallback
    all_stocks = []
    for stocks in SECTOR_REP.values():
        all_stocks.extend(stocks)
    extra = ["RELIANCE.NS","TCS.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS","SBIN.NS",
             "KOTAKBANK.NS","AXISBANK.NS","BAJFINANCE.NS","MARUTI.NS","ASIANPAINT.NS",
             "TITAN.NS","SUNPHARMA.NS","NESTLEIND.NS","ULTRACEMCO.NS","WIPRO.NS",
             "ADANIENT.NS","ADANIPORTS.NS","HINDALCO.NS","TATASTEEL.NS","JSWSTEEL.NS",
             "TATAMOTORS.NS","BAJAJ-AUTO.NS","HEROMOTOCO.NS","TATACONSUM.NS",
             "BPCL.NS","IOC.NS","ONGC.NS","COALINDIA.NS","POWERGRID.NS",
             "NTPC.NS","SBILIFE.NS","HDFCLIFE.NS","ICICIPRULI.NS","PIDILITIND.NS",
             "ZOMATO.NS","IRCTC.NS","IRFC.NS","RVNL.NS","HUDCO.NS","PFC.NS","RECLTD.NS",
             "SAIL.NS","NMDC.NS","VEDL.NS","AMBUJACEM.NS","ACC.NS","SHREECEM.NS",
             "BHEL.NS","HAL.NS","BEL.NS","BEML.NS","MAZAGON.NS","DIXON.NS","AMBER.NS",
             "VOLTAS.NS","HAVELLS.NS","POLYCAB.NS","PERSISTENT.NS","MPHASIS.NS",
             "LTIM.NS","COFORGE.NS","KPITTECH.NS","DEEPAKNTR.NS","ATUL.NS","TATACHEM.NS",
             "DLF.NS","GODREJPROP.NS","PRESTIGE.NS","BRIGADE.NS","BAJAJFINSV.NS",
             "MUTHOOTFIN.NS","MANAPPURAM.NS","CHOLAFIN.NS","SHRIRAMFIN.NS",
             "BLS.NS","ENGINERSIN.NS","JIOFIN.NS","PARADEEP.NS","SUZLON.NS",
             "SYNGENE.NS","VMM.NS","APOLLOHOSP.NS","DIVISLAB.NS","EICHERMOT.NS",
             "TORNTPHARM.NS","AUROPHARMA.NS","ALKEM.NS","LUPIN.NS","MANKIND.NS",
             "CANBK.NS","BANKBARODA.NS","PNB.NS","UNIONBANK.NS","IDFCFIRSTB.NS",
             "RBLBANK.NS","BANDHANBNK.NS","FEDERALBNK.NS","INDUSINDBK.NS",
             "ABCAPITAL.NS","EMCURE.NS","AVALON.NS","GODREJPROP.NS","CONCOR.NS",
             "RAYMOND.NS","SENCO.NS","NAVINFLUOR.NS","RVNL.NS","CLEAN.NS",
             "DEEPAKNTR.NS","CESC.NS","INOXWIND.NS","JSWENERGY.NS","SJVN.NS","NHPC.NS",
             "TATAPOWER.NS","ADANIGREEN.NS","WAAREEENER.NS","SJVN.NS","IEX.NS",
             "NUVAMA.NS","360ONE.NS","ANGELONE.NS","CDSL.NS","BSE.NS","MCX.NS",]
    return list(set(all_stocks + extra))

# ── Nifty Options ─────────────────────────────────────────────
def nifty_options_rec(level, rsi, direction):
    lot = 75
    if direction in ["BULLISH","NEUTRAL"]: otype="CALL (CE)"; mult=1.005
    else: otype="PUT (PE)"; mult=0.995
    strike = round(level*mult/50)*50
    prem_low = round(level*0.008); prem_high = round(level*0.010)
    return {"type":otype,"strike":strike,"expiry":"Current weekly" if rsi>58 else "Current monthly",
            "prem_low":prem_low,"prem_high":prem_high,
            "target":round(prem_low*2),"sl":round(prem_low*0.5),
            "lot":lot,"capital":prem_low*lot}

# ══════════════════════════════════════════════════════════════
# MORNING SCANNER
# ══════════════════════════════════════════════════════════════
def run_morning_scan():
    print(f"\n{'='*60}\nMORNING SCAN — {ist_str()}\n{'='*60}")
    today = today_str(); now = ist_str('%I:%M %p IST')

    send_telegram(f"⏳ <b>Morning Scan Starting...</b>\n{today} {now}\nScanning 2000+ NSE stocks. Full report coming in ~25 mins.")

    sector_signals = get_sector_momentum()
    global_data = get_global_markets()
    fii_dii = get_fii_dii()
    news = get_news()
    nifty = analyze_index("^NSEI","Nifty 50")
    banknifty = analyze_index("^NSEBANK","Bank Nifty")
    sensex = analyze_index("^BSESN","Sensex")
    nifty_dir = nifty['direction'] if nifty else "NEUTRAL"

    # Portfolio
    portfolio_results = []
    for sym in MY_PORTFOLIO:
        r = calculate_signal(sym, sector_signals, nifty_dir)
        if r: portfolio_results.append(r)
        time.sleep(0.5)

    # Full scan
    nse_syms = get_nse_symbols()
    print(f"Scanning {len(nse_syms)} stocks...")
    all_results = []
    for i, sym in enumerate(nse_syms):
        r = calculate_signal(sym, sector_signals, nifty_dir)
        if r: all_results.append(r)
        if (i+1) % 500 == 0:
            print(f"  Progress: {i+1}/{len(nse_syms)} | Valid: {len(all_results)}")
        time.sleep(0.25)

    # Rank — only stocks with 7%+ target gap
    def good_target(r): return r['target_gap'] >= 7.0
    strong = sorted([r for r in all_results if r['signal']=="STRONG BUY" and good_target(r)],
                    key=lambda x:(x['efficiency'],x['buy_score']), reverse=True)
    buys = sorted([r for r in all_results if r['signal']=="BUY" and good_target(r)],
                  key=lambda x:(x['efficiency'],x['buy_score']), reverse=True)
    top20 = (strong+buys)[:20]
    total = len(all_results)

    # Build messages
    tg_msg = build_morning_tg(today, now, global_data, fii_dii, news, nifty,
                               banknifty, sector_signals, portfolio_results, top20, total)
    email_body = build_morning_email(today, now, global_data, fii_dii, news, nifty,
                                      banknifty, sensex, sector_signals, portfolio_results, top20, total)

    # Save CSV
    csv_file = f"/tmp/scan_{now_ist().strftime('%Y%m%d')}.csv"
    if all_results:
        pd.DataFrame(all_results).to_csv(csv_file, index=False)

    send_telegram(tg_msg)
    top_pick = top20[0]['symbol'] if top20 else 'N/A'
    mood = nifty['mood'] if nifty else 'NEUTRAL'
    send_email(f"📈 Morning Scan {today} | {mood} | Top: {top_pick} | {total} scanned",
               email_body, csv_file)
    print("✅ Morning scan complete!")

def build_morning_tg(today, now, gdata, fii_dii, news, nifty, bnifty,
                      sectors, portfolio, top20, total):
    def fmt(d, inv=False):
        if not d or not d.get('price',0): return "N/A"
        c = d['change_pct'] * (-1 if inv else 1)
        e = "🟢" if c>0 else "🔴" if c<0 else "🟡"
        return f"{d['price']:,.2f} ({c:+.2f}%) {e}"

    fii = fii_dii.get('fii_net'); dii = fii_dii.get('dii_net')
    fii_txt = f"₹{abs(fii):,.0f}Cr {'BOUGHT 🟢' if fii>0 else 'SOLD 🔴'}" if fii is not None else "Unavailable"
    dii_txt = f"₹{abs(dii):,.0f}Cr {'BOUGHT 🟢' if dii>0 else 'SOLD 🔴'}" if dii is not None else "Unavailable"

    nifty_txt = f"{nifty['level']:,.0f} ({nifty['change_pct']:+.2f}%) | RSI {nifty['rsi']} | {nifty['mood']}" if nifty else "N/A"
    bn_txt = f"{bnifty['level']:,.0f} ({bnifty['change_pct']:+.2f}%) | RSI {bnifty['rsi']} | {bnifty['mood']}" if bnifty else "N/A"

    news_txt = "".join(f"• <b>{n['stock']}</b>: {n['headline'][:65]}... {n['sentiment']}\n" for n in news[:4])
    port_txt = "".join(f"{'🟢' if 'BUY' in r['signal'] else '🔴' if 'SELL' in r['signal'] else '🟡'} "
                       f"<b>{r['symbol']}</b> ₹{r['price']} | {r['signal']} | RSI:{r['rsi']} | {r['efficiency']}/5"
                       f"{'✅F&O' if r['is_fno'] else ''}\n" for r in portfolio)
    top_txt = ""
    for i,r in enumerate(top20[:5],1):
        top_txt += f"{i}. <b>{r['symbol']}</b> ₹{r['price']} | {r['signal']} | {r['efficiency']}/5 | RSI:{r['rsi']}\n"
        top_txt += f"   Entry ₹{r['entry']} → Target ₹{r['target']} (+{r['target_gap']:.1f}%) | SL ₹{r['sl']}\n"
        if r['options']:
            o = r['options']
            top_txt += f"   🎯 CE: {r['symbol']} {o['strike']} | Prem ₹{o['prem_low']}-{o['prem_high']} | Cap ₹{o['cap_low']:,}\n"

    sec_txt = "".join(f"{'🟢' if 'BULL' in m else '🔴' if 'BEAR' in m else '🟡'} {s}: {m}\n"
                      for s,m in sectors.items())

    opt_txt = ""
    if nifty:
        o = nifty_options_rec(nifty['level'], nifty['rsi'], nifty['direction'])
        opt_txt = f"\n🎯 <b>NIFTY {o['type']}</b>: Strike {o['strike']} | Prem ₹{o['prem_low']}-{o['prem_high']} | Target ₹{o['target']} | SL ₹{o['sl']} | Capital ₹{o['capital']:,}\n"

    return f"""📈 <b>MORNING SCAN — {today} {now}</b>
{total} stocks scanned

━━━━━━━━━━━━━━━━━━━━
🌍 <b>GLOBAL MARKETS</b>
🇺🇸 Dow: {fmt(gdata.get('US_DOW'))} | Nasdaq: {fmt(gdata.get('US_NASDAQ'))}
🛢️ Crude: {fmt(gdata.get('CRUDE_OIL'))} | 💵 USD/INR: {fmt(gdata.get('USD_INR'),True)}
😨 VIX: {fmt(gdata.get('VIX'))} | 🥇 Gold: {fmt(gdata.get('GOLD'))}

━━━━━━━━━━━━━━━━━━━━
💰 <b>FII/DII TODAY</b>
FII: {fii_txt}
DII: {dii_txt}

━━━━━━━━━━━━━━━━━━━━
📰 <b>NEWS</b>
{news_txt}
━━━━━━━━━━━━━━━━━━━━
📊 <b>INDICES</b>
Nifty 50   : {nifty_txt}
Bank Nifty : {bn_txt}
{opt_txt}
━━━━━━━━━━━━━━━━━━━━
🗺️ <b>SECTORS</b>
{sec_txt}
━━━━━━━━━━━━━━━━━━━━
💼 <b>YOUR PORTFOLIO</b>
{port_txt}
━━━━━━━━━━━━━━━━━━━━
🏆 <b>TOP 5 OPPORTUNITIES</b>
{top_txt}
📧 Full report (Top 20 + details) sent to Gmail
⚠️ Verify prices in Zerodha before trading"""

def build_morning_email(today, now, gdata, fii_dii, news, nifty, bnifty, sensex,
                         sectors, portfolio, top20, total):
    # Global section
    g_rows = ""
    items = [("🇺🇸 US Dow","US_DOW","US market overnight — green = India opens positive"),
             ("🇺🇸 US Nasdaq","US_NASDAQ","Tech stocks — affects Indian IT sector"),
             ("🛢️ Crude Oil","CRUDE_OIL","Rising oil = bad for aviation, paints, tyres"),
             ("💵 USD/INR","USD_INR","Rupee weakening = FII may exit"),
             ("😨 VIX","VIX","Below 15 = calm. Above 25 = panic"),
             ("🥇 Gold","GOLD","Rising gold = investors seeking safety")]
    pos=0; neg=0
    for label,key,meaning in items:
        d = gdata.get(key,{})
        p = d.get('price',0); c = d.get('change_pct',0)
        if not p or math.isnan(p):
            g_rows += f"<tr><td><b>{label}</b></td><td colspan='2' style='color:#888'>Fetching...</td><td style='font-size:12px'>{meaning}</td></tr>"
            continue
        col = "#27ae60" if c>0 else "#e74c3c"
        arr = "▲" if c>0 else "▼"
        if key in ["US_DOW","US_NASDAQ"]:
            if c>0: pos+=1
            else: neg+=1
        g_rows += f"<tr><td><b>{label}</b></td><td>{p:,.2f}</td><td style='color:{col}'><b>{arr} {abs(c):.2f}%</b></td><td style='font-size:12px;color:#666'>{meaning}</td></tr>"
    verdict = "POSITIVE 🟢 — Good day for fresh entries" if pos>=2 else "CAUTIOUS 🔴 — Global weakness" if neg>=2 else "MIXED 🟡 — Watch first 30 mins"

    # FII section
    fii=fii_dii.get('fii_net'); dii=fii_dii.get('dii_net')
    fa = fii is not None
    fc = "#27ae60" if fa and fii>0 else "#e74c3c"
    dc = "#27ae60" if fa and dii and dii>0 else "#e74c3c"
    net = (fii or 0)+(dii or 0)

    # News
    n_rows = "".join(f"<tr><td><b>{n['stock']}</b></td><td>{n['headline']}</td>"
                     f"<td style='color:{'#27ae60' if 'POS' in n['sentiment'] else '#e74c3c' if 'NEG' in n['sentiment'] else '#f39c12'}'>{n['sentiment']}</td></tr>"
                     for n in news) or "<tr><td colspan='3'>No major news today</td></tr>"

    # Index rows
    i_rows = ""
    for idx in [nifty, bnifty, sensex]:
        if not idx: continue
        mc=mood_color(idx['mood']); cc="#27ae60" if idx['change_pct']>0 else "#e74c3c"
        rn = "Oversold ✅" if idx['rsi']<40 else "Overbought ⚠️" if idx['rsi']>70 else "Healthy ✅"
        i_rows += f"<tr><td><b>{idx['name']}</b></td><td><b>{idx['level']:,.2f}</b></td><td style='color:{cc}'>{idx['change_pct']:+.2f}%</td><td>{idx['rsi']} {rn}</td><td>{idx['trend']}</td><td>{idx['macd']}</td><td>₹{idx['support']:,.0f}</td><td>₹{idx['resistance']:,.0f}</td><td style='color:{mc}'><b>{idx['mood']}</b></td></tr>"

    # Options
    opt_html = ""
    if nifty:
        o = nifty_options_rec(nifty['level'],nifty['rsi'],nifty['direction'])
        why = "Nifty bullish — CALL profits when Nifty rises" if "CALL" in o['type'] else "Nifty bearish — PUT profits when Nifty falls"
        opt_html = f"""<div style='background:#eaf4fb;padding:15px;border-radius:8px;border-left:4px solid #3498db'>
        <h4>🎯 NIFTY {o['type']} — BUY</h4>
        <p>Strike: <b>{o['strike']}</b> | Expiry: {o['expiry']} | Premium: ₹{o['prem_low']}–{o['prem_high']} | Target: ₹{o['target']} | SL: ₹{o['sl']} | Capital: ₹{o['capital']:,} (1 lot = {o['lot']} shares)</p>
        <p style='font-size:13px'>{why}. Max loss = ₹{o['capital']:,}. ⚠️ Verify actual premium in Zerodha before buying.</p></div>"""

    # Sector
    s_rows = "".join(f"<tr><td><b>{s}</b></td><td style='color:{mood_color(m)}'>{m}</td></tr>" for s,m in sectors.items())

    # Portfolio
    p_rows = ""
    for r in portfolio:
        sc=sig_color(r['signal']); dc2="#27ae60" if r['day_chg']>0 else "#e74c3c"
        stars="⭐"*r['efficiency']
        if r['rsi']>75: note="⚠️ Overbought — consider booking partial profits"
        elif r['rsi']<40: note="✅ Oversold — good to add more"
        elif "BUY" in r['signal'] and r['efficiency']>=4: note="✅ Strong — hold/add"
        elif "SELL" in r['signal']: note="🔴 Review — consider reducing"
        else: note="🟡 Hold — no action needed"
        fno_badge = "<span style='background:#27ae60;color:white;padding:1px 5px;border-radius:3px;font-size:11px'>F&O</span>" if r['is_fno'] else ""
        # Position sizing
        sl_dist = r['price'] - r['sl']
        max_shares = int((200000*0.02)/sl_dist) if sl_dist>0 else 0
        p_rows += f"""<tr>
            <td><b>{r['symbol']}</b> {fno_badge}</td><td>₹{r['price']}</td>
            <td style='color:{dc2}'>{r['day_chg']:+.2f}%</td>
            <td style='color:{sc}'><b>{r['signal']}</b></td>
            <td>{r['rsi']}</td><td>{r['trend']}</td><td>{r['vol_surge']}</td>
            <td>{r['efficiency']}/5 {stars}</td>
            <td>Entry ₹{r['entry']} | T ₹{r['target']} | SL ₹{r['sl']}</td>
            <td style='font-size:11px'>{note}</td></tr>"""
        if r['options']:
            o=r['options']
            p_rows += f"""<tr style='background:#f0faf0'><td colspan='10' style='font-size:12px;padding:5px 10px'>
            🎯 Options: {r['symbol']} {o['strike']} CE ({o['expiry']}) | Prem ₹{o['prem_low']}–{o['prem_high']} | Target ₹{o['tgt_prem']} | SL ₹{o['sl_prem']} | Capital ₹{o['cap_low']:,}–₹{o['cap_high']:,}</td></tr>"""

    # Top 20
    t_rows = ""
    for i,r in enumerate(top20,1):
        sc=sig_color(r['signal']); stars="⭐"*r['efficiency']
        fno_badge = "<span style='background:#27ae60;color:white;padding:1px 5px;border-radius:3px;font-size:11px'>F&O</span>" if r['is_fno'] else ""
        sl_dist = r['price']-r['sl']
        max_shares = int((200000*0.02)/sl_dist) if sl_dist>0 else 0
        t_rows += f"""<tr>
            <td>{i}</td><td><b>{r['symbol']}</b> {fno_badge}</td><td>₹{r['price']}</td>
            <td style='color:{sc}'><b>{r['signal']}</b></td>
            <td>{r['efficiency']}/5 {stars}</td><td>{r['rsi']}</td><td>{r['sector']}</td>
            <td>Entry ₹{r['entry']}<br>Target ₹{r['target']} (+{r['target_gap']:.1f}%)<br>SL ₹{r['sl']}</td>
            <td style='font-size:11px'>{max_shares} shares @ ₹{r['price']} = ₹{max_shares*r['price']:,.0f}<br>(2% risk rule)</td>
        </tr>
        <tr style='background:#f8f9fa'><td colspan='9' style='font-size:12px;padding:4px 10px;color:#555'>{"<br>".join(r['details'])}</td></tr>"""
        if r['options']:
            o=r['options']
            t_rows += f"""<tr style='background:#f0faf0'><td colspan='9' style='font-size:12px;padding:5px 10px'>
            🎯 <b>OPTIONS ROUTE:</b> {r['symbol']} {o['strike']} CE ({o['expiry']}) | Buy premium ₹{o['prem_low']}–{o['prem_high']} | Target ₹{o['tgt_prem']} (+120%) | SL ₹{o['sl_prem']} | Capital ₹{o['cap_low']:,}–₹{o['cap_high']:,}</td></tr>"""

    nifty_mood = nifty['mood'] if nifty else "NEUTRAL 🟡"
    return f"""<html><body style='font-family:Arial,sans-serif;max-width:1000px;margin:auto;padding:20px'>
{html_header('📈 NSE Morning Scanner v4.0', f'{today} | {now} | {total} stocks scanned | Prices: Yesterday 3:30 PM NSE Close')}
<div style='background:#eaf4fb;padding:12px;border-radius:8px;border-left:4px solid {mood_color(nifty_mood)};margin-bottom:20px'>
<b>Market Mood: {nifty_mood} | Opening Verdict: {verdict}</b><br>
<small>Strong Buy: {len([r for r in top20 if r['signal']=='STRONG BUY'])} | Buy: {len([r for r in top20 if r['signal']=='BUY'])} | Total scanned: {total}</small></div>

<h2 style='border-bottom:2px solid #3498db;padding-bottom:5px'>🌍 Global Markets</h2>
{tip("US markets, oil, currency — all affect Indian market opening today.")}
{tbl(["Market","Level","Change","What it means for you"])}
{g_rows}</table>
<div style='background:#e8f8f5;padding:8px;border-radius:6px;margin:8px 0'><b>Opening Verdict: {verdict}</b></div>

<h2 style='border-bottom:2px solid #3498db;padding-bottom:5px;margin-top:20px'>💰 FII/DII Activity</h2>
{tip("FII = foreign funds. DII = Indian mutual funds. Both buying = very bullish.")}
<table border='1' cellpadding='8' style='border-collapse:collapse;font-size:13px'>
<tr style='background:#2c3e50;color:white'><th>Type</th><th>Activity</th><th>Amount</th><th>Impact</th></tr>
<tr><td><b>FII</b></td><td style='color:{fc}'><b>{"BUYING" if fa and fii>0 else "SELLING" if fa else "Unavailable"}</b></td>
<td>{"₹"+f"{abs(fii):,.0f} Cr" if fa else "N/A"}</td>
<td>{"Bullish 🟢" if fa and fii>0 else "Cautious 🔴" if fa else "Check NSE manually"}</td></tr>
<tr><td><b>DII</b></td><td style='color:{dc}'><b>{"BUYING" if fa and dii and dii>0 else "SELLING" if fa else "Unavailable"}</b></td>
<td>{"₹"+f"{abs(dii):,.0f} Cr" if fa and dii else "N/A"}</td>
<td>{"Supporting market 🟢" if fa and dii and dii>0 else ""}</td></tr>
</table>
{"<p><b>Net flow: ₹"+f"{net:+,.0f} Cr — "+("Money flowing IN 🟢" if net>0 else "Money flowing OUT 🔴")+"</b></p>" if fa else ""}

<h2 style='border-bottom:2px solid #3498db;padding-bottom:5px;margin-top:20px'>📰 News Alerts</h2>
{tbl(["Stock","Headline","Sentiment"])}{n_rows}</table>

<h2 style='border-bottom:2px solid #3498db;padding-bottom:5px;margin-top:20px'>📊 Index Dashboard</h2>
{tbl(["Index","Level","Change","RSI","Trend","MACD","Support","Resistance","Mood"])}{i_rows}</table>

<h2 style='border-bottom:2px solid #3498db;padding-bottom:5px;margin-top:20px'>🗺️ Sector Momentum</h2>
<table border='1' cellpadding='6' style='border-collapse:collapse;font-size:13px'>
<tr style='background:#2c3e50;color:white'><th>Sector</th><th>Momentum</th></tr>{s_rows}</table>

<h2 style='border-bottom:2px solid #3498db;padding-bottom:5px;margin-top:20px'>🎯 Nifty Options</h2>
{opt_html}

<h2 style='border-bottom:2px solid #3498db;padding-bottom:5px;margin-top:20px'>💼 Your Portfolio</h2>
{tip("Fresh signals for your 9 holdings. Stars = how many indicators aligned. Options route shown for F&O stocks.")}
{tbl(["Stock","Price","Change","Signal","RSI","Trend","Volume","Efficiency","Entry/Target/SL","Action today"])}
{p_rows}</table>

<h2 style='border-bottom:2px solid #3498db;padding-bottom:5px;margin-top:20px'>🏆 Top 20 Opportunities</h2>
{tip(f"Best setups from {total} NSE stocks. Price>₹50, Volume>50K/day, Target gap>7%. Position size based on ₹2L capital, 2% risk rule.")}
{tbl(["#","Stock","Price","Signal","Efficiency","RSI","Sector","Entry/Target/SL","Position Size"])}{t_rows}</table>

<p style='color:#888;font-size:12px;margin-top:20px;border-top:1px solid #eee;padding-top:10px'>
⚠️ Technical signals only. Verify prices in Zerodha before trading.<br>
All prices = NSE official closing prices from previous trading day.<br>
Options premiums are estimates — verify in Zerodha Options Chain.</p>
</body></html>"""

# ══════════════════════════════════════════════════════════════
# MIDDAY UPDATE
# ══════════════════════════════════════════════════════════════
def run_midday_update():
    print(f"\n{'='*60}\nMIDDAY UPDATE — {ist_str()}\n{'='*60}")
    today = today_str(); now = ist_str('%I:%M %p IST')

    nifty = analyze_index("^NSEI","Nifty 50")
    banknifty = analyze_index("^NSEBANK","Bank Nifty")
    fii_dii = get_fii_dii()
    news = get_news()
    sector_signals = get_sector_momentum()
    nifty_dir = nifty['direction'] if nifty else "NEUTRAL"

    sheet = setup_sheets()
    trades_data = get_open_trades_with_pnl(sheet, nifty_dir)
    total_pnl = sum(t['pnl'] for t in trades_data)
    total_pnl_pct = 0
    if trades_data:
        inv = sum(t['entry']*t['qty'] for t in trades_data)
        cur = sum(t['current']*t['qty'] for t in trades_data)
        total_pnl_pct = ((cur-inv)/inv*100) if inv>0 else 0

    # Quick scan for new signals
    new_signals = []
    scan_list = list(MY_PORTFOLIO)
    for sector, mood in sector_signals.items():
        if "BULLISH" in mood:
            scan_list.extend(SECTOR_REP.get(sector,[])[:3])
    for sym in list(set(scan_list))[:50]:
        r = calculate_signal(sym, sector_signals, nifty_dir)
        if r and "BUY" in r['signal'] and r['efficiency']>=3:
            new_signals.append(r)
        time.sleep(0.3)
    new_signals.sort(key=lambda x:x['efficiency'], reverse=True)
    top5 = new_signals[:5]

    nifty_txt = f"{nifty['level']:,.0f} ({nifty['change_pct']:+.2f}%) | {nifty['mood']}" if nifty else "N/A"
    bn_txt = f"{banknifty['level']:,.0f} ({banknifty['change_pct']:+.2f}%) | {banknifty['mood']}" if banknifty else "N/A"
    fii = fii_dii.get('fii_net')
    fii_txt = f"₹{abs(fii):,.0f}Cr {'BUYING 🟢' if fii>0 else 'SELLING 🔴'}" if fii is not None else "Updating..."

    trades_tg = ""
    for t in trades_data:
        e="🟢" if t['pnl']>=0 else "🔴"
        trades_tg += f"{e} <b>{t['symbol']}</b>: Entry ₹{t['entry']} → Now ₹{t['current']} ({t['day_chg']:+.1f}%)\nP&L: ₹{t['pnl']:+,.0f} ({t['pnl_pct']:+.1f}%) | {t['action']}\n\n"
    if not trades_tg: trades_tg = "No open trades. Use /buy STOCK PRICE QTY to record.\n"

    new_txt = "".join(f"{i}. <b>{r['symbol']}</b> ₹{r['price']} | {r['signal']} | RSI:{r['rsi']}\n   Entry ₹{r['entry']} → Target ₹{r['target']} | SL ₹{r['sl']}\n"
                      for i,r in enumerate(top5,1)) or "No new signals since morning\n"
    news_txt = "".join(f"• <b>{n['stock']}</b>: {n['headline'][:65]}... {n['sentiment']}\n" for n in news[:4])
    sec_txt = "".join(f"{'🟢' if 'BULL' in m else '🔴' if 'BEAR' in m else '🟡'} {s}: {m}\n" for s,m in sector_signals.items())

    tg_msg = f"""☀️ <b>MIDDAY UPDATE — {today} {now}</b>

━━━━━━━━━━━━━━━━━━━━
📊 <b>MARKET MID-SESSION</b>
Nifty 50   : {nifty_txt}
Bank Nifty : {bn_txt}
FII Today  : {fii_txt}

━━━━━━━━━━━━━━━━━━━━
📰 <b>NEWS SINCE MORNING</b>
{news_txt}
━━━━━━━━━━━━━━━━━━━━
🗺️ <b>SECTOR MOMENTUM</b>
{sec_txt}
━━━━━━━━━━━━━━━━━━━━
💼 <b>YOUR TRADES MID-SESSION</b>
{trades_tg}
{'🟢' if total_pnl>=0 else '🔴'} <b>Total P&L: ₹{total_pnl:+,.0f} ({total_pnl_pct:+.1f}%)</b>

━━━━━━━━━━━━━━━━━━━━
🔔 <b>NEW SIGNALS SINCE 8 AM</b>
{new_txt}
📧 Full report sent to Gmail"""

    # Email
    tr_rows = ""
    for t in trades_data:
        pc="#27ae60" if t['pnl']>=0 else "#e74c3c"
        dc="#27ae60" if t['day_chg']>=0 else "#e74c3c"
        ac={"red":"#e74c3c","green":"#27ae60","orange":"#f39c12","blue":"#3498db"}.get(t.get('color','blue'),"#333")
        pct_to_target = min(100, max(0, ((t['current']-t['entry'])/(t['target']-t['entry'])*100))) if t['target']!=t['entry'] else 0
        tr_rows += f"""<tr>
            <td><b>{t['symbol']}</b><br><small>Day {t['days']}</small></td>
            <td>₹{t['entry']}</td><td>₹{t['current']}</td>
            <td style='color:{dc}'>{t['day_chg']:+.2f}%</td>
            <td style='color:{pc}'><b>₹{t['pnl']:+,.0f} ({t['pnl_pct']:+.1f}%)</b></td>
            <td>{t['rsi']}</td>
            <td>T:₹{t['target']} | SL:₹{t['sl']}</td>
            <td><div style='background:#eee;border-radius:3px;height:8px'><div style='background:#27ae60;width:{pct_to_target:.0f}%;height:8px;border-radius:3px'></div></div>{pct_to_target:.0f}% to target</td>
            <td style='color:{ac};font-size:12px'><b>{t['action']}</b><br>{t['reason'][:80]}</td></tr>"""
    if not tr_rows: tr_rows = "<tr><td colspan='9' style='color:#888'>No open trades. Use /buy STOCK PRICE QTY in Telegram.</td></tr>"

    new_rows = "".join(f"""<tr><td>{i}</td><td><b>{r['symbol']}</b></td><td>₹{r['price']}</td>
        <td style='color:{sig_color(r["signal"])}'><b>{r['signal']}</b></td>
        <td>{"⭐"*r['efficiency']} {r['efficiency']}/5</td><td>{r['rsi']}</td>
        <td>₹{r['entry']} | ₹{r['target']} | ₹{r['sl']}</td></tr>"""
        for i,r in enumerate(top5,1)) or "<tr><td colspan='7'>No new signals since morning</td></tr>"

    i_rows = ""
    for idx in [nifty, banknifty]:
        if not idx: continue
        mc=mood_color(idx['mood']); cc="#27ae60" if idx['change_pct']>0 else "#e74c3c"
        i_rows += f"<tr><td><b>{idx['name']}</b></td><td><b>{idx['level']:,.2f}</b></td><td style='color:{cc}'>{idx['change_pct']:+.2f}%</td><td>{idx['rsi']}</td><td>{idx['trend']}</td><td style='color:{mc}'>{idx['mood']}</td></tr>"

    email_body = f"""<html><body style='font-family:Arial,sans-serif;max-width:1000px;margin:auto;padding:20px'>
{html_header('☀️ Midday Market Update v4.0', f'{today} | {now} | Prices: Live (15 min delayed)', '#1a5276', '#2980b9')}
<h2 style='border-bottom:2px solid #2980b9;padding-bottom:5px'>📊 Market Mid-Session</h2>
{tbl(["Index","Level","Change","RSI","Trend","Mood"])}{i_rows}</table>
<p><b>FII Today: {fii_txt}</b></p>
<h2 style='border-bottom:2px solid #2980b9;padding-bottom:5px;margin-top:20px'>📰 News Since Morning</h2>
{tbl(["Stock","Headline","Sentiment"])}{"".join(f"<tr><td><b>{n['stock']}</b></td><td>{n['headline']}</td><td>{'🟢' if 'POS' in n['sentiment'] else '🔴' if 'NEG' in n['sentiment'] else '🟡'} {n['sentiment']}</td></tr>" for n in news)}</table>
<h2 style='border-bottom:2px solid #2980b9;padding-bottom:5px;margin-top:20px'>💼 Your Open Trades</h2>
<div style='background:{"#eafaf1" if total_pnl>=0 else "#fdf2f2"};padding:12px;border-radius:8px;border-left:4px solid {"#27ae60" if total_pnl>=0 else "#e74c3c"};margin-bottom:15px'>
<b>Total P&L: ₹{total_pnl:+,.0f} ({total_pnl_pct:+.1f}%)</b></div>
{tbl(["Stock","Entry","Current","Day Chg","P&L","RSI","Target|SL","Progress","Action"])}{tr_rows}</table>
<h2 style='border-bottom:2px solid #2980b9;padding-bottom:5px;margin-top:20px'>🔔 New Signals Since 8 AM</h2>
{tbl(["#","Stock","Price","Signal","Efficiency","RSI","Entry/Target/SL"])}{new_rows}</table>
<p style='color:#888;font-size:12px;margin-top:15px'>⚠️ Prices 15 min delayed. Verify in Zerodha before acting.</p>
</body></html>"""

    send_telegram(tg_msg)
    send_email(f"☀️ Midday Update {today} | {nifty['mood'] if nifty else 'N/A'} | P&L: ₹{total_pnl:+,.0f}", email_body)
    print("✅ Midday update complete!")

# ══════════════════════════════════════════════════════════════
# EVENING UPDATE
# ══════════════════════════════════════════════════════════════
def get_open_trades_with_pnl(sheet, nifty_dir="NEUTRAL"):
    if not sheet: return []
    try:
        ws = sheet.worksheet("Open Trades")
        records = ws.get_all_records()
        trades = []
        for t in records:
            sym = t.get('Stock',''); entry = float(t.get('Entry Price',0))
            qty = int(t.get('Qty',0))
            if not sym or not entry or not qty: continue
            try:
                df = yf.download(sym+".NS", period="5d", interval="1d", progress=False, auto_adjust=True)
                if df.empty or len(df)<2: continue
                curr = float(df['Close'].iloc[-1]); prev = float(df['Close'].iloc[-2])
                if math.isnan(curr): continue
                rsi = float(ta.momentum.RSIIndicator(df['Close'].squeeze()).rsi().iloc[-1])
                high = float(df['High'].iloc[-1]); low = float(df['Low'].iloc[-1])
                day_chg = ((curr-prev)/prev)*100
            except: continue
            try:
                ed = datetime.strptime(t.get('Entry Date',''), '%d %b %Y')
                days = (now_ist().replace(tzinfo=None)-ed).days
            except: days = int(t.get('Days Held',0))
            pnl = (curr-entry)*qty; pnl_pct = ((curr-entry)/entry)*100
            target = float(t.get('Target',entry*1.1)); sl = float(t.get('Stop Loss',entry*0.97))

            # Smart exit logic
            if curr <= sl or low <= sl:
                action="🛑 EXIT NOW"; reason=f"Stop loss hit at ₹{sl:.2f}. Exit to protect capital."; color="red"
            elif curr >= target or high >= target:
                action="🎯 BOOK PROFITS"; reason=f"Target ₹{target:.2f} hit! Book 75% now, hold 25% with trailing SL."; color="green"
            elif rsi > 78:
                action="⚠️ PARTIAL EXIT"; reason=f"RSI {rsi:.0f} overbought. Book 50% at ₹{curr:.2f}."; color="orange"
            elif pnl_pct > 8:
                action="✅ TRAIL SL"; reason=f"Good profit {pnl_pct:.1f}%. Move SL to entry ₹{entry:.2f}."; color="green"
            elif curr <= sl*1.03:
                action="⚠️ NEAR SL"; reason=f"Only {((curr-sl)/sl*100):.1f}% above SL. Watch closely."; color="orange"
            else:
                action="✅ HOLD"; reason=f"P&L {pnl_pct:+.1f}%. Target ₹{target:.2f} | SL ₹{sl:.2f}."; color="blue"

            trades.append({"symbol":sym,"entry":entry,"qty":qty,"current":round(curr,2),
                           "day_chg":round(day_chg,2),"high":round(high,2),"low":round(low,2),
                           "rsi":round(rsi,1),"pnl":round(pnl,2),"pnl_pct":round(pnl_pct,2),
                           "days":days,"target":target,"sl":sl,"action":action,"reason":reason,"color":color})
            time.sleep(0.5)
        return trades
    except Exception as e:
        print(f"Trades error: {e}"); return []

def run_evening_update():
    print(f"\n{'='*60}\nEVENING UPDATE — {ist_str()}\n{'='*60}")
    today = today_str(); now = ist_str('%I:%M %p IST')

    nifty = analyze_index("^NSEI","Nifty 50")
    banknifty = analyze_index("^NSEBANK","Bank Nifty")
    sensex = analyze_index("^BSESN","Sensex")
    fii_dii = get_fii_dii()
    news = get_news()
    sector_signals = get_sector_momentum()
    nifty_dir = nifty['direction'] if nifty else "NEUTRAL"

    sheet = setup_sheets()
    trades = get_open_trades_with_pnl(sheet, nifty_dir)
    total_invested = sum(t['entry']*t['qty'] for t in trades)
    total_current = sum(t['current']*t['qty'] for t in trades)
    total_pnl = total_current - total_invested
    total_pnl_pct = ((total_current-total_invested)/total_invested*100) if total_invested>0 else 0

    # Portfolio signals
    portfolio_results = []
    for sym in MY_PORTFOLIO:
        r = calculate_signal(sym, sector_signals, nifty_dir)
        if r: portfolio_results.append(r)
        time.sleep(0.5)

    fii=fii_dii.get('fii_net'); dii=fii_dii.get('dii_net')
    fii_txt = f"₹{abs(fii):,.0f}Cr {'BOUGHT 🟢' if fii>0 else 'SOLD 🔴'}" if fii is not None else "Unavailable"
    dii_txt = f"₹{abs(dii):,.0f}Cr {'BOUGHT 🟢' if dii>0 else 'SOLD 🔴'}" if dii is not None else "Unavailable"
    nifty_txt = f"{nifty['level']:,.0f} ({nifty['change_pct']:+.2f}%) | {nifty['mood']}" if nifty else "N/A"
    bn_txt = f"{banknifty['level']:,.0f} ({banknifty['change_pct']:+.2f}%) | {banknifty['mood']}" if banknifty else "N/A"
    news_txt = "".join(f"• <b>{n['stock']}</b>: {n['headline'][:65]}... {n['sentiment']}\n" for n in news[:4])
    trades_tg = ""
    for t in trades:
        e="🟢" if t['pnl']>=0 else "🔴"
        trades_tg += f"{e} <b>{t['symbol']}</b> (Day {t['days']})\nEntry ₹{t['entry']} → Close ₹{t['current']} | P&L ₹{t['pnl']:+,.0f} ({t['pnl_pct']:+.1f}%)\n{t['action']}: {t['reason'][:80]}\n\n"
    if not trades_tg: trades_tg = "No open trades. Record: /buy STOCK PRICE QTY\n"

    # Tomorrow preview
    preview = []
    for t in trades:
        if t['current']>=t['target']*0.93: preview.append(f"🎯 {t['symbol']} is {((t['target']-t['current'])/t['current']*100):.1f}% from target ₹{t['target']:.2f}")
        if t['current']<=t['sl']*1.04: preview.append(f"⚠️ {t['symbol']} is {((t['current']-t['sl'])/t['sl']*100):.1f}% above SL ₹{t['sl']:.2f} — watch closely")
    for r in portfolio_results:
        if r['rsi']>75: preview.append(f"📊 {r['symbol']} RSI {r['rsi']} — overbought, consider booking partial profits")
    if nifty:
        dist = ((nifty['resistance']-nifty['level'])/nifty['level'])*100
        if dist<1.5: preview.append(f"📊 Nifty only {dist:.1f}% from resistance {nifty['resistance']:,.0f} — may face selling tomorrow")
    preview_txt = "\n".join(f"• {p}" for p in preview[:5]) or "• No urgent alerts — positions safe"

    tg_msg = f"""🌆 <b>EVENING UPDATE — {today} {now}</b>

━━━━━━━━━━━━━━━━━━━━
📊 <b>MARKET CLOSED TODAY</b>
Nifty 50   : {nifty_txt}
Bank Nifty : {bn_txt}

💰 <b>FII/DII FINAL</b>
FII: {fii_txt}
DII: {dii_txt}

━━━━━━━━━━━━━━━━━━━━
📰 <b>NEWS TODAY</b>
{news_txt}
━━━━━━━━━━━━━━━━━━━━
💼 <b>CLOSING P&L</b>
{trades_tg}
{'🟢' if total_pnl>=0 else '🔴'} <b>Total P&L: ₹{total_pnl:+,.0f} ({total_pnl_pct:+.1f}%)</b>

━━━━━━━━━━━━━━━━━━━━
🔮 <b>TOMORROW PREVIEW</b>
{preview_txt}

━━━━━━━━━━━━━━━━━━━━
📋 <b>MORNING CHECKLIST</b>
1. Check 8 AM scan for opportunities
2. Verify stop losses still valid
3. Check global markets before 9:15 AM
4. Use /market for live index levels
📧 Full report sent to Gmail"""

    # Email
    i_rows=""
    for idx in [nifty, banknifty, sensex]:
        if not idx: continue
        mc=mood_color(idx['mood']); cc="#27ae60" if idx['change_pct']>0 else "#e74c3c"
        bias="Positive tomorrow likely" if idx['change_pct']>0.5 else "May open weak tomorrow" if idx['change_pct']<-0.5 else "Flat open expected"
        i_rows+=f"<tr><td><b>{idx['name']}</b></td><td><b>{idx['level']:,.2f}</b></td><td style='color:{cc}'>{idx['change_pct']:+.2f}%</td><td>{idx['rsi']}</td><td>{idx['trend']}</td><td>{idx['macd']}</td><td>₹{idx['support']:,.0f}</td><td>₹{idx['resistance']:,.0f}</td><td style='color:{mc}'>{idx['mood']}</td><td>{bias}</td></tr>"

    p_rows=""
    for r in portfolio_results:
        rn="Overbought ⚠️" if r['rsi']>70 else "Oversold ✅" if r['rsi']<40 else "Healthy ✅"
        p_rows+=f"<tr><td><b>{r['symbol']}</b></td><td>₹{r['price']}</td><td style='color:{sig_color(r['signal'])}'><b>{r['signal']}</b></td><td>{r['rsi']} {rn}</td><td>{r['trend']}</td><td>{'⭐'*r['efficiency']} {r['efficiency']}/5</td></tr>"

    tr_rows=""
    for t in trades:
        pc="#27ae60" if t['pnl']>=0 else "#e74c3c"
        dc="#27ae60" if t['day_chg']>=0 else "#e74c3c"
        ac={"red":"#e74c3c","green":"#27ae60","orange":"#f39c12","blue":"#3498db"}.get(t.get('color','blue'),"#333")
        tr_rows+=f"""<tr><td><b>{t['symbol']}</b><br><small>Day {t['days']}</small></td>
            <td>₹{t['entry']}</td><td>₹{t['current']}</td>
            <td style='color:{dc}'>{t['day_chg']:+.2f}%</td>
            <td>₹{t['high']} / ₹{t['low']}</td>
            <td style='color:{pc}'><b>₹{t['pnl']:+,.0f} ({t['pnl_pct']:+.1f}%)</b></td>
            <td>{t['rsi']}</td><td>₹{t['target']} | ₹{t['sl']}</td>
            <td style='color:{ac};font-size:12px'><b>{t['action']}</b><br>{t['reason'][:100]}</td></tr>"""
    if not tr_rows: tr_rows="<tr><td colspan='9' style='color:#888'>No open trades. Use /buy STOCK PRICE QTY in Telegram.</td></tr>"

    prev_rows="".join(f"<tr><td>{p}</td></tr>" for p in preview) or "<tr><td>✅ No urgent alerts — continue holding</td></tr>"
    n_rows="".join(f"<tr><td><b>{n['stock']}</b></td><td>{n['headline']}</td><td>{'🟢' if 'POS' in n['sentiment'] else '🔴' if 'NEG' in n['sentiment'] else '🟡'} {n['sentiment']}</td></tr>" for n in news)

    email_body = f"""<html><body style='font-family:Arial,sans-serif;max-width:1000px;margin:auto;padding:20px'>
{html_header('🌆 Evening Position Update v4.0', f'{today} | {now} | Prices: Today 3:30 PM NSE Close', '#1a3a4a', '#2ecc71')}
<div style='background:{"#eafaf1" if total_pnl>=0 else "#fdf2f2"};padding:12px;border-radius:8px;border-left:4px solid {"#27ae60" if total_pnl>=0 else "#e74c3c"};margin-bottom:20px'>
<b>Today's P&L: ₹{total_pnl:+,.0f} ({total_pnl_pct:+.1f}%) | Invested: ₹{total_invested:,.0f} | Value: ₹{total_current:,.0f}</b></div>

<h2 style='border-bottom:2px solid #2ecc71;padding-bottom:5px'>📊 How Market Closed Today</h2>
{tbl(["Index","Close","Change","RSI","Trend","MACD","Support","Resistance","Mood","Tomorrow"])}{i_rows}</table>

<h2 style='border-bottom:2px solid #2ecc71;padding-bottom:5px;margin-top:20px'>💰 FII/DII Final</h2>
<table border='1' cellpadding='8' style='border-collapse:collapse;font-size:13px'>
<tr style='background:#2c3e50;color:white'><th>Type</th><th>Activity</th><th>Impact</th></tr>
<tr><td><b>FII</b></td><td style='color:{"#27ae60" if fii and fii>0 else "#e74c3c"}'><b>{fii_txt}</b></td><td>{"Bullish for tomorrow 🟢" if fii and fii>0 else "Cautious for tomorrow 🔴" if fii else "Check NSE website"}</td></tr>
<tr><td><b>DII</b></td><td style='color:{"#27ae60" if dii and dii>0 else "#e74c3c"}'><b>{dii_txt}</b></td><td>{"Supporting market 🟢" if dii and dii>0 else ""}</td></tr>
</table>

<h2 style='border-bottom:2px solid #2ecc71;padding-bottom:5px;margin-top:20px'>📰 News Today</h2>
{tbl(["Stock","Headline","Sentiment"])}{n_rows}</table>

<h2 style='border-bottom:2px solid #2ecc71;padding-bottom:5px;margin-top:20px'>📊 Portfolio Closing Signals</h2>
{tbl(["Stock","Close","Signal","RSI","Trend","Efficiency"])}{p_rows}</table>

<h2 style='border-bottom:2px solid #2ecc71;padding-bottom:5px;margin-top:20px'>💼 Your Trades — Closing P&L</h2>
{tbl(["Stock","Entry","Close","Day Chg","High/Low","P&L","RSI","Target|SL","Action"])}{tr_rows}</table>

<h2 style='border-bottom:2px solid #2ecc71;padding-bottom:5px;margin-top:20px'>🔮 Tomorrow Preview</h2>
<table border='1' cellpadding='8' style='border-collapse:collapse;font-size:13px;width:100%'>{prev_rows}</table>

<div style='background:#f8f9fa;padding:12px;border-radius:8px;margin-top:15px'>
<b>Morning Checklist:</b><br>1. Check 8 AM scan for new opportunities<br>
2. Verify stop losses<br>3. Check global markets before 9:15 AM<br>
4. Use /market in Telegram for live index</div>
<p style='color:#888;font-size:12px;margin-top:15px'>⚠️ All prices = NSE official closing prices for {today}</p>
</body></html>"""

    send_telegram(tg_msg)
    mood = nifty['mood'] if nifty else 'N/A'
    send_email(f"🌆 Evening Update {today} | {mood} | P&L: ₹{total_pnl:+,.0f} ({total_pnl_pct:+.1f}%)", email_body)
    print("✅ Evening update complete!")

# ══════════════════════════════════════════════════════════════
# CONFLUENCE SCANNER
# ══════════════════════════════════════════════════════════════
_confluence_sent_today = set()

def run_confluence_scan():
    global _confluence_sent_today
    today = today_str()
    # Reset daily cache
    if not hasattr(run_confluence_scan, '_last_date') or run_confluence_scan._last_date != today:
        _confluence_sent_today = set()
        run_confluence_scan._last_date = today

    print(f"\n{'='*60}\nCONFLUENCE SCAN — {ist_str()}\n{'='*60}")
    now = ist_str('%I:%M %p IST')

    # Skip if market is closed
    n = now_ist()
    if n.weekday() >= 5 or n.hour < 9 or n.hour >= 16:
        print("Market closed — skipping confluence scan")
        return

    sector_signals = get_sector_momentum()
    nifty = analyze_index("^NSEI","Nifty 50")
    banknifty = analyze_index("^NSEBANK","Bank Nifty")
    fii_dii = get_fii_dii()
    news = get_news()
    nifty_dir = nifty['direction'] if nifty else "NEUTRAL"

    if nifty and nifty['direction']=="BEARISH" and nifty['rsi']>65:
        send_telegram(f"⚠️ <b>Confluence Scanner {now}</b>\nMarket BEARISH — no buy signals generated.\nProtect existing positions.")
        return

    nse_syms = get_nse_symbols()
    results = []
    scanned = 0

    for sym in nse_syms:
        # Skip if already sent today
        sym_clean = sym.replace('.NS','')
        if sym_clean in _confluence_sent_today:
            continue

        score, details, data = score_confluence(sym, sector_signals, nifty, banknifty, fii_dii, news)
        if score >= 14:
            entry_data = calculate_signal(sym, sector_signals, nifty_dir)
            if entry_data:
                results.append({**entry_data, "conf_score": score, "conf_details": details, "conf_data": data})
        scanned += 1
        time.sleep(0.4)
        if scanned % 300 == 0:
            print(f"  Progress: {scanned} | Found: {len(results)}")

    results.sort(key=lambda x: x['conf_score'], reverse=True)
    top5 = results[:5]

    if not top5:
        send_telegram(f"🔍 <b>Confluence Scanner — {now}</b>\nScanned: {scanned} stocks\nNo signals met 14/22 threshold.\nNext scan in ~2 hours.")
        return

    # Mark as sent
    for r in top5:
        _confluence_sent_today.add(r['symbol'])

    # Send alerts
    header = f"""🔥 <b>CONFLUENCE ALERT — {today} {now}</b>
{len(top5)} high-conviction signal(s) from {scanned} stocks
Threshold: 14/22 | Ultra Buy (18+): {len([r for r in top5 if r['conf_score']>=18])}
📧 Full detailed report sent to Gmail"""
    send_telegram(header)
    time.sleep(1)

    for i, r in enumerate(top5, 1):
        score = r['conf_score']
        sig_label = "🔥 ULTRA BUY" if score>=18 else "⭐ STRONG BUY"
        stars = "⭐"*(score//4)

        force_txt = ""
        for fname, fscore, fmax, fdetails in r['conf_details']:
            bar = "█"*fscore + "░"*(fmax-fscore)
            force_txt += f"{bar} {fscore}/{fmax} {fname}\n"
            for d in fdetails[:2]:
                force_txt += f"  {d}\n"

        opt_txt = ""
        if r['options']:
            o = r['options']
            opt_txt = f"\n🎯 <b>OPTIONS:</b> {r['symbol']} {o['strike']} CE ({o['expiry']}) | Prem ₹{o['prem_low']}–{o['prem_high']} | Target ₹{o['tgt_prem']} | SL ₹{o['sl_prem']} | Capital ₹{o['cap_low']:,}"

        sl_dist = r['price'] - r['sl']
        max_shares = int((200000*0.02)/sl_dist) if sl_dist>0 else 0

        tg = f"""{sig_label} #{i} — <b>{r['symbol']}</b>
Score: {score}/22 {stars} | Win prob: ~{55+(score-10)*1.5:.0f}%
Price: ₹{r['price']} | RSI: {r['rsi']} | Sector: {r['sector']}

<b>6-Force Breakdown:</b>
{force_txt}
📈 <b>STOCK TRADE</b>
Entry    : ₹{r['entry']}
Target 1 : ₹{r['target1'] if 'target1' in r else round(r['price']*1.065,2)} (+6.5%) — Book 33%
Target 2 : ₹{r['target2'] if 'target2' in r else round(r['price']*1.13,2)} (+13%) — Book 33%
Target 3 : ₹{r['target3'] if 'target3' in r else round(r['price']*1.20,2)} (+20%) — Book 34%
Stop Loss: ₹{r['sl']}
Position : {max_shares} shares = ₹{max_shares*r['price']:,.0f} (2% risk rule)
{opt_txt}
💡 This is a RARE high-conviction setup. Act decisively."""
        send_telegram(tg)
        time.sleep(1)

    # Email
    email_body = build_confluence_email(top5, today, now, scanned)
    top_sym = top5[0]['symbol']
    top_score = top5[0]['conf_score']
    prefix = "🔥 ULTRA BUY" if top_score>=18 else "⭐ STRONG BUY"
    send_email(f"{prefix} Confluence Alert {today} | {top_sym} {top_score}/22 | {len(top5)} signals", email_body)
    print(f"✅ Confluence scan complete — {len(top5)} signals sent!")

def score_confluence(symbol, sector_signals, nifty, banknifty, fii_dii, news):
    try:
        import math
        df = yf.download(symbol, period="6mo", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < 30: return 0, [], {}
        close = df['Close'].squeeze(); volume = df['Volume'].squeeze()
        curr = float(close.iloc[-1])
        if math.isnan(curr) or curr < 50: return 0, [], {}
        avg_vol = float(volume.tail(20).mean())
        if avg_vol < 100000: return 0, [], {}
        rsi = float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
        if rsi > 68: return 0, [], {}

        total = 0; all_details = []

        # F1 Technical (0-4)
        f1=0; f1d=[]
        ema20=float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
        ema50=float(ta.trend.EMAIndicator(close,50).ema_indicator().iloc[-1])
        macd=ta.trend.MACD(close); ml=float(macd.macd().iloc[-1]); sl_v=float(macd.macd_signal().iloc[-1])
        lat_vol=float(volume.iloc[-1]); vol_ratio=lat_vol/avg_vol if avg_vol>0 else 0
        if rsi<=60: f1+=1; f1d.append("✅ RSI in buy zone")
        else: f1d.append(f"❌ RSI {rsi:.0f} elevated")
        if ema20>ema50: f1+=1; f1d.append("✅ EMA uptrend")
        else: f1d.append("❌ EMA downtrend")
        if ml>sl_v: f1+=1; f1d.append("✅ MACD bullish")
        else: f1d.append("❌ MACD bearish")
        if vol_ratio>=2.0: f1+=1; f1d.append(f"✅ Volume {vol_ratio:.1f}x — institutional")
        else: f1d.append(f"❌ Volume {vol_ratio:.1f}x — normal")
        total+=f1; all_details.append(("Technical Setup",f1,4,f1d))

        # F2 Market Structure (0-3)
        f2=0; f2d=[]
        support=float(close.tail(20).min()); resistance=float(close.tail(20).max())
        dist_sup=((curr-support)/support)*100
        week_ago=float(close.iloc[-6]); momentum=((curr-week_ago)/week_ago)*100
        highs=[float(close.iloc[i]) for i in range(-10,-1)]
        hh=all(highs[i]>=highs[i-1]*0.995 for i in range(1,len(highs)))
        if hh: f2+=1; f2d.append("✅ Higher highs pattern")
        else: f2d.append("❌ No higher highs")
        if dist_sup<=5: f2+=1; f2d.append(f"✅ Near support ₹{support:.2f}")
        else: f2d.append(f"❌ {dist_sup:.0f}% above support")
        if momentum>3: f2+=1; f2d.append(f"✅ Weekly momentum +{momentum:.1f}%")
        else: f2d.append(f"❌ Weak weekly {momentum:+.1f}%")
        total+=f2; all_details.append(("Market Structure",f2,3,f2d))

        # F3 Alignment (0-4)
        f3=0; f3d=[]
        sector=get_sector(symbol); smood=sector_signals.get(sector,"NEUTRAL 🟡")
        if "BULLISH" in smood: f3+=2; f3d.append(f"✅ Sector {sector} bullish")
        elif "NEUTRAL" in smood: f3+=1; f3d.append(f"⚠️ Sector {sector} neutral")
        else: f3d.append(f"❌ Sector {sector} bearish")
        if nifty and nifty['direction']=="BULLISH": f3+=1; f3d.append("✅ Nifty bullish")
        elif nifty and nifty['direction']=="BEARISH": f3d.append("❌ Nifty bearish")
        else: f3d.append("⚠️ Nifty neutral")
        if sector=="BANKING" and banknifty and banknifty['direction']=="BULLISH": f3+=1; f3d.append("✅ BankNifty bullish")
        total+=f3; all_details.append(("Sector + Index Alignment",f3,4,f3d))

        # F4 Institutional (0-4)
        f4=0; f4d=[]
        avg_vol5=float(volume.tail(5).mean()); vol_trend=avg_vol5/avg_vol if avg_vol>0 else 1
        prev20=float(close.iloc[-21]) if len(close)>=21 else float(close.iloc[0])
        p20=((curr-prev20)/prev20)*100
        if vol_ratio>=3.0: f4+=2; f4d.append(f"✅ MASSIVE {vol_ratio:.1f}x volume — clear institutional")
        elif vol_ratio>=2.0: f4+=1; f4d.append(f"✅ High {vol_ratio:.1f}x volume")
        else: f4d.append(f"❌ Low {vol_ratio:.1f}x volume")
        if vol_trend>=1.3: f4+=1; f4d.append("✅ Volume trending up — accumulation")
        else: f4d.append("❌ Volume not increasing")
        if p20>2 and vol_trend>=1.2: f4+=1; f4d.append(f"✅ Price +{p20:.1f}% with volume")
        else: f4d.append(f"❌ Price {p20:+.1f}% — weak")
        total+=f4; all_details.append(("Institutional Footprint",f4,4,f4d))

        # F5 Multi-Timeframe (0-3)
        f5=0; f5d=[]
        try:
            wdf = yf.download(symbol, period="1y", interval="1wk", progress=False, auto_adjust=True)
            if not wdf.empty and len(wdf)>=20:
                wc=wdf['Close'].squeeze()
                we20=float(ta.trend.EMAIndicator(wc,10).ema_indicator().iloc[-1])
                we50=float(ta.trend.EMAIndicator(wc,20).ema_indicator().iloc[-1])
                wrsi=float(ta.momentum.RSIIndicator(wc).rsi().iloc[-1])
                if we20>we50 and wrsi<72: f5+=1; f5d.append(f"✅ Weekly uptrend (RSI {wrsi:.0f})")
                else: f5d.append("❌ Weekly not in uptrend")
        except: f5d.append("⚠️ Weekly data unavailable")
        try:
            mdf = yf.download(symbol, period="2y", interval="1mo", progress=False, auto_adjust=True)
            if not mdf.empty and len(mdf)>=12:
                mc2=mdf['Close'].squeeze()
                me6=float(ta.trend.EMAIndicator(mc2,6).ema_indicator().iloc[-1])
                me12=float(ta.trend.EMAIndicator(mc2,12).ema_indicator().iloc[-1])
                if me6>me12: f5+=1; f5d.append("✅ Monthly uptrend")
                else: f5d.append("❌ Monthly not in uptrend")
        except: f5d.append("⚠️ Monthly data unavailable")
        if f5==2: f5+=1; f5d.append("✅ All timeframes aligned!")
        total+=f5; all_details.append(("Multi-Timeframe",f5,3,f5d))

        # F6 Fundamental (0-4)
        f6=0; f6d=[]
        sym_clean=symbol.replace('.NS','')
        stock_news=[n for n in news if sym_clean.upper() in n['stock'].upper()]
        if stock_news:
            pos=[n for n in stock_news if "POSITIVE" in n['sentiment']]
            neg=[n for n in stock_news if "NEGATIVE" in n['sentiment']]
            if pos and not neg: f6+=2; f6d.append(f"✅ Positive news: {pos[0]['headline'][:60]}")
            elif neg: f6d.append(f"❌ Negative news found")
            else: f6+=1; f6d.append("⚠️ Neutral news")
        else: f6+=1; f6d.append("✅ No negative news")
        fii_net=fii_dii.get('fii_net',0) or 0
        if fii_net>2000: f6+=1; f6d.append(f"✅ FII buying ₹{fii_net:,.0f}Cr")
        elif fii_net<-2000: f6d.append(f"❌ FII selling ₹{abs(fii_net):,.0f}Cr")
        else: f6d.append("⚠️ FII neutral")
        try:
            high52=float(close.tail(252).max()) if len(close)>=252 else float(close.max())
            low52=float(close.tail(252).min()) if len(close)>=252 else float(close.min())
            pos_range=((curr-low52)/(high52-low52)*100) if high52!=low52 else 50
            if pos_range>=70: f6+=1; f6d.append("✅ In upper 30% of 52-week range")
            else: f6d.append(f"⚠️ At {pos_range:.0f}% of 52-week range")
        except: pass
        f6=max(0,min(4,f6)); total+=f6; all_details.append(("Fundamental + News",f6,4,f6d))

        return max(0,min(22,total)), all_details, {"rsi":round(rsi,1),"sector":sector}
    except:
        return 0, [], {}

def build_confluence_email(results, today, now, scanned):
    results_html = ""
    for i, r in enumerate(results, 1):
        score = r['conf_score']
        sc = "#1a5276" if score>=18 else "#1e8449"
        bg = "#d6eaf8" if score>=18 else "#d5f5e3"
        sig_label = "🔥 ULTRA BUY" if score>=18 else "⭐ STRONG BUY"
        stars = "⭐"*(score//4)
        sl_dist = r['price']-r['sl']
        max_shares = int((200000*0.02)/sl_dist) if sl_dist>0 else 0
        t1=round(r['price']*1.065,2); t2=round(r['price']*1.13,2); t3=round(r['price']*1.20,2)

        forces_html = ""
        for fname, fscore, fmax, fdetails in r.get('conf_details',[]):
            pct = fscore/fmax*100
            fc = "#27ae60" if pct>=75 else "#f39c12" if pct>=50 else "#e74c3c"
            bar = "█"*fscore + "░"*(fmax-fscore)
            forces_html += f"""<tr style='border-bottom:1px solid #eee'>
                <td style='padding:6px'><b>{fname}</b></td>
                <td style='padding:6px'><span style='font-family:monospace;color:{fc}'>{bar}</span> <b>{fscore}/{fmax}</b></td>
                <td style='padding:6px;font-size:12px'>{"<br>".join(fdetails[:3])}</td></tr>"""

        opt_html = ""
        if r.get('options'):
            o=r['options']
            opt_html = f"""<div style='background:#e8f8f5;padding:10px;border-radius:6px;margin-top:8px'>
            <b>🎯 Options Route:</b> {r['symbol']} {o['strike']} CE ({o['expiry']}) |
            Buy ₹{o['prem_low']}–{o['prem_high']} | Target ₹{o['tgt_prem']} (+120%) |
            SL ₹{o['sl_prem']} | Capital ₹{o['cap_low']:,}–₹{o['cap_high']:,}</div>"""

        results_html += f"""<div style='border:2px solid {sc};border-radius:10px;padding:18px;margin-bottom:20px'>
        <div style='background:{bg};padding:10px;border-radius:6px;margin-bottom:12px'>
        <h3 style='margin:0;color:{sc}'>#{i} {sig_label} — {r['symbol']}</h3>
        <p style='margin:5px 0 0'>Score: <b>{score}/22</b> {stars} | Price: <b>₹{r['price']}</b> | Win prob: ~{55+(score-10)*1.5:.0f}% | RSI: {r['rsi']} | Sector: {r['sector']}</p></div>
        <table style='width:100%;border-collapse:collapse;font-size:13px'>
        <tr style='background:#2c3e50;color:white'><th style='padding:6px'>Force</th><th>Score</th><th>Details</th></tr>
        {forces_html}</table>
        <div style='display:flex;gap:12px;margin-top:12px'>
        <div style='flex:1;background:#eafaf1;padding:10px;border-radius:6px'>
        <b>📈 Stock Trade</b><br>
        Entry: ₹{r['entry']} | SL: ₹{r['sl']}<br>
        🎯 T1: ₹{t1} (+6.5%) — Book 33%<br>
        🎯 T2: ₹{t2} (+13%) — Book 33%<br>
        🎯 T3: ₹{t3} (+20%) — Book 34%<br>
        <small>Position: {max_shares} shares = ₹{max_shares*r['price']:,.0f} (2% risk on ₹2L)</small>
        </div></div>{opt_html}
        <div style='background:#fff3cd;padding:8px;border-radius:6px;margin-top:8px;font-size:13px'>
        💡 Enter at ₹{r['entry']} → SL at ₹{r['sl']} → Book 33% at ₹{t1} → Trail SL → Hold for ₹{t2} and ₹{t3}</div></div>"""

    return f"""<html><body style='font-family:Arial,sans-serif;max-width:900px;margin:auto;padding:20px'>
<div style='background:linear-gradient(135deg,#1a1a2e,#16213e);padding:20px;border-radius:12px;color:white;margin-bottom:20px'>
<h1 style='margin:0'>🔥 Confluence Scanner Alert</h1>
<p style='margin:5px 0 0;opacity:0.9'>{today} | {now} | {len(results)} signals from {scanned} stocks</p>
<p style='margin:3px 0 0;opacity:0.7;font-size:13px'>Threshold: 14/22 | Ultra Buy (18+): {len([r for r in results if r['conf_score']>=18])}</p></div>
<div style='background:#fef9e7;padding:12px;border-radius:8px;border-left:4px solid #f39c12;margin-bottom:20px'>
<b>How to use:</b> Score 18-22 = act with full size. Score 14-17 = act with 75% size.
Always book in 3 parts. Stop loss is mandatory. Position size based on ₹2L capital, 2% risk rule.</div>
{results_html}
<p style='color:#888;font-size:12px;margin-top:15px'>⚠️ Technical signals only. Win probability is estimate — not guarantee. Always use stop loss.</p>
</body></html>"""

# ══════════════════════════════════════════════════════════════
# TELEGRAM COMMANDS
# ══════════════════════════════════════════════════════════════
def process_command(text, chat_id):
    sheet = setup_sheets()
    parts = text.strip().split(); cmd = parts[0].lower(); args = parts[1:]

    if cmd in ['/start','/help']:
        return """🤖 <b>NSE Trading Bot v4.0</b>
24/7 Active | Instant Response

📈 <b>RECORD TRADES</b>
/buy STOCK PRICE QTY
/buyce STOCK STRIKE PREMIUM LOTS
/sell STOCK EXIT_PRICE
/sellce STOCK STRIKE EXIT_PREMIUM

📊 <b>VIEW</b>
/portfolio — open trades
/pnl — same as portfolio

🔍 <b>ANALYSIS</b>
/analyse STOCK
/compare STOCK1 STOCK2
/market — live indices

⏰ <b>AUTO REPORTS</b>
8:00 AM — Morning scan (2000+ stocks)
12:00 PM — Midday update
8:00 PM — Evening P&L

💡 All reports: Telegram + Gmail"""

    elif cmd == '/ping':
        return f"🟢 <b>Bot alive!</b>\n⏰ {ist_str()}\nAll systems running."

    elif cmd == '/market':
        try:
            msg = f"📊 <b>LIVE MARKET</b>\n⏰ {ist_str()} (15 min delayed)\n\n"
            for name, ticker in [("Nifty 50","^NSEI"),("Bank Nifty","^NSEBANK"),("Sensex","^BSESN")]:
                df = yf.download(ticker, period="5d", interval="1d", progress=False, auto_adjust=True)
                if not df.empty and len(df)>=2:
                    curr=float(df['Close'].iloc[-1]); prev=float(df['Close'].iloc[-2])
                    if not math.isnan(curr):
                        chg=((curr-prev)/prev)*100; rsi=float(ta.momentum.RSIIndicator(df['Close'].squeeze()).rsi().iloc[-1])
                        msg+=f"{'🟢' if chg>0 else '🔴'} <b>{name}</b>: {curr:,.0f} ({chg:+.2f}%) | RSI:{rsi:.0f}\n"
                time.sleep(0.3)
            msg+="\n💡 RSI<40=oversold(buy) | RSI>70=overbought(careful)"
            return msg
        except: return "❌ Market data unavailable. Try again."

    elif cmd == '/analyse' and args:
        return analyse_stock(args[0])

    elif cmd == '/compare' and len(args)>=2:
        r1=analyse_stock(args[0]); r2=analyse_stock(args[1])
        return f"⚖️ <b>{args[0].upper()} vs {args[1].upper()}</b>\n\n{r1}\n\n{'━'*30}\n\n{r2}"

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

💡 Set alerts in Zerodha:
Target → ₹{target} | SL → ₹{sl}
Bot tracks in all 3 daily reports."""
        except Exception as e: return f"❌ Error: {e}"

    elif cmd == '/buyce':
        if len(args)<4: return "❌ Format: /buyce STOCK STRIKE PREMIUM LOTS\nExample: /buyce BEL 450 13.5 1"
        try:
            stock=args[0].upper().replace('.NS',''); strike=float(args[1]); prem=float(args[2]); lots=int(args[3])
            lot_size=FON_LOT_SIZES.get(stock,500); total_qty=lot_size*lots; capital=round(prem*total_qty)
            today=today_str()
            if sheet:
                ws=sheet.worksheet("Open Trades")
                ws.append_row([today,stock,f"CE_{strike}",prem,total_qty,round(prem*2.2,1),round(prem*0.5,1),0,f"{lots} lots"])
            return f"""✅ <b>OPTIONS TRADE — {stock} {strike} CE</b>
Premium   : ₹{prem} × {total_qty} = ₹{capital:,}
Target    : ₹{round(prem*2.2,1)} (+120%)
Stop Loss : ₹{round(prem*0.5,1)} (-50%)
Lots      : {lots} × {lot_size} shares
Date      : {today}"""
        except Exception as e: return f"❌ Error: {e}"

    elif cmd == '/sell':
        if len(args)<2: return "❌ Format: /sell STOCK PRICE\nExample: /sell BEL 475"
        try:
            stock=args[0].upper().replace('.NS',''); exit_price=float(args[1]); today=today_str()
            if not sheet: return "❌ Sheets unavailable"
            open_ws=sheet.worksheet("Open Trades"); records=open_ws.get_all_records()
            trade_row=None; row_num=None
            for i,r in enumerate(records,2):
                if r.get('Stock','').upper()==stock and r.get('Type')=='STOCK':
                    trade_row=r; row_num=i; break
            if not trade_row: return f"❌ No open trade for {stock}. Check /portfolio."
            entry=float(trade_row.get('Entry Price',0)); qty=int(trade_row.get('Qty',0))
            pnl=(exit_price-entry)*qty; pnl_pct=((exit_price-entry)/entry)*100; days=trade_row.get('Days Held',0)
            closed_ws=sheet.worksheet("Closed Trades")
            if not closed_ws.row_values(1):
                closed_ws.append_row(["Entry Date","Exit Date","Stock","Type","Entry","Exit","Qty","P&L","P&L%","Days"])
            closed_ws.append_row([trade_row.get('Entry Date'),today,stock,'STOCK',entry,exit_price,qty,round(pnl,2),round(pnl_pct,2),days])
            open_ws.delete_rows(row_num)
            return f"""{'🟢' if pnl>0 else '🔴'} <b>TRADE CLOSED — {stock}</b>
Entry → Exit : ₹{entry} → ₹{exit_price}
Qty : {qty} | Days: {days}
P&L : ₹{pnl:+,.0f} ({pnl_pct:+.1f}%)
{'🎉 Profitable! Well done.' if pnl>0 else '📚 Loss. Review entry signals for learning.'}"""
        except Exception as e: return f"❌ Error: {e}"

    elif cmd == '/sellce':
        if len(args)<3: return "❌ Format: /sellce STOCK STRIKE EXIT_PREMIUM"
        try:
            stock=args[0].upper().replace('.NS',''); strike=float(args[1]); exit_prem=float(args[2]); today=today_str()
            if not sheet: return "❌ Sheets unavailable"
            open_ws=sheet.worksheet("Open Trades"); records=open_ws.get_all_records()
            trade_row=None; row_num=None
            for i,r in enumerate(records,2):
                if r.get('Stock','').upper()==stock and str(strike) in str(r.get('Type','')):
                    trade_row=r; row_num=i; break
            if not trade_row: return f"❌ No open CE trade for {stock} {strike}."
            entry_prem=float(trade_row.get('Entry Price',0)); qty=int(trade_row.get('Qty',0))
            pnl=(exit_prem-entry_prem)*qty; pnl_pct=((exit_prem-entry_prem)/entry_prem)*100; days=trade_row.get('Days Held',0)
            closed_ws=sheet.worksheet("Closed Trades")
            closed_ws.append_row([trade_row.get('Entry Date'),today,stock,f"CE_{strike}",entry_prem,exit_prem,qty,round(pnl,2),round(pnl_pct,2),days])
            open_ws.delete_rows(row_num)
            return f"""{'🟢' if pnl>0 else '🔴'} <b>OPTIONS CLOSED — {stock} {strike} CE</b>
Entry → Exit : ₹{entry_prem} → ₹{exit_prem}
P&L : ₹{pnl:+,.0f} ({pnl_pct:+.1f}%)"""
        except Exception as e: return f"❌ Error: {e}"

    elif cmd in ['/portfolio','/pnl']:
        if not sheet: return "❌ Sheets unavailable"
        try:
            ws=sheet.worksheet("Open Trades"); records=ws.get_all_records()
            if not records: return "📊 <b>No open trades</b>\nUse /buy STOCK PRICE QTY to record."
            msg=f"💼 <b>OPEN POSITIONS</b>\n⏰ {ist_str()}\n\n"; total=0
            for r in records:
                stock=r.get('Stock',''); entry=float(r.get('Entry Price',0)); qty=int(r.get('Qty',0))
                target=float(r.get('Target',0)); sl=float(r.get('Stop Loss',0)); days=r.get('Days Held',0)
                invested=entry*qty; total+=invested
                msg+=f"<b>{stock}</b> ({r.get('Type','STOCK')})\nEntry ₹{entry} × {qty} = ₹{invested:,.0f} | Day {days}\nTarget ₹{target} | SL ₹{sl}\n\n"
            msg+=f"💰 Total: ₹{total:,.0f}"
            return msg
        except Exception as e: return f"❌ Error: {e}"

    return None

def analyse_stock(sym):
    try:
        sym = sym.upper().replace('.NS','')
        n = now_ist()
        if 1 <= n.hour <= 6:
            return f"⏰ Market data unavailable at {ist_str('%I:%M %p IST')}. Yahoo Finance doesn't serve Indian stocks 1-6 AM IST. Try after 6 AM."
        df = yf.download(sym+'.NS', period="3mo", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df)<30: return f"❌ No data for {sym}. Check symbol name."
        close=df['Close'].squeeze(); volume=df['Volume'].squeeze()
        curr=float(close.iloc[-1]); prev=float(close.iloc[-2])
        if math.isnan(curr) or math.isnan(prev): return f"⏰ {sym} data unavailable right now. Try after 9 AM IST."
        rsi=float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
        ema20=float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
        ema50=float(ta.trend.EMAIndicator(close,50).ema_indicator().iloc[-1])
        macd=ta.trend.MACD(close); ml=float(macd.macd().iloc[-1]); sl_v=float(macd.macd_signal().iloc[-1])
        avg_vol=float(volume.tail(20).mean()); lat_vol=float(volume.iloc[-1])
        vol_surge=lat_vol>avg_vol*1.5
        support=round(float(close.tail(20).min()),2); resistance=round(float(close.tail(20).max()),2)
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

        score=sum([1 if (40<=rsi<=65 or rsi<40) else 0, 1 if ema20>ema50 else 0,
                   1 if ml>sl_v else 0, 1 if vol_surge else 0])

        entry=round(curr*0.999,2); target=round(curr*1.10,2); sl_p=round(max(curr*0.97,support*0.98),2)
        sl_dist=curr-sl_p; max_shares=int((200000*0.02)/sl_dist) if sl_dist>0 else 0

        opt_txt=""
        if is_fno and "BUY" in signal and rsi<72 and lot>0:
            strike=round(curr*1.03/50)*50; prem=round(curr*0.028,1); cap=round(prem*lot)
            opt_txt=f"\n🎯 <b>OPTIONS:</b> {sym} {strike} CE | Prem ~₹{prem} | Lot {lot} | Capital ~₹{cap:,}\n⚠️ Verify in Zerodha Options Chain"

        return f"""🔍 <b>ANALYSIS — {sym}</b>
⏰ {ist_str()} (15 min delayed)

💰 ₹{curr} ({day_chg:+.2f}% today)
Signal   : <b>{signal}</b> ({score}/4 {"⭐"*score})
Support  : ₹{support} | Resistance: ₹{resistance}

📊 RSI: {rsi:.1f} {'✅' if rsi<65 else '⚠️'}
Trend  : {'UP ✅' if ema20>ema50 else 'DOWN ❌'}
MACD   : {'Bullish ✅' if ml>sl_v else 'Bearish ❌'}
Volume : {'Surge ✅' if vol_surge else 'Normal'}

📈 <b>Trade Plan</b>
Entry    : ₹{entry}
Target   : ₹{target} (+10%)
Stop Loss: ₹{sl_p} (-3%)
Position : {max_shares} shares = ₹{max_shares*curr:,.0f} (2% risk on ₹2L)
{"F&O ✅ Lot: "+str(lot) if is_fno else "Not F&O"}
{opt_txt}
⚠️ Verify price in Zerodha before trading"""
    except Exception as e:
        return f"❌ Error: {str(e)[:100]}"

# ══════════════════════════════════════════════════════════════
# FLASK ROUTES
# ══════════════════════════════════════════════════════════════
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        if not data: return jsonify({"ok":True})
        msg = data.get('message',{}); text = msg.get('text','')
        chat_id = str(msg.get('chat',{}).get('id',''))
        if text and text.startswith('/'):
            print(f"CMD: {text} from {chat_id}")
            resp = process_command(text, chat_id)
            if resp: send_telegram(resp, chat_id)
    except Exception as e:
        print(f"Webhook error: {e}")
    return jsonify({"ok":True})

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status":"alive","time":ist_str(),"bot":"LoveshNSEBot v4.0"})

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status":"NSE Trading Bot v4.0 — Running 24/7","time":ist_str()})

@app.route('/run_morning', methods=['GET'])
def manual_morning():
    threading.Thread(target=run_morning_scan).start()
    return jsonify({"status":"Morning scan started","time":ist_str()})

@app.route('/run_evening', methods=['GET'])
def manual_evening():
    threading.Thread(target=run_evening_update).start()
    return jsonify({"status":"Evening update started","time":ist_str()})

@app.route('/run_midday', methods=['GET'])
def manual_midday():
    threading.Thread(target=run_midday_update).start()
    return jsonify({"status":"Midday update started","time":ist_str()})

@app.route('/run_confluence', methods=['GET'])
def manual_confluence():
    threading.Thread(target=run_confluence_scan).start()
    return jsonify({"status":"Confluence scan started","time":ist_str()})

# ══════════════════════════════════════════════════════════════
# SCHEDULER — All tasks in IST
# ══════════════════════════════════════════════════════════════
def start_scheduler():
    scheduler = BackgroundScheduler(timezone=IST)

    # Morning scan — 8:00 AM IST Mon-Fri
    scheduler.add_job(run_morning_scan, CronTrigger(
        hour=8, minute=0, day_of_week='mon-fri', timezone=IST))

    # Midday update — 12:00 PM IST Mon-Fri
    scheduler.add_job(run_midday_update, CronTrigger(
        hour=12, minute=0, day_of_week='mon-fri', timezone=IST))

    # Evening update — 8:00 PM IST Mon-Fri
    scheduler.add_job(run_evening_update, CronTrigger(
        hour=20, minute=0, day_of_week='mon-fri', timezone=IST))

    # Confluence scanner — 4x daily during market hours
    scheduler.add_job(run_confluence_scan, CronTrigger(
        hour=9, minute=15, day_of_week='mon-fri', timezone=IST))
    scheduler.add_job(run_confluence_scan, CronTrigger(
        hour=11, minute=0, day_of_week='mon-fri', timezone=IST))
    scheduler.add_job(run_confluence_scan, CronTrigger(
        hour=13, minute=0, day_of_week='mon-fri', timezone=IST))
    scheduler.add_job(run_confluence_scan, CronTrigger(
        hour=14, minute=30, day_of_week='mon-fri', timezone=IST))

    scheduler.start()
    print(f"✅ Scheduler started — all tasks in IST timezone")
    print(f"   Morning scan   : 8:00 AM IST Mon-Fri")
    print(f"   Midday update  : 12:00 PM IST Mon-Fri")
    print(f"   Evening update : 8:00 PM IST Mon-Fri")
    print(f"   Confluence     : 9:15, 11:00, 13:00, 14:30 IST Mon-Fri")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"\n{'='*60}")
    print(f"NSE Trading Bot v4.0 starting on port {port}")
    print(f"Time: {ist_str()}")
    print(f"{'='*60}")
    start_scheduler()
    send_telegram(f"🚀 <b>NSE Trading Bot v4.0 Online!</b>\n⏰ {ist_str()}\n\n✅ Telegram webhook active\n✅ Scheduler running (IST)\n✅ Morning scan: 8:00 AM\n✅ Midday update: 12:00 PM\n✅ Evening update: 8:00 PM\n✅ Confluence: 4x daily\n\nSend /help for commands")
    app.run(host='0.0.0.0', port=port)
