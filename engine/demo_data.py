"""
Synthetic data for testing the pipeline - NOT real company numbers.

We plant a known answer so we can check the machinery finds it:
  * wiki_views      genuinely tracks revenue acceleration (planted signal)
  * search_interest is pure noise with a seasonal pattern (should fail)

If the analysis says search_interest "works" on this data, the analysis is
broken. This is how professional quants validate a backtest before trusting it.
"""
import numpy as np
import pandas as pd

import config

QUARTER_ENDS = pd.date_range("2015-09-30", "2026-06-30", freq="QE")


def generate(seed: int = 7):
    rng = np.random.default_rng(seed)
    fin_rows, sig_rows = [], []
    months = pd.date_range("2015-07-01", "2026-09-01", freq="MS")

    for i, c in enumerate(c for c in config.COMPANIES if c.get("base")):
        n = len(QUARTER_ENDS)
        # Revenue growth wanders slowly (persistent), around a company trend.
        growth = np.zeros(n)
        g = rng.normal(0.08, 0.04)
        for t in range(n):
            g = 0.75 * g + 0.25 * rng.normal(0.07, 0.05) + rng.normal(0, 0.02)
            growth[t] = g
        season = np.array([1.00, 0.95, 1.02, 1.12])  # Q4 holiday bump
        level = 5e9 * (1 + i)
        revenue = []
        for t in range(n):
            level *= np.exp(growth[t] / 4)
            revenue.append(level * season[QUARTER_ENDS[t].quarter - 1])

        for t, end in enumerate(QUARTER_ENDS):
            fin_rows.append(dict(company_id=c["id"],
                                 period_start=(end - pd.DateOffset(months=3) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                                 period_end=end.strftime("%Y-%m-%d"),
                                 revenue=revenue[t],
                                 filed=(end + pd.Timedelta(days=35)).strftime("%Y-%m-%d"),
                                 derived=False))

        # Planted signal: monthly attention whose YoY growth follows revenue
        # growth (plus noise). Strength varies by company type, mirroring H3.
        strength = 1.5 if c["customer"] == "Consumer" else 0.3
        q_idx = np.searchsorted(QUARTER_ENDS, months, side="left").clip(0, n - 1)
        attn_growth = strength * growth[q_idx] + rng.normal(0, 0.06, len(months))
        attn = 1e6 * (1 + i / 3) * np.exp(np.cumsum(attn_growth / 12))
        attn *= 1 + 0.10 * np.sin(2 * np.pi * months.month / 12)  # seasonality
        attn *= np.exp(rng.normal(0, 0.05, len(months)))
        for m, v in zip(months, attn):
            sig_rows.append(dict(company_id=c["id"], signal="wiki_views",
                                 month=m.strftime("%Y-%m-01"), value=float(v)))

        # Noise signal: seasonal 0-100 index with no link to revenue.
        noise = 50 + 15 * np.sin(2 * np.pi * months.month / 12) + np.cumsum(rng.normal(0, 2, len(months)))
        noise = np.clip(noise, 1, 100)
        for m, v in zip(months, noise):
            sig_rows.append(dict(company_id=c["id"], signal="search_interest",
                                 month=m.strftime("%Y-%m-01"), value=float(v)))

    return pd.DataFrame(fin_rows), pd.DataFrame(sig_rows)
