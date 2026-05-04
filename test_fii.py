# ============================================================
# FII/DII LIVE TEST — checks today's data specifically
# ============================================================
import requests
import time
import json
from datetime import datetime

today = datetime.now().strftime('%d-%b-%Y')
print("="*50)
print(f"FII/DII LIVE TEST — Looking for {today}")
print("="*50)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://www.nseindia.com/',
    'Connection': 'keep-alive',
    'Cache-Control': 'no-cache',
}
session = requests.Session()
session.headers.update(headers)

print("\n[1] Warming up NSE session...")
r1 = session.get('https://www.nseindia.com/', timeout=15)
print(f"   Homepage: {r1.status_code}")
time.sleep(2)

r2 = session.get('https://www.nseindia.com/market-data/fii-dii-activity', timeout=15)
print(f"   FII page: {r2.status_code}")
time.sleep(2)

r3 = session.get('https://www.nseindia.com/market-data/equity-market', timeout=15)
print(f"   Equity page: {r3.status_code}")
time.sleep(2)

print("\n[2] Fetching FII/DII data...")
r = session.get('https://www.nseindia.com/api/fiidiiTradeReact', timeout=20)
print(f"   API status: {r.status_code}")
print(f"   Full response: {r.text[:500]}")

if r.status_code == 200 and r.text:
    try:
        data = r.json()
        print(f"\n[3] Parsing {len(data)} records...")
        fii_net = None; dii_net = None; date = ""
        for item in data:
            cat = item.get('category','').upper()
            net = float(str(item.get('netValue','0')).replace(',',''))
            dt = item.get('date','')
            print(f"   {cat}: date={dt} net=₹{net:,.2f}Cr")
            if 'FII' in cat or 'FPI' in cat:
                fii_net = net; date = dt
            elif 'DII' in cat:
                dii_net = net

        print(f"\n[4] RESULT:")
        print(f"   Date    : {date}")
        print(f"   Today   : {today}")
        print(f"   FII Net : ₹{fii_net:,.2f} Cr ({'BUYING' if fii_net>0 else 'SELLING'})")
        print(f"   DII Net : ₹{dii_net:,.2f} Cr ({'BUYING' if dii_net>0 else 'SELLING'})")
        if date == today:
            print(f"   ✅ TODAY'S DATA CONFIRMED")
        else:
            print(f"   ⚠️ Showing {date} data — today's not published yet")
    except Exception as e:
        print(f"   Parse error: {e}")
