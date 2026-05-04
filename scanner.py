import yfinance as yf
import pandas as pd
import ta
from datetime import datetime, timedelta
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
from email.mime.base import MIMEBase
from email import encoders
import io
import feedparser
warnings.filterwarnings('ignore')

# ============================================================
# NSE FULL MARKET SCANNER v2.0
# Owner: Lovesh Ahuja
# Morning scan — 8:00 AM IST daily
# All 6 forces: Technical + Global + FII + News + Earnings + Sector
# ============================================================

GMAIL_ADDRESS    = os.environ.get('GMAIL_ADDRESS')
GMAIL_PASSWORD   = os.environ.get('GMAIL_PASSWORD')
TELEGRAM_TOKEN   = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
GOOGLE_SHEET_ID  = os.environ.get('GOOGLE_SHEET_ID')
GOOGLE_CREDS     = os.environ.get('GOOGLE_CREDENTIALS')

MY_PORTFOLIO = [
    "BLS.NS","ENGINERSIN.NS","HDFCBANK.NS","JIOFIN.NS",
    "PARADEEP.NS","SUZLON.NS","SYNGENE.NS","VMM.NS","BEL.NS"
]

FON_STOCKS = [
    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS",
    "SBIN.NS","KOTAKBANK.NS","AXISBANK.NS","BAJFINANCE.NS","MARUTI.NS",
    "TITAN.NS","SUNPHARMA.NS","WIPRO.NS","HCLTECH.NS","NTPC.NS",
    "POWERGRID.NS","TATAMOTORS.NS","JSWSTEEL.NS","COALINDIA.NS","ONGC.NS",
    "ADANIENT.NS","HINDALCO.NS","TATASTEEL.NS","CIPLA.NS","DRREDDY.NS",
    "DIVISLAB.NS","APOLLOHOSP.NS","EICHERMOT.NS","BAJAJ-AUTO.NS","HEROMOTOCO.NS",
    "BRITANNIA.NS","BPCL.NS","IOC.NS","INDUSINDBK.NS","BAJAJFINSV.NS",
    "SUZLON.NS","BEL.NS","HAL.NS","BHEL.NS","SAIL.NS",
    "TATAPOWER.NS","ADANIGREEN.NS","IRFC.NS","RVNL.NS","PFC.NS",
    "RECLTD.NS","HUDCO.NS","IRCTC.NS","ZOMATO.NS","NYKAA.NS",
]

SECTOR_MAP = {
    "IT": ["TCS.NS","INFY.NS","WIPRO.NS","HCLTECH.NS","TECHM.NS","LTIM.NS","COFORGE.NS","PERSISTENT.NS","MPHASIS.NS","KPITTECH.NS"],
    "BANKING": ["HDFCBANK.NS","ICICIBANK.NS","SBIN.NS","KOTAKBANK.NS","AXISBANK.NS","INDUSINDBK.NS","BANDHANBNK.NS","FEDERALBNK.NS","IDFCFIRSTB.NS"],
    "PHARMA": ["SUNPHARMA.NS","DRREDDY.NS","CIPLA.NS","DIVISLAB.NS","LUPIN.NS","AUROPHARMA.NS","ALKEM.NS","ZYDUSLIFE.NS","MANKIND.NS"],
    "DEFENCE": ["HAL.NS","BEL.NS","BEML.NS","MAZAGON.NS","GRSE.NS","COCHINSHIP.NS","MIDHANI.NS"],
    "POWER": ["NTPC.NS","POWERGRID.NS","TATAPOWER.NS","ADANIGREEN.NS","CESC.NS","SJVN.NS","NHPC.NS","SUZLON.NS","INOXWIND.NS"],
    "AUTO": ["MARUTI.NS","TATAMOTORS.NS","BAJAJ-AUTO.NS","HEROMOTOCO.NS","TVSMOTOR.NS","EICHERMOT.NS"],
    "FMCG": ["HINDUNILVR.NS","ITC.NS","NESTLEIND.NS","BRITANNIA.NS","DABUR.NS","MARICO.NS","COLPAL.NS"],
    "INFRA": ["LT.NS","IRFC.NS","RVNL.NS","HUDCO.NS","PFC.NS","RECLTD.NS","IRB.NS","NCC.NS"],
    "METALS": ["TATASTEEL.NS","JSWSTEEL.NS","HINDALCO.NS","SAIL.NS","NMDC.NS","VEDL.NS"],
    "ENERGY": ["RELIANCE.NS","ONGC.NS","BPCL.NS","IOC.NS","COALINDIA.NS"],
}

def setup_google_sheets():
    try:
        creds_dict = json.loads(GOOGLE_CREDS)
        scopes = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(GOOGLE_SHEET_ID)
        return sheet
    except Exception as e:
        print(f"Google Sheets error: {e}")
        return None

def get_nse_symbols():
    print("Downloading NSE symbol list...")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://www.nseindia.com/',
        }
        session = requests.Session()
        session.get('https://www.nseindia.com', headers=headers, timeout=15)
        time.sleep(2)
        url = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
        r = session.get(url, headers=headers, timeout=30)
        if r.status_code == 200:
            df = pd.read_csv(io.StringIO(r.text))
            symbols = [s.strip() + '.NS' for s in df['SYMBOL'].tolist()]
            print(f"Downloaded {len(symbols)} NSE symbols")
            return symbols
    except Exception as e:
        print(f"NSE download failed: {e}")
    return get_fallback_symbols()

