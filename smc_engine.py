# ============================================================
# SMC ENGINE v1.0 — Smart Money Concepts + Price Action
# Standalone library — imported by scanner.py and confluence_scanner.py
# Covers: Order Blocks, FVG, BOS/CHoCH, Liquidity, S/R,
#         Supply/Demand, Premium/Discount, Inducement,
#         Market Stage, Candlestick Patterns, Killzones
# ============================================================
import numpy as np
import pandas as pd
from datetime import datetime, time
import pytz

IST = pytz.timezone("Asia/Kolkata")


# ─────────────────────────────────────────────────────────────
# 1. MARKET STAGE CLASSIFIER (200MA based)
# ─────────────────────────────────────────────────────────────
def classify_market_stage(df):
    """
    Advancing    = price > 200MA, 200MA up, HH+HL
    Declining    = price < 200MA, 200MA down, LH+LL
    Distribution = price > 200MA, 200MA flat (top forming)
    Accumulation = price < 200MA, 200MA flat (base forming)
    """
    if len(df) < 200:
        return "Unknown"
    try:
        close = df["Close"].squeeze()
        ma200 = close.rolling(200).mean()
        last_close = float(close.iloc[-1])
        last_ma200 = float(ma200.iloc[-1])
        prev_ma200 = float(ma200.iloc[-10])
        ma200_slope = last_ma200 - prev_ma200
        flat = abs(ma200_slope) < (last_ma200 * 0.0015)
        recent = df.tail(30)
        highs = recent["High"].squeeze().values
        lows  = recent["Low"].squeeze().values
        mid   = len(highs) // 2
        hh = float(highs[-1]) > float(highs[mid])
        hl = float(lows[-1])  > float(lows[mid])
        lh = float(highs[-1]) < float(highs[mid])
        ll = float(lows[-1])  < float(lows[mid])
        if last_close > last_ma200 and ma200_slope > 0 and hh and hl:
            return "Advancing"
        elif last_close < last_ma200 and ma200_slope < 0 and lh and ll:
            return "Declining"
        elif last_close > last_ma200 and flat:
            return "Distribution"
        elif last_close < last_ma200 and flat:
            return "Accumulation"
    except:
        pass
    return "Unknown"


