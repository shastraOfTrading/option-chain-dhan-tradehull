from flask import Flask, jsonify, render_template_string, send_from_directory
from Dhan_Tradehull import Tradehull
import os

app = Flask(__name__)

CLIENT_ID    = "1103610460"
ACCESS_TOKEN = (
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9"
    ".eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzgwMjk2ODk4"
    "LCJpYXQiOjE3ODAyMTA0OTgsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIs"
    "IndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTAzNjEwNDYwIn0"
    ".zVIEGTHh3bMAUUVrC8YRAnIMiQbVzqzsRlDOojMXAbCGBt8y5IKjM13V7oN60"
    "M1-M_KIZxWKsgc98nfjIZztgw"
)

def sf(v):
    try:
        return float(v)
    except:
        return 0.0


def compute_trend(chain, atm):
    """
    Derive Bullish / Bearish / Neutral from net OI change on each side.
    Returns dict with trend label + explanation string.
    """
    below = [r for r in chain if r["strike"] < atm]
    above = [r for r in chain if r["strike"] > atm]

    total_pe_doi = sum(r["pe_doi"] for r in below)
    total_ce_doi = sum(r["ce_doi"] for r in above)

    def fmt(v):
        if v >= 1e7:
            return f"{v/1e7:.2f}Cr"
        if v >= 1e5:
            return f"{v/1e5:.2f}L"
        if v >= 1e3:
            return f"{v/1e3:.1f}K"
        return str(round(v))

    if total_pe_doi > 0 and total_ce_doi <= 0:
        trend = "Bullish"
        explanation = (
            f"Fresh put writing below ATM (ΔOI +{fmt(total_pe_doi)}) with no fresh "
            f"call writing above ATM. Put writers actively defending lower levels — "
            f"directional bias is up."
        )
    elif total_ce_doi > 0 and total_pe_doi <= 0:
        trend = "Bearish"
        explanation = (
            f"Fresh call writing above ATM (ΔOI +{fmt(total_ce_doi)}) with no fresh "
            f"put writing below ATM. Call writers capping upside — directional bias is down."
        )
    elif total_ce_doi > 0 and total_pe_doi > 0:
        if total_pe_doi > total_ce_doi * 1.2:
            trend = "Bullish"
            explanation = (
                f"Both sides active, but put writing (+{fmt(total_pe_doi)}) dominates "
                f"call writing (+{fmt(total_ce_doi)}). Net OI change favours bulls."
            )
        elif total_ce_doi > total_pe_doi * 1.2:
            trend = "Bearish"
            explanation = (
                f"Both sides active, but call writing (+{fmt(total_ce_doi)}) dominates "
                f"put writing (+{fmt(total_pe_doi)}). Net OI change favours bears."
            )
        else:
            trend = "Neutral"
            explanation = (
                f"Balanced fresh writing on both sides — CE ΔOI +{fmt(total_ce_doi)}, "
                f"PE ΔOI +{fmt(total_pe_doi)}. Market consolidating around ATM."
            )
    else:
        trend = "Neutral"
        explanation = (
            f"No significant fresh writing on either side. "
            f"CE ΔOI {fmt(total_ce_doi)}, PE ΔOI {fmt(total_pe_doi)}. "
            f"Wait for a clearer signal."
        )

    return {"label": trend, "explanation": explanation}


def build_reason(label, strike, oi, doi, vol):
    """Human-readable reasoning for support / resistance selection."""
    side = "Put" if label == "support" else "Call"

    def fmt(v):
        if v >= 1e7:
            return f"{v/1e7:.2f}Cr"
        if v >= 1e5:
            return f"{v/1e5:.2f}L"
        if v >= 1e3:
            return f"{v/1e3:.1f}K"
        return str(round(v))

    doi_str = (
        f"Fresh {side} writing of +{fmt(doi)}" if doi > 0
        else f"{side} OI change: {fmt(doi)}"
    )
    direction = "defending this level" if label == "support" else "capping upside here"

    return (
        f"{int(strike)} selected — highest weighted {side} OI score "
        f"{'below' if label == 'support' else 'above'} ATM. "
        f"{fmt(oi)} total {side} OI. {doi_str}. "
        f"{side} volume: {fmt(vol)}. Writers {direction}."
    )


