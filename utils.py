# ============================================================
# SHARED UTILITIES — used by all 3 scripts
# ============================================================
import yfinance as yf
import pandas as pd
import ta
import requests
import os
import json
import time
import smtplib
import warnings
import feedparser
import gspread
from google.oauth2.service_account import Credentials
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
warnings.filterwarnings('ignore')

# ── Credentials ──────────────────────────────────────────────
GMAIL_ADDRESS    = os.environ.get('GMAIL_ADDRESS')
GMAIL_PASSWORD   = os.environ.get('GMAIL_PASSWORD')
TELEGRAM_TOKEN   = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
GOOGLE_SHEET_ID  = os.environ.get('GOOGLE_SHEET_ID')
GOOGLE_CREDS     = os.environ.get('GOOGLE_CREDENTIALS')

# ── Portfolio ─────────────────────────────────────────────────
MY_PORTFOLIO = [
    "BLS.NS","ENGINERSIN.NS","HDFCBANK.NS","JIOFIN.NS",
    "PARADEEP.NS","SUZLON.NS","SYNGENE.NS","VMM.NS","BEL.NS"
]

# ── F&O eligible stocks with lot sizes ───────────────────────
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
    "ASIANPAINT":300,"BRITANNIA":250,"NESTLEIND":100,"TITAN":375,
    "DIVISLAB":200,"APOLLOHOSP":125,"BAJAJFINSV":500,
}
FON_STOCKS = set(k+".NS" for k in FON_LOT_SIZES)

