# ============================================================
# FII/DII TEST SCRIPT
# Run this on GitHub Actions to see which source works
# ============================================================
import requests
import time
import json

print("="*50)
print("FII/DII SOURCE TEST")
print("="*50)

results = {}

# Test 1: NSE with full warmup
print("\n[1] Testing NSE API...")
try:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.nseindia.com/',
        'Connection': 'keep-alive',
    }
    session = requests.Session()
    session.headers.update(headers)
    r1 = session.get('https://www.nseindia.com/', timeout=15)
    print(f"   NSE homepage: {r1.status_code}")
    time.sleep(4)
    r2 = session.get('https://www.nseindia.com/market-data/fii-dii-activity', timeout=15)
    print(f"   NSE FII page: {r2.status_code}")
    time.sleep(3)
    r3 = session.get('https://www.nseindia.com/api/fiidiiTradeReact', timeout=20)
    print(f"   NSE API: {r3.status_code}")
    print(f"   Response: {r3.text[:200]}")
    results['NSE'] = r3.status_code
except Exception as e:
    print(f"   Error: {e}")
    results['NSE'] = 'error'

# Test 2: BSE
print("\n[2] Testing BSE API...")
try:
    r = requests.get(
        'https://api.bseindia.com/BseIndiaAPI/api/FIIDIIData/w',
        headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.bseindia.com/'},
        timeout=15)
    print(f"   BSE: {r.status_code}")
    print(f"   Response: {r.text[:200]}")
    results['BSE'] = r.status_code
except Exception as e:
    print(f"   Error: {e}")
    results['BSE'] = 'error'

# Test 3: Tickertape
print("\n[3] Testing Tickertape...")
try:
    r = requests.get(
        'https://api.tickertape.in/market-stats/fii-dii',
        headers={'User-Agent': 'Mozilla/5.0'},
        timeout=15)
    print(f"   Tickertape: {r.status_code}")
    print(f"   Response: {r.text[:200]}")
    results['Tickertape'] = r.status_code
except Exception as e:
    print(f"   Error: {e}")
    results['Tickertape'] = 'error'

# Test 4: Screener
print("\n[4] Testing Screener.in...")
try:
    r = requests.get(
        'https://www.screener.in/api/company/NSE-NIFTY/chart/?q=Price&days=30',
        headers={'User-Agent': 'Mozilla/5.0'},
        timeout=15)
    print(f"   Screener: {r.status_code}")
    print(f"   Response: {r.text[:200]}")
    results['Screener'] = r.status_code
except Exception as e:
    print(f"   Error: {e}")
    results['Screener'] = 'error'

# Test 5: Stooq global data
print("\n[5] Testing Stooq...")
try:
    r = requests.get(
        'https://stooq.com/q/d/l/?s=^dji&i=d',
        headers={'User-Agent': 'Mozilla/5.0'},
        timeout=15)
    print(f"   Stooq: {r.status_code}")
    print(f"   Response: {r.text[:200]}")
    results['Stooq'] = r.status_code
except Exception as e:
    print(f"   Error: {e}")
    results['Stooq'] = 'error'

# Test 6: Yahoo Finance (main data source)
print("\n[6] Testing Yahoo Finance...")
try:
    import yfinance as yf
    df = yf.download("^NSEI", period="2d", interval="1d", progress=False)
    print(f"   Yahoo Finance Nifty: {'✅ Works' if not df.empty else '❌ Empty'}")
    if not df.empty:
        print(f"   Nifty close: {float(df['Close'].iloc[-1]):.2f}")
    results['Yahoo'] = 'works' if not df.empty else 'empty'
except Exception as e:
    print(f"   Error: {e}")
    results['Yahoo'] = 'error'

print("\n" + "="*50)
print("SUMMARY:")
for source, status in results.items():
    print(f"  {source}: {status}")
print("="*50)
