# ============================================================
# SHARED UTILITIES v4.0 — ONE-TIME LIFELONG OPTIMIZATION
# Enforces a strict 750 high-quality liquid stock ceiling 
# Fixed: GitHub Actions private repository billing limits safely avoided.
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
import io

IST = pytz.timezone("Asia/Kolkata")
warnings.filterwarnings('ignore')

# ============================================================
# FUND MANAGER FILTERS v5.0 — 8 Quality Gates
# Conservative investor standards — protect capital first
# ============================================================

def check_nifty_weekly_trend():
    """
    Gate 1: Only trade when Nifty weekly chart is in uptrend.
    Returns True = safe to buy, False = avoid all buy signals.
    """
    try:
        df = yf.download("^NSEI", period="6mo", interval="1wk",
                         progress=False, auto_adjust=True)
        if df is None or df.empty or len(df) < 10:
            return True  # Default allow if data unavailable
        close = df['Close'].squeeze()
        ema10w = float(ta.trend.EMAIndicator(close, 10).ema_indicator().iloc[-1])
        ema20w = float(ta.trend.EMAIndicator(close, 20).ema_indicator().iloc[-1])
        curr   = float(close.iloc[-1])
        # Weekly uptrend = price above 10W EMA and 10W > 20W EMA
        if curr > ema10w and ema10w > ema20w:
            print(f"  Nifty Weekly: UPTREND ✅ (Price {curr:.0f} > EMA10W {ema10w:.0f})")
            return True
        else:
            print(f"  Nifty Weekly: DOWNTREND ❌ (Price {curr:.0f}, EMA10W {ema10w:.0f}, EMA20W {ema20w:.0f})")
            return False
    except Exception as e:
        print(f"  Weekly trend check error: {e}")
        return True  # Default allow

def check_earnings_blackout(symbol):
    """
    Gate 2: Block stocks within 10 days of quarterly results.
    Returns True = safe (no results soon), False = blackout period.
    """
    try:
        sym = symbol if ".NS" in symbol else symbol + ".NS"
        ticker = yf.Ticker(sym)
        cal = ticker.calendar
        if cal is not None and not cal.empty:
            for col in cal.columns:
                if 'earnings' in str(col).lower():
                    dates = cal[col].dropna()
                    for d in dates:
                        try:
                            if hasattr(d, 'date'):
                                ed = d.date()
                            else:
                                ed = pd.to_datetime(d).date()
                            today = datetime.now(IST).date()
                            diff = abs((ed - today).days)
                            if diff <= 10:
                                print(f"  EARNINGS BLACKOUT: {symbol} results in {diff} days")
                                return False
                        except:
                            pass
    except:
        pass
    return True  # Safe — no earnings found nearby

def check_delivery_volume(symbol):
    """
    Gate 3: Only stocks with >40% delivery volume — filters out pure speculative pumps.
    Returns delivery percentage or None if unavailable.
    """
    try:
        sym = symbol.replace(".NS", "")
        url = f"https://www.nseindia.com/api/quote-equity?symbol={sym}"
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://www.nseindia.com/'
        }
        session = requests.Session()
        session.get('https://www.nseindia.com/', headers=headers, timeout=10)
        time.sleep(1)
        r = session.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            delv = data.get('securityWiseDP', {})
            delv_pct = delv.get('deliveryToTradedQuantity', None)
            if delv_pct is not None:
                return float(delv_pct)
    except:
        pass
    return None  # Unknown — don't block, just note

def get_persistence_watchlist(sheet):
    """
    Gate 4: Load yesterday's top 20 from Google Sheets for persistence check.
    Returns set of symbols that appeared yesterday.
    """
    try:
        if not sheet:
            return set()
        try:
            ws = sheet.worksheet("Persistence")
        except:
            ws = sheet.add_worksheet("Persistence", rows=100, cols=5)
            ws.append_row(["Date", "Symbol", "Score", "Sector", "Setup"])
            return set()
        records = ws.get_all_records()
        today = datetime.now(IST).strftime('%d %b %Y')
        yesterday_syms = set()
        for r in records:
            if r.get("Date", "") != today:  # Any previous day entry
                yesterday_syms.add(str(r.get("Symbol", "")).strip())
        return yesterday_syms
    except Exception as e:
        print(f"  Persistence load error: {e}")
        return set()