# ── Sector mapping (500+ stocks) ─────────────────────────────
SECTOR_MAP = {
    "IT":["TCS.NS","INFY.NS","WIPRO.NS","HCLTECH.NS","TECHM.NS","LTIM.NS",
          "COFORGE.NS","PERSISTENT.NS","MPHASIS.NS","KPITTECH.NS","TATAELXSI.NS",
          "CYIENT.NS","BIRLASOFT.NS","MASTEK.NS","TANLA.NS","ROUTE.NS",
          "LATENTVIEW.NS","HAPPSTMNDS.NS","INTELLECT.NS","NEWGEN.NS"],
    "BANKING":["HDFCBANK.NS","ICICIBANK.NS","SBIN.NS","KOTAKBANK.NS","AXISBANK.NS",
               "INDUSINDBK.NS","BANDHANBNK.NS","FEDERALBNK.NS","IDFCFIRSTB.NS",
               "RBLBANK.NS","CANBK.NS","BANKBARODA.NS","PNB.NS","UNIONBANK.NS",
               "KARURVYSYA.NS","CITYUNIONBANK.NS","DCBBANK.NS","EQUITASBNK.NS"],
    "PHARMA":["SUNPHARMA.NS","DRREDDY.NS","CIPLA.NS","DIVISLAB.NS","LUPIN.NS",
              "AUROPHARMA.NS","ALKEM.NS","ZYDUSLIFE.NS","MANKIND.NS","GLENMARK.NS",
              "TORNTPHARM.NS","JUBLPHARMA.NS","AJANTPHARM.NS","NEULANDLAB.NS",
              "LAURUSLABS.NS","GRANULES.NS","APLLTD.NS","ERIS.NS"],
    "DEFENCE":["HAL.NS","BEL.NS","BEML.NS","MAZAGON.NS","GRSE.NS",
               "COCHINSHIP.NS","MIDHANI.NS","GARDENREACH.NS","PARAS.NS"],
    "POWER":["NTPC.NS","POWERGRID.NS","TATAPOWER.NS","ADANIGREEN.NS","CESC.NS",
             "SJVN.NS","NHPC.NS","SUZLON.NS","INOXWIND.NS","JSWENERGY.NS",
             "TORNTPOWER.NS","RPOWER.NS","WAAREEENER.NS","IEX.NS"],
    "AUTO":["MARUTI.NS","TATAMOTORS.NS","BAJAJ-AUTO.NS","HEROMOTOCO.NS",
            "TVSMOTOR.NS","EICHERMOT.NS","MOTHERSON.NS","BHARATFORG.NS",
            "BOSCHLTD.NS","APOLLOTYRE.NS","MRF.NS","CEATLTD.NS","BALKRISIND.NS"],
    "FMCG":["HINDUNILVR.NS","ITC.NS","NESTLEIND.NS","BRITANNIA.NS","DABUR.NS",
            "MARICO.NS","COLPAL.NS","EMAMILTD.NS","JYOTHYLAB.NS","VBL.NS",
            "RADICO.NS","MCDOWELL-N.NS","TATACONSUM.NS","GODREJCP.NS"],
    "INFRA":["LT.NS","IRFC.NS","RVNL.NS","HUDCO.NS","PFC.NS","RECLTD.NS",
             "IRB.NS","NCC.NS","PNCINFRA.NS","KNRCON.NS","GMRINFRA.NS",
             "JSWINFRA.NS","ADANIPORTS.NS","CONCOR.NS","BLUEDART.NS"],
    "METALS":["TATASTEEL.NS","JSWSTEEL.NS","HINDALCO.NS","SAIL.NS","NMDC.NS",
              "VEDL.NS","NATIONALUM.NS","HINDCOPPER.NS","MOIL.NS"],
    "ENERGY":["RELIANCE.NS","ONGC.NS","BPCL.NS","IOC.NS","COALINDIA.NS",
              "GAIL.NS","OIL.NS","MGL.NS","IGL.NS","PETRONET.NS"],
    "REALTY":["DLF.NS","GODREJPROP.NS","PRESTIGE.NS","BRIGADE.NS","SOBHA.NS",
              "MAHLIFE.NS","PHOENIXLTD.NS","OBEROIRLTY.NS","KOLTEPATIL.NS"],
    "FINANCE":["BAJFINANCE.NS","BAJAJFINSV.NS","MUTHOOTFIN.NS","MANAPPURAM.NS",
               "CHOLAFIN.NS","SHRIRAMFIN.NS","M&MFIN.NS","POONAWALLA.NS",
               "LICHSGFIN.NS","CANFINHOME.NS","AAVAS.NS","CREDITACC.NS"],
    "CHEMICALS":["DEEPAKNTR.NS","ATUL.NS","NAVINFLUOR.NS","CLEAN.NS","VINATI.NS",
                 "FLUOROCHEM.NS","AARTI.NS","TATACHEM.NS","GHCL.NS","ALKYLAMINE.NS",
                 "AARTIDRUGS.NS","COROMANDEL.NS","PIIND.NS","SUMICHEM.NS"],
    "CEMENT":["ULTRACEMCO.NS","AMBUJACEM.NS","ACC.NS","SHREECEM.NS","RAMCOCEM.NS",
              "JKCEMENT.NS","STARCEMENT.NS","BIRLACORPN.NS"],
    "INSURANCE":["SBILIFE.NS","HDFCLIFE.NS","ICICIPRULI.NS","ICICIGI.NS",
                 "NIACL.NS","GICRE.NS","STARHEALTH.NS","MFSL.NS"],
}

def get_stock_sector(symbol):
    for sector, stocks in SECTOR_MAP.items():
        if symbol in stocks:
            return sector
    return "GENERAL"

# ── Google Sheets ─────────────────────────────────────────────
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

# ── Telegram ──────────────────────────────────────────────────
def send_telegram(message, chat_id=None):
    try:
        cid = chat_id or TELEGRAM_CHAT_ID
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        for chunk in [message[i:i+4000] for i in range(0, len(message), 4000)]:
            requests.post(url, data={"chat_id": cid, "text": chunk,
                          "parse_mode": "HTML"}, timeout=15)
            time.sleep(0.5)
        print("Telegram sent!")
    except Exception as e:
        print(f"Telegram error: {e}")

# ── Email ─────────────────────────────────────────────────────
def send_email(subject, body, csv_file=None):
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_ADDRESS
        msg['To'] = GMAIL_ADDRESS
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        if csv_file and os.path.exists(csv_file):
            with open(csv_file, "rb") as f:
                part = MIMEBase('application', 'octet-stream')
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
        print("Email sent!")
    except Exception as e:
        print(f"Email error: {e}")

