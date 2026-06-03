"""
Nifty Option Chain Dashboard — Backend
======================================================
Run:  python nifty_dashboard_backend.py
Opens: http://localhost:8080   (auto-opens browser)

Requires:
    pip install Dhan-Tradehull flask flask-cors
"""

import math, json, traceback
from flask import Flask, jsonify
from flask_cors import CORS
from Dhan_Tradehull import Tradehull

# ── Credentials ──────────────────────────────────────────────
CLIENT_ID    = "1103610460"
ACCESS_TOKEN = (
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9"
    ".eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzgwMjk2ODk4"
    "LCJpYXQiOjE3ODAyMTA0OTgsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIs"
    "IndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTAzNjEwNDYwIn0"
    ".zVIEGTHh3bMAUUVrC8YRAnIMiQbVzqzsRlDOojMXAbCGBt8y5IKjM13V7oN60"
    "M1-M_KIZxWKsgc98nfjIZztgw"
)

app = Flask(__name__)
CORS(app)

def safe_float(val, decimals=2):
    """Convert to rounded float, return 0 on failure."""
    try:
        v = float(val)
        return round(v, decimals) if not math.isnan(v) else 0.0
    except Exception:
        return 0.0

def compute_payload():
    tsl = Tradehull(CLIENT_ID, ACCESS_TOKEN)
    atm, oc = tsl.get_option_chain(
        Underlying="NIFTY",
        exchange="INDEX",
        expiry=1,
        num_strikes=10
    )

    # ── Core ratios ──────────────────────────────────────────
    total_pe_oi  = safe_float(oc["PE OI"].sum(),  0)
    total_ce_oi  = safe_float(oc["CE OI"].sum(),  0)
    total_pe_vol = safe_float(oc["PE Volume"].sum(), 0)
    total_ce_vol = safe_float(oc["CE Volume"].sum(), 0)

    pcr  = round(total_pe_oi  / total_ce_oi,  2) if total_ce_oi  else 0
    vpcr = round(total_pe_vol / total_ce_vol, 2) if total_ce_vol else 0

    # ── Support / Resistance ─────────────────────────────────
    support_strike    = safe_float(oc.loc[oc["PE OI"].idxmax(), "Strike Price"], 0)
    resistance_strike = safe_float(oc.loc[oc["CE OI"].idxmax(), "Strike Price"], 0)

    pw_row = oc.loc[oc["PE Chg in OI"].idxmax()]
    cw_row = oc.loc[oc["CE Chg in OI"].idxmax()]
    max_put_writing  = {"strike": safe_float(pw_row["Strike Price"], 0), "doi": safe_float(pw_row["PE Chg in OI"])}
    max_call_writing = {"strike": safe_float(cw_row["Strike Price"], 0), "doi": safe_float(cw_row["CE Chg in OI"])}

    # ── ATM Greeks ───────────────────────────────────────────
    atm_row = oc[oc["Strike Price"] == atm]
    greeks = {}
    if not atm_row.empty:
        r = atm_row.iloc[0]
        greeks = {
            "ce_delta": safe_float(r.get("CE Delta", 0)),
            "ce_gamma": safe_float(r.get("CE Gamma", 0)),
            "ce_theta": safe_float(r.get("CE Theta", 0)),
            "ce_vega":  safe_float(r.get("CE Vega",  0)),
            "pe_delta": safe_float(r.get("PE Delta", 0)),
            "pe_gamma": safe_float(r.get("PE Gamma", 0)),
            "pe_theta": safe_float(r.get("PE Theta", 0)),
            "pe_vega":  safe_float(r.get("PE Vega",  0)),
        }

    # ── Top 3 supports & resistances ─────────────────────────
    top3_sup = oc.nlargest(3, "PE OI")[["Strike Price", "PE OI"]].values.tolist()
    top3_res = oc.nlargest(3, "CE OI")[["Strike Price", "CE OI"]].values.tolist()

    # ── Best delta strikes (buyer perspective) ───────────────
    call_candidates = oc.loc[oc["CE Delta"] > 0.30, ["Strike Price", "CE Delta", "CE IV", "CE LTP"]]
    put_candidates  = oc.loc[oc["PE Delta"] < -0.30, ["Strike Price", "PE Delta", "PE IV", "PE LTP"]]

    suggested_call = None
    if not call_candidates.empty:
        r = call_candidates.iloc[0]
        suggested_call = {
            "strike": safe_float(r["Strike Price"], 0),
            "delta":  safe_float(r["CE Delta"]),
            "iv":     safe_float(r.get("CE IV", 0)),
            "ltp":    safe_float(r.get("CE LTP", 0)),
        }
    suggested_put = None
    if not put_candidates.empty:
        r = put_candidates.iloc[-1]
        suggested_put = {
            "strike": safe_float(r["Strike Price"], 0),
            "delta":  safe_float(r["PE Delta"]),
            "iv":     safe_float(r.get("PE IV", 0)),
            "ltp":    safe_float(r.get("PE LTP", 0)),
        }

    # ── LTP ──────────────────────────────────────────────────
    ltp = safe_float(atm, 0)  # best proxy; replace with live index quote if available

    # ── Max Pain ─────────────────────────────────────────────
    def max_pain(df):
        strikes = df["Strike Price"].tolist()
        best_strike, best_loss = None, float("inf")
        for s in strikes:
            loss = 0
            for _, row in df.iterrows():
                sp = row["Strike Price"]
                loss += max(0, s - sp) * safe_float(row.get("CE OI", 0), 0)
                loss += max(0, sp - s) * safe_float(row.get("PE OI", 0), 0)
            if loss < best_loss:
                best_loss, best_strike = loss, s
        return best_strike

    mp = max_pain(oc)

    # ── Probability range using ATM IV ───────────────────────
    atm_iv = 0.0
    if not atm_row.empty:
        ce_iv = safe_float(atm_row.iloc[0].get("CE IV", 0))
        pe_iv = safe_float(atm_row.iloc[0].get("PE IV", 0))
        atm_iv = (ce_iv + pe_iv) / 2 if (ce_iv and pe_iv) else (ce_iv or pe_iv)
    dte = 3  # days to expiry — update from expiry date if available
    if atm_iv > 0 and ltp > 0:
        daily_move = ltp * (atm_iv / 100) * math.sqrt(dte / 252)
        prob_low  = round(ltp - daily_move)
        prob_high = round(ltp + daily_move)
    else:
        prob_low = prob_high = 0

    # ── Scoring engine (buyer-weighted) ──────────────────────
    bull_score = 0
    bear_score = 0

    # PCR (30%)
    if pcr > 1.2:   bull_score += 30
    elif pcr > 1.0: bull_score += 20
    elif pcr < 0.8: bear_score += 30
    else:           bear_score += 15

    # Volume PCR (20%)
    if vpcr > 1.2:   bull_score += 20
    elif vpcr > 1.0: bull_score += 12
    elif vpcr < 0.8: bear_score += 20
    else:            bear_score += 10

    # PE writing vs call writing (20%)
    if max_put_writing["doi"] > max_call_writing["doi"]:
        bull_score += 20
    else:
        bear_score += 20

    # ATM delta (10%)
    if greeks.get("ce_delta", 0) >= 0.50:
        bull_score += 10
    else:
        bear_score += 5

    # CE OI unwinding vs buildup (20%)
    ce_doi_total = safe_float(oc["CE Chg in OI"].sum(), 0)
    pe_doi_total = safe_float(oc["PE Chg in OI"].sum(), 0)
    if pe_doi_total > ce_doi_total:
        bull_score += 20
    else:
        bear_score += 20

    bull_score = min(bull_score, 100)
    bear_score = min(bear_score, 100)

    if bull_score >= 65:
        bias       = "BULLISH"
        confidence = round(bull_score * 0.82 + 18)
        action     = "BUY CALL ON DIPS"
        avoid      = "Put buying · Naked trades"
        risk       = "Medium"
        setup_bias = "Bullish"
        entry_ref  = round(atm + 30) if ltp > 0 else 0
        sl_ref     = round(atm - 30)
        t1_ref     = round(resistance_strike)
        t2_ref     = round(resistance_strike + 100)
    elif bear_score >= 65:
        bias       = "BEARISH"
        confidence = round(bear_score * 0.82 + 18)
        action     = "BUY PUT ON RALLIES"
        avoid      = "Call buying · Naked trades"
        risk       = "Medium"
        setup_bias = "Bearish"
        entry_ref  = round(atm - 30) if ltp > 0 else 0
        sl_ref     = round(atm + 30)
        t1_ref     = round(support_strike)
        t2_ref     = round(support_strike - 100)
    else:
        bias       = "NEUTRAL"
        confidence = 50
        action     = "WAIT — NO TRADE"
        avoid      = "Option buying in either direction"
        risk       = "High"
        setup_bias = "Neutral"
        entry_ref  = sl_ref = t1_ref = t2_ref = 0

    risk_reward = "1:3" if t1_ref and sl_ref else "—"

    # ── Full option chain rows ────────────────────────────────
    chain_rows = []
    for _, row in oc.iterrows():
        chain_rows.append({
            "strike":    safe_float(row["Strike Price"], 0),
            "isATM":     safe_float(row["Strike Price"], 0) == safe_float(atm, 0),
            "ce_ltp":    safe_float(row.get("CE LTP",        0)),
            "ce_oi":     safe_float(row.get("CE OI",         0), 0),
            "ce_doi":    safe_float(row.get("CE Chg in OI",  0), 0),
            "ce_vol":    safe_float(row.get("CE Volume",     0), 0),
            "ce_iv":     safe_float(row.get("CE IV",         0)),
            "ce_delta":  safe_float(row.get("CE Delta",      0)),
            "ce_theta":  safe_float(row.get("CE Theta",      0)),
            "pe_ltp":    safe_float(row.get("PE LTP",        0)),
            "pe_oi":     safe_float(row.get("PE OI",         0), 0),
            "pe_doi":    safe_float(row.get("PE Chg in OI",  0), 0),
            "pe_vol":    safe_float(row.get("PE Volume",     0), 0),
            "pe_iv":     safe_float(row.get("PE IV",         0)),
            "pe_delta":  safe_float(row.get("PE Delta",      0)),
            "pe_theta":  safe_float(row.get("PE Theta",      0)),
        })

    # ── Heatmap data ─────────────────────────────────────────
    max_ce = max((r["ce_oi"] for r in chain_rows), default=1) or 1
    max_pe = max((r["pe_oi"] for r in chain_rows), default=1) or 1
    heatmap = [
        {
            "strike":  r["strike"],
            "side":    "res" if r["strike"] > safe_float(atm, 0) else "sup",
            "ce_oi":   r["ce_oi"],
            "pe_oi":   r["pe_oi"],
            "ce_pct":  round(r["ce_oi"] / max_ce * 100),
            "pe_pct":  round(r["pe_oi"] / max_pe * 100),
        }
        for r in chain_rows
    ]

    # ── Institutional signals ────────────────────────────────
    bull_signals = []
    bear_signals = []
    if pe_doi_total > 0:  bull_signals.append(f"Put writing active (+{int(pe_doi_total):,})")
    if ce_doi_total < 0:  bull_signals.append("Call OI unwinding — ceiling lifting")
    if pcr > 1.1:         bull_signals.append(f"PCR {pcr} — more puts than calls")
    if vpcr > 1.0:        bull_signals.append(f"Vol PCR {vpcr} — put volume surge")
    if ce_doi_total > 0:  bear_signals.append(f"Call writing active (+{int(ce_doi_total):,})")
    if pe_doi_total < 0:  bear_signals.append("Put OI unwinding — support weakening")
    if pcr < 0.9:         bear_signals.append(f"PCR {pcr} — call-heavy positioning")
    if vpcr < 0.9:        bear_signals.append(f"Vol PCR {vpcr} — call volume surge")

    return {
        "atm":              safe_float(atm, 0),
        "ltp":              ltp,
        "pcr":              pcr,
        "vpcr":             vpcr,
        "atm_iv":           round(atm_iv, 2),
        "support":          support_strike,
        "resistance":       resistance_strike,
        "max_pain":         safe_float(mp, 0),
        "max_put_writing":  max_put_writing,
        "max_call_writing": max_call_writing,
        "greeks":           greeks,
        "top3_supports":    [[safe_float(r[0], 0), safe_float(r[1], 0)] for r in top3_sup],
        "top3_resistances": [[safe_float(r[0], 0), safe_float(r[1], 0)] for r in top3_res],
        "suggested_call":   suggested_call,
        "suggested_put":    suggested_put,
        "prob_low":         prob_low,
        "prob_high":        prob_high,
        "dte":              dte,
        "bull_score":       bull_score,
        "bear_score":       bear_score,
        "bias":             bias,
        "confidence":       confidence,
        "action":           action,
        "avoid":            avoid,
        "risk":             risk,
        "setup_bias":       setup_bias,
        "entry_ref":        entry_ref,
        "sl_ref":           sl_ref,
        "t1_ref":           t1_ref,
        "t2_ref":           t2_ref,
        "risk_reward":      risk_reward,
        "chain":            chain_rows,
        "heatmap":          heatmap,
        "bull_signals":     bull_signals,
        "bear_signals":     bear_signals,
    }


@app.route("/api/data")
def get_data():
    try:
        payload = compute_payload()
        return jsonify({"ok": True, "data": payload})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()}), 500


@app.route("/")
def index():
    with open("nifty_dashboard.html", "r") as f:
        return f.read()


if __name__ == "__main__":
    import webbrowser, threading
    threading.Timer(1.2, lambda: webbrowser.open("http://localhost:8080")).start()
    print("🚀  Nifty Dashboard running at http://localhost:8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