def get_fallback_symbols():
    return list(set([
        "RELIANCE.NS","TCS.NS","HDFCBANK.NS","BHARTIARTL.NS","ICICIBANK.NS",
        "INFY.NS","SBIN.NS","HINDUNILVR.NS","ITC.NS","KOTAKBANK.NS",
        "LT.NS","AXISBANK.NS","BAJFINANCE.NS","MARUTI.NS","ASIANPAINT.NS",
        "TITAN.NS","SUNPHARMA.NS","NESTLEIND.NS","ULTRACEMCO.NS","WIPRO.NS",
        "HCLTECH.NS","POWERGRID.NS","NTPC.NS","TECHM.NS","INDUSINDBK.NS",
        "BAJAJFINSV.NS","ONGC.NS","JSWSTEEL.NS","COALINDIA.NS","TATAMOTORS.NS",
        "ADANIENT.NS","ADANIPORTS.NS","HINDALCO.NS","TATASTEEL.NS","BRITANNIA.NS",
        "CIPLA.NS","DRREDDY.NS","DIVISLAB.NS","APOLLOHOSP.NS","EICHERMOT.NS",
        "BAJAJ-AUTO.NS","HEROMOTOCO.NS","GRASIM.NS","TATACONSUM.NS","BPCL.NS",
        "IOC.NS","SBILIFE.NS","HDFCLIFE.NS","ICICIPRULI.NS","PIDILITIND.NS",
        "GODREJCP.NS","MUTHOOTFIN.NS","BIOCON.NS","LUPIN.NS","TORNTPHARM.NS",
        "AUROPHARMA.NS","ALKEM.NS","IPCALAB.NS","ABBOTINDIA.NS","ZYDUSLIFE.NS",
        "NATCOPHARM.NS","GLAND.NS","LALPATHLAB.NS","METROPOLIS.NS","MAXHEALTH.NS",
        "FORTIS.NS","NH.NS","KIMS.NS","BANDHANBNK.NS","FEDERALBNK.NS",
        "IDFCFIRSTB.NS","RBLBANK.NS","CANBK.NS","BANKBARODA.NS","PNB.NS",
        "UNIONBANK.NS","MAHABANK.NS","UCOBANK.NS","CENTRALBNK.NS","INDIANB.NS",
        "SUZLON.NS","JIOFIN.NS","SYNGENE.NS","BLS.NS","ENGINERSIN.NS",
        "VMM.NS","PARADEEP.NS","ZOMATO.NS","NYKAA.NS","DELHIVERY.NS",
        "IRCTC.NS","IRFC.NS","RVNL.NS","HUDCO.NS","PFC.NS",
        "RECLTD.NS","SJVN.NS","NHPC.NS","CESC.NS","TATAPOWER.NS",
        "ADANIGREEN.NS","TORNTPOWER.NS","SAIL.NS","NMDC.NS","MOIL.NS",
        "NATIONALUM.NS","VEDL.NS","HINDCOPPER.NS","APLAPOLLO.NS","AMBUJACEM.NS",
        "ACC.NS","SHREECEM.NS","RAMCOCEM.NS","JKCEMENT.NS","INDIGO.NS",
        "BLUEDART.NS","CONCOR.NS","TVSMOTOR.NS","BHARATFORG.NS","MOTHERSON.NS",
        "BOSCHLTD.NS","APOLLOTYRE.NS","MRF.NS","CEATLTD.NS","BALKRISIND.NS",
        "SIEMENS.NS","ABB.NS","HAVELLS.NS","CROMPTON.NS","POLYCAB.NS",
        "THERMAX.NS","BHEL.NS","HAL.NS","BEL.NS","BEML.NS",
        "MAZAGON.NS","COCHINSHIP.NS","GRSE.NS","INFOEDGE.NS","TEAMLEASE.NS",
        "QUESS.NS","SIS.NS","CDSL.NS","BSE.NS","MCX.NS",
        "ICICIGI.NS","NIACL.NS","GICRE.NS","STARHEALTH.NS","MFSL.NS",
        "LICHSGFIN.NS","CANFINHOME.NS","AAVAS.NS","MANAPPURAM.NS","CHOLAFIN.NS",
        "SHRIRAMFIN.NS","DIXON.NS","AMBER.NS","VOLTAS.NS","BLUESTAR.NS",
        "BATAINDIA.NS","RELAXO.NS","TRENT.NS","PAGEIND.NS","KPRMILL.NS",
        "VARDHMAN.NS","TRIDENT.NS","PERSISTENT.NS","MPHASIS.NS","LTIM.NS",
        "COFORGE.NS","KPITTECH.NS","TATAELXSI.NS","TANLA.NS","NAUKRI.NS",
        "CYIENT.NS","DEEPAKNTR.NS","ATUL.NS","NAVINFLUOR.NS","CLEAN.NS",
        "VINATI.NS","FLUOROCHEM.NS","AARTI.NS","TATACHEM.NS","GHCL.NS",
        "COROMANDEL.NS","PIIND.NS","GRANULES.NS","LAURUSLABS.NS","ERIS.NS",
        "JBCHEPHARM.NS","AJANTPHARM.NS","NEULANDLAB.NS","DMART.NS","COLPAL.NS",
        "EMAMILTD.NS","MARICO.NS","DABUR.NS","VBL.NS","RADICO.NS",
        "MCDOWELL-N.NS","IEX.NS","LTTS.NS","DLF.NS","GODREJPROP.NS",
        "PRESTIGE.NS","BRIGADE.NS","SOBHA.NS","PHOENIXLTD.NS","LINDEINDIA.NS",
        "JSWINFRA.NS","IRB.NS","PNCINFRA.NS","KNRCON.NS","NCC.NS",
        "FLUOROCHEM.NS","STARCEMENT.NS","KAJARIACER.NS","ROUTE.NS","MASTEK.NS",
        "TEJASNET.NS","STLTECH.NS","RITES.NS","MIDHANI.NS","GARDENREACH.NS",
        "NUVAMA.NS","360ONE.NS","ANGELONE.NS","MOTILALOFS.NS","POONAWALLA.NS",
        "EQUITASBNK.NS","UTKARSHBNK.NS","SURYODAY.NS","KARURVYSYA.NS",
        "DCBBANK.NS","CITYUNIONBANK.NS","CHOLAHLDNG.NS","BAJAJHLDNG.NS",
        "LICHOUSING.NS","INDIAGLYCO.NS","TRIVENI.NS","BALRAMCHIN.NS",
        "RENUKA.NS","DCMSHRIRAM.NS","CHAMBALFERT.NS","GNFC.NS","GSFC.NS",
        "RCF.NS","NFL.NS","RALLIS.NS","MANKIND.NS","GLENMARK.NS",
        "WOCKPHARMA.NS","STRIDES.NS","ALEMBICLTD.NS","APLLTD.NS","JUBLPHARMA.NS",
        "AARTIDRUGS.NS","TIINDIA.NS","SUPRAJIT.NS","ENDURANCE.NS","SCHAEFFLER.NS",
        "GRINDWELL.NS","CARBORUNIV.NS","INOXWIND.NS","JSWENERGY.NS","WAAREEENER.NS",
        "CENTURYPLY.NS","GREENPANEL.NS","SOBHA.NS","MAHLIFE.NS","APTUS.NS",
        "CREDITACC.NS","SPANDANA.NS","LICI.NS","DIVI.NS","PIRAMAL.NS",
        "SOLARA.NS","CAPLIPOINT.NS","NATCOPHARM.NS","IPCALAB.NS","ABBOTINDIA.NS",
        "OBEROIRLTY.NS","KOLTEPATIL.NS","SUNTECK.NS","PHOENIXLTD.NS","BRIGADE.NS",
    ]))