# ── Global Markets ────────────────────────────────────────────
def get_global_markets():
    print("Fetching global markets...")
    tickers = {
        "US_DOW":"^DJI","US_NASDAQ":"^IXIC","US_SP500":"^GSPC",
        "CRUDE_OIL":"CL=F","GOLD":"GC=F","USD_INR":"INR=X","VIX":"^VIX",
    }
    result = {}
    for name, ticker in tickers.items():
        for attempt in range(3):
            try:
                df = yf.download(ticker, period="5d", interval="1d", progress=False)
                if not df.empty and len(df) >= 2:
                    curr = float(df['Close'].iloc[-1])
                    prev = float(df['Close'].iloc[-2])
                    chg = ((curr - prev) / prev) * 100
                    result[name] = {"price": round(curr, 2), "change_pct": round(chg, 2)}
                    break
            except:
                time.sleep(1)
        time.sleep(0.3)
    return result

# ── FII/DII ───────────────────────────────────────────────────
def get_fii_dii():
    print("Fetching FII/DII...")
    # Method 1: NSE API with session
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.nseindia.com/',
            'Connection': 'keep-alive',
        }
        session = requests.Session()
        session.get('https://www.nseindia.com/', headers=headers, timeout=15)
        time.sleep(3)
        session.get('https://www.nseindia.com/market-data/fii-dii-activity',
                    headers=headers, timeout=15)
        time.sleep(2)
        r = session.get('https://www.nseindia.com/api/fiidiiTradeReact',
                        headers=headers, timeout=15)
        if r.status_code == 200 and r.text:
            data = r.json()
            if data and len(data) > 0:
                latest = data[0]
                fii = float(str(latest.get('fiiNet','0')).replace(',','').replace(' ','') or 0)
                dii = float(str(latest.get('diiNet','0')).replace(',','').replace(' ','') or 0)
                return {"date": latest.get('date',''),"fii_net": fii,"dii_net": dii,"source":"NSE"}
    except Exception as e:
        print(f"FII method 1 failed: {e}")

    # Method 2: BSE India
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.bseindia.com/'}
        r = requests.get('https://api.bseindia.com/BseIndiaAPI/api/FIIDIIData/w',
                        headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if data:
                latest = data[0] if isinstance(data, list) else data
                fii = float(str(latest.get('FII_NET_VALUE',
                       latest.get('fii_net_value', '0'))).replace(',', '') or 0)
                dii = float(str(latest.get('DII_NET_VALUE',
                       latest.get('dii_net_value', '0'))).replace(',', '') or 0)
                return {"date": latest.get('TRADE_DATE', ''),"fii_net": fii,
                        "dii_net": dii,"source":"BSE"}
    except Exception as e:
        print(f"FII method 2 failed: {e}")

    # Method 3: Moneycontrol RSS fallback
    print("FII/DII: Using estimated data")
    return {"date": datetime.now().strftime('%d-%b-%Y'),
            "fii_net": None, "dii_net": None, "source": "unavailable"}

# ── News ──────────────────────────────────────────────────────
def get_news(portfolio_stocks=None):
    print("Fetching news...")
    if portfolio_stocks is None:
        portfolio_stocks = ["BLS","ENGINERSIN","HDFCBANK","JIOFIN","PARADEEP",
                           "SUZLON","SYNGENE","VMM","BEL","NIFTY","SENSEX",
                           "BANKNIFTY","MARKET","INDIA","STOCK"]
    feeds = [
        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "https://www.moneycontrol.com/rss/business.xml",
        "https://feeds.feedburner.com/ndtvprofit-latest",
        "https://www.livemint.com/rss/markets",
    ]
    news_items = []
    seen = set()
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:25]:
                title = entry.get('title', '')
                summary = entry.get('summary', '')[:300]
                pub_time = entry.get('published', '')
                text = (title + " " + summary).upper()
                matched_stock = None
                for stock in portfolio_stocks:
                    if stock.upper() in text:
                        matched_stock = stock
                        break
                if not matched_stock:
                    matched_stock = "MARKET"
                pos_words = ["SURGE","JUMP","GAIN","RISE","BUY","ORDER","PROFIT",
                            "UP","BULLISH","GROWTH","RECORD","HIGH","STRONG",
                            "BEAT","RALLY","POSITIVE","WIN","CONTRACT"]
                neg_words = ["FALL","DROP","LOSS","CRASH","SELL","DOWN","BEARISH",
                            "DECLINE","WEAK","MISS","FRAUD","SCAM","PENALTY",
                            "NEGATIVE","CONCERN","RISK","WARN","CUT"]
                pos_count = sum(1 for w in pos_words if w in text)
                neg_count = sum(1 for w in neg_words if w in text)
                if pos_count > neg_count:
                    sentiment = "POSITIVE 🟢"
                    impact = "Stock likely to rise today"
                elif neg_count > pos_count:
                    sentiment = "NEGATIVE 🔴"
                    impact = "Stock may face selling pressure"
                else:
                    sentiment = "NEUTRAL 🟡"
                    impact = "Watch for direction"
                key = title[:60]
                if key not in seen:
                    seen.add(key)
                    news_items.append({
                        "stock": matched_stock,
                        "headline": title[:150],
                        "sentiment": sentiment,
                        "impact": impact,
                        "time": pub_time[:20] if pub_time else "",
                    })
        except Exception as e:
            print(f"Feed error: {e}")
    return news_items[:15]

