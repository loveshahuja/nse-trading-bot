import yfinance as yf
import pandas as pd
import ta
from datetime import datetime
import time
import warnings
import smtplib
import requests
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
warnings.filterwarnings('ignore')

# ============================================================
# NSE DAILY SCANNER — AUTO EMAIL + TELEGRAM
# Owner: Lovesh Ahuja
# Runs daily at 8:00 AM IST via GitHub Actions
# ============================================================

GMAIL_ADDRESS    = os.environ.get('GMAIL_ADDRESS')
GMAIL_PASSWORD   = os.environ.get('GMAIL_PASSWORD')
TELEGRAM_TOKEN   = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

MY_PORTFOLIO = [
    "BLS.NS","ENGINERSIN.NS","HDFCBANK.NS",
    "JIOFIN.NS","PARADEEP.NS","SUZLON.NS",
    "SYNGENE.NS","VMM.NS","BEL.NS"
]

NSE_STOCKS = list(set([
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
    "AUROPHARMA.NS","ALKEM.NS","IPCALAB.NS","ABBOTINDIA.NS","GLAXO.NS",
    "ZYDUSLIFE.NS","NATCOPHARM.NS","GLAND.NS","LALPATHLAB.NS","METROPOLIS.NS",
    "MAXHEALTH.NS","FORTIS.NS","NH.NS","KIMS.NS","BANDHANBNK.NS",
    "FEDERALBNK.NS","IDFCFIRSTB.NS","RBLBANK.NS","CANBK.NS","BANKBARODA.NS",
    "PNB.NS","UNIONBANK.NS","SUZLON.NS","JIOFIN.NS","SYNGENE.NS",
    "BLS.NS","ENGINERSIN.NS","VMM.NS","PARADEEP.NS","ZOMATO.NS",
    "NYKAA.NS","DELHIVERY.NS","IRCTC.NS","IRFC.NS","RVNL.NS",
    "HUDCO.NS","PFC.NS","RECLTD.NS","SJVN.NS","NHPC.NS",
    "CESC.NS","TATAPOWER.NS","ADANIGREEN.NS","TORNTPOWER.NS","SAIL.NS",
    "NMDC.NS","MOIL.NS","NATIONALUM.NS","VEDL.NS","HINDCOPPER.NS",
    "APLAPOLLO.NS","AMBUJACEM.NS","ACC.NS","SHREECEM.NS","RAMCOCEM.NS",
    "JKCEMENT.NS","INDIGO.NS","BLUEDART.NS","CONCOR.NS","TVSMOTOR.NS",
    "BHARATFORG.NS","MOTHERSON.NS","BOSCHLTD.NS","APOLLOTYRE.NS","MRF.NS",
    "CEATLTD.NS","BALKRISIND.NS","SIEMENS.NS","ABB.NS","HAVELLS.NS",
    "CROMPTON.NS","POLYCAB.NS","THERMAX.NS","BHEL.NS","HAL.NS",
    "BEL.NS","BEML.NS","MAZAGON.NS","COCHINSHIP.NS","GRSE.NS",
    "INFOEDGE.NS","TEAMLEASE.NS","QUESS.NS","SIS.NS","CDSL.NS",
    "BSE.NS","MCX.NS","ICICIGI.NS","NIACL.NS","GICRE.NS",
    "STARHEALTH.NS","MFSL.NS","LICHSGFIN.NS","CANFINHOME.NS","AAVAS.NS",
    "REPCO.NS","MANAPPURAM.NS","CHOLAFIN.NS","SHRIRAMFIN.NS","DIXON.NS",
    "AMBER.NS","VOLTAS.NS","BLUESTAR.NS","BATAINDIA.NS","RELAXO.NS",
    "TRENT.NS","ABFRL.NS","PAGEIND.NS","KPRMILL.NS","VARDHMAN.NS",
    "TRIDENT.NS","PERSISTENT.NS","MPHASIS.NS","LTIM.NS","COFORGE.NS",
    "KPITTECH.NS","TATAELXSI.NS","SONATSOFTW.NS","HAPPSTMNDS.NS","TANLA.NS",
    "INTELLECT.NS","NEWGEN.NS","NAUKRI.NS","CYIENT.NS","BIRLASOFT.NS",
    "DEEPAKNTR.NS","ATUL.NS","NAVINFLUOR.NS","CLEAN.NS","VINATI.NS",
    "SOLARINDS.NS","SUPREMEIND.NS","ASTRAL.NS","GRANULES.NS","LAURUSLABS.NS",
    "ERIS.NS","JBCHEPHARM.NS","AJANTPHARM.NS","NEULANDLAB.NS","DMART.NS",
    "COLPAL.NS","EMAMILTD.NS","MARICO.NS","DABUR.NS","JYOTHYLAB.NS",
    "VBL.NS","RADICO.NS","MCDOWELL-N.NS","IEX.NS","TATACOMM.NS",
    "LTTS.NS","DLF.NS","GODREJPROP.NS","PRESTIGE.NS","BRIGADE.NS",
    "SOBHA.NS","PHOENIXLTD.NS","LINDEINDIA.NS","JSWINFRA.NS","GMRINFRA.NS",
    "IRB.NS","PNCINFRA.NS","KNRCON.NS","NCC.NS","FLUOROCHEM.NS",
    "LICI.NS","STARCEMENT.NS","KAJARIACER.NS","CERA.NS","DIXON.NS",
    "ROUTE.NS","LATENTVIEW.NS","MASTEK.NS","TEJASNET.NS","STLTECH.NS",
    "RITES.NS","MIDHANI.NS","GARDENREACH.NS","RTNPOWER.NS","GEPIL.NS",
    "GREENPANEL.NS","CENTURYPLY.NS","NUVAMA.NS","360ONE.NS","ANGELONE.NS",
    "MOTILALOFS.NS","EDELWEISS.NS","IIFL.NS","POONAWALLA.NS","CREDITACC.NS",
    "SPANDANA.NS","UTKARSHBNK.NS","EQUITASBNK.NS","SURYODAY.NS","MAHABANK.NS",
    "UCOBANK.NS","CENTRALBNK.NS","INDIANB.NS","IOB.NS","KARURVYSYA.NS",
    "SOUTHBANK.NS","DCBBANK.NS","CITYUNIONBANK.NS","CHOLAHLDNG.NS","BAJAJHLDNG.NS",
    "LICHOUSING.NS","SBFC.NS","INDIAGLYCO.NS","TRIVENI.NS","BALRAMCHIN.NS",
    "RENUKA.NS","DCMSHRIRAM.NS","CHAMBALFERT.NS","GNFC.NS","GSFC.NS",
    "RCF.NS","NFL.NS","COROMANDEL.NS","PIIND.NS","SUMICHEM.NS",
    "RALLIS.NS","TATACHEM.NS","GHCL.NS","JUBLPHARMA.NS","GLENMARK.NS",
    "FDC.NS","MANKIND.NS","WOCKPHARMA.NS","STRIDES.NS","ALEMBICLTD.NS",
    "APLLTD.NS","CAPLIPOINT.NS","AARTI.NS","AARTIDRUGS.NS","KFINTECH.NS",
    "TIINDIA.NS","SUPRAJIT.NS","ENDURANCE.NS","SCHAEFFLER.NS","SKFINDIA.NS",
    "GRINDWELL.NS","CARBORUNIV.NS","INOXWIND.NS","JSWENERGY.NS","WAAREEENER.NS",
    "HFCL.NS","M&MFIN.NS","OBEROIRLTY.NS","MAHLIFE.NS","APTUS.NS",
    "HOMEFIRST.NS","CAMS.NS","IPCALAB.NS","DIVI.NS","PIRAMAL.NS",
    "MM.NS","TATACHEM.NS","ZYDUSLIFE.NS","GLAND.NS","SUVEN.NS",
]))