def get_global_markets():
    print("Fetching global markets...")
    result = {}
    indices = {
        "US_DOW": "^DJI",
        "US_NASDAQ": "^IXIC",
        "US_SP500": "^GSPC",
        "GIFT_NIFTY": "^NSEI",
        "CRUDE_OIL": "CL=F",
        "GOLD": "GC=F",
        "USD_INR": "INR=X",
        "VIX": "^VIX",
    }
    for name, ticker in indices.items():
        try:
            df = yf.download(ticker, period="5d", interval="1d", progress=False)
            if not df.empty and len(df) >= 2:
                prev = float(df['Close'].iloc[-2])
                curr = float(df['Close'].iloc[-1])
                change_pct = ((curr - prev) / prev) * 100
                result[name] = {"price": curr, "change_pct": round(change_pct, 2)}
        except:
            pass
        time.sleep(0.3)
    return result

def get_fii_dii():
    print("Fetching FII/DII data...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.nseindia.com/'}
        session = requests.Session()
        session.get('https://www.nseindia.com', headers=headers, timeout=10)
        url = "https://www.nseindia.com/api/fiidiiTradeReact"
        r = session.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if data:
                latest = data[0]
                return {
                    "date": latest.get("date", ""),
                    "fii_net": float(str(latest.get("fiiNet", "0")).replace(",", "")),
                    "dii_net": float(str(latest.get("diiNet", "0")).replace(",", "")),
                }
    except Exception as e:
        print(f"FII/DII error: {e}")
    return {"date": "N/A", "fii_net": 0, "dii_net": 0}

def get_news():
    print("Fetching news...")
    news_items = []
    feeds = [
        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "https://www.moneycontrol.com/rss/business.xml",
        "https://feeds.feedburner.com/ndtvprofit-latest",
    ]
    portfolio_names = ["BLS","ENGINERSIN","HDFCBANK","JIOFIN","PARADEEP",
                       "SUZLON","SYNGENE","VMM","BEL","NIFTY","SENSEX","BANKNIFTY"]
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:20]:
                title = entry.get('title', '')
                summary = entry.get('summary', '')[:200]
                text = (title + " " + summary).upper()
                for stock in portfolio_names:
                    if stock in text:
                        sentiment = "POSITIVE 🟢" if any(w in text for w in ["SURGE","JUMP","GAIN","RISE","BUY","ORDER","PROFIT","UP","BULLISH","GROWTH"]) \
                            else "NEGATIVE 🔴" if any(w in text for w in ["FALL","DROP","LOSS","CRASH","SELL","DOWN","BEARISH","DECLINE","WEAK"]) \
                            else "NEUTRAL 🟡"
                        news_items.append({
                            "stock": stock,
                            "headline": title[:120],
                            "sentiment": sentiment
                        })
                        break
        except Exception as e:
            print(f"News feed error: {e}")
    seen = set()
    unique_news = []
    for item in news_items:
        key = item['stock'] + item['headline'][:50]
        if key not in seen:
            seen.add(key)
            unique_news.append(item)
    return unique_news[:10]

def get_sector_momentum():
    print("Calculating sector momentum...")
    sector_signals = {}
    for sector, stocks in SECTOR_MAP.items():
        bull_count = 0
        total = 0
        for symbol in stocks[:5]:
            try:
                df = yf.download(symbol, period="1mo", interval="1d", progress=False)
                if df.empty or len(df) < 20:
                    continue
                close = df['Close'].squeeze()
                ema20 = ta.trend.EMAIndicator(close, window=20).ema_indicator().iloc[-1]
                ema50 = ta.trend.EMAIndicator(close, window=50).ema_indicator().iloc[-1] if len(close) >= 50 else ema20
                rsi = ta.momentum.RSIIndicator(close).rsi().iloc[-1]
                if ema20 > ema50 and rsi < 70:
                    bull_count += 1
                total += 1
                time.sleep(0.2)
            except:
                pass
        if total > 0:
            score = bull_count / total
            if score >= 0.6:
                sector_signals[sector] = "BULLISH 🟢"
            elif score >= 0.4:
                sector_signals[sector] = "NEUTRAL 🟡"
            else:
                sector_signals[sector] = "BEARISH 🔴"
    return sector_signals

def get_stock_sector(symbol):
    sym = symbol.replace(".NS", "")
    for sector, stocks in SECTOR_MAP.items():
        if symbol in stocks or sym + ".NS" in stocks:
            return sector
    return "GENERAL"

def calculate_support_resistance(close_series):
    recent = close_series.tail(20)
    support = round(float(recent.min()), 2)
    resistance = round(float(recent.max()), 2)
    return support, resistance

def get_options_recommendation(symbol, current_price, rsi, signal, sector_mood):
    sym = symbol.replace(".NS", "")
    is_fno = symbol in FON_STOCKS
    if not is_fno:
        return None
    if "BUY" not in signal:
        return None
    if rsi > 70:
        return None

    lot_sizes = {
        "RELIANCE": 250, "TCS": 150, "HDFCBANK": 550, "ICICIBANK": 700,
        "INFY": 400, "SBIN": 1500, "KOTAKBANK": 400, "AXISBANK": 1200,
        "BAJFINANCE": 125, "MARUTI": 100, "TITAN": 375, "SUNPHARMA": 700,
        "WIPRO": 1500, "HCLTECH": 700, "NTPC": 2250, "TATAMOTORS": 1425,
        "JSWSTEEL": 675, "ADANIENT": 250, "HINDALCO": 1400, "TATASTEEL": 5500,
        "CIPLA": 650, "DRREDDY": 125, "SUZLON": 2900, "BEL": 2950,
        "HAL": 150, "BHEL": 4350, "SAIL": 6750, "TATAPOWER": 1350,
        "IRFC": 4800, "RVNL": 2750, "PFC": 1200, "RECLTD": 975,
        "ZOMATO": 2475, "IRCTC": 875,
    }
    lot_size = lot_sizes.get(sym, 500)

    if rsi < 45:
        strike_offset = 1.02
        expiry_type = "Current month"
        strike_label = "ATM+2%"
    elif rsi < 55:
        strike_offset = 1.03
        expiry_type = "Current month"
        strike_label = "ATM+3%"
    else:
        strike_offset = 1.05
        expiry_type = "Next month"
        strike_label = "ATM+5%"

    strike = round(current_price * strike_offset / 50) * 50
    est_premium_low = round(current_price * 0.025, 1)
    est_premium_high = round(current_price * 0.035, 1)
    target_premium = round(est_premium_low * 2.2, 1)
    sl_premium = round(est_premium_low * 0.5, 1)
    capital_low = round(est_premium_low * lot_size)
    capital_high = round(est_premium_high * lot_size)

    return {
        "type": "CALL (CE)",
        "strike": strike,
        "strike_label": strike_label,
        "expiry": expiry_type,
        "premium_low": est_premium_low,
        "premium_high": est_premium_high,
        "target_premium": target_premium,
        "sl_premium": sl_premium,
        "lot_size": lot_size,
        "capital_low": capital_low,
        "capital_high": capital_high,
        "max_gain_pct": 120,
    }