# ── Index Analysis ────────────────────────────────────────────
def analyze_index(ticker, name):
    try:
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)
        if df.empty or len(df) < 30:
            return None
        close = df['Close'].squeeze()
        volume = df.get('Volume', pd.Series()).squeeze()
        rsi = float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
        ema20 = float(ta.trend.EMAIndicator(close, window=20).ema_indicator().iloc[-1])
        ema50 = float(ta.trend.EMAIndicator(close, window=50).ema_indicator().iloc[-1])
        macd_obj = ta.trend.MACD(close)
        macd_line = float(macd_obj.macd().iloc[-1])
        signal_line = float(macd_obj.macd_signal().iloc[-1])
        current = float(close.iloc[-1])
        prev = float(close.iloc[-2])
        support = round(float(close.tail(20).min()), 2)
        resistance = round(float(close.tail(20).max()), 2)
        change_pct = ((current - prev) / prev) * 100
        if ema20 > ema50 and macd_line > signal_line and rsi < 70:
            direction = "BULLISH"; mood = "BULLISH 🟢"
        elif ema20 < ema50 and macd_line < signal_line:
            direction = "BEARISH"; mood = "BEARISH 🔴"
        elif rsi > 70:
            direction = "OVERBOUGHT"; mood = "OVERBOUGHT ⚠️"
        else:
            direction = "NEUTRAL"; mood = "NEUTRAL 🟡"
        return {
            "name": name, "level": round(current, 2),
            "change_pct": round(change_pct, 2),
            "rsi": round(rsi, 1), "trend": "UP" if ema20 > ema50 else "DOWN",
            "macd": "BULLISH" if macd_line > signal_line else "BEARISH",
            "support": support, "resistance": resistance,
            "direction": direction, "mood": mood,
            "prev": round(prev, 2),
        }
    except Exception as e:
        print(f"Index error {name}: {e}")
        return None

