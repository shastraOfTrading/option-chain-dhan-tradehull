"""
NIFTY Option Cockpit — Backend v5
===================================================
Run:   python cockpit_backend.py
Opens: http://localhost:8080

Install:
    pip install Dhan-Tradehull flask flask-cors
"""

import math
import json
import traceback
import webbrowser
import threading

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from Dhan_Tradehull import Tradehull

# ── Credentials ───────────────────────────────────────────────
CLIENT_ID    = "1103610460"
ACCESS_TOKEN = (
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzgwMzM4NzE1LCJpYXQiOjE3ODAyNTIzMTUsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTAzNjEwNDYwIn0.2H5d8QxYbAtIG3-3F0Zp0hO1ZX6qLWpac3pwZb7Xh1G8kPnXf0J2CQBSyKyJ5i5lcKYS8qgGtV9JVSMy_gYoUw"
)

app = Flask(__name__, static_folder=".")
CORS(app)


# ── Helpers ───────────────────────────────────────────────────
def sf(val, decimals=2):
    """Safe float — returns 0.0 on failure or NaN."""
    try:
        v = float(val)
        return round(v, decimals) if not math.isnan(v) else 0.0
    except Exception:
        return 0.0


def stars(value, all_values):
    """1-5 star rating based on where value sits in the distribution."""
    sv = sorted(all_values)
    n  = len(sv)
    if n == 0:
        return 3
    p = [sv[max(0, int(n * t))] for t in (0.2, 0.4, 0.6, 0.8)]
    if value >= p[3]: return 5
    if value >= p[2]: return 4
    if value >= p[1]: return 3
    if value >= p[0]: return 2
    return 1


def buyer_quality(delta, theta_abs, iv):
    """
    GOOD / FAIR / POOR for an option buyer.
    Based purely on Delta range, IV level, Theta.
    No invented signal.
    """
    goods, issues = [], []

    # Delta
    if 0.35 <= delta <= 0.55:
        goods.append(f"Delta {delta} — optimal range (0.35–0.55) for buyers")
    elif delta < 0.25:
        issues.append(f"Delta {delta} bahut low hai — option bahut slow hai, avoid karo")
    elif delta > 0.65:
        issues.append(f"Delta {delta} — deep ITM hai, premium zyada padegi")
    else:
        goods.append(f"Delta {delta} — acceptable range")

    # IV
    if iv < 14:
        goods.append(f"IV {iv}% — LOW, options saste hain, buyers ke liye sahi")
    elif iv < 20:
        goods.append(f"IV {iv}% — moderate, fair pricing")
    else:
        issues.append(f"IV {iv}% — HIGH, premium mehngi hai, overpay mat karo")

    # Theta
    if theta_abs <= 7:
        goods.append(f"Theta ₹{theta_abs}/day — manageable decay")
    elif theta_abs <= 12:
        issues.append(f"Theta ₹{theta_abs}/day — moderate decay, short trade rakho")
    else:
        issues.append(f"Theta ₹{theta_abs}/day — heavy decay, intraday only")

    label = "POOR" if len(issues) >= 2 else "GOOD" if len(goods) >= 2 else "FAIR"
    return {"label": label, "goods": goods, "issues": issues}


def market_direction(total_pe_doi, total_ce_doi):
    """
    Returns direction + reason string.
    Purely from OI change totals — no invented view.
    """
    if total_pe_doi > 0 and total_ce_doi > 0:
        ratio = total_pe_doi / total_ce_doi if total_ce_doi else 1
        if ratio >= 1.3:
            return "Bullish", (
                f"Put writing (+{total_pe_doi/1e5:.1f}L) call writing "
                f"(+{total_ce_doi/1e5:.1f}L) se {ratio:.1f}x zyada hai. "
                f"Bade players downside protect kar rahe hain — structure bullish hai."
            )
        elif ratio <= 0.77:
            return "Bearish", (
                f"Call writing (+{total_ce_doi/1e5:.1f}L) put writing "
                f"(+{total_pe_doi/1e5:.1f}L) se {1/ratio:.1f}x zyada hai. "
                f"Call writers market cap kar rahe hain — structure bearish hai."
            )
    if total_pe_doi < 0 and total_ce_doi < 0:
        return "Unwinding", (
            f"Dono PE ({total_pe_doi/1e5:.1f}L) aur CE ({total_ce_doi/1e5:.1f}L) OI "
            f"decrease ho rahi hai. Participants positions close kar rahe hain — "
            f"low conviction environment, wait karo."
        )
    diff_pct = abs(total_pe_doi - total_ce_doi) / max(abs(total_pe_doi), abs(total_ce_doi), 1) * 100
    return "Neutral", (
        f"PE ΔOI ({total_pe_doi/1e5:+.1f}L) aur CE ΔOI ({total_ce_doi/1e5:+.1f}L) "
        f"kaafi similar hain (diff {diff_pct:.0f}%). Koi clear edge nahi — ek side "
        f"dominate hone ka wait karo."
    )


