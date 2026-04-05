"""
Strait of Hormuz Crisis — Global Energy Market Impact Visualization
====================================================================
Single file. Three charts. <400 lines.

Usage:
  1) Run fetch_data() on your local machine (needs internet + free EIA API key)
     → generates prices.csv
  2) Run main() to produce three interactive HTML charts
  3) To plug your own data: just replace the CSV files, formats documented below.

Deps:  pip install plotly pandas numpy requests
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json, os

OUT = "output"
os.makedirs(OUT, exist_ok=True)

# ── key geopolitical events (shared across charts) ────────
EVENTS = [
    ("2026-02-28", "US-Israel strikes on Iran"),
    ("2026-03-04", "Iran declares Strait closed"),
    ("2026-03-11", "IEA 400 mb reserve release"),
    ("2026-03-22", "Trump 48h ultimatum"),
    ("2026-03-28", "Trump signals negotiation"),
]

# color palette
C = dict(
    brent="#c44d2b", wti="#d4735c", diesel="#8c3518",
    jkm="#1D9E75", ttf="#0F6E56", naphtha="#378ADD",
    lpg="#D4537E", gold="#BA7517", event="#6b6b6b",
)


# ═══════════════════════════════════════════════════════════
# SECTION 0 — DATA FETCHERS  (run locally with internet)
# ═══════════════════════════════════════════════════════════

def fetch_prices(eia_key: str, fred_key: str, out="prices.csv"):
    """
    Pull daily price series from free public APIs.
    EIA key: https://www.eia.gov/opendata/register.php  (free)
    FRED key: https://fred.stlouisfed.org/docs/api/api_key.html (free)

    Produces CSV with columns: date, brent, wti, henry_hub, heating_oil, gasoline
    Plus from FRED: jkm_lng (monthly), ttf (daily if available)

    Run once, commit the CSV, then charts work offline.
    """
    import requests

    START = "2026-01-01"
    series = {  # EIA petroleum spot prices
        "brent":      "RBRTE",
        "wti":        "RWTC",
        "heating_oil":"EER_EPD2F_PF4_Y35NY_DPG",
        "gasoline":   "EER_EPMRU_PF4_Y35NY_DPG",
    }
    frames = {}
    for name, sid in series.items():
        url = (f"https://api.eia.gov/v2/petroleum/pri/spt/data/"
               f"?api_key={eia_key}&frequency=daily&data[0]=value"
               f"&facets[series][]={sid}&start={START}&sort[0][column]=period"
               f"&sort[0][direction]=asc&length=5000")
        r = requests.get(url).json()
        rows = r.get("response", {}).get("data", [])
        if rows:
            s = pd.Series(
                {row["period"]: float(row["value"]) for row in rows},
                name=name
            )
            s.index = pd.to_datetime(s.index)
            frames[name] = s
            print(f"  EIA  {name}: {len(s)} rows")

    # Henry Hub from EIA natural gas
    url = (f"https://api.eia.gov/v2/natural-gas/pri/fut/data/"
           f"?api_key={eia_key}&frequency=daily&data[0]=value"
           f"&facets[series][]=RNGC1&start={START}&length=5000")
    r = requests.get(url).json()
    rows = r.get("response", {}).get("data", [])
    if rows:
        s = pd.Series(
            {row["period"]: float(row["value"]) for row in rows},
            name="henry_hub"
        )
        s.index = pd.to_datetime(s.index)
        frames["henry_hub"] = s
        print(f"  EIA  henry_hub: {len(s)} rows")

    # FRED: JKM LNG Asia
    for sid, name in [("PNGASJPUSDM", "jkm_lng")]:
        url = (f"https://api.stlouisfed.org/fred/series/observations"
               f"?series_id={sid}&api_key={fred_key}&file_type=json"
               f"&observation_start={START}")
        r = requests.get(url).json()
        obs = r.get("observations", [])
        if obs:
            s = pd.Series(
                {o["date"]: float(o["value"]) for o in obs if o["value"] != "."},
                name=name
            )
            s.index = pd.to_datetime(s.index)
            frames[name] = s
            print(f"  FRED {name}: {len(s)} rows")

    df = pd.DataFrame(frames)
    df.index.name = "date"
    df.to_csv(out)
    print(f"\n→ Saved {out}  ({len(df)} rows, {len(df.columns)} series)")
    return df


# ═══════════════════════════════════════════════════════════
# SECTION 1 — CHART 1: Multi-commodity price trajectories
# ═══════════════════════════════════════════════════════════
# Input CSV format:  date (index), then one column per commodity (daily USD price)
# All series get rebased to index=100 on first available date.

def chart_prices(csv_path="prices.csv") -> str:
    """
    Indexed price chart (base=100) with event annotations.
    Returns path to output HTML.
    """
    df = pd.read_csv(csv_path, index_col="date", parse_dates=True)

    # drop columns with fewer than 5 data points (e.g. monthly series)
    df = df.loc[:, df.count() >= 5]

    # rebase each series to 100 at its own first non-null value
    idx = df.copy()
    for col in idx.columns:
        first_valid = idx[col].first_valid_index()
        if first_valid is not None:
            idx[col] = (idx[col] / idx[col].loc[first_valid]) * 100

    LABELS = {  # column_name → (display, color)
        "brent":      ("Brent crude ($/bbl)",       C["brent"]),
        "wti":        ("WTI crude ($/bbl)",          C["wti"]),
        "heating_oil":("Heating oil ($/gal)",        C["diesel"]),
        "gasoline":   ("Gasoline RBOB ($/gal)",      C["lpg"]),
        "henry_hub":  ("Henry Hub nat. gas ($/MMBtu)",C["ttf"]),
        "jkm_lng":    ("JKM LNG Asia ($/MMBtu)",     C["jkm"]),
    }

    fig = go.Figure()
    for col in idx.columns:
        label, color = LABELS.get(col, (col, "#888"))
        s = idx[col].dropna()
        if len(s) < 2:
            continue
        # add raw price to hover
        raw = df[col].dropna()
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values, name=label,
            line=dict(color=color, width=2.5),
            customdata=raw.reindex(s.index).values,
            hovertemplate="%{x|%b %d}: index %{y:.1f}  (raw %{customdata:.2f})<extra>" + label + "</extra>",
        ))

    # event lines
    for dt, txt in EVENTS:
        fig.add_vline(x=dt, line=dict(color=C["event"], width=0.8, dash="dot"))
        fig.add_annotation(
            x=dt, y=1.02, yref="paper", text=txt, showarrow=False,
            font=dict(size=10, color=C["event"], family="DM Sans, sans-serif"), textangle=-35,
        )

    fig.update_layout(
        title=dict(
            text="Energy price trajectories since January 2026",
            font=dict(size=16, family="DM Sans, sans-serif", color="#1a1a1a"),
        ),
        yaxis_title="Index (Jan 2 = 100)",
        xaxis_title=None,
        template="plotly_white",
        font=dict(family="DM Sans, sans-serif", size=12, color="#1a1a1a"),
        height=520, margin=dict(t=80, r=30),
        legend=dict(orientation="h", y=-0.15, font=dict(size=11)),
        hovermode="x unified",
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
    )
    out = f"{OUT}/1_price_index.html"
    fig.write_html(out, include_plotlyjs="cdn")
    print(f"→ {out}")
    return out


# ═══════════════════════════════════════════════════════════
# SECTION 2 — CHART 2a: Country × Commodity vulnerability matrix
#              CHART 2b: Trade flow disruption map
# ═══════════════════════════════════════════════════════════
# Matrix data is embedded (sourced from CF40, IEA, CRS reports).
# You can override by providing vulnerability.csv:
#   rows = countries, columns = commodities, values = 0-10 score

VULN_DATA = {
    #               Crude Diesel LNG  LPG  Naphtha Fert. Helium Alum.
    "Japan":        [9,    8,    8,   6,   8,      4,    7,     3],
    "South Korea":  [9,    7,    9,   5,   9,      3,    9,     4],
    "India":        [8,    7,    6,   10,  5,      7,    2,     3],
    "China":        [6,    4,    5,   8,   6,      3,    6,     2],
    "EU":           [5,    8,    7,   3,   5,      5,    5,     4],
    "UK":           [5,    8,    8,   3,   4,      5,    5,     3],
    "USA":          [3,    3,    2,   2,   2,      4,    4,     5],
    "SE Asia":      [7,    6,    7,   7,   7,      8,    2,     3],
    "Africa":       [6,    7,    4,   5,   3,      9,    1,     2],
    "Gulf states":  [4,    5,    3,   3,   4,      2,    3,     8],
}
VULN_COLS = ["Crude", "Diesel", "LNG", "LPG", "Naphtha", "Fertilizer", "Helium", "Aluminum"]

# (country, commodity) → (rationale, source_label, source_url)
VULN_SOURCES = {
    ("India",       "LPG"):       ("90% of LPG imports from Middle East; millions forced to cook on coal/firewood",
                                   "IEA OMR / OilPrice.com",
                                   "https://oilprice.com/Energy/Energy-General/The-Critical-Commodities-Caught-in-the-Hormuz-Blockade.html"),
    ("South Korea", "Helium"):    ("2/3 of global memory chips; helium listed among 14 critical materials monitored",
                                   "Valuates / J2 Sourcing",
                                   "https://reports.valuates.com/blogs/helium-supply-disruption-semiconductor-impact-2026"),
    ("South Korea", "Naphtha"):   ("Petrochemical producers cut run rates by up to 50%",
                                   "Atlantic Council",
                                   "https://www.atlanticcouncil.org/blogs/energysource/the-strait-of-hormuz-crisis-will-ripple-across-plastics-and-food-supply-chains-helping-beijing-and-moscow-hurting-americans/"),
    ("South Korea", "LNG"):       ("75% of Strait oil exports + 59% LNG go to Asia; Korea low nuclear share",
                                   "Wikipedia / IEA",
                                   "https://en.wikipedia.org/wiki/Economic_impact_of_the_2026_Iran_war"),
    ("Japan",       "Crude"):     ("IEA: Japan and Korea particularly reliant on Strait oil flows",
                                   "IEA Strait of Hormuz page",
                                   "https://www.iea.org/about/oil-security-and-emergency-response/strait-of-hormuz"),
    ("Japan",       "Naphtha"):   ("42% of Japan naphtha supply from Middle East",
                                   "Atlantic Council",
                                   "https://www.atlanticcouncil.org/blogs/energysource/the-strait-of-hormuz-crisis-will-ripple-across-plastics-and-food-supply-chains-helping-beijing-and-moscow-hurting-americans/"),
    ("Japan",       "LNG"):       ("Major LNG importer; Asian prices surged to attract cargoes",
                                   "IEA Middle East topic page",
                                   "https://www.iea.org/topics/the-middle-east-and-global-energy-markets"),
    ("EU",          "Diesel"):    ("Middle East was filling EU diesel gap after Russia/India supply cut off",
                                   "LSEG analysis",
                                   "https://www.lseg.com/en/insights/all-eyes-on-hormuz"),
    ("UK",          "LNG"):       ("UK expected worst-hit major economy; inflation forecast >5%",
                                   "Wikipedia economic impact",
                                   "https://en.wikipedia.org/wiki/Economic_impact_of_the_2026_Iran_war"),
    ("UK",          "Diesel"):    ("EU-wide diesel crisis applies equally to UK; same supply dependency",
                                   "LSEG analysis",
                                   "https://www.lseg.com/en/insights/all-eyes-on-hormuz"),
    ("China",       "LPG"):       ("2nd largest Hormuz LPG importer; domestic price at 12-year high",
                                   "OilPrice / Argus",
                                   "https://oilprice.com/Energy/Energy-General/The-Critical-Commodities-Caught-in-the-Hormuz-Blockade.html"),
    ("China",       "Crude"):     ("Risk mainly via external demand shock; has Russia/C.Asia pipeline alternatives; Iran allowed Chinese vessels",
                                   "CF40 report / Wikipedia",
                                   "https://en.wikipedia.org/wiki/2026_Strait_of_Hormuz_crisis"),
    ("Africa",      "Fertilizer"):("86% of Gulf→E.Africa fertilizer ships ceased; no strategic reserves",
                                   "OilPrice / Windward data",
                                   "https://oilprice.com/Energy/Energy-General/The-Critical-Commodities-Caught-in-the-Hormuz-Blockade.html"),
    ("SE Asia",     "Fertilizer"):("Asia fertilizer-dependent regions particularly vulnerable per ING",
                                   "OilPrice / ING",
                                   "https://oilprice.com/Energy/Energy-General/The-Critical-Commodities-Caught-in-the-Hormuz-Blockade.html"),
    ("USA",         "Aluminum"):  ("US imports >1/5 of aluminum from Persian Gulf",
                                   "RFE/RL / Argus",
                                   "https://english.shabtabnews.com/2026/04/02/how-irans-hormuz-blockade-chokes-global-trade-beyond-oil-and-gas/"),
    ("USA",         "Crude"):     ("Mainly inflation/political risk, not direct supply shortage",
                                   "CF40 report",
                                   "https://finance.sina.com.cn/wm/2026-03-24/doc-inhscaeu4135679.shtml"),
    ("Gulf states", "Aluminum"):  ("~10% global supply, >80% exported; infrastructure physically damaged",
                                   "RFE/RL / Argus",
                                   "https://english.shabtabnews.com/2026/04/02/how-irans-hormuz-blockade-chokes-global-trade-beyond-oil-and-gas/"),
    ("South Korea", "Crude"):     ("IEA: Japan and Korea particularly reliant on Strait oil flows",
                                   "IEA Strait of Hormuz page",
                                   "https://www.iea.org/about/oil-security-and-emergency-response/strait-of-hormuz"),
    ("India",       "Crude"):     ("Major importer; China+India received 44% of Strait crude exports",
                                   "IEA Strait of Hormuz page",
                                   "https://www.iea.org/about/oil-security-and-emergency-response/strait-of-hormuz"),
    ("India",       "Fertilizer"):("India imports 18% of Gulf urea; among most exposed",
                                   "WEF",
                                   "https://www.weforum.org/stories/2026/04/beyond-oil-lng-commodities-impacted-closure-hormuz-strait/"),
}


def chart_vulnerability(csv_path: str | None = None) -> str:
    """
    Heatmap: country rows × commodity columns.
    Hover shows score rationale + source with clickable URL.
    """
    if csv_path and os.path.exists(csv_path):
        df = pd.read_csv(csv_path, index_col=0)
    else:
        df = pd.DataFrame(VULN_DATA, index=VULN_COLS).T

    # build hover text matrix with sources
    hover = []
    for country in df.index:
        row = []
        for commodity in df.columns:
            score = df.loc[country, commodity]
            key = (country, commodity)
            if key in VULN_SOURCES:
                rationale, src_label, src_url = VULN_SOURCES[key]
                txt = (f"<b>{country} × {commodity}: {score}/10</b><br>"
                       f"{rationale}<br>"
                       f"<i>Source: {src_label}</i><br>"
                       f"{src_url}")
            else:
                txt = (f"<b>{country} × {commodity}: {score}/10</b><br>"
                       f"<i>Estimated from import structure</i>")
            row.append(txt)
        hover.append(row)

    fig = go.Figure(go.Heatmap(
        z=df.values,
        x=df.columns.tolist(),
        y=df.index.tolist(),
        colorscale=[
            [0.0, "#f5f4f0"],
            [0.3, "#FAC775"],
            [0.6, "#EF9F27"],
            [0.8, "#c44d2b"],
            [1.0, "#791F1F"],
        ],
        zmin=0, zmax=10,
        text=df.values,
        texttemplate="%{text}",
        textfont=dict(size=13),
        hovertext=hover,
        hovertemplate="%{hovertext}<extra></extra>",
        colorbar=dict(title="Score", tickvals=[0, 5, 10],
                      ticktext=["Low", "Med", "High"]),
    ))

    fig.update_layout(
        title=dict(
            text="Country × commodity vulnerability assessment (0–10 scale)",
            font=dict(size=16, family="DM Sans, sans-serif", color="#1a1a1a"),
        ),
        template="plotly_white",
        font=dict(family="DM Sans, sans-serif", size=12, color="#1a1a1a"),
        height=460, margin=dict(l=100, t=60),
        yaxis=dict(autorange="reversed"),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
    )
    out = f"{OUT}/2a_vulnerability_matrix.html"
    fig.write_html(out, include_plotlyjs="cdn")
    print(f"→ {out}")
    return out


# Trade flow map: arcs from Gulf to importers, color = disrupted vs alternative

FLOWS = [
    # (from_lat, from_lon, to_lat, to_lon, label, status)
    # Disrupted Gulf → Asia/Europe
    (26.0, 56.0, 35.5, 139.7, "Crude → Japan",       "disrupted"),
    (26.0, 56.0, 37.5, 127.0, "Crude → S.Korea",     "disrupted"),
    (26.0, 56.0, 30.0, 120.0, "Crude → China",        "disrupted"),
    (26.0, 56.0, 19.0,  73.0, "LPG → India",          "disrupted"),
    (25.5, 51.5, 35.5, 139.7, "LNG → Japan",          "disrupted"),
    (25.5, 51.5, 51.0,   3.0, "LNG → Europe",         "disrupted"),
    (26.0, 56.0, 51.0,   3.0, "Diesel → Europe",      "disrupted"),
    (25.5, 51.5, 37.5, 127.0, "Helium → S.Korea",     "disrupted"),
    # Alternative routes activated
    (29.5, -95.0, 51.0,  3.0, "US crude → Europe",    "alternative"),
    (29.5, -95.0, 35.5, 139.7, "US LNG → Japan",      "alternative"),
    (55.0,  73.0, 30.0, 120.0, "Russia oil → China",   "alternative"),
    (5.0,    2.0, 51.0,   3.0, "W.Africa oil → EU",    "alternative"),
    (14.0, 108.0, 35.5, 139.7, "Vietnam oil → Japan",  "alternative"),
]

def chart_trade_flows() -> str:
    """
    Globe map with arcs: red = disrupted flows, green = alternative routes.
    """
    fig = go.Figure()

    for flat, flon, tlat, tlon, label, status in FLOWS:
        color = "#c44d2b" if status == "disrupted" else "#1D9E75"
        dash = "solid" if status == "disrupted" else "dash"
        width = 2 if status == "disrupted" else 1.5

        # arc via intermediate point (crude great-circle approx)
        mid_lat = (flat + tlat) / 2 + 5
        mid_lon = (flon + tlon) / 2

        fig.add_trace(go.Scattergeo(
            lat=[flat, mid_lat, tlat],
            lon=[flon, mid_lon, tlon],
            mode="lines",
            line=dict(color=color, width=width, dash=dash),
            name=label,
            showlegend=False,
            hoverinfo="text",
            text=[None, label, None],
        ))

    # endpoints: Gulf hub
    fig.add_trace(go.Scattergeo(
        lat=[26.0], lon=[56.0], mode="markers+text",
        marker=dict(size=12, color="#c44d2b", symbol="x"),
        text=["Strait of Hormuz"], textposition="bottom center",
        textfont=dict(size=11, color="#791F1F"),
        showlegend=False, hoverinfo="text",
    ))

    # legend entries
    for status, color, dash, label in [
        ("disrupted", "#c44d2b", "solid", "Disrupted flow"),
        ("alternative", "#1D9E75", "dash", "Alternative route"),
    ]:
        fig.add_trace(go.Scattergeo(
            lat=[None], lon=[None], mode="lines",
            line=dict(color=color, width=2, dash=dash),
            name=label,
        ))

    fig.update_geos(
        projection_type="natural earth",
        showland=True, landcolor="#f5f4f0",
        showocean=True, oceancolor="#e6f1fb",
        showcountries=True, countrycolor="#e0ddd8",
        lataxis_range=[-10, 65], lonaxis_range=[-30, 160],
    )
    fig.update_layout(
        title=dict(
            text="Disrupted energy flows and alternative routes",
            font=dict(size=16, family="DM Sans, sans-serif", color="#1a1a1a"),
        ),
        template="plotly_white",
        font=dict(family="DM Sans, sans-serif", size=12, color="#1a1a1a"),
        height=480, margin=dict(t=60, b=20, l=10, r=10),
        legend=dict(x=0.01, y=0.01, font=dict(size=11)),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
    )
    out = f"{OUT}/2b_trade_flows.html"
    fig.write_html(out, include_plotlyjs="cdn")
    print(f"→ {out}")
    return out


# ═══════════════════════════════════════════════════════════
# SECTION 3 — CHART 3: Supply gap vs buffer + long-tail risks
# ═══════════════════════════════════════════════════════════
# Data from IEA OMR March 2026, EIA STEO, CNBC, CRS

SUPPLY_GAP = {
    # category: (mb/d or equivalent unit, positive = buffer, negative = gap)
    "Strait disruption":              -20.0,
    "Gulf production shut-in":        -11.0,
    "Saudi/UAE bypass pipelines":       4.5,
    "IEA strategic reserve release":    1.5,   # 400mb over ~270 days
    "OPEC+ emergency increase":         0.2,
    "Non-OPEC+ output response":        1.1,
    "Net gap":                         None,   # computed
}

LONGTAIL = [
    # (item, recovery_months, severity 1-10, note)
    ("Qatar Ras Laffan LNG plant",     36, 9, "Missile damage; 20% global LNG offline"),
    ("Qatar helium production",        48, 8, "3-5 yr rebuild; 33% global supply gone"),
    ("Gulf petrochemical plants",      18, 7, "40+ facilities damaged across 9 countries"),
    ("Saudi Ras Tanura refinery",      12, 7, "Drone strike; largest Saudi refinery"),
    ("Iraq export infrastructure",      9, 6, "Storage full, pipelines damaged"),
    ("Marine insurance normalization",  6, 5, "War-risk premiums persist post-conflict"),
    ("Shipping route confidence",       6, 4, "Tanker owners slow to return"),
]


def chart_supply_gap() -> str:
    """
    Waterfall chart: supply disruption vs buffers → net gap.
    Plus horizontal bar: long-tail recovery timelines.
    """
    fig = make_subplots(
        rows=2, cols=1, row_heights=[0.45, 0.55],
        subplot_titles=[
            "How large is the supply gap? (million barrels/day)",
            "How long until recovery after a ceasefire?",
        ],
        vertical_spacing=0.18,
    )

    # ── 3a: waterfall ──
    labels, values, colors, texts = [], [], [], []
    running = 0
    items = list(SUPPLY_GAP.items())
    for name, val in items:
        if val is None:
            continue
        labels.append(name)
        values.append(val)
        running += val
        colors.append("#c44d2b" if val < 0 else "#1D9E75")
        texts.append(f"{val:+.1f}")

    # net gap bar
    labels.append("NET GAP")
    values.append(running)
    colors.append("#791F1F")
    texts.append(f"{running:+.1f}")

    # plotly waterfall
    fig.add_trace(go.Waterfall(
        x=labels, y=values,
        measure=["relative"] * (len(values) - 1) + ["total"],
        text=texts, textposition="outside",
        connector=dict(line=dict(color="#e0ddd8", width=0.5)),
        increasing=dict(marker=dict(color="#1D9E75")),
        decreasing=dict(marker=dict(color="#c44d2b")),
        totals=dict(marker=dict(color="#791F1F")),
        hovertemplate="%{x}: %{y:+.1f} mb/d<extra></extra>",
    ), row=1, col=1)

    # ── 3b: long-tail recovery bars ──
    lt_sorted = sorted(LONGTAIL, key=lambda x: x[1], reverse=True)
    names = [r[0] for r in lt_sorted]
    months = [r[1] for r in lt_sorted]
    severity = [r[2] for r in lt_sorted]
    notes = [r[3] for r in lt_sorted]

    # color by severity
    bar_colors = []
    for s in severity:
        if s >= 8:
            bar_colors.append("#c44d2b")
        elif s >= 6:
            bar_colors.append("#EF9F27")
        else:
            bar_colors.append("#378ADD")

    fig.add_trace(go.Bar(
        y=names, x=months, orientation="h",
        marker=dict(color=bar_colors),
        text=[f"{m} mo" for m in months],
        textposition="outside",
        hovertemplate="%{y}<br>%{x} months to recover<br>"
                      + "<extra></extra>",
        customdata=notes,
    ), row=2, col=1)

    fig.update_layout(
        template="plotly_white",
        font=dict(family="DM Sans, sans-serif", size=12, color="#1a1a1a"),
        height=820, showlegend=False,
        margin=dict(t=60, l=220, r=40),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
    )
    fig.update_yaxes(autorange="reversed", row=2, col=1)
    fig.update_xaxes(title_text="Months", row=2, col=1)
    fig.update_xaxes(title_text=None, row=1, col=1)

    out = f"{OUT}/3_supply_gap_longtail.html"
    fig.write_html(out, include_plotlyjs="cdn")
    print(f"→ {out}")
    return out


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def main(prices_csv: str | None = None):
    """
    Generate all charts. If prices_csv is None or missing,
    chart 1 is skipped (no fake data — run fetch_prices() first).
    """
    print("=" * 60)
    print("Hormuz Energy Crisis — Visualization Suite")
    print("=" * 60)

    # Chart 1: prices (only if real data available)
    if prices_csv and os.path.exists(prices_csv):
        chart_prices(prices_csv)
    else:
        print("\n⚠  prices.csv not found — skipping chart 1.")
        print("   Run fetch_prices(eia_key, fred_key) to generate it.\n")

    # Chart 2a: vulnerability matrix
    chart_vulnerability()

    # Chart 2b: trade flow map
    chart_trade_flows()

    # Chart 3: supply gap + long-tail
    chart_supply_gap()

    print("\n" + "=" * 60)
    print(f"Done. All outputs in ./{OUT}/")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    csv = sys.argv[1] if len(sys.argv) > 1 else None
    main(csv)