# ── Sector Momentum ───────────────────────────────────────────
def get_sector_momentum():
    print("Calculating sector momentum...")
    result = {}
    for sector, stocks in SECTOR_MAP.items():
        bull = 0; total = 0
        for sym in stocks[:6]:
            try:
                df = yf.download(sym, period="2mo", interval="1d", progress=False)
                if df.empty or len(df) < 20:
                    continue
                close = df['Close'].squeeze()
                ema20 = float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
                ema50 = float(ta.trend.EMAIndicator(close,50).ema_indicator().iloc[-1]) if len(close)>=50 else ema20
                rsi = float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
                macd = ta.trend.MACD(close)
                ml = float(macd.macd().iloc[-1])
                sl = float(macd.macd_signal().iloc[-1])
                if ema20 > ema50 and ml > sl and rsi < 72:
                    bull += 1
                total += 1
                time.sleep(0.2)
            except:
                pass
        if total > 0:
            score = bull / total
            if score >= 0.65: result[sector] = "BULLISH 🟢"
            elif score >= 0.4: result[sector] = "NEUTRAL 🟡"
            else: result[sector] = "BEARISH 🔴"
    return result

# ── Stock Signal ──────────────────────────────────────────────
def calculate_signal(symbol, sector_signals=None, nifty_direction="NEUTRAL"):
    try:
        df = yf.download(symbol, period="6mo", interval="1d", progress=False)
        if df.empty or len(df) < 30:
            return None
        close = df['Close'].squeeze()
        volume = df['Volume'].squeeze()
        current_price = float(close.iloc[-1])

        # Minimum filters
        if current_price < 50:
            return None
        avg_vol = float(volume.tail(20).mean())
        if avg_vol < 50000:
            return None

        rsi = float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
        ema20 = float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
        ema50 = float(ta.trend.EMAIndicator(close,50).ema_indicator().iloc[-1]) if len(close)>=50 else ema20
        macd_obj = ta.trend.MACD(close)
        macd_line = float(macd_obj.macd().iloc[-1])
        signal_line = float(macd_obj.macd_signal().iloc[-1])
        prev_price = float(close.iloc[-2])
        latest_vol = float(volume.iloc[-1])
        vol_surge = latest_vol > avg_vol * 1.5
        support = round(float(close.tail(20).min()), 2)
        resistance = round(float(close.tail(20).max()), 2)
        sector = get_stock_sector(symbol)
        sector_mood = sector_signals.get(sector,"NEUTRAL 🟡") if sector_signals else "NEUTRAL 🟡"
        sym_clean = symbol.replace(".NS","")
        is_fno = symbol in FON_STOCKS
        lot_size = FON_LOT_SIZES.get(sym_clean, 500) if is_fno else 0

        # Scoring
        score = 0
        details = []
        if 40 <= rsi <= 65:
            score += 1; details.append(f"RSI {rsi:.1f} ✅ Healthy buy zone (40–65 is ideal)")
        elif rsi < 40:
            score += 1; details.append(f"RSI {rsi:.1f} ✅ Oversold — strong buy opportunity")
        else:
            details.append(f"RSI {rsi:.1f} ⚠️ Elevated — stock may be overheated")
        if ema20 > ema50:
            score += 1; details.append("Trend UP ✅ Short term moving avg above long term — uptrend")
        else:
            details.append("Trend DOWN ❌ Short term below long term — downtrend")
        if macd_line > signal_line:
            score += 1; details.append("MACD Bullish ✅ Momentum shifting in favour of buyers")
        else:
            details.append("MACD Bearish ❌ Selling momentum dominant")
        if vol_surge:
            score += 1; details.append("Volume Surge ✅ Big institutional players buying today")
        else:
            details.append("Volume normal — no unusual buying activity")
        if "BULLISH" in sector_mood:
            score += 1; details.append(f"Sector {sector} ✅ Entire sector is bullish today")
        else:
            details.append(f"Sector {sector} — {sector_mood}")

        # Buy/sell logic
        bs = 0; ss = 0
        if rsi < 40: bs += 2
        elif rsi < 50: bs += 1
        if rsi > 70: ss += 2
        elif rsi > 60: ss += 1
        if ema20 > ema50: bs += 2
        else: ss += 2
        if macd_line > signal_line: bs += 2
        else: ss += 2
        if vol_surge: bs += 1
        if nifty_direction == "BULLISH": bs += 1
        elif nifty_direction == "BEARISH": ss += 1

        if bs >= 6: sig = "STRONG BUY"
        elif bs >= 4 and bs > ss: sig = "BUY"
        elif ss >= 6: sig = "STRONG SELL"
        elif ss >= 4 and ss > bs: sig = "SELL"
        else: sig = "HOLD"

        entry = round(current_price * 0.999, 2)
        target = round(current_price * 1.10, 2)
        sl = round(current_price * 0.97, 2)

        # Smart SL based on support
        smart_sl = max(sl, round(support * 0.98, 2))
        smart_target = min(target, round(resistance * 1.02, 2)) if resistance > current_price else target

        # Options
        opts = None
        if is_fno and "BUY" in sig and rsi < 68:
            if rsi < 45: mult = 1.02; exp = "Current monthly"
            elif rsi < 55: mult = 1.03; exp = "Current monthly"
            else: mult = 1.05; exp = "Next monthly"
            strike = round(current_price * mult / 50) * 50
            prem_low = round(current_price * 0.025, 1)
            prem_high = round(current_price * 0.035, 1)
            tgt_prem = round(prem_low * 2.2, 1)
            sl_prem = round(prem_low * 0.5, 1)
            cap_low = round(prem_low * lot_size)
            cap_high = round(prem_high * lot_size)
            opts = {
                "type":"CALL (CE)","strike":strike,"expiry":exp,
                "prem_low":prem_low,"prem_high":prem_high,
                "tgt_prem":tgt_prem,"sl_prem":sl_prem,
                "lot_size":lot_size,"cap_low":cap_low,"cap_high":cap_high,
            }

        ts = f"NSE Close — {(datetime.now()-timedelta(days=1)).strftime('%d %b %Y')} 3:30 PM"
        return {
            "symbol": sym_clean, "price": round(current_price,2),
            "prev": round(prev_price,2),
            "day_chg": round(((current_price-prev_price)/prev_price)*100,2),
            "signal": sig, "buy_score": bs, "sell_score": ss,
            "efficiency": score, "details": details,
            "rsi": round(rsi,1), "trend": "UP" if ema20>ema50 else "DOWN",
            "macd": "BULLISH" if macd_line>signal_line else "BEARISH",
            "vol_surge": "YES" if vol_surge else "no",
            "support": support, "resistance": resistance,
            "sector": sector, "sector_mood": sector_mood,
            "is_fno": is_fno, "lot_size": lot_size,
            "entry": entry, "target": smart_target, "sl": smart_sl,
            "options": opts, "timestamp": ts,
            "avg_vol": round(avg_vol),
        }
    except:
        return None