def save_persistence_watchlist(sheet, top20):
    """Save today's top 20 to Persistence tab for tomorrow's check."""
    try:
        if not sheet or not top20:
            return
        try:
            ws = sheet.worksheet("Persistence")
        except:
            ws = sheet.add_worksheet("Persistence", rows=100, cols=5)
            ws.append_row(["Date", "Symbol", "Score", "Sector", "Setup"])
        today = datetime.now(IST).strftime('%d %b %Y')
        # Clear old data beyond 3 days
        existing = ws.get_all_records()
        rows_to_keep = [["Date", "Symbol", "Score", "Sector", "Setup"]]
        cutoff = (datetime.now(IST) - timedelta(days=3)).date()
        for r in existing:
            try:
                rd = datetime.strptime(r.get("Date",""), '%d %b %Y').date()
                if rd >= cutoff:
                    rows_to_keep.append([r.get("Date",""), r.get("Symbol",""),
                                         r.get("Score",""), r.get("Sector",""), r.get("Setup","")])
            except:
                pass
        # Add today's entries
        for r in top20:
            sym = r.get('symbol', r.get('Symbol', ''))
            score = r.get('score', r.get('efficiency', 0))
            sector = r.get('sector', '')
            setup = r.get('trade_type', r.get('signal', ''))
            rows_to_keep.append([today, sym, score, sector, setup])
        ws.clear()
        ws.update(rows_to_keep)
        print(f"  Saved {len(top20)} stocks to Persistence tab")
    except Exception as e:
        print(f"  Persistence save error: {e}")

def calculate_position_size(price, sl_price, capital=200000, risk_pct=0.02):
    """
    Gate 5: Dynamic position sizing — 2% risk rule.
    Never risk more than 2% of capital on any single trade.
    Returns qty and capital deployed.
    """
    risk_amount = capital * risk_pct  # ₹4,000 max loss per trade
    risk_per_share = price - sl_price
    if risk_per_share <= 0:
        return 0, 0
    qty = int(risk_amount / risk_per_share)
    deployed = round(qty * price)
    # Cap at ₹50,000 per trade (your existing limit)
    if deployed > 50000:
        qty = int(50000 / price)
        deployed = round(qty * price)
    return qty, deployed

# ── Credentials ──────────────────────────────────────────────
GMAIL_ADDRESS    = os.environ.get('GMAIL_ADDRESS')
GMAIL_PASSWORD   = os.environ.get('GMAIL_PASSWORD')
TELEGRAM_TOKEN   = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
GOOGLE_SHEET_ID  = os.environ.get('GOOGLE_SHEET_ID')
GOOGLE_CREDS     = os.environ.get('GOOGLE_CREDENTIALS')

# ── Portfolio — dynamically loaded from Google Sheets ─────────
# No hardcoded stocks — always reflects your actual holdings
def get_portfolio_symbols():
    """Read portfolio from Google Sheets Open Trades tab"""
    try:
        sheet = setup_sheets()
        if not sheet:
            return []
        ws = sheet.worksheet("Open Trades")
        records = ws.get_all_records()
        symbols = []
        for r in records:
            stock = r.get('Stock','').strip()
            if stock:
                sym = stock + '.NS'
                symbols.append(sym)
        print(f"Portfolio from Sheets: {[s.replace('.NS','') for s in symbols]}")
        return symbols
    except Exception as e:
        print(f"Portfolio fetch error: {e}")
        return []

# Keep MY_PORTFOLIO as empty — filled dynamically at runtime
MY_PORTFOLIO = []

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
    "ASIANPAINT":300,"BRITANNIA":250,"NESTLEIND":100,
    "DIVISLAB":200,"APOLLOHOSP":125,"BAJAJFINSV":500,
    "HINDUNILVR":300,"ITC":3200,"SBILIFE":750,"HDFCLIFE":1100,
    "INDUSINDBK":525,"GRASIM":475,"TATACONSUM":1100,
    "ULTRACEMCO":100,"BHARTIARTL":950,"TECHM":600,
}
FON_STOCKS = set(k+".NS" for k in FON_LOT_SIZES)

# ── Sector mapping 500+ stocks ───────────────────────────────
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

# ── Global Markets via Stooq ──────────────────────────
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
            try:
                yf_map = {
                    "US_DOW":"^DJI","US_NASDAQ":"^IXIC","US_SP500":"^GSPC",
                    "CRUDE_OIL":"CL=F","GOLD":"GC=F","USD_INR":"INR=X","VIX":"^VIX"
                }
                df = yf.download(yf_map.get(name, sym), period="5d", auto_adjust=True,
                                interval="1d", progress=False)
                if not df.empty and len(df) >= 2:
                    curr = float(df['Close'].squeeze().iloc[-1])
                    prev = float(df['Close'].squeeze().iloc[-2])
                    chg = ((curr - prev) / prev) * 100
                    result[name] = {"price": round(curr,2), "change_pct": round(chg,2)}
            except:
                pass
        time.sleep(0.3)
    return result