def calculate_signal(symbol):
    try:
        df = yf.download(symbol, period="3mo", interval="1d", progress=False)
        if df.empty or len(df) < 30:
            return None
        close = df["Close"].squeeze()
        volume = df["Volume"].squeeze()
        rsi = ta.momentum.RSIIndicator(close).rsi().iloc[-1]
        ema20 = ta.trend.EMAIndicator(close, window=20).ema_indicator().iloc[-1]
        ema50 = ta.trend.EMAIndicator(close, window=50).ema_indicator().iloc[-1]
        macd_obj = ta.trend.MACD(close)
        macd_line = macd_obj.macd().iloc[-1]
        signal_line = macd_obj.macd_signal().iloc[-1]
        current_price = float(close.iloc[-1])
        avg_volume = float(volume.tail(20).mean())
        latest_volume = float(volume.iloc[-1])
        volume_surge = latest_volume > (avg_volume * 1.5)

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

        return {
            "symbol": symbol.replace(".NS",""),
            "price": round(current_price, 2),
            "signal": signal,
            "buy_score": buy_score,
            "rsi": round(float(rsi), 1),
            "trend": "UP" if ema20 > ema50 else "DOWN",
            "volume_surge": "YES" if volume_surge else "no",
            "macd": "BULLISH" if macd_line > signal_line else "BEARISH"
        }
    except:
        return None

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        r = requests.post(url, data=payload, timeout=15)
        print(f"Telegram: {r.status_code}")
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