def get_nifty_options(nifty_level, nifty_rsi, direction):
    if direction == "BULLISH":
        option_type = "CALL (CE)"
        strike = round(nifty_level * 1.005 / 50) * 50
        premium_low = round(nifty_level * 0.008)
        premium_high = round(nifty_level * 0.01)
        action = "BUY"
    else:
        option_type = "PUT (PE)"
        strike = round(nifty_level * 0.995 / 50) * 50
        premium_low = round(nifty_level * 0.008)
        premium_high = round(nifty_level * 0.01)
        action = "BUY"

    target = round(premium_low * 2)
    sl = round(premium_low * 0.5)
    lot_size = 75
    capital = premium_low * lot_size

    expiry = "Current weekly" if nifty_rsi > 55 else "Current monthly"

    return {
        "action": action,
        "type": option_type,
        "strike": strike,
        "expiry": expiry,
        "premium_low": premium_low,
        "premium_high": premium_high,
        "target": target,
        "sl": sl,
        "lot_size": lot_size,
        "capital": capital,
    }

def calculate_signal(symbol, sector_signals=None):
    try:
        df = yf.download(symbol, period="6mo", interval="1d", progress=False)
        if df.empty or len(df) < 30:
            return None
        close = df["Close"].squeeze()
        volume = df["Volume"].squeeze()
        rsi = float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
        ema20 = float(ta.trend.EMAIndicator(close, window=20).ema_indicator().iloc[-1])
        ema50 = float(ta.trend.EMAIndicator(close, window=50).ema_indicator().iloc[-1]) if len(close) >= 50 else ema20
        macd_obj = ta.trend.MACD(close)
        macd_line = float(macd_obj.macd().iloc[-1])
        signal_line = float(macd_obj.macd_signal().iloc[-1])
        current_price = float(close.iloc[-1])
        prev_price = float(close.iloc[-2])
        avg_volume = float(volume.tail(20).mean())
        latest_volume = float(volume.iloc[-1])
        volume_surge = latest_volume > (avg_volume * 1.5)
        support, resistance = calculate_support_resistance(close)
        sector = get_stock_sector(symbol)
        sector_mood = sector_signals.get(sector, "NEUTRAL 🟡") if sector_signals else "NEUTRAL 🟡"
        is_fno = symbol in FON_STOCKS

        # Efficiency scoring
        score = 0
        score_details = []

        if 40 <= rsi <= 65:
            score += 1
            score_details.append(f"RSI {rsi:.1f} ✅ Healthy buy zone")
        elif rsi < 40:
            score += 1
            score_details.append(f"RSI {rsi:.1f} ✅ Oversold — strong buy zone")
        else:
            score_details.append(f"RSI {rsi:.1f} ⚠️ Elevated — be careful")

        if ema20 > ema50:
            score += 1
            score_details.append("EMA20 > EMA50 ✅ Uptrend confirmed")
        else:
            score_details.append("EMA20 < EMA50 ❌ Downtrend")

        if macd_line > signal_line:
            score += 1
            score_details.append("MACD Bullish ✅ Momentum building")
        else:
            score_details.append("MACD Bearish ❌ Momentum weak")

        if volume_surge:
            score += 1
            score_details.append("Volume Surge ✅ Big players buying")
        else:
            score_details.append("Volume normal — no institutional surge")

        if "BULLISH" in sector_mood:
            score += 1
            score_details.append(f"Sector {sector} ✅ Bullish")
        else:
            score_details.append(f"Sector {sector} — {sector_mood}")

        # Signal determination
        buy_score = 0
        sell_score = 0
        if rsi < 40: buy_score += 2
        elif rsi < 50: buy_score += 1
        if rsi > 70: sell_score += 2
        elif rsi > 60: sell_score += 1
        if ema20 > ema50: buy_score += 2
        else: sell_score += 2
        if macd_line > signal_line: buy_score += 2
        else: sell_score += 2
        if volume_surge: buy_score += 1

        if buy_score >= 5: signal = "STRONG BUY"
        elif buy_score >= 3 and buy_score > sell_score: signal = "BUY"
        elif sell_score >= 5: signal = "STRONG SELL"
        elif sell_score >= 3 and sell_score > buy_score: signal = "SELL"
        else: signal = "HOLD"

        entry = round(current_price * 0.999, 2)
        target = round(current_price * 1.10, 2)
        stop_loss = round(current_price * 0.97, 2)

        options_rec = get_options_recommendation(symbol, current_price, rsi, signal, sector_mood)

        return {
            "symbol": symbol.replace(".NS", ""),
            "price": round(current_price, 2),
            "prev_price": round(prev_price, 2),
            "price_change_pct": round(((current_price - prev_price) / prev_price) * 100, 2),
            "signal": signal,
            "buy_score": buy_score,
            "sell_score": sell_score,
            "efficiency": score,
            "efficiency_max": 5,
            "score_details": score_details,
            "rsi": round(rsi, 1),
            "trend": "UP" if ema20 > ema50 else "DOWN",
            "macd": "BULLISH" if macd_line > signal_line else "BEARISH",
            "volume_surge": "YES" if volume_surge else "no",
            "support": support,
            "resistance": resistance,
            "sector": sector,
            "sector_mood": sector_mood,
            "is_fno": is_fno,
            "entry": entry,
            "target": target,
            "stop_loss": stop_loss,
            "options": options_rec,
            "price_timestamp": f"NSE Close — {(datetime.now() - timedelta(days=1)).strftime('%d %b %Y')} 3:30 PM",
        }
    except Exception as e:
        return None

def analyze_index(ticker, name):
    try:
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)
        if df.empty or len(df) < 30:
            return None
        close = df['Close'].squeeze()
        rsi = float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
        ema20 = float(ta.trend.EMAIndicator(close, window=20).ema_indicator().iloc[-1])
        ema50 = float(ta.trend.EMAIndicator(close, window=50).ema_indicator().iloc[-1])
        macd_obj = ta.trend.MACD(close)
        macd_line = float(macd_obj.macd().iloc[-1])
        signal_line = float(macd_obj.macd_signal().iloc[-1])
        current = float(close.iloc[-1])
        prev = float(close.iloc[-2])
        support, resistance = calculate_support_resistance(close)
        change_pct = ((current - prev) / prev) * 100

        if ema20 > ema50 and macd_line > signal_line and rsi < 70:
            direction = "BULLISH"
            mood = "BULLISH 🟢"
        elif ema20 < ema50 or (macd_line < signal_line and rsi > 60):
            direction = "BEARISH"
            mood = "BEARISH 🔴"
        else:
            direction = "NEUTRAL"
            mood = "NEUTRAL 🟡"

        return {
            "name": name,
            "level": round(current, 2),
            "change_pct": round(change_pct, 2),
            "rsi": round(rsi, 1),
            "trend": "UP" if ema20 > ema50 else "DOWN",
            "macd": "BULLISH" if macd_line > signal_line else "BEARISH",
            "support": support,
            "resistance": resistance,
            "direction": direction,
            "mood": mood,
        }
    except:
        return None