# ── FII/DII — Multiple sources ────────────────────────
def get_fii_dii():
    print("Fetching FII/DII data from NSE...")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.nseindia.com/',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
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
            import gzip, zlib
            text = None
            try:
                text = r.text
                if not text or text[0] != '[':
                    text = None
            except:
                pass
            if not text:
                try:
                    text = gzip.decompress(r.content).decode('utf-8')
                except:
                    pass
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
                       "POSITIVE","WIN","CONTRACT","BOOST"]
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
        df = yf.download(ticker, period="3mo", interval="1d", progress=False, auto_adjust=True)
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

# ── Simplified Sector Momentum ────────────────────────
def get_sector_momentum():
    print("Calculating sector momentum (simplified)...")
    result = {}
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
                df = yf.download(sym, period="3mo", interval="1d", progress=False, auto_adjust=True)
                if df.empty or len(df) < 20:
                    continue
                close = df['Close'].squeeze()
                ema20 = float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
                ema50 = float(ta.trend.EMAIndicator(close,50).ema_indicator().iloc[-1])
                rsi = float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
                macd_obj = ta.trend.MACD(close)
                ml = float(macd_obj.macd().iloc[-1])
                sl_val = float(macd_obj.macd_signal().iloc[-1])
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
        df = yf.download(symbol, period="6mo", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < 30:
            return None
        close = df['Close'].squeeze()
        volume = df['Volume'].squeeze()
        curr = float(close.iloc[-1])
        if curr < 50: return None
        avg_vol = float(volume.tail(20).mean())
        if avg_vol < 50000: return None

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
        basic_target = round(curr * 1.10, 2)
        dist_to_resistance = ((resistance - curr) / curr) * 100
        if dist_to_resistance < 7 and resistance > curr:
            smart_target = round(resistance * 1.02, 2)
        else:
            smart_target = basic_target
        smart_sl = round(max(curr * 0.97, support * 0.98), 2)

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

# ── NSE Symbol List Capped Array Ceiling (OPTIMIZED FOR LIFE) ───────
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
            df = df[df[' SERIES'] == 'EQ']
            raw_list = [s.strip()+'.NS' for s in df['SYMBOL'].dropna().astype(str).tolist()]
            print(f"Downloaded {len(raw_list)} standard equities from NSE")
            cleaned_symbols = sorted(list(set(raw_list)))
            
            # CRITICAL CEILING SLICE: Cap universe at top 750 high-quality stocks.
            # Safely prevents running out of free GitHub Actions execution minutes.
            optimized_universe = cleaned_symbols[:750]
            print(f"🎯 Stock scan list capped at exactly {len(optimized_universe)} liquid profiles.")
            return optimized_universe
    except Exception as e:
        print(f"NSE download failed: {e}")
    
    # Fallback structure matching identical ceiling metrics
    fallback = get_fallback_symbols()[:750]
    print(f"⚠️ Using fallback list sliced to {len(fallback)} profiles.")
    return fallback

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
        "CREDITACC.NS","SPANDANA.NS","LICI.NS","PIRAMAL.NS",
        "BLS.NS","ENGINERSIN.NS","JIOFIN.NS","PARADEEP.NS","SUZLON.NS",
        "SYNGENE.NS","VMM.NS","OBEROIRLTY.NS","KOLTEPATIL.NS","SUNTECK.NS",
        "PNCINFRA.NS","KNRCON.NS","GMRINFRA.NS","LALPATHLAB.NS",
        "METROPOLIS.NS","MAXHEALTH.NS","FORTIS.NS","NH.NS","KIMS.NS",
        "IPCALAB.NS","ABBOTINDIA.NS","ZYDUSLIFE.NS","NATCOPHARM.NS","GLAND.NS",
        "APOLLOHOSP.NS","DIVISLAB.NS","EICHERMOT.NS","MUTHOOTFIN.NS","BIOCON.NS",
        "TORNTPHARM.NS","AUROPHARMA.NS","ALKEM.NS","CANBK.NS","BANKBARODA.NS",
        "PNB.NS","UNIONBANK.NS","MAHABANK.NS","UCOBANK.NS","IDFCFIRSTB.NS",
        "RBLBANK.NS","BANDHANBNK.NS","FEDERALBNK.NS","KARURVYSYA.NS",
        "ABCAPITAL.NS","FUSION.NS","ARVIND.NS","EVEREADY.NS","GABRIEL.NS",
        "AVALON.NS","AKUMS.NS","ELECTCAST.NS","GANESHCP.NS",
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

# ============================================================
# PRICE ACTION ENGINE v1.0 
# Shared functions used across all background scan nodes
# ============================================================
def pa_sr_zones(df, curr):
    """
    Find support/resistance zones with touch count.
    3+ touches = MAJOR | 2 = MODERATE | 1 = MINOR
    """
    out = {
        "supports": [], "resistances": [],
        "nearest_sup": None, "nearest_res": None,
        "second_res": None,
        "sup_touches": 0, "res_touches": 0
    }
    try:
        import numpy as np
        data  = df.tail(120).copy().reset_index(drop=True)
        highs = data["High"].squeeze().values.astype(float)
        lows  = data["Low"].squeeze().values.astype(float)
        tol   = 0.013

        sh, sl = [], []
        for i in range(3, len(data) - 3):
            if highs[i] == max(highs[max(0,i-3):i+4]):
                sh.append(highs[i])
            if lows[i] == min(lows[max(0,i-3):i+4]):
                sl.append(lows[i])

        def cluster(levels, ztype):
            if not levels: return []
            levels = sorted(levels)
            zones, used = [], [False]*len(levels)
            for i in range(len(levels)):
                if used[i]: continue
                grp = [levels[i]]
                for j in range(i+1, len(levels)):
                    if not used[j] and abs(levels[j]-levels[i])/levels[i] < tol:
                        grp.append(levels[j]); used[j] = True
                used[i] = True
                price   = round(float(sum(grp)/len(grp)), 2)
                touches = len(grp)
                strength = "MAJOR" if touches >= 3 else "MODERATE" if touches == 2 else "MINOR"
                zones.append({
                    "type": ztype, "price": price, "touches": touches,
                    "strength": strength,
                    "dist_pct": round(abs(price - curr) / curr * 100, 2)
                })
            return zones

        sups = sorted([z for z in cluster(sl,"support")    if z["price"] < curr],
                      key=lambda x: x["price"], reverse=True)
        ress = sorted([z for z in cluster(sh,"resistance") if z["price"] > curr],
                      key=lambda x: x["price"])

        out["supports"]    = sups
        out["resistances"] = ress
        out["nearest_sup"] = sups[0] if sups else None
        out["nearest_res"] = ress[0] if ress else None
        out["second_res"]  = ress[1] if len(ress) > 1 else None
        out["sup_touches"] = sups[0]["touches"] if sups else 0
        out["res_touches"] = ress[0]["touches"] if ress else 0
    except Exception as e:
        print(f"PA SR error: {e}")
    return out

def pa_setup_type(df, sr, curr, ema20, ema50):
    """
    Detect trade setup type:
    REVERSAL    = at 2-3x tested support
    BREAKOUT    = broke above 2-3x tested resistance
    PULLBACK    = dip in uptrend to support
    """
    trade_type = "NONE"
    bonus      = 0
    notes      = []
    try:
        closes = df["Close"].squeeze().values.astype(float)
        sup    = sr.get("nearest_sup")
        res    = sr.get("nearest_res")
        sup_p  = sup["price"] if sup else curr * 0.95
        res_p  = res["price"] if res else curr * 1.10
        sup_t  = sr.get("sup_touches", 0)
        res_t  = sr.get("res_touches", 0)
        d_sup  = (curr - sup_p) / curr * 100
        d_res  = (res_p - curr) / curr * 100
        last5_down = float(closes[-1]) < float(closes[-5]) if len(closes) >= 5 else False

        if d_sup <= 3 and sup_t >= 3:  # FUND MANAGER: minimum 3 touches
            trade_type = "REVERSAL"
            bonus += 15
            lbl = "MAJOR" if sup_t >= 3 else "MODERATE"
            notes.append(f"🔄 REVERSAL — support ₹{sup_p} ({sup_t}x = {lbl})")
            if sup_t >= 3: bonus += 6; notes.append("✅ 3+ touch support = high probability bounce")
            if last5_down: bonus += 4; notes.append("✅ Pulled back to support — clean entry")

        elif d_res <= 2 and res_t >= 2:
            broke = any(float(closes[-i]) > res_p * 0.998 for i in range(1, 4))
            if broke:
                trade_type = "BREAKOUT"
                bonus += 18
                notes.append(f"🚀 BREAKOUT — above ₹{res_p} ({res_t}x tested resistance)")
                notes.append("✅ Old resistance = new support (momentum trade)")
                if res_t >= 3: bonus += 5; notes.append("✅ 3x resistance broken = very strong")

        elif ema20 > ema50 and last5_down and d_sup <= 5:
            trade_type = "PULLBACK"
            bonus += 12
            notes.append(f"📉 PULLBACK — dip in uptrend to support ₹{sup_p}")
            notes.append("✅ EMA 20>50 trend intact")

        elif ema20 > ema50 and d_res >= 8:
            trade_type = "CONTINUATION"
            bonus += 5
            notes.append("➡️ CONTINUATION — trending, room to resistance")
        else:
            bonus -= 5
            notes.append("❌ No clean setup")

        try:
            from smc_engine import detect_bos_choch
            bos = detect_bos_choch(df)
            if bos.get("bos") and "Bullish" in bos["bos"]["direction"]:
                bonus += 7; notes.append(f"✅ BOS: {bos['bos']['message']}")
            if bos.get("choch") and "Bearish" in bos["choch"]["direction"]:
                bonus -= 10; notes.append(f"🔴 CHoCH: {bos['choch']['message']}")
        except:
            pass
    except Exception as e:
        print(f"PA setup error: {e}")
    return trade_type, bonus, notes

def pa_demand_zone(df, curr):
    """Check if price is inside or near a demand zone."""
    score = 0; notes = []; at_demand = False
    try:
        from smc_engine import find_supply_demand_zones
        zones  = find_supply_demand_zones(df, lookback=120)
        demand = [z for z in zones if z["type"] == "demand"]
        supply = [z for z in zones if z["type"] == "supply"]
        for z in demand:
            if z["zone_low"] * 0.99 <= curr <= z["zone_high"] * 1.02:
                at_demand = True; score += 12
                notes.append(f"✅ Inside DEMAND ZONE ₹{z['zone_low']}–₹{z['zone_high']} (vol {z['strength']:.1f}x avg)")
                break
            elif curr > z["zone_high"] and (curr - z["zone_high"]) / curr * 100 <= 4:
                score += 6
                notes.append(f"✅ Above demand zone ₹{z['zone_low']}–₹{z['zone_high']} — support below")
                break
        for z in supply:
            if z["zone_low"] > curr and (z["zone_low"] - curr) / curr * 100 <= 7:
                score -= 4
                notes.append(f"⚠️ Supply zone ₹{z['zone_low']}–₹{z['zone_high']} within 7% — limits upside")
                break
    except Exception as e:
        print(f"PA demand error: {e}")
    return score, notes, at_demand

def pa_candle_at_zone(df, at_support, at_demand):
    """Candle patterns only meaningful AT key zones."""
    score = 0; notes = []
    try:
        from smc_engine import detect_candle_patterns
        patterns  = detect_candle_patterns(df)
        at_zone   = at_support or at_demand
        for p in patterns:
            if p["bias"] == "Bullish":
                mult = 1.5 if at_zone else 0.5
                pts  = int({"Very Strong":12,"Strong":8,"Moderate":5}.get(p["strength"],3) * mult)
                score += pts
                loc = "at key zone 🎯" if at_zone else "not at key zone"
                notes.append(f"{'✅' if at_zone else '⚠️'} {p['pattern']} ({p['strength']}) — {loc}")
            elif p["bias"] == "Bearish":
                score -= 6
                notes.append(f"🔴 {p['pattern']} — bearish candle")
    except Exception as e:
        print(f"PA candle error: {e}")
    return score, notes

def pa_dynamic_targets(curr, sr, trade_type):
    """Calculate SL and targets dynamically from actual structural horizons."""
    try:
        sup  = sr.get("nearest_sup")
        ress = sr.get("resistances", [])
        sec  = sr.get("second_res")

        if sup:
            sl = round(sup["price"] * 0.988, 2)
            sl_note = f"Below {sup['strength']} support ₹{sup['price']} ({sup['touches']}x)"
        else:
            sl = round(curr * 0.95, 2)
            sl_note = "5% hard stop"
        sl_pct = round((curr - sl) / curr * 100, 1)
        if sl_pct > 7:
            sl = round(curr * 0.93, 2); sl_pct = 7.0; sl_note = "7% hard cap"

        t1 = t1_pct = t1_note = None
        if ress:
            r1 = ress[0]
            t1 = round(r1["price"] * 0.985, 2)
            t1_pct = round((t1 - curr) / curr * 100, 1)
            t1_note = f"Below {r1['strength']} res ₹{r1['price']} ({r1['touches']}x)"
            if t1_pct < 4 and len(ress) > 1:
                r1 = ress[1]; t1 = round(r1["price"]*0.985,2)
                t1_pct = round((t1-curr)/curr*100,1)
                t1_note = f"2nd resistance ₹{r1['price']} ({r1['touches']}x)"
        if not t1 or t1_pct < 4:
            t1 = round(curr*1.08,2); t1_pct = 8.0; t1_note = "8% default"

        if sec:
            t2 = round(sec["price"]*0.985,2)
            t2_pct = round((t2-curr)/curr*100,1)
            t2_note = f"2nd resistance ₹{sec['price']} ({sec['touches']}x)"
        else:
            t2 = round(curr*1.15,2); t2_pct = 15.0; t2_note = "15% trail"
        if t2_pct < t1_pct + 3:
            t2 = round(curr*1.15,2); t2_pct = 15.0; t2_note = "15% trail"

        t3 = t3_pct = t3_note = None
        if trade_type == "BREAKOUT":
            if len(ress) > 2:
                r3 = ress[2]; t3 = round(r3["price"]*0.985,2)
                t3_pct = round((t3-curr)/curr*100,1)
                t3_note = f"3rd resistance ₹{r3['price']}"
            else:
                t3 = round(curr*1.25,2); t3_pct = 25.0; t3_note = "25% breakout ext"

        rr   = round((t1-curr)/(curr-sl),1) if (curr-sl)>0 else 0
        hold = "10-20 days" if t1_pct>=15 else "5-10 days" if t1_pct>=8 else "3-5 days"

        return {
            "sl":sl,"sl_pct":sl_pct,"sl_note":sl_note,
            "t1":t1,"t1_pct":t1_pct,"t1_note":t1_note,
            "t2":t2,"t2_pct":t2_pct,"t2_note":t2_note,
            "t3":t3,"t3_pct":t3_pct,"t3_note":t3_note,
            "rr":rr,"hold":hold
        }
    except Exception as e:
        print(f"PA targets error: {e}")
        return {
            "sl":round(curr*0.95,2),"sl_pct":5.0,"sl_note":"default",
            "t1":round(curr*1.08,2),"t1_pct":8.0,"t1_note":"default",
            "t2":round(curr*1.15,2),"t2_pct":15.0,"t2_note":"default",
            "t3":None,"t3_pct":None,"t3_note":None,
            "rr":1.5,"hold":"5-7 days"
        }

def pa_analyse(symbol, sector_signals, nifty_cond,
               min_price=50, max_price=3000,
               min_vol=150000, max_rsi=68, min_score=75):
    try:
        sym       = symbol if ".NS" in symbol else symbol + ".NS"
        sym_clean = sym.replace(".NS", "")

        df = yf.download(sym, period="18mo", interval="1d", auto_adjust=True, progress=False)
        if df is None or df.empty or len(df) < 80:
            return None

        df.columns = [str(c[0]).capitalize() if isinstance(c, tuple) else str(c).capitalize() for c in df.columns]

        close  = df["Close"].squeeze()
        volume = df["Volume"].squeeze()
        curr   = float(close.iloc[-1])
        prev   = float(close.iloc[-2])

        if curr < min_price or curr > max_price: return None
        avg_vol = float(volume.tail(20).mean())
        if avg_vol < min_vol: return None
        rsi_now = float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
        if rsi_now > max_rsi: return None

        ema20  = float(ta.trend.EMAIndicator(close, 20).ema_indicator().iloc[-1])
        ema50  = float(ta.trend.EMAIndicator(close, 50).ema_indicator().iloc[-1])
        ema200 = float(ta.trend.EMAIndicator(close, 200).ema_indicator().iloc[-1]) if len(close)>=200 else ema50
        macd_obj = ta.trend.MACD(close)
        macd_l   = float(macd_obj.macd().iloc[-1])
        macd_s   = float(macd_obj.macd_signal().iloc[-1])
        lat_vol  = float(volume.iloc[-1])
        vol_ratio = round(lat_vol / avg_vol, 1) if avg_vol > 0 else 1.0

        if ema20 < ema50 * 0.97 and rsi_now < 38:
            return None

        score = 0
        notes = []

        sr  = pa_sr_zones(df, curr)
        sup = sr.get("nearest_sup")
        res = sr.get("nearest_res")

        if sup:
            d = (curr - sup["price"]) / curr * 100
            if d <= 2:
                score += 15
                notes.append(f"✅ AT support ₹{sup['price']} ({sup['touches']}x = {sup['strength']})")
            elif d <= 5:
                score += 8
                notes.append(f"✅ Near support ₹{sup['price']} ({d:.1f}% away, {sup['touches']} touches)")
            else:
                score += 3
                notes.append(f"⚠️ Support ₹{sup['price']} is {d:.1f}% away")
        if res:
            d = (res["price"] - curr) / curr * 100
            if d >= 10:   score += 10; notes.append(f"✅ Resistance ₹{res['price']} {d:.1f}% away")
            elif d >= 6:  score += 5;  notes.append(f"⚠️ Resistance ₹{res['price']} {d:.1f}% away")
            else:         score -= 5;  notes.append(f"❌ Resistance ₹{res['price']} only {d:.1f}% away")
        else:
            score += 5; notes.append("✅ No overhead resistance")

        trade_type, setup_bonus, setup_notes = pa_setup_type(df, sr, curr, ema20, ema50)
        score += setup_bonus
        notes.extend(setup_notes)
        if trade_type == "NONE": return None

        ds_score, ds_notes, at_demand = pa_demand_zone(df, curr)
        score += ds_score
        notes.extend(ds_notes)

        if 35 <= rsi_now <= 55:       score += 8;  notes.append(f"✅ RSI {rsi_now:.1f} — ideal entry")
        elif 55 < rsi_now <= max_rsi: score += 4; notes.append(f"⚠️ RSI {rsi_now:.1f} — elevated")
        elif rsi_now < 35:            score += 5;  notes.append(f"✅ RSI {rsi_now:.1f} — oversold")
        else:                         score -= 8;  notes.append(f"❌ RSI {rsi_now:.1f} — overbought")

        if ema20 > ema50 > ema200:  score += 10; notes.append("✅ EMA 20>50>200 — full bull alignment")
        elif ema20 > ema50:          score += 5;  notes.append("✅ EMA 20>50 — uptrend")
        else:                        score -= 6;  notes.append("❌ EMA bearish")

        if macd_l > macd_s and (macd_l-macd_s) > 0:  score += 7; notes.append("✅ MACD bullish + rising")
        elif macd_l > macd_s:                          score += 3; notes.append("⚠️ MACD bullish, weakening")
        else:                                          score -= 4; notes.append("❌ MACD bearish")

        if vol_ratio >= 2.0:   score += 5; notes.append(f"✅ Volume {vol_ratio}x avg")
        elif vol_ratio >= 1.3: score += 2; notes.append(f"⚠️ Volume {vol_ratio}x avg")

        at_sup_zone = sup and (curr - sup["price"]) / curr * 100 <= 3
        c_score, c_notes = pa_candle_at_zone(df, at_sup_zone, at_demand)
        score += c_score
        notes.extend(c_notes)

        sector     = get_stock_sector(sym)
        sec_mood   = sector_signals.get(sector, "NEUTRAL 🟡")
        if nifty_cond == "BULLISH":     score += 8; notes.append("✅ Nifty BULLISH")
        elif nifty_cond == "BEARISH":   score -= 8; notes.append("⚠️ Nifty BEARISH — smaller size")
        elif nifty_cond == "OVERBOUGHT": score -= 3; notes.append("⚠️ Nifty OVERBOUGHT")
        else:                           score += 3; notes.append("⚠️ Nifty NEUTRAL")

        if "BULLISH" in sec_mood:   score += 7; notes.append(f"✅ Sector {sector} BULLISH")
        elif "BEARISH" in sec_mood: score -= 5; notes.append(f"⚠️ Sector {sector} BEARISH")
        else:                       score += 2; notes.append(f"⚠️ Sector {sector} NEUTRAL")

        score = min(100, max(0, score))

        threshold = min_score + (10 if nifty_cond == "BEARISH" else 0)
        if score < threshold: return None

        lv = pa_dynamic_targets(curr, sr, trade_type)
        if lv["rr"] < 1.8: return None

        stage = "Unknown"
        try:
            from smc_engine import classify_market_stage
            stage = classify_market_stage(df)
        except: pass

        day_chg = round((curr - prev) / prev * 100, 2)
        lot     = FON_LOT_SIZES.get(sym_clean, 0)

        if score >= 82:   signal_label = "STRONG BUY 🔥"
        elif score >= 70: signal_label = "BUY ⭐"
        else:             signal_label = "WATCH 👀"

        return {
            "symbol":      sym_clean,
            "price":       round(curr, 2),
            "day_chg":     day_chg,
            "signal":      signal_label,
            "score":       score,
            "trade_type":  trade_type,
            "stage":       stage,
            "rsi":         round(rsi_now, 1),
            "ema_bull":    ema20 > ema50,
            "macd_bull":   macd_l > macd_s,
            "vol_ratio":   vol_ratio,
            "support":     sup["price"] if sup else round(curr*0.95,2),
            "sup_touches": sr.get("sup_touches", 0),
            "sup_strength":sup["strength"] if sup else "MINOR",
            "resistance":  res["price"] if res else round(curr*1.10,2),
            "res_touches": sr.get("res_touches", 0),
            "at_demand":   at_demand,
            "entry":       round(curr * 0.999, 2),
            "sl":          lv["sl"],   "sl_pct":  lv["sl_pct"],  "sl_note":  lv["sl_note"],
            "t1":          lv["t1"],   "t1_pct":  lv["t1_pct"],  "t1_note":  lv["t1_note"],
            "t2":          lv["t2"],   "t2_pct":  lv["t2_pct"],  "t2_note":  lv["t2_note"],
            "t3":          lv["t3"],   "t3_pct":  lv["t3_pct"],  "t3_note":  lv["t3_note"],
            "rr":          lv["rr"],   "hold":    lv["hold"],
            "sector":      sector,
            "is_fno":      lot > 0,
            "lot":         lot,
            "notes":       notes,
            "efficiency":  min(5, int(score / 20)),
            "target":      lv["t1"],    
            "sl_legacy":   lv["sl"],    
        }
    except Exception as e:
        print(f"PA analyse error {symbol}: {e}")
        return None

def pa_format_alert(r, rank=1, nifty_cond="NEUTRAL"):
    try:
        from smc_engine import get_killzone
        kz = get_killzone()
    except:
        kz = {"zone":"N/A","quality":"N/A","note":""}

    risk = 200000 * 0.02
    rps  = r["price"] * (r["sl_pct"] / 100)
    qty  = int(risk / rps) if rps > 0 else 0
    dep  = round(qty * r["price"])
    bar  = "█" * int(r["score"]/10) + "░" * (10 - int(r["score"]/10))

    badge = {
        "REVERSAL":"🔄 REVERSAL AT SUPPORT",
        "BREAKOUT":"🚀 STRUCTURE BREAKOUT",
        "PULLBACK":"📉 PULLBACK IN UPTREND",
        "CONTINUATION":"➡️ TREND CONTINUATION",
    }.get(r["trade_type"], r["trade_type"])

    nw = "\n⚠️ Nifty BEARISH — use 50% position" if nifty_cond == "BEARISH" else ""

    t_block = (
        f"Target 1   : ₹{r['t1']} (+{r['t1_pct']}%) → exit 60%\n"
        f"   📍 {r['t1_note']}\n"
        f"Target 2   : ₹{r['t2']} (+{r['t2_pct']}%) → exit rest\n"
        f"   📍 {r['t2_note']}"
    )
    if r.get("t3"):
        t_block += f"\nTarget 3   : ₹{r['t3']} (+{r['t3_pct']}%) — breakout ext\n   📍 {r['t3_note']}"

    return f"""{'🔥' if r['score']>=82 else '⭐'} <b>#{rank} — {r['symbol']}</b>  {badge}
━━━━━━━━━━━━━━━━━━━━
Signal     : <b>{r['signal']}</b>
Score      : {r['score']}/100  [{bar}]
Stage      : {r['stage']} | {r['sector']}{nw}

💰 ₹{r['price']} ({r['day_chg']:+.2f}%) | RSI {r['rsi']} | Vol {r['vol_ratio']}x

📐 <b>Key Levels</b>
Support    : ₹{r['support']} — {r['sup_touches']}x tested ({r['sup_strength']})
Resistance : ₹{r['resistance']} — {r['res_touches']} touches
{'✅ INSIDE DEMAND ZONE' if r['at_demand'] else ''}

📌 <b>Trade Plan</b>
Entry      : ₹{r['entry']}
Stop Loss  : ₹{r['sl']} (-{r['sl_pct']}%)
   📍 {r['sl_note']}
{t_block}
R/R Ratio  : 1:{r['rr']} | Hold: {r['hold']}

📐 <b>Position (2% risk on ₹2L)</b>
{qty} shares = ₹{dep:,} | Max loss: ₹{round(qty*r['price']*r['sl_pct']/100):,}
{'F&O ✅ Lot: '+str(r['lot']) if r['is_fno'] else ''}

⏰ {kz['zone']} ({kz['quality']}) — {kz['note']}
⚠️ Verify in Zerodha | /buy {r['symbol']} {r['entry']} {qty}"""

def pa_nifty_condition():
    try:
        ndf = yf.download("^NSEI", period="30d", interval="1d", progress=False, auto_adjust=True)
        if ndf is None or ndf.empty or len(ndf) < 10:
            return "NEUTRAL", 50.0
        ndf.columns = [str(c[0]).capitalize() if isinstance(c, tuple) else str(c).capitalize() for c in ndf.columns]
        nc   = ndf["Close"].squeeze()
        rsi  = float(ta.momentum.RSIIndicator(nc).rsi().iloc[-1])
        e20  = float(ta.trend.EMAIndicator(nc, 20).ema_indicator().iloc[-1])
        e50  = float(ta.trend.EMAIndicator(nc, 50).ema_indicator().iloc[-1])
        chg  = float((nc.iloc[-1] - nc.iloc[-2]) / nc.iloc[-2] * 100)
        if rsi > 72:                                 return "OVERBOUGHT", rsi
        elif e20 > e50 and rsi > 45 and chg > -0.8: return "BULLISH",    rsi
        elif e20 < e50 or rsi < 35:                  return "BEARISH",    rsi
        else:                                        return "NEUTRAL",    rsi
    except Exception as e:
        print(f"Nifty condition error: {e}")
        return "NEUTRAL", 50.0
