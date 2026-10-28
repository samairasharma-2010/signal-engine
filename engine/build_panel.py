"""
Turns raw tables into one research table ("panel"): one row per company per
fiscal quarter, with revenue and every signal measured the same way.

Measures
--------
*_yoy    log year-on-year growth  = ln(this quarter / same quarter last year)
         (log growth is ~% growth for small changes and removes seasonality)
*_accel  acceleration = this quarter's yoy - last quarter's yoy
         (is growth speeding up or slowing down? = the "surprise" vs trend)
"""
import numpy as np
import pandas as pd


def _assign_months_to_quarters(quarters: pd.DataFrame, monthly: pd.DataFrame) -> pd.Series:
    """Average of the monthly signal over each fiscal quarter.
    A month belongs to the quarter that contains its 15th day, which handles
    odd fiscal calendars (e.g. Apple's quarters end on the last Saturday)."""
    if monthly.empty:
        return pd.Series(np.nan, index=quarters.index)
    m = monthly.copy()
    m["mid"] = pd.to_datetime(m["month"]) + pd.Timedelta(days=14)
    out = []
    for _, q in quarters.iterrows():
        vals = m.loc[(m["mid"] >= q["period_start"]) & (m["mid"] <= q["period_end"]), "value"]
        out.append(vals.mean() if len(vals) == 3 else np.nan)  # need a full quarter
    return pd.Series(out, index=quarters.index)


def _yoy(values: pd.Series, ends: pd.Series) -> pd.Series:
    """Log change vs 4 quarters earlier - only if that really is ~1 year earlier."""
    prev_val = values.shift(4)
    gap = (ends - ends.shift(4)).dt.days
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.log(values / prev_val)
    out[(gap < 350) | (gap > 380) | (values <= 0) | (prev_val <= 0)] = np.nan
    return out


def build_panel(financials: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    rows = []
    signal_names = sorted(signals["signal"].unique()) if not signals.empty else []
    for cid, fin in financials.groupby("company_id"):
        q = fin.copy()
        q["period_start"] = pd.to_datetime(q["period_start"])
        q["period_end"] = pd.to_datetime(q["period_end"])
        q = q.sort_values("period_end").reset_index(drop=True)

        q["rev_yoy"] = _yoy(q["revenue"], q["period_end"])
        q["rev_accel"] = q["rev_yoy"] - q["rev_yoy"].shift(1)

        for s in signal_names:
            monthly = signals[(signals["company_id"] == cid) & (signals["signal"] == s)]
            q[f"{s}_level"] = _assign_months_to_quarters(q, monthly)
            q[f"{s}_yoy"] = _yoy(q[f"{s}_level"], q["period_end"])
            q[f"{s}_accel"] = q[f"{s}_yoy"] - q[f"{s}_yoy"].shift(1)

        # Next quarter's revenue, for the "does it lead?" test.
        q["rev_yoy_next"] = q["rev_yoy"].shift(-1)
        q["rev_accel_next"] = q["rev_accel"].shift(-1)
        rows.append(q)

    if not rows:
        return pd.DataFrame()
    panel = pd.concat(rows, ignore_index=True)
    panel["period_start"] = panel["period_start"].dt.strftime("%Y-%m-%d")
    panel["period_end"] = panel["period_end"].dt.strftime("%Y-%m-%d")
    return panel
