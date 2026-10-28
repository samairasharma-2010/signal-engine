"""
Alternative Investment Signal Engine - website.

    streamlit run app.py
"""
import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import config
from engine import db

st.set_page_config(page_title="Signal Engine", layout="wide")

# ---------------------------------------------------------------- data -----
MODE = "live" if db.db_path("live").exists() and not db.read_table("live", "panel").empty else "demo"


@st.cache_data
def load(mode, table):
    return db.read_table(mode, table)


panel = load(MODE, "panel")
card = load(MODE, "scorecard")
breakdown = load(MODE, "company_breakdown")

if panel.empty:
    st.error("No data yet. Run `python pipeline.py demo` (test data) or "
             "`python pipeline.py fetch` (real data) first.")
    st.stop()

panel["period_end"] = pd.to_datetime(panel["period_end"])
signals = sorted(c[:-6] for c in panel.columns if c.endswith("_level"))
label = lambda s: config.SIGNAL_LABELS.get(s, s.replace("_", " ").title())
pct = lambda v: "n/a" if pd.isna(v) else f"{(np.exp(v) - 1) * 100:+.1f}%"

# -------------------------------------------------------------- header -----
st.title("Alternative Investment Signal Engine")
st.caption("Does public attention data tell us anything about a company's revenue "
           "before the company reports it?")
if MODE == "demo":
    st.warning("**SYNTHETIC TEST DATA - these are not real company numbers.** "
               "The demo exists to check the analysis finds a planted signal and rejects "
               "a noise signal. Run `python pipeline.py fetch` for real data.")

companies = [c for c in config.COMPANIES if c["id"] in set(panel["company_id"])]
tab_company, tab_research, tab_method = st.tabs(
    ["Company view", "Research scorecard", "Methodology"])

# --------------------------------------------------------- company view ----
with tab_company:
    left, right = st.columns([2, 1])
    with left:
        comp = st.selectbox("Company", companies,
                            format_func=lambda c: f"{c['name']}  ({c['sector']})")
    with right:
        sig = st.selectbox("Signal to compare", signals, format_func=label)

    cp = panel[panel["company_id"] == comp["id"]].sort_values("period_end")
    latest = cp.dropna(subset=["rev_yoy"]).iloc[-1]
    q_label = latest["period_end"].strftime("quarter ending %d %b %Y")

    st.subheader(f"{comp['name']} - latest {q_label}")
    cols = st.columns(len(signals) + 1)
    cols[0].metric("Revenue growth (YoY)", pct(latest["rev_yoy"]),
                   delta=None if pd.isna(latest["rev_accel"]) else
                   f"{latest['rev_accel'] * 100:+.1f} pts vs last quarter")
    for col, s in zip(cols[1:], signals):
        col.metric(label(s) + " (YoY)", pct(latest[f"{s}_yoy"]),
                   delta=None if pd.isna(latest[f"{s}_accel"]) else
                   f"{latest[f'{s}_accel'] * 100:+.1f} pts vs last quarter")
    if comp["currency"] != "USD":
        st.caption(f"Revenue in {comp['currency']}; growth rates are comparable, levels are not.")

    # Chart: revenue growth vs signal growth over time
    chart_df = pd.DataFrame({
        "Quarter end": cp["period_end"],
        "Revenue": (np.exp(cp["rev_yoy"]) - 1) * 100,
        label(sig): (np.exp(cp[f"{sig}_yoy"]) - 1) * 100,
    }).melt("Quarter end", var_name="Series", value_name="YoY change (%)").dropna()
    line = alt.Chart(chart_df).mark_line(point=True).encode(
        x="Quarter end:T", y="YoY change (%):Q", color="Series:N",
        tooltip=["Quarter end:T", "Series:N", alt.Tooltip("YoY change (%):Q", format=".1f")],
    ).properties(height=320, title="Year-on-year change: revenue vs signal")
    st.altair_chart(line, use_container_width=True)

    # Plain-English historical result
    d = cp[[f"{sig}_accel", "rev_accel"]].dropna()
    d = d[(d.iloc[:, 0] != 0) & (d.iloc[:, 1] != 0)]
    if len(d) >= 8:
        hits = int((np.sign(d.iloc[:, 0]) == np.sign(d.iloc[:, 1])).sum())
        st.info(f"In **{hits} of {len(d)} quarters** ({hits / len(d):.0%}), the direction of "
                f"change in {label(sig).lower()} growth matched the direction of change in "
                f"{comp['name']}'s revenue growth in the same quarter. A coin flip would match "
                f"about 50% of the time.")
    else:
        st.info("Not enough overlapping quarters yet for a historical comparison.")

    with st.expander("Raw quarterly data"):
        show = cp[["period_start", "period_end", "revenue", "rev_yoy", "rev_accel"]
                  + [f"{sig}_level", f"{sig}_yoy", f"{sig}_accel"]].copy()
        show["period_end"] = show["period_end"].dt.strftime("%Y-%m-%d")
        st.dataframe(show.round(4), use_container_width=True, hide_index=True)