# ── NSE Symbol List ───────────────────────────────────────────
def get_nse_symbols():
    print("Downloading NSE symbol list...")
    try:
        import io
        headers = {
            'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer':'https://www.nseindia.com/',
        }
        session = requests.Session()
        session.get('https://www.nseindia.com', headers=headers, timeout=15)
        time.sleep(2)
        r = session.get(
            'https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv',
            headers=headers, timeout=30)
        if r.status_code == 200:
            df = pd.read_csv(io.StringIO(r.text))
            syms = [s.strip()+'.NS' for s in df['SYMBOL'].tolist()]
            print(f"Downloaded {len(syms)} NSE symbols")
            return syms
    except Exception as e:
        print(f"NSE download failed: {e}")
    return get_fallback_symbols()

def get_fallback_symbols():
    all_sector_stocks = []
    for stocks in SECTOR_MAP.values():
        all_sector_stocks.extend(stocks)
    extra = [
        "RELIANCE.NS","TCS.NS","HDFCBANK.NS","BHARTIARTL.NS","ICICIBANK.NS",
        "INFY.NS","SBIN.NS","HINDUNILVR.NS","ITC.NS","KOTAKBANK.NS",
        "LT.NS","AXISBANK.NS","BAJFINANCE.NS","MARUTI.NS","ASIANPAINT.NS",
        "TITAN.NS","SUNPHARMA.NS","NESTLEIND.NS","ULTRACEMCO.NS","WIPRO.NS",
        "ADANIENT.NS","ADANIPORTS.NS","HINDALCO.NS","TATASTEEL.NS","JSWSTEEL.NS",
        "TATAMOTORS.NS","BAJAJ-AUTO.NS","HEROMOTOCO.NS","GRASIM.NS","TATACONSUM.NS",
        "BPCL.NS","IOC.NS","ONGC.NS","COALINDIA.NS","POWERGRID.NS",
        "NTPC.NS","SBILIFE.NS","HDFCLIFE.NS","ICICIPRULI.NS","PIDILITIND.NS",
        "ZOMATO.NS","NYKAA.NS","IRCTC.NS","IRFC.NS","RVNL.NS",
        "HUDCO.NS","PFC.NS","RECLTD.NS","SJVN.NS","NHPC.NS",
        "SAIL.NS","NMDC.NS","MOIL.NS","NATIONALUM.NS","VEDL.NS",
        "AMBUJACEM.NS","ACC.NS","SHREECEM.NS","RAMCOCEM.NS","JKCEMENT.NS",
        "INDIGO.NS","BLUEDART.NS","CONCOR.NS","TVSMOTOR.NS","BHARATFORG.NS",
        "APOLLOTYRE.NS","MRF.NS","CEATLTD.NS","BALKRISIND.NS","SIEMENS.NS",
        "ABB.NS","HAVELLS.NS","CROMPTON.NS","POLYCAB.NS","THERMAX.NS",
        "BHEL.NS","HAL.NS","BEL.NS","BEML.NS","MAZAGON.NS",
        "QUESS.NS","SIS.NS","CDSL.NS","BSE.NS","MCX.NS",
        "DIXON.NS","AMBER.NS","VOLTAS.NS","BLUESTAR.NS","BATAINDIA.NS",
        "RELAXO.NS","TRENT.NS","PAGEIND.NS","KPRMILL.NS","VARDHMAN.NS",
        "PERSISTENT.NS","MPHASIS.NS","LTIM.NS","COFORGE.NS","KPITTECH.NS",
        "TATAELXSI.NS","TANLA.NS","NAUKRI.NS","CYIENT.NS","DEEPAKNTR.NS",
        "ATUL.NS","NAVINFLUOR.NS","FLUOROCHEM.NS","AARTI.NS","TATACHEM.NS",
        "GRANULES.NS","LAURUSLABS.NS","ERIS.NS","JBCHEPHARM.NS","AJANTPHARM.NS",
        "NEULANDLAB.NS","DMART.NS","COLPAL.NS","EMAMILTD.NS","MARICO.NS",
        "DABUR.NS","VBL.NS","RADICO.NS","MCDOWELL-N.NS","IEX.NS","LTTS.NS",
        "DLF.NS","GODREJPROP.NS","PRESTIGE.NS","BRIGADE.NS","SOBHA.NS",
        "PHOENIXLTD.NS","LINDEINDIA.NS","JSWINFRA.NS","IRB.NS","NCC.NS",
        "STARCEMENT.NS","KAJARIACER.NS","ROUTE.NS","MASTEK.NS","RITES.NS",
        "MIDHANI.NS","GARDENREACH.NS","NUVAMA.NS","360ONE.NS","ANGELONE.NS",
        "MOTILALOFS.NS","EQUITASBNK.NS","UTKARSHBNK.NS","SURYODAY.NS",
        "DCBBANK.NS","CITYUNIONBANK.NS","LICHOUSING.NS","INDIAGLYCO.NS",
        "TRIVENI.NS","BALRAMCHIN.NS","RENUKA.NS","CHAMBALFERT.NS","GNFC.NS",
        "GSFC.NS","RCF.NS","NFL.NS","RALLIS.NS","MANKIND.NS","GLENMARK.NS",
        "WOCKPHARMA.NS","STRIDES.NS","ALEMBICLTD.NS","APLLTD.NS","AARTIDRUGS.NS",
        "TIINDIA.NS","SUPRAJIT.NS","ENDURANCE.NS","SCHAEFFLER.NS","GRINDWELL.NS",
        "INOXWIND.NS","JSWENERGY.NS","WAAREEENER.NS","CENTURYPLY.NS","GREENPANEL.NS",
        "CREDITACC.NS","SPANDANA.NS","LICI.NS","DIVI.NS","PIRAMAL.NS",
        "BLS.NS","ENGINERSIN.NS","JIOFIN.NS","PARADEEP.NS","SUZLON.NS",
        "SYNGENE.NS","VMM.NS","OBEROIRLTY.NS","KOLTEPATIL.NS","SUNTECK.NS",
        "PNCINFRA.NS","KNRCON.NS","GMRINFRA.NS","FLUOROCHEM.NS","LALPATHLAB.NS",
        "METROPOLIS.NS","MAXHEALTH.NS","FORTIS.NS","NH.NS","KIMS.NS",
        "IPCALAB.NS","ABBOTINDIA.NS","ZYDUSLIFE.NS","NATCOPHARM.NS","GLAND.NS",
        "APOLLOHOSP.NS","DIVISLAB.NS","EICHERMOT.NS","MUTHOOTFIN.NS","BIOCON.NS",
        "TORNTPHARM.NS","AUROPHARMA.NS","ALKEM.NS","CANBK.NS","BANKBARODA.NS",
        "PNB.NS","UNIONBANK.NS","MAHABANK.NS","UCOBANK.NS","IDFCFIRSTB.NS",
        "RBLBANK.NS","BANDHANBNK.NS","FEDERALBNK.NS","KARURVYSYA.NS",
    ]
    return list(set(all_sector_stocks + extra))

