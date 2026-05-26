# ============================================================
# CONFLUENCE SCANNER v3.0 — uses pa_analyse() from utils.py
# ============================================================
from utils import *
import pytz
IST = pytz.timezone("Asia/Kolkata")

try:
    from smc_engine import get_killzone
    SMC_AVAILABLE = True
except ImportError:
    SMC_AVAILABLE = False

MAX_RESULTS = 3
_sent_today = set()

def already_sent(sym):
    from datetime import date
    key = f"{sym}_{date.today().isoformat()}"
    if key in _sent_today: return True
    _sent_today.add(key); return False

def log_to_sheets(results):
    try:
        sheet = setup_sheets()
        if not sheet: return
        try: ws = sheet.worksheet("Signal Log")
        except:
            ws = sheet.add_worksheet("Signal Log", rows=5000, cols=25)
            ws.append_row(["Date","Time","Stock","Setup","Signal","Score",
                           "Entry","SL","SL%","T1","T1%","T2","T2%","T3","T3%",
                           "R/R","Hold","RSI","Stage","Sector",
                           "Support","SupTouches","Resistance","AtDemand","Outcome"])
        d = datetime.now(IST).strftime('%d %b %Y')
        t = datetime.now(IST).strftime('%I:%M %p')
        for r in results:
            ws.append_row([d, t, r["symbol"], r["trade_type"], r["signal"], r["score"],
                           r["entry"], r["sl"], r["sl_pct"],
                           r["t1"], r["t1_pct"], r["t2"], r["t2_pct"],
                           r.get("t3",""), r.get("t3_pct",""),
                           r["rr"], r["hold"], r["rsi"], r["stage"], r["sector"],
                           r["support"], r["sup_touches"], r["resistance"],
                           "YES" if r["at_demand"] else "NO", "OPEN"])
        print(f"Logged {len(results)} signals")
    except Exception as e: print(f"Log error: {e}")