def rec_ce_reason(r):
    parts = []
    if 0.35 <= r["ce_d"] <= 0.55:
        parts.append(f"Delta {r['ce_d']} optimal range mein hai")
    elif r["ce_d"] > 0.55:
        parts.append(f"Delta {r['ce_d']} — ITM strike hai, mehngi par reliable")
    else:
        parts.append(f"Delta {r['ce_d']} — thodi slow hai par sabse acchi available hai")
    parts.append(f"Theta ₹{abs(r['ce_th']):.1f}/day — "
                 + ("short trade ke liye theek hai" if abs(r["ce_th"]) < 10
                    else "heavy decay, sirf intraday lo"))
    parts.append(f"IV {r['ce_iv']}% — "
                 + ("LOW IV, sasta mil raha hai abhi. Buyers ke liye green signal." if r["ce_iv"] < 14
                    else "moderate IV, fair deal." if r["ce_iv"] < 20
                    else "HIGH IV, premium mehngi hai — sochke lo."))
    return ". ".join(parts) + "."


def rec_pe_reason(r):
    parts = []
    if -0.55 <= r["pe_d"] <= -0.35:
        parts.append(f"Delta {r['pe_d']} — accha put exposure milega")
    else:
        parts.append(f"Delta {r['pe_d']} — OTM put hai, zyada move chahiye")
    parts.append(f"Theta ₹{abs(r['pe_th']):.1f}/day decay")
    parts.append(f"IV {r['pe_iv']}% — "
                 + ("cheap premium" if r["pe_iv"] < 14 else
                    "fair" if r["pe_iv"] < 20 else "mehngi, careful"))
    return (". ".join(parts)
            + ". Yaad raho: sirf tab lo jab support toot jaaye volume ke saath. "
              "Bullish structure mein put mat kharido.")


