"""
NIFTY Option Chain Cockpit — Backend
=============================================
Run:   python nifty_cockpit_backend.py
Opens: http://localhost:8080

pip install Dhan-Tradehull flask flask-cors
"""

import math, json, traceback
from flask import Flask, jsonify
from flask_cors import CORS
from Dhan_Tradehull import Tradehull

# ── Credentials ───────────────────────────────────────────────────────────────
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

# ── helpers ───────────────────────────────────────────────────────────────────
def sf(val, d=2):
    try:
        v = float(val)
        return round(v, d) if not math.isnan(v) else 0.0
    except Exception:
        return 0.0

def stars(value, p25, p50, p75, p90):
    """Map a value to 1-5 stars against simple percentile thresholds."""
    if value >= p90: return 5
    if value >= p75: return 4
    if value >= p50: return 3
    if value >= p25: return 2
    return 1

def buyer_quality(delta, theta, iv, ltp):
    """
    Return a quality label + list of reasons — purely from option greeks.
    No invented market view.
    """
    issues, goods = [], []

    if iv > 20:   issues.append(f"IV {iv}% is high — you are overpaying for premium")
    elif iv < 12: goods.append(f"IV {iv}% is low — cheap premium, good for buyers")
    else:         goods.append(f"IV {iv}% is moderate — fair premium")

    abs_theta = abs(theta)
    if abs_theta > 10:  issues.append(f"Theta ₹{abs_theta}/day is heavy — time decay eating your premium fast")
    elif abs_theta > 5: goods.append(f"Theta ₹{abs_theta}/day is moderate — manageable daily decay")
    else:               goods.append(f"Theta ₹{abs_theta}/day is low — good for multi-session holds")

    if delta < 0.25:    issues.append(f"Delta {delta} is very low — option barely moves with NIFTY")
    elif delta < 0.35:  issues.append(f"Delta {delta} is low — slow directional response")
    elif delta <= 0.55: goods.append(f"Delta {delta} — healthy directional exposure")
    else:               goods.append(f"Delta {delta} — deep ITM, moves almost like NIFTY itself")

    label = "POOR" if len(issues) >= 2 else "GOOD" if len(goods) >= 2 else "FAIR"
    return {"label": label, "goods": goods, "issues": issues}