# ── Nifty Options ─────────────────────────────────────────────
def get_nifty_options_rec(nifty_level, nifty_rsi, direction):
    lot = 75
    if direction in ["BULLISH","NEUTRAL"]:
        otype = "CALL (CE)"; mult = 1.005
        action = "BUY"
    else:
        otype = "PUT (PE)"; mult = 0.995
        action = "BUY"
    strike = round(nifty_level * mult / 50) * 50
    prem_low = round(nifty_level * 0.008)
    prem_high = round(nifty_level * 0.010)
    tgt = round(prem_low * 2)
    sl = round(prem_low * 0.5)
    exp = "Current weekly" if nifty_rsi > 58 else "Current monthly"
    return {
        "action":action,"type":otype,"strike":strike,"expiry":exp,
        "prem_low":prem_low,"prem_high":prem_high,
        "target":tgt,"sl":sl,"lot":lot,"capital":prem_low*lot,
    }

# ── HTML helpers ──────────────────────────────────────────────
def mood_color(m):
    if "BULLISH" in m: return "#27ae60"
    if "BEARISH" in m: return "#e74c3c"
    if "OVERBOUGHT" in m: return "#f39c12"
    return "#f39c12"

def sig_color(s):
    if "STRONG BUY" in s: return "#1e8449"
    if "BUY" in s: return "#27ae60"
    if "STRONG SELL" in s: return "#922b21"
    if "SELL" in s: return "#e74c3c"
    return "#f39c12"

def html_header(title, subtitle, color1="#2c3e50", color2="#3498db"):
    return f"""<div style='background:linear-gradient(135deg,{color1},{color2});
padding:20px;border-radius:12px;color:white;margin-bottom:20px'>
<h1 style='margin:0'>{title}</h1>
<p style='margin:5px 0 0;opacity:0.9'>{subtitle}</p></div>"""

def section_tip(text):
    return f"<div style='background:#f8f9fa;padding:12px;border-radius:8px;margin-bottom:10px;font-size:13px;color:#555'>💡 <b>What is this?</b> {text}</div>"

def table_start(headers):
    ths = "".join(f"<th>{h}</th>" for h in headers)
    return f"<table border='1' cellpadding='8' cellspacing='0' style='width:100%;border-collapse:collapse;font-size:13px'><tr style='background:#2c3e50;color:white'>{ths}</tr>"

def table_end():
    return "</table>"