# ── Core computation ──────────────────────────────────────────
def compute():
    tsl = Tradehull(CLIENT_ID, ACCESS_TOKEN)
    atm_raw, oc = tsl.get_option_chain(
        Underlying="NIFTY",
        exchange="INDEX",
        expiry=1,
        num_strikes=10
    )
    atm = sf(atm_raw, 0)

    # ── Build rows ────────────────────────────────────────────
    rows = []
    for _, r in oc.iterrows():
        rows.append({
            "strike":  sf(r["Strike Price"], 0),
            "is_atm":  sf(r["Strike Price"], 0) == atm,
            "ce_ltp":  sf(r.get("CE LTP",        0)),
            "ce_oi":   sf(r.get("CE OI",          0), 0),
            "ce_doi":  sf(r.get("CE Chg in OI",   0), 0),
            "ce_vol":  sf(r.get("CE Volume",      0), 0),
            "ce_iv":   sf(r.get("CE IV",          0)),
            "ce_d":    sf(r.get("CE Delta",       0)),
            "ce_th":   sf(r.get("CE Theta",       0)),
            "ce_vg":   sf(r.get("CE Vega",        0)),
            "pe_ltp":  sf(r.get("PE LTP",         0)),
            "pe_oi":   sf(r.get("PE OI",          0), 0),
            "pe_doi":  sf(r.get("PE Chg in OI",   0), 0),
            "pe_vol":  sf(r.get("PE Volume",      0), 0),
            "pe_iv":   sf(r.get("PE IV",          0)),
            "pe_d":    sf(r.get("PE Delta",       0)),
            "pe_th":   sf(r.get("PE Theta",       0)),
            "pe_vg":   sf(r.get("PE Vega",        0)),
        })

    # sort descending by strike (resistance on top)
    rows.sort(key=lambda x: x["strike"], reverse=True)

    ltp = atm  # best proxy; replace with live index LTP if your Dhan plan provides it

    # ── Support & Resistance ──────────────────────────────────
    above = [r for r in rows if r["strike"] > atm]
    below = [r for r in rows if r["strike"] < atm]

    # Strongest support = highest PE OI below ATM
    sup = max(below, key=lambda x: x["pe_oi"]) if below \
          else max(rows,  key=lambda x: x["pe_oi"])

    # Strongest resistance = highest CE OI above ATM
    res = max(above, key=lambda x: x["ce_oi"]) if above \
          else max(rows,  key=lambda x: x["ce_oi"])

    # Star ratings
    all_pe_oi = [r["pe_oi"] for r in rows]
    all_ce_oi = [r["ce_oi"] for r in rows]
    sup_stars = stars(sup["pe_oi"], all_pe_oi)
    res_stars = stars(res["ce_oi"], all_ce_oi)

    # Dynamic explanations
    sup_doi_txt = f"+{sup['pe_doi']/1e5:.1f}L" if sup["pe_doi"] >= 0 \
                  else f"{sup['pe_doi']/1e5:.1f}L"
    sup_trend   = ("deewar mazboot ho rahi hai"
                   if sup["pe_doi"] > 0 else "writers nikal rahe hain — floor weak ho sakti hai")
    sup_explain = (f"Put writers ne aaj <b>{sup_doi_txt} naye contracts</b> "
                   f"{int(sup['strike'])} par add kiye. {sup_trend.capitalize()}.")

    res_doi_txt = f"+{res['ce_doi']/1e5:.1f}L" if res["ce_doi"] >= 0 \
                  else f"{res['ce_doi']/1e5:.1f}L"
    res_trend   = ("chhat aur bhaari ho gayi — breakout mushkil"
                   if res["ce_doi"] > 0 else "writers nikal rahe hain — ceiling lift ho rahi hai!")
    res_explain = (f"Call writers ne aaj <b>{res_doi_txt} contracts</b> "
                   f"{int(res['strike'])} par add kiye. {res_trend.capitalize()}.")

    # ── Totals ────────────────────────────────────────────────
    total_pe_oi  = sum(r["pe_oi"]  for r in rows)
    total_ce_oi  = sum(r["ce_oi"]  for r in rows)
    total_pe_doi = sum(r["pe_doi"] for r in rows)
    total_ce_doi = sum(r["ce_doi"] for r in rows)

    mkt_dir, mkt_reason = market_direction(total_pe_doi, total_ce_doi)

    # ── Top 3 writing activity ────────────────────────────────
    top3_pe = sorted(rows, key=lambda x: x["pe_doi"], reverse=True)[:3]
    top3_ce = sorted(rows, key=lambda x: x["ce_doi"], reverse=True)[:3]

    # ── Recommended strikes (buyer) ───────────────────────────
    # Best CE for buyer: delta 0.40–0.55 (ATM zone only — never OTM junk)
    # Fallback to 0.38+ if nothing found, but NEVER below 0.35
    ce_cands = [r for r in rows if 0.40 <= r["ce_d"] <= 0.55 and r["ce_ltp"] > 0]
    if not ce_cands:
        ce_cands = [r for r in rows if 0.35 <= r["ce_d"] < 0.40 and r["ce_ltp"] > 0]
    # Sort: lowest IV first (cheapest premium), then lowest theta (slowest decay)
    ce_cands.sort(key=lambda x: (x["ce_iv"], abs(x["ce_th"])))
    rec_ce = ce_cands[0] if ce_cands else None

    # Best PE for buyer: delta -0.55 to -0.40 (ATM zone only)
    pe_cands = [r for r in rows if -0.55 <= r["pe_d"] <= -0.40 and r["pe_ltp"] > 0]
    if not pe_cands:
        pe_cands = [r for r in rows if -0.40 < r["pe_d"] <= -0.35 and r["pe_ltp"] > 0]
    pe_cands.sort(key=lambda x: (x["pe_iv"], abs(x["pe_th"])))
    rec_pe = pe_cands[0] if pe_cands else None

    if rec_ce:
        q = buyer_quality(rec_ce["ce_d"], abs(rec_ce["ce_th"]), rec_ce["ce_iv"])
        rec_ce = {**rec_ce, "quality": q["label"], "goods": q["goods"],
                  "issues": q["issues"], "reason": rec_ce_reason(rec_ce)}

    if rec_pe:
        q = buyer_quality(abs(rec_pe["pe_d"]), abs(rec_pe["pe_th"]), rec_pe["pe_iv"])
        rec_pe = {**rec_pe, "quality": q["label"], "goods": q["goods"],
                  "issues": q["issues"], "reason": rec_pe_reason(rec_pe)}

    # ── Greeks decision block (for the Greeks tab) ────────────
    # All calcs based purely on rec_ce numbers — no invented data
    greek_block = None
    if rec_ce:
        c         = rec_ce
        delta     = c["ce_d"]
        theta_abs = abs(c["ce_th"])
        iv        = c["ce_iv"]
        ltp_opt   = c["ce_ltp"]
        res_strike = res["strike"]
        sup_strike = sup["strike"]

        # Break-even: how many pts NIFTY must move just to cover today's theta
        breakeven_pts  = round(theta_abs / delta) if delta > 0 else 0
        breakeven_nifty = round(ltp + breakeven_pts)

        # T1 scenario: NIFTY reaches resistance
        t1_move        = round(res_strike - ltp)
        t1_option_gain = round(t1_move * delta, 1)
        t1_option_ltp  = round(ltp_opt + t1_option_gain, 1)
        t1_pct         = round((t1_option_gain / ltp_opt) * 100) if ltp_opt > 0 else 0

        # Flat scenario: NIFTY does nothing for 3 days
        days_to_exp    = 3
        flat_loss      = round(theta_abs * days_to_exp, 1)
        flat_ltp       = round(ltp_opt - flat_loss, 1)
        flat_pct       = round((flat_loss / ltp_opt) * 100) if ltp_opt > 0 else 0

        # IV interpretation
        if iv < 12:
            iv_verdict = "Bahut sasta — kharidne ka best time hai"
            iv_color   = "green"
        elif iv < 16:
            iv_verdict = "Sasta — fair deal, buy karo"
            iv_color   = "green"
        elif iv < 20:
            iv_verdict = "Moderate — theek hai, par sochke lo"
            iv_color   = "amber"
        else:
            iv_verdict = "Mehngi — overpay mat karo, wait karo"
            iv_color   = "red"

        # Theta verdict
        if theta_abs <= 6:
            theta_verdict = "Low decay — multi-day hold bhi theek hai"
        elif theta_abs <= 10:
            theta_verdict = "Moderate — aaj ya kal exit karo"
        else:
            theta_verdict = "Heavy decay — strictly intraday only"

        greek_block = {
            "strike":          c["strike"],
            "ltp":             ltp_opt,
            "delta":           delta,
            "theta":           c["ce_th"],
            "theta_abs":       theta_abs,
            "iv":              iv,
            "vega":            c["ce_vg"],
            "breakeven_pts":   breakeven_pts,
            "breakeven_nifty": breakeven_nifty,
            "t1_strike":       res_strike,
            "t1_move":         t1_move,
            "t1_option_ltp":   t1_option_ltp,
            "t1_option_gain":  t1_option_gain,
            "t1_pct":          t1_pct,
            "flat_days":       days_to_exp,
            "flat_loss":       flat_loss,
            "flat_ltp":        flat_ltp,
            "flat_pct":        flat_pct,
            "iv_verdict":      iv_verdict,
            "iv_color":        iv_color,
            "theta_verdict":   theta_verdict,
        }

    # ── Bottom bar verdict ────────────────────────────────────
    top_pe_txt = " · ".join(
        f"<b>{int(r['strike'])} PE</b> {r['pe_doi']/1e5:+.1f}L"
        for r in top3_pe if r["pe_doi"] > 0
    )
    top_ce_txt = " · ".join(
        f"<b>{int(r['strike'])} CE</b> {r['ce_doi']/1e5:+.1f}L"
        for r in top3_ce if r["ce_doi"] > 0
    )
    side = ("put writers call writers se zyada active hain"
            if total_pe_doi > total_ce_doi
            else "call writers put writers se zyada active hain")
    btm_verdict = " · ".join(filter(None, [top_pe_txt, top_ce_txt]))
    if btm_verdict:
        btm_verdict += f". {side.capitalize()}."
    else:
        btm_verdict = mkt_reason

    preferred = (f"{int(rec_ce['strike'])} CE" if rec_ce else "—")

    # ── Chain for frontend (only fields needed) ───────────────
    chain_out = []
    for r in rows:
        chain_out.append({
            "strike": r["strike"],
            "atm":    r["is_atm"],
            "ce_ltp": r["ce_ltp"],  "ce_d":  r["ce_d"],
            "ce_th":  r["ce_th"],   "ce_iv": r["ce_iv"],
            "ce_vg":  r["ce_vg"],   "ce_oi": r["ce_oi"],
            "ce_doi": r["ce_doi"],  "ce_vol": r["ce_vol"],
            "pe_ltp": r["pe_ltp"],  "pe_d":  r["pe_d"],
            "pe_th":  r["pe_th"],   "pe_iv": r["pe_iv"],
            "pe_vg":  r["pe_vg"],   "pe_oi": r["pe_oi"],
            "pe_doi": r["pe_doi"],  "pe_vol": r["pe_vol"],
        })

    return {
        "atm":        atm,
        "ltp":        ltp,
        "support":    sup["strike"],
        "resistance": res["strike"],
        "dist_sup":   round(ltp - sup["strike"]),
        "dist_res":   round(res["strike"] - ltp),

        "sup_row": {
            "strike":  sup["strike"],
            "pe_oi":   sup["pe_oi"],
            "pe_doi":  sup["pe_doi"],
            "pe_vol":  sup["pe_vol"],
            "stars":   sup_stars,
            "explain": sup_explain,
        },
        "res_row": {
            "strike":  res["strike"],
            "ce_oi":   res["ce_oi"],
            "ce_doi":  res["ce_doi"],
            "ce_vol":  res["ce_vol"],
            "stars":   res_stars,
            "explain": res_explain,
        },

        "top3_pe": [{"strike": int(r["strike"]), "pe_doi": r["pe_doi"]} for r in top3_pe],
        "top3_ce": [{"strike": int(r["strike"]), "ce_doi": r["ce_doi"]} for r in top3_ce],

        "total_pe_oi":  total_pe_oi,
        "total_ce_oi":  total_ce_oi,
        "total_pe_doi": total_pe_doi,
        "total_ce_doi": total_ce_doi,

        "mkt_direction": mkt_dir,
        "mkt_reason":    mkt_reason,

        "rec_ce":      rec_ce,
        "rec_pe":      rec_pe,
        "greek_block": greek_block,

        "chain": chain_out,

        "bottom": {
            "direction": mkt_dir,
            "verdict":   btm_verdict,
            "preferred": preferred,
        },
    }


# ── Flask routes ──────────────────────────────────────────────
@app.route("/api/data")
def api_data():
    try:
        data = compute()
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        return jsonify({
            "ok":    False,
            "error": str(e),
            "trace": traceback.format_exc()
        }), 500


@app.route("/")
def index():
    return send_from_directory(".", "cockpit.html")


# ── Entry point ───────────────────────────────────────────────
if __name__ == "__main__":
    url = "http://localhost:8080"
    threading.Timer(1.3, lambda: webbrowser.open(url)).start()
    print(f"\n🚀  NIFTY Cockpit running at {url}\n")
    app.run(host="0.0.0.0", port=8080, debug=False)