def save_to_sheets(sheet, top20, portfolio_results, today):
    try:
        ws = sheet.worksheet("Daily Scan")
        headers = ["Date","Rank","Stock","Price","Signal","Efficiency","RSI","Trend","MACD","Volume","Sector","Entry","Target","SL","F&O"]
        try:
            ws.row_values(1)
        except:
            ws.append_row(headers)
        for i, r in enumerate(top20, 1):
            ws.append_row([
                today, i, r['symbol'], r['price'], r['signal'],
                f"{r['efficiency']}/5", r['rsi'], r['trend'], r['macd'],
                r['volume_surge'], r['sector'], r['entry'], r['target'],
                r['stop_loss'], "YES" if r['is_fno'] else "NO"
            ])
        print("Saved to Google Sheets!")
    except Exception as e:
        print(f"Sheets save error: {e}")

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        r = requests.post(url, data=payload, timeout=15)
        if r.status_code == 200:
            print("Telegram sent!")
        else:
            print(f"Telegram error: {r.text[:100]}")
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
            with open(csv_file, "rb") as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(csv_file)}"')
                msg.attach(part)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_ADDRESS, GMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Email sent!")
    except Exception as e:
        print(f"Email error: {e}")

def build_telegram_message(today, global_data, fii_dii, news, nifty, banknifty, sensex, portfolio_results, top20):
    # Market mood
    buy_count = len([r for r in top20 if "BUY" in r['signal']])
    nifty_mood = nifty['mood'] if nifty else "N/A"

    # Global summary
    dow = global_data.get('US_DOW', {})
    dow_txt = f"+{dow.get('change_pct',0):.1f}% 🟢" if dow.get('change_pct', 0) > 0 else f"{dow.get('change_pct',0):.1f}% 🔴"

    # FII
    fii_net = fii_dii.get('fii_net', 0)
    fii_txt = f"BOUGHT ₹{abs(fii_net):.0f} Cr 🟢" if fii_net > 0 else f"SOLD ₹{abs(fii_net):.0f} Cr 🔴"

    # News
    news_txt = ""
    for n in news[:3]:
        news_txt += f"{n['stock']}: {n['headline'][:60]}... {n['sentiment']}\n"
    if not news_txt:
        news_txt = "No major news affecting your stocks today\n"

    # Portfolio
    port_txt = ""
    for r in portfolio_results:
        e = "🟢" if "BUY" in r['signal'] else "🔴" if "SELL" in r['signal'] else "🟡"
        port_txt += f"{e} <b>{r['symbol']}</b> ₹{r['price']} | {r['signal']} | RSI:{r['rsi']} | Eff:{r['efficiency']}/5\n"

    # Top 5
    top_txt = ""
    for i, r in enumerate(top20[:5], 1):
        fno = "F&O✅" if r['is_fno'] else ""
        top_txt += f"{i}. <b>{r['symbol']}</b> ₹{r['price']} | {r['signal']} | RSI:{r['rsi']} | {r['efficiency']}/5 {fno}\n"

    # Nifty option
    nifty_opt = ""
    if nifty:
        opt = get_nifty_options(nifty['level'], nifty['rsi'], nifty['direction'])
        nifty_opt = f"\n🎯 <b>NIFTY OPTION</b>\nBuy {opt['strike']} {opt['type']} {opt['expiry']}\nPremium ₹{opt['premium_low']}–{opt['premium_high']} | Target ₹{opt['target']} | SL ₹{opt['sl']}\nCapital needed: ₹{opt['capital']:,}\n"

    msg = f"""📈 <b>NSE DAILY SCANNER — {today}</b>
⏰ Prices as of: Yesterday 3:30 PM NSE Close

━━━━━━━━━━━━━━━━━━━━
🌍 <b>GLOBAL</b>
US Dow: {dow_txt} | FII: {fii_txt}
Nifty: {nifty['level'] if nifty else 'N/A'} | Mood: {nifty_mood}

━━━━━━━━━━━━━━━━━━━━
📰 <b>NEWS</b>
{news_txt}
━━━━━━━━━━━━━━━━━━━━
💼 <b>YOUR PORTFOLIO</b>
{port_txt}
━━━━━━━━━━━━━━━━━━━━
🏆 <b>TOP 5 TODAY</b>
{top_txt}{nifty_opt}
━━━━━━━━━━━━━━━━━━━━
📧 Full report sent to Gmail
⚠️ Verify prices in Zerodha before trading"""

    return msg