def run():
    today   = datetime.now(IST).strftime('%d %b %Y')
    now_str = datetime.now(IST).strftime('%I:%M %p IST')
    print(f"\n{'='*60}\nConfluence v3.0 — {today} {now_str}\n{'='*60}")

    nifty_cond, nifty_rsi = pa_nifty_condition()
    print(f"Nifty: {nifty_cond} | RSI: {nifty_rsi:.1f}")

    # ── FUND MANAGER GATE: Nifty Weekly Trend ─────────────────
    print("[GATE] Checking Nifty weekly trend...")
    nifty_weekly_ok = check_nifty_weekly_trend()
    if not nifty_weekly_ok:
        print("  ⚠️ Weekly downtrend — raising score threshold")

    # Fund Manager standard: min score 75, raised further in bad conditions
    min_score = 75
    if nifty_cond == "BEARISH":      min_score = 82
    if not nifty_weekly_ok:          min_score = max(min_score, 80)
    if nifty_cond == "OVERBOUGHT":   min_score = max(min_score, 78)
    print(f"  Min score threshold: {min_score}/100")

    sector_signals = get_sector_momentum()
    fii_dii = get_fii_dii()
    fii_net = fii_dii.get("fii_net", 0) or 0
    nse_symbols = get_nse_symbols()
    sheet = setup_sheets()
    yesterday_picks = get_persistence_watchlist(sheet)
    print(f"  Persistence watchlist: {len(yesterday_picks)} stocks from yesterday")
    print(f"Scanning {len(nse_symbols)} stocks | Min score: {min_score}...")

    results = []; scanned = 0
    for i, sym in enumerate(nse_symbols):
        try:
            if already_sent(sym.replace(".NS","")): continue
            r = pa_analyse(sym, sector_signals, nifty_cond, min_score=min_score)
            if r:
                # ── FUND MANAGER QUALITY FILTERS v5.0 ──────────────────
                # F1: Block bearish sector
                if "BEARISH" in str(sector_signals.get(r.get("sector",""), "")):
                    print(f"  BLOCKED {r['symbol']} — Sector BEARISH")
                    scanned += 1; continue
                # F2: Require minimum 3 support touches
                if r.get("sup_touches", 0) < 3:
                    print(f"  BLOCKED {r['symbol']} — Support {r.get('sup_touches',0)}x (need 3+)")
                    scanned += 1; continue
                # F3: Block Declining/Distribution stage
                if str(r.get("stage","")).lower() in ["declining", "distribution"]:
                    print(f"  BLOCKED {r['symbol']} — Stage {r.get('stage','')}")
                    scanned += 1; continue
                # F4: MACD + EMA both bearish
                if not r.get("macd_bull", True) and not r.get("ema_bull", True):
                    print(f"  BLOCKED {r['symbol']} — MACD+EMA bearish")
                    scanned += 1; continue
                # F5: Weekly downtrend — only very high scores
                if not nifty_weekly_ok and r.get("score", 0) < 82:
                    print(f"  BLOCKED {r['symbol']} — Weekly downtrend, score {r.get('score',0)}")
                    scanned += 1; continue
                # ── END FILTERS ─────────────────────────────────────────
                # Persistence bonus + position sizing
                if r["symbol"] in yesterday_picks:
                    r["score"] = min(100, r["score"] + 5)
                    r["persistence"] = True
                    print(f"  PERSISTENCE: {r['symbol']} confirmed 2nd day ✔️")
                else:
                    r["persistence"] = False
                sl_price = r.get("sl", r["price"] * 0.97)
                qty, deployed = calculate_position_size(r["price"], sl_price)
                r["recommended_qty"] = qty
                r["recommended_deploy"] = deployed
                results.append(r)
                persist_tag = " ✔️PERSISTENT" if r["persistence"] else ""
                print(f"  FOUND: {r['symbol']} {r['score']}/100 | {r['trade_type']} | Sup:{r['support']}({r['sup_touches']}x) | T1:+{r['t1_pct']}% | R/R:{r['rr']}{persist_tag}")
            scanned += 1
            if (i+1) % 300 == 0: print(f"  Progress: {i+1}/{len(nse_symbols)} | Found: {len(results)}")
            time.sleep(0.4)
        except: pass

    results.sort(key=lambda x: (x.get("persistence", False), x["score"]), reverse=True)
    top = results[:MAX_RESULTS]
    print(f"\nDone. Scanned:{scanned} | Qualified:{len(results)} | Sending:{len(top)}")

    kz = get_killzone() if SMC_AVAILABLE else {"zone":"N/A","quality":"NONE","note":""}
    fii_txt = f"FII {'Buying' if fii_net>0 else 'Selling'} Rs{abs(fii_net):,.0f} Cr" if fii_net else "FII: N/A"

    if not top:
        weekly_status = "✅ UPTREND" if nifty_weekly_ok else "❌ DOWNTREND"
        send_telegram(f"""🚫 <b>NO CONFLUENCE SIGNAL — {today} {now_str}</b>

Scanned: {scanned} | Market: {nifty_cond} (RSI {nifty_rsi:.0f})
Nifty Weekly: {weekly_status}
Min Score Required: {min_score}/100
Persistence Watchlist: {len(yesterday_picks)} candidates from yesterday

No stock cleared all quality gates today.
<b>This is the correct decision — no forced trades.</b>

Killzone: {kz['zone']} — {kz['note']}
Next scan in 2 hours.""")
        return

    send_telegram(f"""CONFLUENCE v3.0 — {today} {now_str}
{len(top)} signal(s) | {scanned} scanned
Market: {nifty_cond} (RSI {nifty_rsi:.0f}) | {fii_txt}
Filter: S/R touches + Demand zone + Setup type + Score>={min_score}
Full report sent to Gmail""")
    time.sleep(0.5)

    for i, r in enumerate(top, 1):
        send_telegram(pa_format_alert(r, i, nifty_cond))
        time.sleep(1)

    rows = ""
    for r in top:
        notes_html = "".join(f"<li style='font-size:12px;margin:2px'>{n}</li>" for n in r["notes"])
        color = "#1a5276" if r["score"] >= 82 else "#1e8449"
        t3_cell = f"<td><b>T3:</b> Rs{r['t3']} (+{r['t3_pct']}%)<br><small>{r['t3_note']}</small></td>" if r.get("t3") else "<td>-</td>"
        qty = int(200000*0.02/(r["price"]*r["sl_pct"]/100)) if r["price"]*r["sl_pct"]>0 else 0
        rows += f"""<div style='background:white;border:1px solid #ddd;border-radius:8px;margin:15px 0;overflow:hidden'>
        <div style='background:{color};color:white;padding:15px'>
        <h2 style='margin:0'>{r['signal']} - {r['symbol']} ({r['trade_type']})</h2>
        <p style='margin:4px 0 0;opacity:.9'>Score:{r['score']}/100 | Rs{r['price']} | RSI {r['rsi']} | {r['sector']} | {r['stage']}</p></div>
        <table border='1' cellpadding='10' style='width:100%;border-collapse:collapse;font-size:13px'>
        <tr style='background:#eaf4fb'>
        <td><b>Support:</b> Rs{r['support']}<br><small>{r['sup_touches']}x = {r['sup_strength']}</small></td>
        <td><b>Resistance:</b> Rs{r['resistance']}</td>
        <td><b>Demand Zone:</b> {'YES' if r['at_demand'] else 'No'}</td>
        <td><b>Hold:</b> {r['hold']}</td><td><b>R/R:</b> 1:{r['rr']}</td></tr>
        <tr><td><b>Entry:</b> Rs{r['entry']}</td>
        <td><b>SL:</b> Rs{r['sl']} (-{r['sl_pct']}%)<br><small>{r['sl_note']}</small></td>
        <td><b>T1:</b> Rs{r['t1']} (+{r['t1_pct']}%)<br><small>{r['t1_note']}</small></td>
        <td><b>T2:</b> Rs{r['t2']} (+{r['t2_pct']}%)<br><small>{r['t2_note']}</small></td>
        {t3_cell}</tr></table>
        <div style='padding:15px'><ul style='margin:5px 0;padding-left:18px'>{notes_html}</ul>
        <div style='background:#eafaf1;padding:10px;border-radius:6px;margin-top:8px;font-size:13px'>
        Action: Enter Rs{r['entry']} - SL Rs{r['sl']} - Exit 60% at T1 Rs{r['t1']} - move SL to entry - hold rest for Rs{r['t2']}
        </div></div></div>"""

    html = f"""<html><body style='font-family:Arial,sans-serif;max-width:950px;margin:auto;padding:20px'>
    <div style='background:linear-gradient(135deg,#0f2027,#203a43);padding:20px;border-radius:12px;color:white;margin-bottom:20px'>
    <h1 style='margin:0'>Confluence v3.0 - Price Action First</h1>
    <p style='margin:5px 0 0;opacity:.9'>{today} | {now_str} | {len(top)} signal(s) | {scanned} scanned</p>
    <p style='margin:5px 0 0;opacity:.7;font-size:13px'>S/R touch count + Demand zones + Setup type + Dynamic targets</p>
    </div>{rows}
    <p style='color:#999;font-size:12px;margin-top:20px'>Always use stop loss. Technical analysis only.</p></body></html>"""

    log_to_sheets(top)
    # Save today's results for tomorrow's persistence check
    if sheet:
        save_persistence_watchlist(sheet, top)
    send_email(
        subject=f"Confluence v3.0 - {today} | {top[0]['symbol']} {top[0]['score']}/100 | {top[0]['trade_type']}",
        body=html
    )
    print("v3.0 complete!")

run()