def compute():
    tsl = Tradehull(CLIENT_ID, ACCESS_TOKEN)
    atm, oc = tsl.get_option_chain(
        Underlying="NIFTY",
        exchange="INDEX",
        expiry=1,
        num_strikes=10
    )
    atm = sf(atm, 0)

    # ── Raw chain rows ─────────────────────────────────────────────────────────
    rows = []
    for _, r in oc.iterrows():
        sp      = sf(r["Strike Price"], 0)
        ce_oi   = sf(r.get("CE OI",        0), 0)
        ce_doi  = sf(r.get("CE Chg in OI", 0), 0)
        ce_vol  = sf(r.get("CE Volume",    0), 0)
        ce_iv   = sf(r.get("CE IV",        0))
        ce_d    = sf(r.get("CE Delta",     0))
        ce_th   = sf(r.get("CE Theta",     0))
        ce_vg   = sf(r.get("CE Vega",      0))
        ce_ltp  = sf(r.get("CE LTP",       0))
        pe_oi   = sf(r.get("PE OI",        0), 0)
        pe_doi  = sf(r.get("PE Chg in OI", 0), 0)
        pe_vol  = sf(r.get("PE Volume",    0), 0)
        pe_iv   = sf(r.get("PE IV",        0))
        pe_d    = sf(r.get("PE Delta",     0))
        pe_th   = sf(r.get("PE Theta",     0))
        pe_vg   = sf(r.get("PE Vega",      0))
        pe_ltp  = sf(r.get("PE LTP",       0))
        rows.append({
            "strike":  sp,
            "is_atm":  sp == atm,
            "ce_oi":   ce_oi,  "ce_doi": ce_doi, "ce_vol": ce_vol,
            "ce_iv":   ce_iv,  "ce_d":   ce_d,   "ce_th":  ce_th,
            "ce_vg":   ce_vg,  "ce_ltp": ce_ltp,
            "pe_oi":   pe_oi,  "pe_doi": pe_doi, "pe_vol": pe_vol,
            "pe_iv":   pe_iv,  "pe_d":   pe_d,   "pe_th":  pe_th,
            "pe_vg":   pe_vg,  "pe_ltp": pe_ltp,
        })

    rows.sort(key=lambda x: x["strike"], reverse=True)  # descending: resistance on top

    # ── OI thresholds (for colour coding) ─────────────────────────────────────
    ce_dois = [r["ce_doi"] for r in rows if r["ce_doi"] > 0]
    pe_dois = [r["pe_doi"] for r in rows if r["pe_doi"] > 0]
    ce_thresh = sorted(ce_dois)[int(len(ce_dois)*0.6)] if ce_dois else 50000
    pe_thresh = sorted(pe_dois)[int(len(pe_dois)*0.6)] if pe_dois else 50000

    # ── Support & Resistance ───────────────────────────────────────────────────
    above_atm = [r for r in rows if r["strike"] > atm]
    below_atm = [r for r in rows if r["strike"] < atm]

    # Strongest support = highest PE OI below ATM
    sup_row = max(below_atm, key=lambda x: x["pe_oi"]) if below_atm else max(rows, key=lambda x: x["pe_oi"])
    # Strongest resistance = highest CE OI above ATM
    res_row = max(above_atm, key=lambda x: x["ce_oi"]) if above_atm else max(rows, key=lambda x: x["ce_oi"])

    sup_strike = sup_row["strike"]
    res_strike = res_row["strike"]
    ltp_proxy  = atm  # best proxy for live NIFTY LTP from option chain

    # ── Star ratings (based on all PE/CE OI values) ────────────────────────────
    all_pe_oi = sorted([r["pe_oi"] for r in rows])
    all_ce_oi = sorted([r["ce_oi"] for r in rows])
    def pct(lst, v): return stars(v, lst[max(0,int(len(lst)*.25))], lst[int(len(lst)*.5)], lst[int(len(lst)*.75)], lst[int(len(lst)*.9)])

    sup_stars = pct(all_pe_oi, sup_row["pe_oi"])
    res_stars = pct(all_ce_oi, res_row["ce_oi"])

    # ── Dynamic explanations ───────────────────────────────────────────────────
    def explain_support(r):
        doi_str = f"+{r['pe_doi']/100000:.2f}L" if r["pe_doi"] >= 0 else f"{r['pe_doi']/100000:.2f}L"
        action  = "added" if r["pe_doi"] > 0 else "reduced"
        trend   = "Support strengthening — put writers defending this level." if r["pe_doi"] > 0 else "Put writers exiting — support may weaken."
        return f"Put writers {action} {doi_str} contracts at {int(r['strike'])} today. {trend}"

    def explain_resistance(r):
        doi_str = f"+{r['ce_doi']/100000:.2f}L" if r["ce_doi"] >= 0 else f"{r['ce_doi']/100000:.2f}L"
        action  = "added" if r["ce_doi"] > 0 else "removed"
        trend   = "Resistance strengthening — call writers capping this level." if r["ce_doi"] > 0 else "Call writers exiting — ceiling may lift."
        return f"Call writers {action} {doi_str} contracts at {int(r['strike'])} today. {trend}"

    # ── Top 3 put / call writing ───────────────────────────────────────────────
    top3_pe_writing = sorted(rows, key=lambda x: x["pe_doi"], reverse=True)[:3]
    top3_ce_writing = sorted(rows, key=lambda x: x["ce_doi"], reverse=True)[:3]

    # ── Market Positioning — purely from data ──────────────────────────────────
    total_pe_doi = sum(r["pe_doi"] for r in rows)
    total_ce_doi = sum(r["ce_doi"] for r in rows)
    total_pe_oi  = sum(r["pe_oi"]  for r in rows)
    total_ce_oi  = sum(r["ce_oi"]  for r in rows)

    if total_pe_doi > 0 and total_ce_doi > 0:
        if total_pe_doi > total_ce_doi * 1.3:
            mkt_direction = "Bullish"
            mkt_reason = (
                f"Put writing (+{total_pe_doi/100000:.2f}L contracts) exceeds call writing "
                f"(+{total_ce_doi/100000:.2f}L contracts). "
                f"Put writers are defending the market — they profit only if NIFTY stays above their strikes."
            )
        elif total_ce_doi > total_pe_doi * 1.3:
            mkt_direction = "Bearish"
            mkt_reason = (
                f"Call writing (+{total_ce_doi/100000:.2f}L contracts) exceeds put writing "
                f"(+{total_pe_doi/100000:.2f}L contracts). "
                f"Call writers are capping the market — they profit only if NIFTY stays below their strikes."
            )
        else:
            diff_pct = abs(total_pe_doi - total_ce_doi) / max(total_pe_doi, total_ce_doi) * 100
            mkt_direction = "Neutral"
            mkt_reason = (
                f"Both sides adding similar positions (PE: +{total_pe_doi/100000:.2f}L, "
                f"CE: +{total_ce_doi/100000:.2f}L, diff {diff_pct:.0f}%). "
                f"No clear edge — wait for one side to dominate."
            )
    elif total_pe_doi < 0 and total_ce_doi < 0:
        mkt_direction = "Unwinding"
        mkt_reason = f"Both PE and CE OI decreasing — market participants closing positions. Low conviction environment."
    else:
        mkt_direction = "Mixed"
        mkt_reason = f"OI changes are mixed. PE ΔOI: {total_pe_doi/100000:.2f}L, CE ΔOI: {total_ce_doi/100000:.2f}L."

    # ── Recommended CE & PE strikes (buyer perspective) ───────────────────────
    # Best call: CE delta 0.35–0.55, lowest IV among qualifying
    ce_candidates = [r for r in rows if 0.35 <= r["ce_d"] <= 0.55 and r["ce_ltp"] > 0]
    if not ce_candidates:
        ce_candidates = [r for r in rows if r["ce_d"] > 0.25 and r["ce_ltp"] > 0]
    ce_candidates.sort(key=lambda x: (x["ce_iv"], abs(x["ce_th"])))
    rec_ce = ce_candidates[0] if ce_candidates else None

    # Best put: PE delta -0.35 to -0.55, lowest IV
    pe_candidates = [r for r in rows if -0.55 <= r["pe_d"] <= -0.35 and r["pe_ltp"] > 0]
    if not pe_candidates:
        pe_candidates = [r for r in rows if r["pe_d"] < -0.25 and r["pe_ltp"] > 0]
    pe_candidates.sort(key=lambda x: (x["pe_iv"], abs(x["pe_th"])))
    rec_pe = pe_candidates[0] if pe_candidates else None

    def ce_reason(r):
        parts = []
        if 0.35 <= r["ce_d"] <= 0.55:
            parts.append(f"Delta {r['ce_d']} gives good directional exposure")
        elif r["ce_d"] > 0.55:
            parts.append(f"Delta {r['ce_d']} — deep ITM, expensive but reliable")
        else:
            parts.append(f"Delta {r['ce_d']} — cheaper but slower response")
        parts.append(f"Theta ₹{abs(r['ce_th']):.1f}/day decay")
        if r["ce_iv"] < 14:
            parts.append(f"IV {r['ce_iv']}% — cheap premium, good for buyers")
        elif r["ce_iv"] > 20:
            parts.append(f"IV {r['ce_iv']}% — expensive; buy only with strong conviction")
        else:
            parts.append(f"IV {r['ce_iv']}% — fair pricing")
        return ". ".join(parts) + "."

    def pe_reason(r):
        parts = []
        if -0.55 <= r["pe_d"] <= -0.35:
            parts.append(f"Delta {r['pe_d']} gives good directional exposure for put buyers")
        else:
            parts.append(f"Delta {r['pe_d']} — OTM put, needs sharper move")
        parts.append(f"Theta ₹{abs(r['pe_th']):.1f}/day decay")
        if r["pe_iv"] < 14:
            parts.append(f"IV {r['pe_iv']}% — cheap premium")
        elif r["pe_iv"] > 20:
            parts.append(f"IV {r['pe_iv']}% — elevated; buy only on clear bearish reversal")
        else:
            parts.append(f"IV {r['pe_iv']}% — fair")
        return ". ".join(parts) + "."

    # ── Bottom decision (data-only) ────────────────────────────────────────────
    # Sort put writing contributors for bottom panel
    sorted_pe = sorted(rows, key=lambda x: x["pe_doi"], reverse=True)[:3]
    sorted_ce = sorted(rows, key=lambda x: x["ce_doi"], reverse=True)[:3]

    bottom_reasons = []
    for r in sorted_pe:
        if r["pe_doi"] > 0:
            bottom_reasons.append(f"{int(r['strike'])} PE added +{r['pe_doi']/100000:.2f}L OI")
    for r in sorted_ce:
        if r["ce_doi"] > 0:
            bottom_reasons.append(f"{int(r['strike'])} CE added +{r['ce_doi']/100000:.2f}L OI")

    preferred_strike = f"{int(rec_ce['strike'])} CE" if rec_ce else "—"

    # ── Build final payload ────────────────────────────────────────────────────
    def row_color(r):
        """Return a color token based on OI change significance."""
        if r["ce_doi"] > ce_thresh:  return "strong_call_write"   # dark red
        if r["pe_doi"] > pe_thresh:  return "strong_put_write"     # dark green
        if r["ce_doi"] < 0:          return "call_unwind"          # orange
        if r["pe_doi"] < 0:          return "put_unwind"           # blue
        return "neutral"

    chain = []
    for r in rows:
        chain.append({**r, "color": row_color(r)})

    return {
        "atm":           atm,
        "ltp":           ltp_proxy,
        "support":       sup_strike,
        "resistance":    res_strike,
        "dist_support":  round(ltp_proxy - sup_strike),
        "dist_resistance": round(res_strike - ltp_proxy),
        "sup_row":       {**sup_row, "stars": sup_stars, "explanation": explain_support(sup_row)},
        "res_row":       {**res_row, "stars": res_stars, "explanation": explain_resistance(res_row)},
        "top3_pe":       [{"strike": int(r["strike"]), "pe_doi": r["pe_doi"]} for r in top3_pe_writing],
        "top3_ce":       [{"strike": int(r["strike"]), "ce_doi": r["ce_doi"]} for r in top3_ce_writing],
        "mkt_direction": mkt_direction,
        "mkt_reason":    mkt_reason,
        "total_pe_oi":   total_pe_oi,
        "total_ce_oi":   total_ce_oi,
        "total_pe_doi":  total_pe_doi,
        "total_ce_doi":  total_ce_doi,
        "rec_ce":        {**rec_ce, "quality": buyer_quality(rec_ce["ce_d"], rec_ce["ce_th"], rec_ce["ce_iv"], rec_ce["ce_ltp"]), "reason": ce_reason(rec_ce)} if rec_ce else None,
        "rec_pe":        {**rec_pe, "quality": buyer_quality(abs(rec_pe["pe_d"]), rec_pe["pe_th"], rec_pe["pe_iv"], rec_pe["pe_ltp"]), "reason": pe_reason(rec_pe)} if rec_pe else None,
        "chain":         chain,
        "bottom": {
            "direction":   mkt_direction,
            "reasons":     bottom_reasons,
            "preferred":   preferred_strike,
            "mkt_reason":  mkt_reason,
        },
    }


@app.route("/api/data")
def get_data():
    try:
        return jsonify({"ok": True, "data": compute()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()}), 500


@app.route("/")
def index():
    with open("nifty_cockpit.html") as f:
        return f.read()


if __name__ == "__main__":
    import webbrowser, threading
    threading.Timer(1.2, lambda: webbrowser.open("http://localhost:8080")).start()
    print("🚀  Nifty Cockpit → http://localhost:8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