def run_scanner():
    today = datetime.now().strftime('%d %b %Y')
    now = datetime.now().strftime('%I:%M %p')
    print(f"NSE Scanner starting — {today} {now}")

    # Portfolio scan
    print("Scanning portfolio...")
    portfolio_results = []
    for symbol in MY_PORTFOLIO:
        result = calculate_signal(symbol)
        if result:
            portfolio_results.append(result)
        time.sleep(0.5)

    # Full NSE scan
    print(f"Scanning {len(NSE_STOCKS)} stocks...")
    all_results = []
    for i, symbol in enumerate(NSE_STOCKS):
        result = calculate_signal(symbol)
        if result:
            all_results.append(result)
        if (i+1) % 100 == 0:
            print(f"Progress: {i+1}/{len(NSE_STOCKS)} | Found: {len(all_results)}")
        time.sleep(0.3)

    # Sort results
    strong_buys = sorted([r for r in all_results if r['signal']=="STRONG BUY"], key=lambda x: x['buy_score'], reverse=True)
    buys = sorted([r for r in all_results if r['signal']=="BUY"], key=lambda x: x['buy_score'], reverse=True)
    top20 = (strong_buys + buys)[:20]
    sell_count = len([r for r in all_results if "SELL" in r['signal']])
    buy_count = len(strong_buys) + len(buys)

    if buy_count > sell_count * 1.5: mood = "BULLISH 🟢"; mood_note = "Good day to look for entries"
    elif sell_count > buy_count * 1.5: mood = "BEARISH 🔴"; mood_note = "Be cautious today"
    else: mood = "NEUTRAL 🟡"; mood_note = "Mixed signals, wait for clarity"

    # Save CSV
    csv_file = f"scan_{datetime.now().strftime('%Y%m%d')}.csv"
    if all_results:
        pd.DataFrame(all_results).to_csv(csv_file, index=False)

    # Build Telegram message
    port_lines = ""
    for r in portfolio_results:
        e = "🟢" if "BUY" in r['signal'] else "🔴" if "SELL" in r['signal'] else "🟡"
        port_lines += f"{e} <b>{r['symbol']}</b> ₹{r['price']} | {r['signal']} | RSI:{r['rsi']}\n"

    top_lines = ""
    for i, r in enumerate(top20[:10], 1):
        top_lines += f"{i}. <b>{r['symbol']}</b> ₹{r['price']} | RSI:{r['rsi']} | Vol:{r['volume_surge']}\n"

    tg_msg = f"""📈 <b>NSE Daily Scanner — {today}</b>

🌡 <b>Market Mood: {mood}</b>
{mood_note}

📊 Scanned: {len(all_results)} stocks
🟢 Buy: {buy_count} | 🔴 Sell: {sell_count}

━━━━━━━━━━━━━━━━━━━━
💼 <b>YOUR PORTFOLIO</b>
━━━━━━━━━━━━━━━━━━━━
{port_lines}
━━━━━━━━━━━━━━━━━━━━
🏆 <b>TOP 10 OPPORTUNITIES</b>
━━━━━━━━━━━━━━━━━━━━
{top_lines}
⚠️ Signals only. Do your own research before trading."""

    send_telegram(tg_msg)

    # Build email
    port_html = ""
    for r in portfolio_results:
        c = "#27ae60" if "BUY" in r['signal'] else "#e74c3c" if "SELL" in r['signal'] else "#f39c12"
        port_html += f"<tr><td><b>{r['symbol']}</b></td><td>₹{r['price']}</td><td style='color:{c}'><b>{r['signal']}</b></td><td>{r['rsi']}</td><td>{r['trend']}</td><td>{r['volume_surge']}</td></tr>"

    top_html = ""
    for i, r in enumerate(top20, 1):
        c = "#1e8449" if "STRONG" in r['signal'] else "#27ae60"
        top_html += f"<tr><td>{i}</td><td><b>{r['symbol']}</b></td><td>₹{r['price']}</td><td style='color:{c}'><b>{r['signal']}</b></td><td>{r['rsi']}</td><td>{r['trend']}</td><td>{r['volume_surge']}</td></tr>"

    email_html = f"""<html><body style="font-family:Arial,sans-serif;max-width:800px;margin:auto;padding:20px">
<h2 style="color:#2c3e50;border-bottom:2px solid #3498db;padding-bottom:10px">
📈 NSE Daily Scanner — {today} {now}</h2>
<div style="background:#eaf4fb;padding:15px;border-radius:8px;border-left:4px solid #3498db;margin-bottom:20px">
<h3 style="margin:0">🌡 Market Mood: <span style="color:{'#27ae60' if 'BULL' in mood else '#e74c3c' if 'BEAR' in mood else '#e67e22'}">{mood}</span></h3>
<p style="margin:5px 0 0">Scanned <b>{len(all_results)}</b> stocks | Buy signals: <b>{buy_count}</b> | Sell signals: <b>{sell_count}</b></p>
</div>
<h3 style="color:#2c3e50">💼 Your Portfolio</h3>
<table border="1" cellpadding="8" cellspacing="0" style="width:100%;border-collapse:collapse;font-size:14px">
<tr style="background:#2c3e50;color:white"><th>Stock</th><th>Price</th><th>Signal</th><th>RSI</th><th>Trend</th><th>Volume</th></tr>
{port_html}</table>
<h3 style="color:#2c3e50;margin-top:25px">🏆 Top 20 Buy Opportunities Today</h3>
<table border="1" cellpadding="8" cellspacing="0" style="width:100%;border-collapse:collapse;font-size:14px">
<tr style="background:#2c3e50;color:white"><th>#</th><th>Stock</th><th>Price</th><th>Signal</th><th>RSI</th><th>Trend</th><th>Volume</th></tr>
{top_html}</table>
<p style="color:#7f8c8d;font-size:12px;margin-top:20px;border-top:1px solid #eee;padding-top:10px">
⚠️ These are technical signals only. Always do your own research before investing.<br>
Full scan results attached as CSV.</p>
</body></html>"""

    send_email(
        subject=f"📈 NSE Scanner {today} | {mood} | Top: {top20[0]['symbol'] if top20 else 'N/A'}",
        body=email_html,
        csv_file=csv_file
    )

    print(f"\n✅ Done! Scanned {len(all_results)} stocks.")
    print(f"Top pick: {top20[0]['symbol'] if top20 else 'N/A'}")

run_scanner()