@app.route("/api/data")
def data():
    tsl = Tradehull(CLIENT_ID, ACCESS_TOKEN)
    atm, oc = tsl.get_option_chain(
        Underlying="NIFTY",
        exchange="INDEX",
        expiry=1,
        num_strikes=10
    )

    # ── Support & Resistance ──────────────────────────────────────────────────
    below = oc[oc["Strike Price"] < atm].copy()
    above = oc[oc["Strike Price"] > atm].copy()

    below["score"] = (
        below["PE OI"] * 0.5
        + below["PE Chg in OI"].clip(lower=0) * 0.3
        + below["PE Volume"] * 0.2
    )
    above["score"] = (
        above["CE OI"] * 0.5
        + above["CE Chg in OI"].clip(lower=0) * 0.3
        + above["CE Volume"] * 0.2
    )

    support    = below.sort_values("score", ascending=False).iloc[0]
    resistance = above.sort_values("score", ascending=False).iloc[0]

    # ── Chain-wide maxima (for cell highlights) ───────────────────────────────
    highest_ce_oi  = sf(oc["CE OI"].max())
    highest_pe_oi  = sf(oc["PE OI"].max())
    highest_ce_vol = sf(oc["CE Volume"].max())
    highest_pe_vol = sf(oc["PE Volume"].max())

    # ── Build rows ────────────────────────────────────────────────────────────
    rows = []
    for _, r in oc.iterrows():
        rows.append({
            "strike":      sf(r["Strike Price"]),
            "ce_oi":       sf(r["CE OI"]),
            "ce_doi":      sf(r["CE Chg in OI"]),
            "ce_vol":      sf(r["CE Volume"]),
            "ce_ltp":      sf(r["CE LTP"]),
            "pe_oi":       sf(r["PE OI"]),
            "pe_doi":      sf(r["PE Chg in OI"]),
            "pe_vol":      sf(r["PE Volume"]),
            "pe_ltp":      sf(r["PE LTP"]),
            # Row classification
            "atm":        sf(r["Strike Price"]) == sf(atm),
            "support":    sf(r["Strike Price"]) == sf(support["Strike Price"]),
            "resistance": sf(r["Strike Price"]) == sf(resistance["Strike Price"]),
            # Cell highlights
            "max_ce_oi":  sf(r["CE OI"])     == highest_ce_oi,
            "max_pe_oi":  sf(r["PE OI"])     == highest_pe_oi,
            "max_ce_vol": sf(r["CE Volume"]) == highest_ce_vol,
            "max_pe_vol": sf(r["PE Volume"]) == highest_pe_vol,
        })

    # ── Trend (computed server-side and returned to frontend) ─────────────────
    trend = compute_trend(rows, sf(atm))

    # ── Support / resistance reasoning ───────────────────────────────────────
    sup_reason = build_reason(
        "support",
        sf(support["Strike Price"]),
        sf(support["PE OI"]),
        sf(support["PE Chg in OI"]),
        sf(support["PE Volume"]),
    )
    res_reason = build_reason(
        "resistance",
        sf(resistance["Strike Price"]),
        sf(resistance["CE OI"]),
        sf(resistance["CE Chg in OI"]),
        sf(resistance["CE Volume"]),
    )

    return jsonify({
        "atm": sf(atm),
        "trend": trend,                        # NEW — used by Trend card
        "support": {
            "strike": sf(support["Strike Price"]),
            "oi":     sf(support["PE OI"]),
            "doi":    sf(support["PE Chg in OI"]),
            "vol":    sf(support["PE Volume"]),
            "reason": sup_reason,
        },
        "resistance": {
            "strike": sf(resistance["Strike Price"]),
            "oi":     sf(resistance["CE OI"]),
            "doi":    sf(resistance["CE Chg in OI"]),
            "vol":    sf(resistance["CE Volume"]),
            "reason": res_reason,
        },
        "chain": rows,
    })


@app.route("/")
def home():
    # Serve the dashboard HTML from the templates folder
    return send_from_directory("templates", "strikelens_dashboard.html")


if __name__ == "__main__":
    app.run(port=8080, debug=True)