# ─────────────────────────────────────────────────────────────
# 2. SUPPORT & RESISTANCE ZONES
# ─────────────────────────────────────────────────────────────
def find_support_resistance(df, lookback=100, merge_pct=0.003):
    if len(df) < 20:
        return []
    try:
        data  = df.tail(lookback).copy().reset_index(drop=True)
        highs = data["High"].squeeze().values.astype(float)
        lows  = data["Low"].squeeze().values.astype(float)
        closes= data["Close"].squeeze().values.astype(float)
        sh, sl = [], []
        for i in range(2, len(data)-2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
               highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                sh.append(highs[i])
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
               lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                sl.append(lows[i])

        def cluster(prices, ztype):
            if not prices: return []
            prices = sorted(prices)
            zones, grp = [], [prices[0]]
            for p in prices[1:]:
                if (p - grp[-1]) / grp[-1] < merge_pct:
                    grp.append(p)
                else:
                    zones.append({"price":round(float(np.mean(grp)),2),"type":ztype,"strength":len(grp)})
                    grp = [p]
            zones.append({"price":round(float(np.mean(grp)),2),"type":ztype,"strength":len(grp)})
            return zones

        zones = cluster(sh,"resistance") + cluster(sl,"support")
        lc = float(closes[-1])
        for z in zones:
            z["distance_pct"] = round(abs(z["price"]-lc)/lc*100, 2)
        zones.sort(key=lambda x: x["distance_pct"])
        return zones
    except:
        return []


def nearest_sr(df, lookback=100):
    zones = find_support_resistance(df, lookback)
    lc    = float(df["Close"].squeeze().iloc[-1])
    sups  = [z for z in zones if z["price"] < lc]
    ress  = [z for z in zones if z["price"] > lc]
    return (max(sups, key=lambda x: x["price"]) if sups else None,
            min(ress, key=lambda x: x["price"]) if ress else None)


# ─────────────────────────────────────────────────────────────
# 3. SUPPLY & DEMAND ZONES
# ─────────────────────────────────────────────────────────────
def find_supply_demand_zones(df, lookback=100):
    if len(df) < 20: return []
    try:
        data   = df.tail(lookback).copy().reset_index(drop=True)
        closes = data["Close"].squeeze().values.astype(float)
        opens  = data["Open"].squeeze().values.astype(float)
        highs  = data["High"].squeeze().values.astype(float)
        lows   = data["Low"].squeeze().values.astype(float)
        vols   = data["Volume"].squeeze().values.astype(float) if "Volume" in data.columns else np.ones(len(data))
        avg_vol = float(np.mean(vols))
        zones, lc = [], float(closes[-1])
        for i in range(1, len(data)-1):
            rng = highs[i] - lows[i]
            if rng == 0: continue
            body_pct  = abs(closes[i]-opens[i]) / rng
            vol_ratio = vols[i]/avg_vol if avg_vol > 0 else 1
            if closes[i] < opens[i] and body_pct > 0.6 and vol_ratio > 1.2:
                zh = round(float(max(opens[i], closes[i-1])), 2)
                zl = round(float(opens[i]), 2)
                zones.append({"type":"supply","zone_high":zh,"zone_low":zl,
                              "strength":round(vol_ratio,2),"mitigated": lc > zh})
            if closes[i] > opens[i] and body_pct > 0.6 and vol_ratio > 1.2:
                zh = round(float(opens[i]), 2)
                zl = round(float(min(opens[i], closes[i-1])), 2)
                zones.append({"type":"demand","zone_high":zh,"zone_low":zl,
                              "strength":round(vol_ratio,2),"mitigated": lc < zl})
        return [z for z in zones if not z["mitigated"]]
    except:
        return []


# ─────────────────────────────────────────────────────────────
# 4. ORDER BLOCKS (ICT)
# ─────────────────────────────────────────────────────────────
def find_order_blocks(df, lookback=50, min_move_pct=1.5):
    if len(df) < 10: return []
    try:
        data   = df.tail(lookback).copy().reset_index(drop=True)
        opens  = data["Open"].squeeze().values.astype(float)
        closes = data["Close"].squeeze().values.astype(float)
        obs, lc = [], float(closes[-1])
        for i in range(1, len(data)-3):
            mu = (closes[i+2]-closes[i])/closes[i]*100
            md = (closes[i]-closes[i+2])/closes[i]*100
            if closes[i] < opens[i] and mu >= min_move_pct:
                obs.append({"type":"bullish_ob","ob_high":round(float(opens[i]),2),
                            "ob_low":round(float(closes[i]),2),"move_pct":round(mu,2),
                            "mitigated": lc < float(closes[i])})
            if closes[i] > opens[i] and md >= min_move_pct:
                obs.append({"type":"bearish_ob","ob_high":round(float(closes[i]),2),
                            "ob_low":round(float(opens[i]),2),"move_pct":round(md,2),
                            "mitigated": lc > float(closes[i])})
        return [o for o in obs if not o["mitigated"]]
    except:
        return []


def price_at_order_block(price, obs, tol=0.5):
    for ob in obs:
        lo = ob["ob_low"]  * (1 - tol/100)
        hi = ob["ob_high"] * (1 + tol/100)
        if lo <= price <= hi:
            return ob
    return None


# ─────────────────────────────────────────────────────────────
# 5. FAIR VALUE GAP (FVG) / IMBALANCE
# ─────────────────────────────────────────────────────────────
def find_fvg(df, lookback=50):
    if len(df) < 10: return []
    try:
        data   = df.tail(lookback).copy().reset_index(drop=True)
        highs  = data["High"].squeeze().values.astype(float)
        lows   = data["Low"].squeeze().values.astype(float)
        closes = data["Close"].squeeze().values.astype(float)
        fvgs, lc = [], float(closes[-1])
        for i in range(1, len(data)-1):
            if highs[i-1] < lows[i+1]:
                fh, fl = round(float(lows[i+1]),2), round(float(highs[i-1]),2)
                filled = (fl <= lc <= fh) or lc < fl
                fvgs.append({"type":"bullish_fvg","fvg_high":fh,"fvg_low":fl,"filled":filled})
            if lows[i-1] > highs[i+1]:
                fh, fl = round(float(lows[i-1]),2), round(float(highs[i+1]),2)
                filled = (fl <= lc <= fh) or lc > fh
                fvgs.append({"type":"bearish_fvg","fvg_high":fh,"fvg_low":fl,"filled":filled})
        return [f for f in fvgs if not f["filled"]]
    except:
        return []


def nearest_fvg(df, lookback=50):
    fvgs = find_fvg(df, lookback)
    lc   = float(df["Close"].squeeze().iloc[-1])
    above = [f for f in fvgs if f["fvg_low"] > lc]
    below = [f for f in fvgs if f["fvg_high"] < lc]
    return (max(below, key=lambda x: x["fvg_high"]) if below else None,
            min(above, key=lambda x: x["fvg_low"])  if above else None)


# ─────────────────────────────────────────────────────────────
# 6. BREAK OF STRUCTURE (BOS) & CHANGE OF CHARACTER (CHoCH)
# ─────────────────────────────────────────────────────────────
def detect_bos_choch(df, lookback=50):
    if len(df) < 20:
        return {"bos":None,"choch":None,"trend":"Unknown"}
    try:
        data   = df.tail(lookback).copy().reset_index(drop=True)
        highs  = data["High"].squeeze().values.astype(float)
        lows   = data["Low"].squeeze().values.astype(float)
        closes = data["Close"].squeeze().values.astype(float)
        sh, sl = [], []
        for i in range(2, len(data)-2):
            if highs[i]>highs[i-1] and highs[i]>highs[i-2] and highs[i]>highs[i+1] and highs[i]>highs[i+2]:
                sh.append((i, highs[i]))
            if lows[i]<lows[i-1] and lows[i]<lows[i-2] and lows[i]<lows[i+1] and lows[i]<lows[i+2]:
                sl.append((i, lows[i]))
        if len(sh) < 2 or len(sl) < 2:
            return {"bos":None,"choch":None,"trend":"Unknown"}
        lc  = float(closes[-1])
        sh2 = sh[-1][1]; sh1 = sh[-2][1]
        sl2 = sl[-1][1]; sl1 = sl[-2][1]
        trend = "Bullish" if sh2>sh1 and sl2>sl1 else "Bearish" if sh2<sh1 and sl2<sl1 else "Ranging"
        bos = choch = None
        if trend=="Bullish" and lc>sh2:
            bos = {"direction":"Bullish_BOS","level":round(sh2,2),"message":f"Bullish BOS — broke above ₹{sh2:.2f}"}
        if trend=="Bearish" and lc<sl2:
            bos = {"direction":"Bearish_BOS","level":round(sl2,2),"message":f"Bearish BOS — broke below ₹{sl2:.2f}"}
        if trend=="Bullish" and lc<sl2:
            choch = {"direction":"Bearish_CHoCH","level":round(sl2,2),"message":f"⚠️ CHoCH — broke below ₹{sl2:.2f} (reversal warning)"}
        if trend=="Bearish" and lc>sh2:
            choch = {"direction":"Bullish_CHoCH","level":round(sh2,2),"message":f"✅ CHoCH — broke above ₹{sh2:.2f} (potential reversal up)"}
        return {"bos":bos,"choch":choch,"trend":trend}
    except:
        return {"bos":None,"choch":None,"trend":"Unknown"}


# ─────────────────────────────────────────────────────────────
# 7. LIQUIDITY POOLS & SWEEPS
# ─────────────────────────────────────────────────────────────
def find_liquidity_pools(df, lookback=50):
    if len(df) < 20:
        return {"bsl":[],"ssl":[],"swept":[]}
    try:
        data   = df.tail(lookback).copy().reset_index(drop=True)
        highs  = data["High"].squeeze().values.astype(float)
        lows   = data["Low"].squeeze().values.astype(float)
        closes = data["Close"].squeeze().values.astype(float)
        thr    = 0.002
        bsl, ssl, seen_h, seen_l = [], [], set(), set()
        for i in range(len(highs)):
            ch = [highs[i]]
            for j in range(i+1, len(highs)):
                if abs(highs[j]-highs[i])/highs[i] < thr: ch.append(highs[j])
            if len(ch) >= 2:
                key = round(float(np.mean(ch)),2)
                if key not in seen_h:
                    seen_h.add(key); bsl.append({"price":key,"touches":len(ch),"type":"BSL"})
            cl = [lows[i]]
            for j in range(i+1, len(lows)):
                if abs(lows[j]-lows[i])/lows[i] < thr: cl.append(lows[j])
            if len(cl) >= 2:
                key = round(float(np.mean(cl)),2)
                if key not in seen_l:
                    seen_l.add(key); ssl.append({"price":key,"touches":len(cl),"type":"SSL"})
        lc, lh, ll = float(closes[-1]), float(highs[-1]), float(lows[-1])
        swept = []
        for lv in bsl:
            if lh > lv["price"] and lc < lv["price"]:
                swept.append({"type":"BSL_Swept","price":lv["price"],"message":f"BSL swept ₹{lv['price']} — likely reversal DOWN"})
        for lv in ssl:
            if ll < lv["price"] and lc > lv["price"]:
                swept.append({"type":"SSL_Swept","price":lv["price"],"message":f"SSL swept ₹{lv['price']} — likely reversal UP ✅"})
        return {"bsl":bsl[:5],"ssl":ssl[:5],"swept":swept}
    except:
        return {"bsl":[],"ssl":[],"swept":[]}


# ─────────────────────────────────────────────────────────────
# 8. PREMIUM & DISCOUNT (Fibonacci 50%)
# ─────────────────────────────────────────────────────────────
def premium_discount(df, lookback=50):
    try:
        data = df.tail(lookback)
        sh   = float(data["High"].squeeze().max())
        sl   = float(data["Low"].squeeze().min())
        lc   = float(data["Close"].squeeze().iloc[-1])
        if sh == sl: return None
        rng  = sh - sl
        eq   = (sh + sl) / 2
        pos  = (lc - sl) / rng * 100
        f618 = sh - rng * 0.618
        f79  = sh - rng * 0.79
        return {
            "swing_high":   round(sh,2), "swing_low":round(sl,2),
            "equilibrium":  round(eq,2),
            "fib_618":      round(f618,2), "fib_79":round(f79,2),
            "current_zone": "Discount" if lc < eq else "Premium",
            "position_pct": round(pos,1),
            "bias":         "BUY zone" if lc < eq else "SELL zone",
            "in_ote":       f79 <= lc <= f618,
        }
    except:
        return None


# ─────────────────────────────────────────────────────────────
# 9. INDUCEMENT DETECTION
# ─────────────────────────────────────────────────────────────
def detect_inducement(df, lookback=30):
    if len(df) < 15: return []
    try:
        data   = df.tail(lookback).copy().reset_index(drop=True)
        highs  = data["High"].squeeze().values.astype(float)
        lows   = data["Low"].squeeze().values.astype(float)
        closes = data["Close"].squeeze().values.astype(float)
        signals, thr = [], 0.005
        for i in range(5, len(data)-2):
            ph = float(max(highs[i-5:i]))
            pl = float(min(lows[i-5:i]))
            if highs[i]>ph and (highs[i]-ph)/ph<thr and closes[i]<ph:
                signals.append({"type":"Bearish_Inducement","level":round(ph,2),
                                "message":f"⚠️ Bearish inducement trap near ₹{ph:.2f}"})
            if lows[i]<pl and (pl-lows[i])/pl<thr and closes[i]>pl:
                signals.append({"type":"Bullish_Inducement","level":round(pl,2),
                                "message":f"✅ Bullish inducement near ₹{pl:.2f} — false breakdown"})
        return signals[-3:] if signals else []
    except:
        return []


# ─────────────────────────────────────────────────────────────
# 10. CANDLESTICK PATTERNS
# ─────────────────────────────────────────────────────────────
def detect_candle_patterns(df):
    if len(df) < 3: return []
    try:
        data   = df.tail(5).copy().reset_index(drop=True)
        opens  = data["Open"].squeeze().values.astype(float)
        closes = data["Close"].squeeze().values.astype(float)
        highs  = data["High"].squeeze().values.astype(float)
        lows   = data["Low"].squeeze().values.astype(float)
        patterns, i = [], len(data)-1
        body  = abs(closes[i]-opens[i])
        rng   = highs[i]-lows[i]
        if rng == 0: return []
        upper = highs[i] - max(opens[i],closes[i])
        lower = min(opens[i],closes[i]) - lows[i]
        bpct  = body/rng
        if lower>=2*body and upper<=0.1*rng and closes[i]>opens[i]:
            patterns.append({"pattern":"Hammer","bias":"Bullish","strength":"Strong"})
        if upper>=2*body and lower<=0.1*rng and closes[i]<opens[i]:
            patterns.append({"pattern":"Shooting Star","bias":"Bearish","strength":"Strong"})
        if bpct < 0.05:
            patterns.append({"pattern":"Doji","bias":"Neutral","strength":"Weak"})
        if bpct > 0.92:
            patterns.append({"pattern":"Marubozu","bias":"Bullish" if closes[i]>opens[i] else "Bearish","strength":"Very Strong"})
        if i >= 1:
            if closes[i-1]<opens[i-1] and closes[i]>opens[i] and opens[i]<closes[i-1] and closes[i]>opens[i-1]:
                patterns.append({"pattern":"Bullish Engulfing","bias":"Bullish","strength":"Very Strong"})
            if closes[i-1]>opens[i-1] and closes[i]<opens[i] and opens[i]>closes[i-1] and closes[i]<opens[i-1]:
                patterns.append({"pattern":"Bearish Engulfing","bias":"Bearish","strength":"Very Strong"})
        if i >= 2:
            if (closes[i-2]<opens[i-2] and abs(closes[i-1]-opens[i-1])<abs(closes[i-2]-opens[i-2])*0.3
                    and closes[i]>opens[i] and closes[i]>(opens[i-2]+closes[i-2])/2):
                patterns.append({"pattern":"Morning Star","bias":"Bullish","strength":"Very Strong"})
            if (closes[i-2]>opens[i-2] and abs(closes[i-1]-opens[i-1])<abs(closes[i-2]-opens[i-2])*0.3
                    and closes[i]<opens[i] and closes[i]<(opens[i-2]+closes[i-2])/2):
                patterns.append({"pattern":"Evening Star","bias":"Bearish","strength":"Very Strong"})
        return patterns
    except:
        return []


# ─────────────────────────────────────────────────────────────
# 11. KILLZONE TIME FILTER (IST)
# ─────────────────────────────────────────────────────────────
def get_killzone():
    try:
        now = datetime.now(IST).time()
        zones = [
            (time(9,15),  time(9,45),  "NSE_OPEN",     "MEDIUM","Often fake move — wait for direction"),
            (time(9,45),  time(11,0),  "MORNING_TREND","HIGH",  "Real direction establishing — good entries"),
            (time(11,0),  time(12,0),  "MID_MORNING",  "MEDIUM","Good momentum continuation"),
            (time(12,0),  time(13,30), "MIDDAY_CHOP",  "LOW",   "Avoid — choppy, low volume"),
            (time(13,30), time(14,0),  "PRE_POWER",    "MEDIUM","Setting up for power hour"),
            (time(14,0),  time(15,30), "POWER_HOUR",   "HIGH",  "Best time — real moves, high volume"),
        ]
        for s, e, name, quality, note in zones:
            if s <= now <= e:
                return {"zone":name,"quality":quality,"note":note,"trade":quality!="LOW"}
    except:
        pass
    return {"zone":"MARKET_CLOSED","quality":"NONE","note":"Market closed","trade":False}


# ─────────────────────────────────────────────────────────────
# 12. MASTER SMC SCORE
# Returns score + all details — designed to ADD to existing scores
# ─────────────────────────────────────────────────────────────
def calculate_smc_score(df, symbol=""):
    """
    Core function used by scanner.py and confluence_scanner.py.
    Returns a dict with smc_score (integer) and full analysis details.
    smc_score is meant to be ADDED to existing RSI/momentum scores.
    """
    empty = {"smc_score":0,"smc_signal":"NEUTRAL","smc_details":[],
             "smc_warnings":[],"stage":"Unknown","order_block":None,
             "fvg_below":None,"fvg_above":None,"bos_choch":{},
             "premium_disc":None,"liquidity":{},"candle_patterns":[],
             "supply_demand":[],"sr_zones":[]}
    if df is None or len(df) < 30:
        return empty

    try:
        lc = float(df["Close"].squeeze().iloc[-1])
        score, details, warnings = 0, [], []

        # 1. Stage
        stage = classify_market_stage(df)
        if stage == "Advancing":
            score += 20; details.append("✅ Advancing stage (200MA up, HH+HL)")
        elif stage == "Accumulation":
            score += 8;  details.append("⚠️ Accumulation — base forming, watch for breakout")
        elif stage == "Declining":
            score -= 20; warnings.append("🔴 Declining stage — avoid longs")
        elif stage == "Distribution":
            score -= 8;  warnings.append("⚠️ Distribution — possible top forming")

        # 2. Premium/Discount
        pd_z = premium_discount(df)
        if pd_z:
            if pd_z["current_zone"] == "Discount":
                score += 12; details.append(f"✅ Discount zone ({pd_z['position_pct']}% of range)")
            else:
                score -= 8;  warnings.append(f"⚠️ Premium zone ({pd_z['position_pct']}%) — not ideal to buy")
            if pd_z["in_ote"]:
                score += 8;  details.append("✅ OTE zone (62–79% retracement) — institutional entry")

        # 3. Order Block
        obs   = find_order_blocks(df)
        at_ob = price_at_order_block(lc, obs)
        if at_ob:
            if at_ob["type"] == "bullish_ob":
                score += 18; details.append(f"✅ At Bullish OB ₹{at_ob['ob_low']}–₹{at_ob['ob_high']}")
            else:
                score -= 12; warnings.append(f"⚠️ At Bearish OB ₹{at_ob['ob_low']}–₹{at_ob['ob_high']}")

        # 4. FVG
        fvg_below, fvg_above = nearest_fvg(df)
        if fvg_below and fvg_below["type"] == "bullish_fvg":
            dist = (lc - fvg_below["fvg_high"]) / lc * 100
            if dist < 3:
                score += 8; details.append(f"✅ Bullish FVG support ₹{fvg_below['fvg_low']}–₹{fvg_below['fvg_high']} ({dist:.1f}% away)")

        # 5. BOS/CHoCH
        bos_choch = detect_bos_choch(df)
        if bos_choch.get("bos"):
            if "Bullish" in bos_choch["bos"]["direction"]:
                score += 12; details.append(f"✅ {bos_choch['bos']['message']}")
            else:
                score -= 12; warnings.append(f"🔴 {bos_choch['bos']['message']}")
        if bos_choch.get("choch"):
            if "Bullish" in bos_choch["choch"]["direction"]:
                score += 8;  details.append(f"✅ {bos_choch['choch']['message']}")
            else:
                score -= 15; warnings.append(f"🔴 {bos_choch['choch']['message']}")

        # 6. Liquidity sweep
        liq = find_liquidity_pools(df)
        for sweep in liq.get("swept", []):
            if "UP" in sweep["message"]:
                score += 12; details.append(f"✅ {sweep['message']}")
            else:
                score -= 8;  warnings.append(f"⚠️ {sweep['message']}")

        # 7. Inducement
        for ind in detect_inducement(df):
            if "Bullish" in ind["type"]:
                score += 5; details.append(f"✅ {ind['message']}")
            else:
                warnings.append(f"⚠️ {ind['message']}")

        # 8. Candle patterns
        patterns = detect_candle_patterns(df)
        pts_map  = {"Very Strong":12,"Strong":8,"Moderate":5,"Weak":2}
        for p in patterns:
            pts = pts_map.get(p["strength"],5)
            if p["bias"] == "Bullish":
                score += pts; details.append(f"✅ {p['pattern']} ({p['strength']})")
            elif p["bias"] == "Bearish":
                score -= pts; warnings.append(f"🔴 {p['pattern']} ({p['strength']})")

        # Signal label
        if   score >= 55: signal = "STRONG_BUY"
        elif score >= 35: signal = "BUY"
        elif score >= 15: signal = "WEAK_BUY"
        elif score <= -35: signal = "STRONG_SELL"
        elif score <= -15: signal = "SELL"
        else:             signal = "NEUTRAL"

        return {
            "smc_score":      score,
            "smc_signal":     signal,
            "smc_details":    details,
            "smc_warnings":   warnings,
            "stage":          stage,
            "order_block":    at_ob,
            "fvg_below":      fvg_below,
            "fvg_above":      fvg_above,
            "bos_choch":      bos_choch,
            "premium_disc":   pd_z,
            "liquidity":      liq,
            "candle_patterns": patterns,
            "supply_demand":  find_supply_demand_zones(df),
            "sr_zones":       find_support_resistance(df),
        }
    except Exception as e:
        print(f"SMC score error ({symbol}): {e}")
        return empty


# ─────────────────────────────────────────────────────────────
# 13. HTML FORMATTER (matches existing bot's HTML style)
# ─────────────────────────────────────────────────────────────
def format_smc_section(smc):
    """Formats SMC analysis as HTML — appended to existing /analyse output."""
    if not smc or smc.get("stage") == "Unknown":
        return ""
    try:
        score  = smc.get("smc_score", 0)
        stage  = smc.get("stage", "Unknown")
        pd_z   = smc.get("premium_disc") or {}
        ob     = smc.get("order_block")
        fvg    = smc.get("fvg_below")
        bos    = smc.get("bos_choch", {})
        liq    = smc.get("liquidity", {})
        pats   = smc.get("candle_patterns", [])
        kz     = get_killzone()
        sig    = smc.get("smc_signal","NEUTRAL")
        sig_map = {"STRONG_BUY":"🚀 STRONG BUY","BUY":"🟢 BUY","WEAK_BUY":"🔵 WEAK BUY",
                   "NEUTRAL":"⚪ NEUTRAL","SELL":"🔴 SELL","STRONG_SELL":"💀 STRONG SELL"}

        lines = [
            "\n━━━━━━━━━━━━━━━━━━━━",
            "🧠 <b>SMART MONEY ANALYSIS (SMC)</b>",
            f"SMC Signal : <b>{sig_map.get(sig,sig)}</b> (Score: {score})",
            f"Stage      : <b>{stage}</b>",
        ]
        if pd_z:
            ote = " | 🎯 OTE zone" if pd_z.get("in_ote") else ""
            lines.append(f"Zone       : {pd_z.get('current_zone','N/A')} ({pd_z.get('position_pct','?')}% of range){ote}")
            lines.append(f"Equilibrium: ₹{pd_z.get('equilibrium','N/A')} | OTE: ₹{pd_z.get('fib_79','N/A')}–₹{pd_z.get('fib_618','N/A')}")
        if ob:
            ot = "Bullish ✅" if ob["type"]=="bullish_ob" else "Bearish ⚠️"
            lines.append(f"Order Block: {ot} ₹{ob['ob_low']}–₹{ob['ob_high']} ({ob['move_pct']}% move after)")
        if fvg:
            lines.append(f"FVG Support: ₹{fvg['fvg_low']}–₹{fvg['fvg_high']} (unfilled gap = price magnet)")
        if bos.get("bos"):
            lines.append(f"Structure  : {bos['bos']['message']}")
        if bos.get("choch"):
            lines.append(f"CHoCH      : {bos['choch']['message']}")
        swept = liq.get("swept", [])
        if swept:
            lines.append(f"Liquidity  : {swept[-1]['message']}")
        if pats:
            lines.append(f"Candles    : " + ", ".join([f"{p['pattern']} ({p['bias']})" for p in pats]))
        lines.append(f"Killzone   : {kz['zone']} ({kz['quality']}) — {kz['note']}")
        if smc.get("smc_details"):
            lines.append("\n✅ <b>SMC Confluence factors:</b>")
            for d in smc["smc_details"][:6]:
                lines.append(f"   {d}")
        if smc.get("smc_warnings"):
            lines.append("\n⚠️ <b>SMC Warnings:</b>")
            for w in smc["smc_warnings"][:4]:
                lines.append(f"   {w}")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)
    except Exception as e:
        return f"\n[SMC format error: {e}]"