def build_email_body(today, now, global_data, fii_dii, news, nifty, banknifty, sensex, sector_signals, portfolio_results, top20, total_scanned):

    def mood_color(mood):
        if "BULLISH" in mood: return "#27ae60"
        if "BEARISH" in mood: return "#e74c3c"
        return "#f39c12"

    def signal_color(sig):
        if "STRONG BUY" in sig: return "#1e8449"
        if "BUY" in sig: return "#27ae60"
        if "SELL" in sig: return "#e74c3c"
        return "#f39c12"

    # Section 1 — Global
    global_rows = ""
    global_items = [
        ("🇺🇸 US Dow Jones", "US_DOW", "If US rose → India opens positive. If US fell → India opens negative."),
        ("🇺🇸 US Nasdaq", "US_NASDAQ", "Tech stocks indicator. Affects Indian IT stocks."),
        ("🛢️ Crude Oil", "CRUDE_OIL", "Rising oil = higher fuel costs = negative for aviation, paint, tyre stocks."),
        ("💵 USD/INR", "USD_INR", "Weaker rupee = FII may sell India = negative. Stable rupee = positive."),
        ("😨 VIX (Fear Index)", "VIX", "Below 15 = calm market. Above 20 = fear. Above 25 = panic — avoid new trades."),
        ("🥇 Gold", "GOLD", "Rising gold = investors seeking safety = market may be cautious."),
    ]
    for label, key, meaning in global_items:
        d = global_data.get(key, {})
        price = d.get('price', 0)
        chg = d.get('change_pct', 0)
        color = "#27ae60" if chg > 0 else "#e74c3c" if chg < 0 else "#f39c12"
        arrow = "▲" if chg > 0 else "▼" if chg < 0 else "●"
        global_rows += f"<tr><td><b>{label}</b></td><td>{price:,.2f}</td><td style='color:{color}'>{arrow} {abs(chg):.2f}%</td><td style='font-size:12px;color:#7f8c8d'>{meaning}</td></tr>"

    # Section 2 — FII/DII
    fii_net = fii_dii.get('fii_net', 0)
    dii_net = fii_dii.get('dii_net', 0)
    fii_color = "#27ae60" if fii_net > 0 else "#e74c3c"
    dii_color = "#27ae60" if dii_net > 0 else "#e74c3c"

    # Section 3 — News
    news_rows = ""
    if news:
        for n in news:
            sc = "#27ae60" if "POSITIVE" in n['sentiment'] else "#e74c3c" if "NEGATIVE" in n['sentiment'] else "#f39c12"
            news_rows += f"<tr><td><b>{n['stock']}</b></td><td>{n['headline']}</td><td style='color:{sc}'>{n['sentiment']}</td></tr>"
    else:
        news_rows = "<tr><td colspan='3' style='color:#7f8c8d'>No major news affecting your stocks today</td></tr>"

    # Section 4 — Indices
    index_rows = ""
    for idx in [nifty, banknifty, sensex]:
        if idx:
            mc = mood_color(idx['mood'])
            chg_color = "#27ae60" if idx['change_pct'] > 0 else "#e74c3c"
            index_rows += f"""<tr>
                <td><b>{idx['name']}</b></td>
                <td>{idx['level']:,.2f}</td>
                <td style='color:{chg_color}'>{idx['change_pct']:+.2f}%</td>
                <td>RSI: {idx['rsi']}</td>
                <td>{idx['trend']}</td>
                <td>{idx['macd']}</td>
                <td>₹{idx['support']:,.0f}</td>
                <td>₹{idx['resistance']:,.0f}</td>
                <td style='color:{mc}'><b>{idx['mood']}</b></td>
            </tr>"""

    # Section 5 — Index Options
    index_options_html = ""
    if nifty:
        opt = get_nifty_options(nifty['level'], nifty['rsi'], nifty['direction'])
        index_options_html = f"""
        <div style='background:#eaf4fb;padding:15px;border-radius:8px;border-left:4px solid #3498db;margin:10px 0'>
        <h4 style='margin:0 0 8px'>🎯 NIFTY {opt['type']} — {opt['action']}</h4>
        <table style='width:100%;font-size:13px'><tr>
        <td><b>Strike:</b> {opt['strike']}</td>
        <td><b>Expiry:</b> {opt['expiry']}</td>
        <td><b>Premium:</b> ₹{opt['premium_low']}–{opt['premium_high']}</td>
        <td><b>Target:</b> ₹{opt['target']} (+100%)</td>
        <td><b>SL:</b> ₹{opt['sl']}</td>
        <td><b>Capital:</b> ₹{opt['capital']:,}</td>
        </tr></table>
        <p style='font-size:12px;color:#2c3e50;margin:8px 0 0'>
        💡 <b>What this means:</b> Nifty is at {nifty['level']:,.0f}. You're betting it will cross {opt['strike']} before {opt['expiry']} expiry.
        Pay ₹{opt['premium_low']}–{opt['premium_high']} per share. 1 lot = {opt['lot_size']} shares = ₹{opt['capital']:,} total.
        If Nifty reaches {opt['strike']+200:.0f} → your premium becomes ₹{opt['target']}. That's 100% profit.
        Maximum loss = capital paid. Cannot lose more than that.</p>
        </div>"""

    # Section 6 — Portfolio
    port_rows = ""
    for r in portfolio_results:
        sc = signal_color(r['signal'])
        eff_stars = "⭐" * r['efficiency']
        port_rows += f"""<tr>
            <td><b>{r['symbol']}</b></td>
            <td>₹{r['price']}</td>
            <td style='color:{sc}'><b>{r['signal']}</b></td>
            <td>{r['rsi']}</td>
            <td>{r['trend']}</td>
            <td>{r['volume_surge']}</td>
            <td>{r['efficiency']}/5 {eff_stars}</td>
            <td style='font-size:11px;color:#7f8c8d'>{r['price_timestamp']}</td>
        </tr>"""

    # Section 7 — Top 20
    top_rows = ""
    for i, r in enumerate(top20, 1):
        sc = signal_color(r['signal'])
        eff_stars = "⭐" * r['efficiency']
        fno_badge = "<span style='background:#27ae60;color:white;padding:2px 6px;border-radius:4px;font-size:11px'>F&O</span>" if r['is_fno'] else ""

        # Options row
        opt_html = ""
        if r['options']:
            o = r['options']
            opt_html = f"""
            <tr style='background:#f0faf0'><td colspan='9' style='padding:8px 12px'>
            <b>🎯 OPTIONS:</b> Buy {r['symbol']} {o['strike']} {o['type']} ({o['expiry']}) |
            Premium: ₹{o['premium_low']}–{o['premium_high']} |
            Target: ₹{o['target_premium']} (+{o['max_gain_pct']}%) |
            SL: ₹{o['sl_premium']} |
            Lot: {o['lot_size']} shares |
            Capital: ₹{o['capital_low']:,}–{o['capital_high']:,}
            <br><span style='font-size:11px;color:#555'>
            💡 You pay ₹{o['capital_low']:,} max. If {r['symbol']} hits ₹{r['target']}, option premium doubles. Maximum loss = premium paid only.
            </span></td></tr>"""

        top_rows += f"""<tr>
            <td>{i}</td>
            <td><b>{r['symbol']}</b> {fno_badge}</td>
            <td>₹{r['price']}</td>
            <td style='color:{sc}'><b>{r['signal']}</b></td>
            <td>{r['efficiency']}/5 {eff_stars}</td>
            <td>{r['rsi']}</td>
            <td>{r['sector']}</td>
            <td>Entry ₹{r['entry']} | Target ₹{r['target']} | SL ₹{r['stop_loss']}</td>
            <td style='font-size:11px;color:#7f8c8d'>{r['price_timestamp']}</td>
        </tr>
        <tr style='background:#f8f9fa'><td colspan='9' style='padding:4px 12px;font-size:12px;color:#555'>
        {'<br>'.join(r['score_details'][:3])}
        </td></tr>{opt_html}"""

    # Sector summary
    sector_rows = ""
    for sector, mood in sector_signals.items():
        mc = mood_color(mood)
        sector_rows += f"<tr><td><b>{sector}</b></td><td style='color:{mc}'>{mood}</td></tr>"

    nifty_mood_color = mood_color(nifty['mood'] if nifty else "NEUTRAL")
    overall_mood = nifty['mood'] if nifty else "NEUTRAL 🟡"

    html = f"""<html><body style='font-family:Arial,sans-serif;max-width:1000px;margin:auto;padding:20px;color:#2c3e50'>

<div style='background:linear-gradient(135deg,#2c3e50,#3498db);padding:20px;border-radius:12px;color:white;margin-bottom:20px'>
<h1 style='margin:0'>📈 NSE Daily Scanner</h1>
<p style='margin:5px 0 0;opacity:0.9'>{today} | Scan time: {now} | Stocks scanned: {total_scanned}</p>
<p style='margin:5px 0 0;opacity:0.8;font-size:13px'>⏰ All prices as of: Yesterday 3:30 PM (NSE Official Close)</p>
</div>

<div style='background:#eaf4fb;padding:15px;border-radius:8px;border-left:4px solid {nifty_mood_color};margin-bottom:20px'>
<h3 style='margin:0'>🌡️ Overall Market Mood: <span style='color:{nifty_mood_color}'>{overall_mood}</span></h3>
<p style='margin:5px 0 0;font-size:13px'>Buy signals: <b>{len([r for r in top20 if 'BUY' in r['signal']])}</b> | Scanned: <b>{total_scanned}</b> stocks</p>
</div>

<!-- SECTION 1: GLOBAL MARKETS -->
<h2 style='border-bottom:2px solid #3498db;padding-bottom:8px'>🌍 Section 1 — Global Markets</h2>
<div style='background:#f8f9fa;padding:12px;border-radius:8px;margin-bottom:10px;font-size:13px;color:#555'>
💡 <b>What is this?</b> Before Indian market opens at 9:15 AM, check what happened globally overnight.
US markets, oil prices and currency all affect how Indian stocks will move today.
Green = positive for India. Red = be cautious today.
</div>
<table border='1' cellpadding='8' cellspacing='0' style='width:100%;border-collapse:collapse;font-size:13px'>
<tr style='background:#2c3e50;color:white'><th>Market</th><th>Level</th><th>Change</th><th>What it means for you</th></tr>
{global_rows}
</table>

<!-- SECTION 2: FII/DII -->
<h2 style='border-bottom:2px solid #3498db;padding-bottom:8px;margin-top:25px'>💰 Section 2 — FII/DII Activity</h2>
<div style='background:#f8f9fa;padding:12px;border-radius:8px;margin-bottom:10px;font-size:13px;color:#555'>
💡 <b>What is this?</b> FII = Foreign funds (Goldman Sachs, JP Morgan etc.) DII = Indian mutual funds.
When FII buys heavily = market goes up. When FII sells = market falls.
Think of them as the big fish — they move the ocean.
</div>
<table border='1' cellpadding='8' cellspacing='0' style='width:100%;border-collapse:collapse;font-size:13px'>
<tr style='background:#2c3e50;color:white'><th>Type</th><th>Activity</th><th>Amount</th><th>Impact</th></tr>
<tr><td><b>FII (Foreign)</b></td>
<td style='color:{fii_color}'><b>{'BUYING 🟢' if fii_net > 0 else 'SELLING 🔴'}</b></td>
<td style='color:{fii_color}'>₹{abs(fii_net):,.0f} Cr</td>
<td>{'Foreign money flowing IN — bullish signal 🟢' if fii_net > 0 else 'Foreign money flowing OUT — be cautious 🔴'}</td></tr>
<tr><td><b>DII (Domestic)</b></td>
<td style='color:{dii_color}'><b>{'BUYING 🟢' if dii_net > 0 else 'SELLING 🔴'}</b></td>
<td style='color:{dii_color}'>₹{abs(dii_net):,.0f} Cr</td>
<td>{'Indian funds buying — supporting market 🟢' if dii_net > 0 else 'Indian funds selling — reducing exposure 🟡'}</td></tr>
</table>

<!-- SECTION 3: NEWS -->
<h2 style='border-bottom:2px solid #3498db;padding-bottom:8px;margin-top:25px'>📰 Section 3 — News Alerts</h2>
<div style='background:#f8f9fa;padding:12px;border-radius:8px;margin-bottom:10px;font-size:13px;color:#555'>
💡 <b>What is this?</b> Latest news filtered for YOUR portfolio stocks and major market events.
Positive news = stock likely to rise today. Negative = stock may fall. Neutral = no major impact.
</div>
<table border='1' cellpadding='8' cellspacing='0' style='width:100%;border-collapse:collapse;font-size:13px'>
<tr style='background:#2c3e50;color:white'><th>Stock</th><th>Headline</th><th>Impact</th></tr>
{news_rows}
</table>

<!-- SECTION 4: INDEX DASHBOARD -->
<h2 style='border-bottom:2px solid #3498db;padding-bottom:8px;margin-top:25px'>📊 Section 4 — Index Dashboard</h2>
<div style='background:#f8f9fa;padding:12px;border-radius:8px;margin-bottom:10px;font-size:13px;color:#555'>
💡 <b>What is this?</b> Think of Nifty as the pulse of the market.
Support = floor — buyers appear here if market falls. Resistance = ceiling — sellers appear here.
RSI below 40 = oversold (good to buy). RSI above 70 = overbought (be careful).
</div>
<table border='1' cellpadding='8' cellspacing='0' style='width:100%;border-collapse:collapse;font-size:13px'>
<tr style='background:#2c3e50;color:white'><th>Index</th><th>Level</th><th>Change</th><th>RSI</th><th>Trend</th><th>MACD</th><th>Support</th><th>Resistance</th><th>Mood</th></tr>
{index_rows}
</table>

<!-- SECTION 5: INDEX OPTIONS -->
<h2 style='border-bottom:2px solid #3498db;padding-bottom:8px;margin-top:25px'>🎯 Section 5 — Index Options</h2>
<div style='background:#f8f9fa;padding:12px;border-radius:8px;margin-bottom:10px;font-size:13px;color:#555'>
💡 <b>What is this?</b> Instead of buying stocks, you can trade Nifty directly using options.
CALL = you expect Nifty to rise. PUT = you expect Nifty to fall.
You pay a small premium. If correct → 50–100% profit. If wrong → only premium lost.
⚠️ Premium range is estimated. Check actual premium in Zerodha before buying.
</div>
{index_options_html}

<!-- SECTION 6: PORTFOLIO -->
<h2 style='border-bottom:2px solid #3498db;padding-bottom:8px;margin-top:25px'>💼 Section 6 — Your Portfolio Signals</h2>
<div style='background:#f8f9fa;padding:12px;border-radius:8px;margin-bottom:10px;font-size:13px;color:#555'>
💡 <b>What is this?</b> Fresh technical analysis of stocks you already hold.
STRONG BUY = consider adding more. BUY = hold or add small. HOLD = sit tight. SELL = consider exiting.
Efficiency stars show how many indicators are aligned today.
</div>
<table border='1' cellpadding='8' cellspacing='0' style='width:100%;border-collapse:collapse;font-size:13px'>
<tr style='background:#2c3e50;color:white'><th>Stock</th><th>Price</th><th>Signal</th><th>RSI</th><th>Trend</th><th>Volume</th><th>Efficiency</th><th>Price as of</th></tr>
{port_rows}
</table>

<!-- SECTION 7: TOP 20 -->
<h2 style='border-bottom:2px solid #3498db;padding-bottom:8px;margin-top:25px'>🏆 Section 7 — Top 20 Opportunities Today</h2>
<div style='background:#f8f9fa;padding:12px;border-radius:8px;margin-bottom:10px;font-size:13px;color:#555'>
💡 <b>What is this?</b> Best buy opportunities from {total_scanned} stocks scanned today.
Ranked by efficiency score — higher score = more indicators aligned = higher confidence.
Each stock shows Stock Route (buy shares) AND Options Route (buy CE).
F&O badge = this stock has liquid options available.
⚠️ Always verify entry price in Zerodha. Prices shown are yesterday's close.
</div>

<!-- SECTOR HEAT MAP -->
<h3>🗺️ Sector Momentum Today</h3>
<table border='1' cellpadding='6' cellspacing='0' style='width:50%;border-collapse:collapse;font-size:13px;margin-bottom:15px'>
<tr style='background:#2c3e50;color:white'><th>Sector</th><th>Momentum</th></tr>
{sector_rows}
</table>

<table border='1' cellpadding='8' cellspacing='0' style='width:100%;border-collapse:collapse;font-size:12px'>
<tr style='background:#2c3e50;color:white'>
<th>#</th><th>Stock</th><th>Price</th><th>Signal</th><th>Efficiency</th><th>RSI</th><th>Sector</th><th>Entry/Target/SL</th><th>Price as of</th>
</tr>
{top_rows}
</table>

<p style='color:#7f8c8d;font-size:12px;margin-top:20px;border-top:1px solid #eee;padding-top:10px'>
⚠️ These are technical signals only. Always do your own research before investing.<br>
All prices are based on NSE official closing prices from previous trading day 3:30 PM.<br>
Option premiums are estimated ranges — check actual premiums in Zerodha before trading.<br>
Use /analyse STOCKNAME in Telegram for real-time on-demand analysis anytime.<br>
Full scan data attached as CSV.
</p>
</body></html>"""
    return html