# ------------------------------------------------------ research scorecard --
with tab_research:
    st.subheader("Which signals carry information?")
    st.write("Each row is one test, pooled across all companies. A signal is promising "
             "only if the **adjusted p-value is below 0.05** *and* the **out-of-sample "
             "R²** is above zero (it beat the baseline on quarters it never saw).")
    if card.empty:
        st.info("No scorecard yet.")
    else:
        t = card.copy()
        t["Signal"] = t["signal"].map(label)
        t["Measure"] = t["measure"].map({"yoy": "Growth (YoY)", "accel": "Acceleration"})
        t["Timing"] = t["horizon"].map({0: "Same quarter (nowcast)", 1: "Next quarter (lead)"})
        t["Verdict"] = np.where((t["p_adjusted"] < 0.05) & (t["oos_r2"] > 0),
                                "Promising", "No reliable link")
        st.dataframe(
            t[["Signal", "Measure", "Timing", "n", "companies", "corr_within",
               "p_adjusted", "hit_rate", "oos_r2", "Verdict"]].rename(columns={
                "n": "Quarters", "companies": "Companies", "corr_within": "Correlation",
                "p_adjusted": "Adjusted p", "hit_rate": "Direction hit rate",
                "oos_r2": "Out-of-sample R²"}).round(3),
            use_container_width=True, hide_index=True)

    st.subheader("By company (acceleration, same quarter)")
    st.caption("Descriptive only - about 35 quarters per company is too few for firm conclusions.")
    if not breakdown.empty:
        bsig = st.selectbox("Signal", sorted(breakdown["signal"].unique()),
                            format_func=label, key="bsig")
        b = breakdown[breakdown["signal"] == bsig].copy()
        b["Company"] = b["company_id"].map(lambda i: config.COMPANY_BY_ID[i]["name"])
        b["Main customer"] = b["company_id"].map(lambda i: config.COMPANY_BY_ID[i]["customer"])
        bars = alt.Chart(b).mark_bar().encode(
            x=alt.X("spearman:Q", title="Rank correlation with revenue acceleration",
                    scale=alt.Scale(domain=[-1, 1])),
            y=alt.Y("Company:N", sort="-x", title=None),
            color=alt.Color("Main customer:N"),
            tooltip=["Company", "Main customer", alt.Tooltip("spearman:Q", format=".2f"),
                     alt.Tooltip("hit_rate:Q", format=".0%"), "n"],
        ).properties(height=320)
        st.altair_chart(bars, use_container_width=True)

# ----------------------------------------------------------- methodology ----
with tab_method:
    st.subheader("How the numbers are made")
    st.markdown(f"""
1. **Revenue** comes from the SEC's free XBRL database, *as first reported* - later
   revisions are ignored, because investors didn't know them at the time. Adidas is not
   an SEC filer, so its figures come from its own quarterly reports (entered by hand).
2. **Signals** are monthly. Each month is assigned to the company's own fiscal quarter,
   and a quarter needs all three months.
3. **Year-on-year log growth** removes seasonality (holiday quarters, summer travel).
4. **Acceleration** = this quarter's growth minus last quarter's. This is closest to what
   moves share prices: whether growth beats or misses its recent trend.
5. **Timing:** a quarter's signal is complete on the last day of the quarter; revenue is
   published weeks later. So a same-quarter link is a genuine early read, not hindsight.
6. **Significance** uses a circular-shift permutation test (2,000 shuffles) that keeps
   each signal's slow-moving pattern. On the synthetic test data, an ordinary test called
   a pure-noise signal significant (p = 0.002); this test correctly did not.
7. **Multiple testing:** p-values are adjusted with Benjamini-Hochberg.
8. **Out-of-sample:** the model is fitted on quarters before {config.OUT_OF_SAMPLE_START} and
   scored after it, against a baseline that predicts each company's average.

**Limitations:** 10 large companies only; attention is not purchases; Google Trends is
rescaled per search term; correlation is not causation.
""")
    meta = load(MODE, "meta")
    if not meta.empty:
        st.caption(f"Data built {meta['built_at'].iloc[0]} ({MODE} mode).")
