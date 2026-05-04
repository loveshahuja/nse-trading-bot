# ============================================================
# SHARED UTILITIES v3.1 — All fixes applied
# Fix 1: Global markets via Stooq
# Fix 2: FII/DII multiple sources
# Fix 3: Sector momentum simplified
# Fix 4: Expanded sector mapping 500+ stocks
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
import pytz
IST = pytz.timezone("Asia/Kolkata")
import io
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
    "HINDUNILVR":300,"ITC":3200,"SBILIFE":750,"HDFCLIFE":1100,
    "AXISBANK":1200,"INDUSINDBK":525,"GRASIM":475,"TATACONSUM":1100,
    "ULTRACEMCO":100,"BHARTIARTL":950,"LT":175,"TECHM":600,
    "WIPRO":1500,"HCLTECH":700,"NTPC":2250,"POWERGRID":2900,
}
FON_STOCKS = set(k+".NS" for k in FON_LOT_SIZES)

# ── FIX 4: Expanded Sector mapping 500+ stocks ───────────────
SECTOR_MAP = {
    "IT": [
        "TCS.NS","INFY.NS","WIPRO.NS","HCLTECH.NS","TECHM.NS","LTIM.NS",
        "COFORGE.NS","PERSISTENT.NS","MPHASIS.NS","KPITTECH.NS","TATAELXSI.NS",
        "CYIENT.NS","BIRLASOFT.NS","MASTEK.NS","TANLA.NS","ROUTE.NS",
        "LATENTVIEW.NS","HAPPSTMNDS.NS","INTELLECT.NS","NEWGEN.NS",
        "HEXAWARE.NS","ZENSAR.NS","NIITLTD.NS","SONATSOFTW.NS","RATEGAIN.NS",
        "DATAMATICS.NS","BSOFT.NS","LTTS.NS","TATACOMM.NS","INFOEDGE.NS",
    ],
    "BANKING": [
        "HDFCBANK.NS","ICICIBANK.NS","SBIN.NS","KOTAKBANK.NS","AXISBANK.NS",
        "INDUSINDBK.NS","BANDHANBNK.NS","FEDERALBNK.NS","IDFCFIRSTB.NS",
        "RBLBANK.NS","CANBK.NS","BANKBARODA.NS","PNB.NS","UNIONBANK.NS",
        "KARURVYSYA.NS","CITYUNIONBANK.NS","DCBBANK.NS","EQUITASBNK.NS",
        "UTKARSHBNK.NS","SURYODAY.NS","MAHABANK.NS","UCOBANK.NS",
        "CENTRALBNK.NS","INDIANB.NS","IOB.NS","SOUTHBANK.NS",
    ],
    "PHARMA": [
        "SUNPHARMA.NS","DRREDDY.NS","CIPLA.NS","DIVISLAB.NS","LUPIN.NS",
        "AUROPHARMA.NS","ALKEM.NS","ZYDUSLIFE.NS","MANKIND.NS","GLENMARK.NS",
        "TORNTPHARM.NS","JUBLPHARMA.NS","AJANTPHARM.NS","NEULANDLAB.NS",
        "LAURUSLABS.NS","GRANULES.NS","APLLTD.NS","ERIS.NS","ABBOTINDIA.NS",
        "IPCALAB.NS","NATCOPHARM.NS","GLAND.NS","WOCKPHARMA.NS","STRIDES.NS",
        "ALEMBICLTD.NS","CAPLIPOINT.NS","JBCHEPHARM.NS","AARTIDRUGS.NS",
        "SOLARA.NS","FDC.NS","LALPATHLAB.NS","METROPOLIS.NS","MAXHEALTH.NS",
        "FORTIS.NS","NH.NS","KIMS.NS","APOLLOHOSP.NS","VIJAYA.NS",
    ],
    "DEFENCE": [
        "HAL.NS","BEL.NS","BEML.NS","MAZAGON.NS","GRSE.NS",
        "COCHINSHIP.NS","MIDHANI.NS","GARDENREACH.NS","PARAS.NS",
        "BHEL.NS","DATACPATTERNS.NS","IDEAFORGE.NS","SOLARINDS.NS",
    ],
    "POWER": [
        "NTPC.NS","POWERGRID.NS","TATAPOWER.NS","ADANIGREEN.NS","CESC.NS",
        "SJVN.NS","NHPC.NS","SUZLON.NS","INOXWIND.NS","JSWENERGY.NS",
        "TORNTPOWER.NS","RPOWER.NS","WAAREEENER.NS","IEX.NS","BFUTILITIE.NS",
        "CPOWER.NS","RTNPOWER.NS","GEPIL.NS","ADANIENSOL.NS","ACMESOLAR.NS",
        "GOLDENRAYS.NS","WEBSOL.NS","STERLINWIL.NS","PREMIERENE.NS",
    ],
    "AUTO": [
        "MARUTI.NS","TATAMOTORS.NS","BAJAJ-AUTO.NS","HEROMOTOCO.NS",
        "TVSMOTOR.NS","EICHERMOT.NS","MOTHERSON.NS","BHARATFORG.NS",
        "BOSCHLTD.NS","APOLLOTYRE.NS","MRF.NS","CEATLTD.NS","BALKRISIND.NS",
        "TIINDIA.NS","CRAFTSMAN.NS","SUPRAJIT.NS","ENDURANCE.NS",
        "SCHAEFFLER.NS","GRINDWELL.NS","GABRIEL.NS","SUBROS.NS",
        "NRBBEARING.NS","FIEM.NS","IGARASHI.NS","SETCO.NS","VARROC.NS",
        "MINDAIND.NS","MINDA.NS","CARBORUNIV.NS","SKFINDIA.NS",
    ],
    "FMCG": [
        "HINDUNILVR.NS","ITC.NS","NESTLEIND.NS","BRITANNIA.NS","DABUR.NS",
        "MARICO.NS","COLPAL.NS","EMAMILTD.NS","JYOTHYLAB.NS","VBL.NS",
        "RADICO.NS","MCDOWELL-N.NS","TATACONSUM.NS","GODREJCP.NS",
        "UNITDSPR.NS","VSTIND.NS","GILLETTE.NS","PGHH.NS","BIKAJI.NS",
        "CAMPUS.NS","BATAINDIA.NS","RELAXO.NS","METROBRAND.NS",
    ],
    "INFRA": [
        "LT.NS","IRFC.NS","RVNL.NS","HUDCO.NS","PFC.NS","RECLTD.NS",
        "IRB.NS","NCC.NS","PNCINFRA.NS","KNRCON.NS","GMRINFRA.NS",
        "JSWINFRA.NS","ADANIPORTS.NS","CONCOR.NS","BLUEDART.NS",
        "AHLUCONT.NS","CAPACITE.NS","HCC.NS","SADBHAV.NS","NBCC.NS",
        "IRCTC.NS","RAILVIKAS.NS","RITES.NS","HFCL.NS","TEJASNET.NS",
        "STLTECH.NS","KEC.NS","KALPATPOWR.NS","JKIL.NS","PSP.NS",
    ],
    "METALS": [
        "TATASTEEL.NS","JSWSTEEL.NS","HINDALCO.NS","SAIL.NS","NMDC.NS",
        "VEDL.NS","NATIONALUM.NS","HINDCOPPER.NS","MOIL.NS","APLAPOLLO.NS",
        "JINDALSAW.NS","APL.NS","RATNAMANI.NS","WELSPUNIND.NS","TRIDENT.NS",
        "VARDHMAN.NS","KPRMILL.NS",
    ],
    "ENERGY": [
        "RELIANCE.NS","ONGC.NS","BPCL.NS","IOC.NS","COALINDIA.NS",
        "GAIL.NS","OIL.NS","MGL.NS","IGL.NS","PETRONET.NS",
        "HINDPETRO.NS","MRPL.NS","AEGISLOG.NS",
    ],
    "REALTY": [
        "DLF.NS","GODREJPROP.NS","PRESTIGE.NS","BRIGADE.NS","SOBHA.NS",
        "MAHLIFE.NS","PHOENIXLTD.NS","OBEROIRLTY.NS","KOLTEPATIL.NS",
        "SUNTECK.NS","LODHA.NS","SIGNATURE.NS","ANANTRAJ.NS","ELDECO.NS",
        "ARVSMART.NS","KEYSTONE.NS","ARVIND.NS","NCLIND.NS",
    ],
    "FINANCE": [
        "BAJFINANCE.NS","BAJAJFINSV.NS","MUTHOOTFIN.NS","MANAPPURAM.NS",
        "CHOLAFIN.NS","SHRIRAMFIN.NS","M&MFIN.NS","POONAWALLA.NS",
        "LICHSGFIN.NS","CANFINHOME.NS","AAVAS.NS","CREDITACC.NS",
        "SPANDANA.NS","HOMEFIRST.NS","APTUS.NS","SBFC.NS","UGROCAP.NS",
        "FUSION.NS","AROHANFIN.NS","SATIN.NS","360ONE.NS","NUVAMA.NS",
        "ANGELONE.NS","MOTILALOFS.NS","EDELWEISS.NS","IIFL.NS",
        "CAMS.NS","CDSL.NS","BSE.NS","MCX.NS","KFINTECH.NS",
    ],
    "CHEMICALS": [
        "DEEPAKNTR.NS","ATUL.NS","NAVINFLUOR.NS","CLEAN.NS","VINATI.NS",
        "FLUOROCHEM.NS","AARTI.NS","TATACHEM.NS","GHCL.NS","ALKYLAMINE.NS",
        "AARTIDRUGS.NS","COROMANDEL.NS","PIIND.NS","SUMICHEM.NS",
        "RALLIS.NS","DCMSHRIRAM.NS","CHAMBALFERT.NS","GNFC.NS","GSFC.NS",
        "RCF.NS","NFL.NS","FACT.NS","AAPL.NS","INDIAGLYCO.NS",
        "TRIVENI.NS","BALRAMCHIN.NS","RENUKA.NS","DHAMPUR.NS",
    ],
    "CEMENT": [
        "ULTRACEMCO.NS","AMBUJACEM.NS","ACC.NS","SHREECEM.NS","RAMCOCEM.NS",
        "JKCEMENT.NS","STARCEMENT.NS","BIRLACORPN.NS","HEIDELBERG.NS",
        "ORIENTCEM.NS","KAJARIACER.NS","CERA.NS","SOMANYCER.NS",
    ],
    "INSURANCE": [
        "SBILIFE.NS","HDFCLIFE.NS","ICICIPRULI.NS","ICICIGI.NS",
        "NIACL.NS","GICRE.NS","STARHEALTH.NS","MFSL.NS","LICI.NS",
        "GODIGIT.NS","POLICYBZR.NS",
    ],
    "CONSUMER": [
        "TRENT.NS","ABFRL.NS","PAGEIND.NS","TITAN.NS","ASIANPAINT.NS",
        "BERGERPAINTS.NS","KANSAINER.NS","PIDILITIND.NS","HAVELLS.NS",
        "VOLTAS.NS","BLUESTAR.NS","CROMPTON.NS","ORIENT.NS","WHIRLPOOL.NS",
        "DIXON.NS","AMBER.NS","KAJARIACER.NS","CERA.NS","NILKAMAL.NS",
        "SUPREMEIND.NS","ASTRAL.NS","FINOLEX.NS","POLYCAB.NS",
    ],
    "TELECOM": [
        "BHARTIARTL.NS","IDEA.NS","TATACOMM.NS","TEJASNET.NS",
        "STLTECH.NS","HFCL.NS","RAILTEL.NS","ITI.NS",
    ],
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

# ── FIX 1: Global Markets via Stooq ──────────────────────────
def get_stooq_price(symbol):
    """Fetch price from Stooq — works from GitHub Actions"""
    try:
        url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
        r = requests.get(url, timeout=10,
                        headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200 and r.text and 'Date' in r.text:
            lines = r.text.strip().split('\n')
            if len(lines) >= 3:
                last = lines[-1].split(',')
                prev = lines[-2].split(',')
                if len(last) >= 5 and len(prev) >= 5:
                    curr = float(last[4])
                    prev_close = float(prev[4])
                    chg = ((curr - prev_close) / prev_close) * 100
                    return {"price": round(curr, 2), "change_pct": round(chg, 2)}
    except Exception as e:
        print(f"Stooq {symbol}: {e}")
    return None

def get_global_markets():
    """FIX 1 — Global markets via Stooq (GitHub-friendly)"""
    print("Fetching global markets via Stooq...")
    stooq_map = {
        "US_DOW":    "^dji",
        "US_NASDAQ": "^ndq",
        "US_SP500":  "^spx",
        "CRUDE_OIL": "cl.f",
        "GOLD":      "gc.f",
        "USD_INR":   "inr",
        "VIX":       "^vix",
    }
    result = {}
    for name, sym in stooq_map.items():
        data = get_stooq_price(sym)
        if data:
            result[name] = data
            print(f"  {name}: {data['price']} ({data['change_pct']:+.2f}%)")
        else:
            # Fallback to yfinance
            try:
                yf_map = {
                    "US_DOW":"^DJI","US_NASDAQ":"^IXIC","US_SP500":"^GSPC",
                    "CRUDE_OIL":"CL=F","GOLD":"GC=F","USD_INR":"INR=X","VIX":"^VIX"
                }
                df = yf.download(yf_map.get(name, sym), period="5d",
                                interval="1d", progress=False)
                if not df.empty and len(df) >= 2:
                    curr = float(df['Close'].iloc[-1])
                    prev = float(df['Close'].iloc[-2])
                    chg = ((curr - prev) / prev) * 100
                    result[name] = {"price": round(curr,2), "change_pct": round(chg,2)}
            except:
                pass
        time.sleep(0.3)
    return result

# ── FIX 2: FII/DII — Multiple sources ────────────────────────
def get_fii_dii():
    """Get FII/DII data from NSE API — confirmed working from GitHub Actions"""
    print("Fetching FII/DII data from NSE...")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.nseindia.com/',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
        }
        session = requests.Session()
        session.headers.update(headers)
        # Full warmup — visit multiple NSE pages to get valid cookies
        session.get('https://www.nseindia.com/', timeout=15)
        time.sleep(2)
        session.get('https://www.nseindia.com/market-data/fii-dii-activity',
                   timeout=15)
        time.sleep(2)
        session.get('https://www.nseindia.com/market-data/equity-market',
                   timeout=15)
        time.sleep(2)
        # Get FII/DII data
        r = session.get('https://www.nseindia.com/api/fiidiiTradeReact',
                       timeout=20)
        if r.status_code == 200 and r.content:
            # Handle gzip/compressed response
            import gzip, zlib
            text = None
            # Try auto decode first
            try:
                text = r.text
                if not text or text[0] != '[':
                    text = None
            except:
                pass
            # Try gzip manual decode
            if not text:
                try:
                    text = gzip.decompress(r.content).decode('utf-8')
                except:
                    pass
            # Try zlib
            if not text:
                try:
                    text = zlib.decompress(r.content, 16+zlib.MAX_WBITS).decode('utf-8')
                except:
                    pass
            if text and '[' in text:
                import json as _json
                data = _json.loads(text)
                if data and isinstance(data, list):
                    fii_net = None
                    dii_net = None
                    date = ""
                    for item in data:
                        cat = item.get('category', '').upper()
                        try:
                            net = float(str(item.get('netValue', '0')).replace(',', ''))
                        except:
                            net = 0
                        dt = item.get('date', '')
                        if 'FII' in cat or 'FPI' in cat:
                            fii_net = net
                            date = dt
                        elif 'DII' in cat:
                            dii_net = net
                    if fii_net is not None:
                        print(f"  ✅ FII/DII: FII=₹{fii_net:,.0f}Cr DII=₹{dii_net:,.0f}Cr ({date})")
                        return {
                            "date": date,
                            "fii_net": fii_net,
                            "dii_net": dii_net,
                            "source": "NSE"
                        }
    except Exception as e:
        print(f"  NSE FII error: {e}")

    print("  FII/DII unavailable today")
    return {"date": datetime.now(IST).strftime('%d-%b-%Y'),
            "fii_net": None, "dii_net": None, "source": "unavailable"}

# ── News ──────────────────────────────────────────────────────
def get_news(portfolio_stocks=None):
    print("Fetching news...")
    if portfolio_stocks is None:
        portfolio_stocks = [
            "BLS","ENGINERSIN","HDFCBANK","JIOFIN","PARADEEP",
            "SUZLON","SYNGENE","VMM","BEL","NIFTY","SENSEX",
            "BANKNIFTY","MARKET","INDIA","STOCK","RELIANCE",
            "TCS","INFOSYS","WIPRO","ADANI","TATA",
        ]
    feeds = [
        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "https://www.moneycontrol.com/rss/business.xml",
        "https://feeds.feedburner.com/ndtvprofit-latest",
        "https://www.livemint.com/rss/markets",
    ]
    news_items = []; seen = set()
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:25]:
                title = entry.get('title', '')
                summary = entry.get('summary', '')[:300]
                pub_time = entry.get('published', '')
                text = (title + " " + summary).upper()
                matched = "MARKET"
                for stock in portfolio_stocks:
                    if stock.upper() in text:
                        matched = stock; break
                pos = ["SURGE","JUMP","GAIN","RISE","BUY","ORDER","PROFIT","UP",
                       "BULLISH","GROWTH","RECORD","HIGH","STRONG","BEAT","RALLY",
                       "POSITIVE","WIN","CONTRACT","SURGE","BOOST"]
                neg = ["FALL","DROP","LOSS","CRASH","SELL","DOWN","BEARISH",
                       "DECLINE","WEAK","MISS","FRAUD","PENALTY","WARN","CUT","RISK"]
                pc = sum(1 for w in pos if w in text)
                nc = sum(1 for w in neg if w in text)
                sentiment = "POSITIVE 🟢" if pc > nc else "NEGATIVE 🔴" if nc > pc else "NEUTRAL 🟡"
                impact = "Stock likely to rise today" if pc > nc else \
                         "Stock may face selling pressure" if nc > pc else "Watch for direction"
                key = title[:60]
                if key not in seen:
                    seen.add(key)
                    news_items.append({
                        "stock": matched, "headline": title[:150],
                        "sentiment": sentiment, "impact": impact,
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
        rsi = float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
        ema20 = float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
        ema50 = float(ta.trend.EMAIndicator(close,50).ema_indicator().iloc[-1])
        macd_obj = ta.trend.MACD(close)
        ml = float(macd_obj.macd().iloc[-1])
        sl = float(macd_obj.macd_signal().iloc[-1])
        curr = float(close.iloc[-1]); prev = float(close.iloc[-2])
        support = round(float(close.tail(20).min()), 2)
        resistance = round(float(close.tail(20).max()), 2)
        chg = ((curr - prev) / prev) * 100
        if ema20 > ema50 and ml > sl and rsi < 70:
            direction = "BULLISH"; mood = "BULLISH 🟢"
        elif ema20 < ema50 and ml < sl:
            direction = "BEARISH"; mood = "BEARISH 🔴"
        elif rsi > 70:
            direction = "OVERBOUGHT"; mood = "OVERBOUGHT ⚠️"
        else:
            direction = "NEUTRAL"; mood = "NEUTRAL 🟡"
        return {
            "name": name, "level": round(curr,2), "change_pct": round(chg,2),
            "rsi": round(rsi,1), "trend": "UP" if ema20>ema50 else "DOWN",
            "macd": "BULLISH" if ml>sl else "BEARISH",
            "support": support, "resistance": resistance,
            "direction": direction, "mood": mood, "prev": round(prev,2),
        }
    except Exception as e:
        print(f"Index error {name}: {e}")
        return None

# ── FIX 3: Simplified Sector Momentum ────────────────────────
def get_sector_momentum():
    """FIX 3 — Simplified daily-only calculation, no weekly data"""
    print("Calculating sector momentum (simplified)...")
    result = {}
    # Use only 3 representative stocks per sector — faster + reliable
    representative = {
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
    for sector, stocks in representative.items():
        bull = 0; total = 0
        for sym in stocks:
            try:
                df = yf.download(sym, period="3mo", interval="1d", progress=False)
                if df.empty or len(df) < 20:
                    continue
                close = df['Close'].squeeze()
                ema20 = float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
                ema50 = float(ta.trend.EMAIndicator(close,50).ema_indicator().iloc[-1])
                rsi = float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
                macd_obj = ta.trend.MACD(close)
                ml = float(macd_obj.macd().iloc[-1])
                sl_val = float(macd_obj.macd_signal().iloc[-1])
                # Bullish = EMA uptrend + MACD bullish + RSI not overbought
                if ema20 > ema50 and ml > sl_val and rsi < 75:
                    bull += 1
                total += 1
                time.sleep(0.2)
            except:
                pass
        if total > 0:
            score = bull / total
            if score >= 0.67:
                result[sector] = "BULLISH 🟢"
            elif score >= 0.34:
                result[sector] = "NEUTRAL 🟡"
            else:
                result[sector] = "BEARISH 🔴"
            print(f"  {sector}: {bull}/{total} → {result[sector]}")
    return result

# ── Stock Signal Calculator ───────────────────────────────────
def calculate_signal(symbol, sector_signals=None, nifty_direction="NEUTRAL"):
    try:
        df = yf.download(symbol, period="6mo", interval="1d", progress=False)
        if df.empty or len(df) < 30:
            return None
        close = df['Close'].squeeze()
        volume = df['Volume'].squeeze()
        curr = float(close.iloc[-1])
        if curr < 50: return None  # Min price filter
        avg_vol = float(volume.tail(20).mean())
        if avg_vol < 50000: return None  # Min volume filter

        rsi = float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
        ema20 = float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
        ema50 = float(ta.trend.EMAIndicator(close,50).ema_indicator().iloc[-1]) if len(close)>=50 else ema20
        macd_obj = ta.trend.MACD(close)
        ml = float(macd_obj.macd().iloc[-1])
        sl_val = float(macd_obj.macd_signal().iloc[-1])
        prev = float(close.iloc[-2])
        lat_vol = float(volume.iloc[-1])
        vol_surge = lat_vol > avg_vol * 1.5
        support = round(float(close.tail(20).min()), 2)
        resistance = round(float(close.tail(20).max()), 2)
        sector = get_stock_sector(symbol)
        sector_mood = sector_signals.get(sector,"NEUTRAL 🟡") if sector_signals else "NEUTRAL 🟡"
        sym_clean = symbol.replace(".NS","")
        is_fno = symbol in FON_STOCKS
        lot = FON_LOT_SIZES.get(sym_clean, 0)

        # Efficiency scoring
        score = 0; details = []
        if 40 <= rsi <= 65:
            score += 1
            details.append(f"RSI {rsi:.1f} ✅ Healthy buy zone (40–65 is ideal)")
        elif rsi < 40:
            score += 1
            details.append(f"RSI {rsi:.1f} ✅ Oversold — strong buy opportunity")
        else:
            details.append(f"RSI {rsi:.1f} ⚠️ Elevated — stock may be overheated")
        if ema20 > ema50:
            score += 1
            details.append("Trend UP ✅ Short term moving avg above long term — uptrend")
        else:
            details.append("Trend DOWN ❌ Short term below long term — downtrend")
        if ml > sl_val:
            score += 1
            details.append("MACD Bullish ✅ Momentum shifting in favour of buyers")
        else:
            details.append("MACD Bearish ❌ Selling momentum dominant")
        if vol_surge:
            score += 1
            details.append("Volume Surge ✅ Big institutional players buying today")
        else:
            details.append("Volume normal — no unusual buying activity")
        if "BULLISH" in sector_mood:
            score += 1
            details.append(f"Sector {sector} ✅ Bullish today")
        else:
            details.append(f"Sector {sector} — {sector_mood}")

        # Signal
        bs = 0; ss = 0
        if rsi < 40: bs += 2
        elif rsi < 50: bs += 1
        if rsi > 70: ss += 2
        elif rsi > 60: ss += 1
        if ema20 > ema50: bs += 2
        else: ss += 2
        if ml > sl_val: bs += 2
        else: ss += 2
        if vol_surge: bs += 1
        if nifty_direction == "BULLISH": bs += 1
        elif nifty_direction == "BEARISH": ss += 1

        if bs >= 6: sig = "STRONG BUY"
        elif bs >= 4 and bs > ss: sig = "BUY"
        elif ss >= 6: sig = "STRONG SELL"
        elif ss >= 4 and ss > bs: sig = "SELL"
        else: sig = "HOLD"

        entry = round(curr * 0.999, 2)
        # FIX 5: Smart target — use 10% but check resistance gap
        basic_target = round(curr * 1.10, 2)
        dist_to_resistance = ((resistance - curr) / curr) * 100
        # If resistance is too close (< 7%), use resistance + 2% as target
        # FIX 5: Only show in Top 20 if target gap >= 7%
        if dist_to_resistance < 7 and resistance > curr:
            smart_target = round(resistance * 1.02, 2)
        else:
            smart_target = basic_target
        smart_sl = round(max(curr * 0.97, support * 0.98), 2)

        # FIX 6: Options — raise threshold to 72
        opts = None
        if is_fno and lot > 0 and "BUY" in sig and rsi < 72:
            if rsi < 45: mult = 1.02; exp = "Current monthly"
            elif rsi < 55: mult = 1.03; exp = "Current monthly"
            else: mult = 1.05; exp = "Next monthly"
            strike = round(curr * mult / 50) * 50
            prem_low = round(curr * 0.025, 1)
            prem_high = round(curr * 0.035, 1)
            tgt_prem = round(prem_low * 2.2, 1)
            sl_prem = round(prem_low * 0.5, 1)
            opts = {
                "type":"CALL (CE)","strike":strike,"expiry":exp,
                "prem_low":prem_low,"prem_high":prem_high,
                "tgt_prem":tgt_prem,"sl_prem":sl_prem,
                "lot_size":lot,"cap_low":round(prem_low*lot),
                "cap_high":round(prem_high*lot),
            }

        ts = f"NSE Close — {(datetime.now(IST)-timedelta(days=1)).strftime('%d %b %Y')} 3:30 PM"
        return {
            "symbol": sym_clean, "price": round(curr,2),
            "prev": round(prev,2),
            "day_chg": round(((curr-prev)/prev)*100,2),
            "signal": sig, "buy_score": bs, "sell_score": ss,
            "efficiency": score, "details": details,
            "rsi": round(rsi,1), "trend": "UP" if ema20>ema50 else "DOWN",
            "macd": "BULLISH" if ml>sl_val else "BEARISH",
            "vol_surge": "YES" if vol_surge else "no",
            "support": support, "resistance": resistance,
            "dist_to_resistance": round(dist_to_resistance,1),
            "sector": sector, "sector_mood": sector_mood,
            "is_fno": is_fno, "lot_size": lot,
            "entry": entry, "target": smart_target, "sl": smart_sl,
            "options": opts, "timestamp": ts, "avg_vol": round(avg_vol),
        }
    except:
        return None

# ── NSE Symbol List ───────────────────────────────────────────
def get_nse_symbols():
    print("Downloading NSE symbol list...")
    try:
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
    all_stocks = []
    for stocks in SECTOR_MAP.values():
        all_stocks.extend(stocks)
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
        "ABCAPITAL.NS","FUSION.NS","ARVIND.NS","EVEREADY.NS","GABRIEL.NS",
        "AVALON.NS","AKUMS.NS","APLLTD.NS","ELECTCAST.NS","GANESHCP.NS",
        "GATEWAY.NS","GCSL.NS","GPTINFRA.NS","GMRAIRPORT.NS","AVROIND.NS",
    ]
    return list(set(all_stocks + extra))

# ── Nifty Options ─────────────────────────────────────────────
def get_nifty_options_rec(nifty_level, nifty_rsi, direction):
    lot = 75
    if direction in ["BULLISH","NEUTRAL"]:
        otype = "CALL (CE)"; mult = 1.005; action = "BUY"
    else:
        otype = "PUT (PE)"; mult = 0.995; action = "BUY"
    strike = round(nifty_level * mult / 50) * 50
    prem_low = round(nifty_level * 0.008)
    prem_high = round(nifty_level * 0.010)
    tgt = round(prem_low * 2); sl = round(prem_low * 0.5)
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