def run_scanner():
    today = datetime.now().strftime('%d %b %Y')
    now = datetime.now().strftime('%I:%M %p')
    print(f"\n{'='*60}")
    print(f"NSE Daily Scanner v2.0 — {today} {now}")
    print(f"{'='*60}")

    # Setup sheets
    sheet = setup_google_sheets()

    # Step 1: Global markets
    global_data = get_global_markets()
    print(f"Global data: {len(global_data)} markets fetched")

    # Step 2: FII/DII
    fii_dii = get_fii_dii()
    print(f"FII: {fii_dii.get('fii_net', 0):.0f} Cr | DII: {fii_dii.get('dii_net', 0):.0f} Cr")

    # Step 3: News
    news = get_news()
    print(f"News: {len(news)} relevant items found")

    # Step 4: Indices
    print("Analyzing indices...")
    nifty = analyze_index("^NSEI", "Nifty 50")
    banknifty = analyze_index("^NSEBANK", "Bank Nifty")
    sensex = analyze_index("^BSESN", "Sensex")
    if nifty: print(f"Nifty: {nifty['level']:.0f} | {nifty['mood']}")

    # Step 5: Sector momentum
    sector_signals = get_sector_momentum()
    print(f"Sectors analyzed: {len(sector_signals)}")

    # Step 6: Portfolio scan
    print("Scanning portfolio...")
    portfolio_results = []
    for symbol in MY_PORTFOLIO:
        result = calculate_signal(symbol, sector_signals)
        if result:
            portfolio_results.append(result)
        time.sleep(0.5)
    print(f"Portfolio: {len(portfolio_results)} stocks scanned")

    # Step 7: Full NSE scan
    nse_symbols = get_nse_symbols()
    print(f"Starting full scan of {len(nse_symbols)} NSE stocks...")
    all_results = []
    for i, symbol in enumerate(nse_symbols):
        result = calculate_signal(symbol, sector_signals)
        if result:
            all_results.append(result)
        if (i + 1) % 200 == 0:
            print(f"Progress: {i+1}/{len(nse_symbols)} | Valid: {len(all_results)}")
        time.sleep(0.25)

    # Filter & rank
    strong_buys = sorted([r for r in all_results if r['signal'] == "STRONG BUY"], key=lambda x: x['efficiency'], reverse=True)
    buys = sorted([r for r in all_results if r['signal'] == "BUY"], key=lambda x: x['efficiency'], reverse=True)
    top20 = (strong_buys + buys)[:20]
    sell_count = len([r for r in all_results if "SELL" in r['signal']])
    buy_count = len(strong_buys) + len(buys)
    total_scanned = len(all_results)
    print(f"\nScan complete! Total: {total_scanned} | Strong Buy: {len(strong_buys)} | Buy: {len(buys)} | Sell: {sell_count}")

    # Save to sheets
    if sheet:
        save_to_sheets(sheet, top20, portfolio_results, today)

    # Save CSV
    csv_file = f"scan_{datetime.now().strftime('%Y%m%d')}.csv"
    if all_results:
        pd.DataFrame(all_results).to_csv(csv_file, index=False)

    # Build & send Telegram
    tg_msg = build_telegram_message(today, global_data, fii_dii, news, nifty, banknifty, sensex, portfolio_results, top20)
    send_telegram(tg_msg)

    # Build & send Email
    email_body = build_email_body(today, now, global_data, fii_dii, news, nifty, banknifty, sensex, sector_signals, portfolio_results, top20, total_scanned)
    top_pick = top20[0]['symbol'] if top20 else 'N/A'
    nifty_mood = nifty['mood'] if nifty else 'N/A'
    send_email(
        subject=f"📈 NSE Scanner {today} | {nifty_mood} | Top: {top_pick} | Scanned: {total_scanned}",
        body=email_body,
        csv_file=csv_file
    )

    print("\n✅ Scanner complete!")

run_scanner()
