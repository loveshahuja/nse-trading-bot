import requests
import time
import json
import gzip
import zlib
from datetime import datetime

today = datetime.now().strftime('%d-%b-%Y')
print("="*50)
print(f"FII/DII TEST — {today}")
print("="*50)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.nseindia.com/',
    'Connection': 'keep-alive',
}
# No Accept-Encoding — let requests handle decompression automatically
session = requests.Session()
session.headers.update(headers)

print("\n[1] Warming up...")
r1 = session.get('https://www.nseindia.com/', timeout=15)
print(f"   Homepage: {r1.status_code}")
time.sleep(3)

print("\n[2] Fetching FII data...")
r = session.get('https://www.nseindia.com/api/fiidiiTradeReact', timeout=20)
print(f"   Status: {r.status_code}")
print(f"   Encoding: {r.encoding}")
print(f"   Content-Type: {r.headers.get('Content-Type','')}")

# Try multiple decode methods
text = None

# Method 1: requests auto decode
try:
    text = r.text
    if text and len(text) > 10 and text[0] == '[':
        print(f"   Method 1 (auto): ✅ {text[:100]}")
    else:
        print(f"   Method 1 (auto): ❌ {repr(text[:50])}")
        text = None
except Exception as e:
    print(f"   Method 1 error: {e}")

# Method 2: manual gzip
if not text:
    try:
        raw = gzip.decompress(r.content)
        text = raw.decode('utf-8')
        print(f"   Method 2 (gzip): ✅ {text[:100]}")
    except Exception as e:
        print(f"   Method 2 (gzip): ❌ {e}")

# Method 3: zlib
if not text:
    try:
        raw = zlib.decompress(r.content, 16+zlib.MAX_WBITS)
        text = raw.decode('utf-8')
        print(f"   Method 3 (zlib): ✅ {text[:100]}")
    except Exception as e:
        print(f"   Method 3 (zlib): ❌ {e}")

# Method 4: raw content as latin-1
if not text:
    try:
        text = r.content.decode('latin-1')
        if '[' in text:
            start = text.find('[')
            text = text[start:]
            print(f"   Method 4 (latin): ✅ {text[:100]}")
        else:
            text = None
    except Exception as e:
        print(f"   Method 4: ❌ {e}")

if text:
    try:
        data = json.loads(text)
        print(f"\n[3] Parsed {len(data)} records:")
        fii_net = None; dii_net = None; date = ""
        for item in data:
            cat = item.get('category','').upper()
            net = float(str(item.get('netValue','0')).replace(',',''))
            dt = item.get('date','')
            print(f"   {cat}: {dt} = ₹{net:,.2f} Cr")
            if 'FII' in cat or 'FPI' in cat:
                fii_net = net; date = dt
            elif 'DII' in cat:
                dii_net = net
        print(f"\n✅ FII: ₹{fii_net:,.2f} Cr | DII: ₹{dii_net:,.2f} Cr | Date: {date}")
        print(f"{'✅ TODAY DATA' if date==today else '⚠️ LATEST AVAILABLE: '+date}")
    except Exception as e:
        print(f"\n❌ JSON parse error: {e}")
        print(f"   Raw text: {repr(text[:200])}")
else:
    print("\n❌ Could not decode response")
