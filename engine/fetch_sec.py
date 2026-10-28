"""
Quarterly revenue from the SEC's free XBRL "company facts" API.

Three details matter for honest research:

1. Companies use different XBRL tags for revenue, and some switched tags in
   2018 (new accounting standard ASC 606). We read several tags and, for each
   period, take the largest value - total revenue is always at least as big as
   any sub-component.

2. Companies sometimes revise old numbers. We keep the value from the EARLIEST
   filing, i.e. "as first reported" - what an investor actually knew then.

3. Annual reports (10-K) usually don't state the 4th quarter on its own.
   We derive it: Q4 = full year - (Q1 + Q2 + Q3).
"""
import time

import pandas as pd
import requests

REVENUE_TAGS = [
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
    "SalesRevenueGoodsNet",
]


def fetch_companyfacts(cik: int, user_agent: str) -> dict:
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
    r = requests.get(url, headers={"User-Agent": user_agent}, timeout=60)
    r.raise_for_status()
    time.sleep(0.2)  # SEC allows max 10 requests/second; stay well below
    return r.json()


def _raw_facts(js: dict) -> pd.DataFrame:
    rows = []
    gaap = js.get("facts", {}).get("us-gaap", {})
    for tag in REVENUE_TAGS:
        for item in gaap.get(tag, {}).get("units", {}).get("USD", []):
            if "start" not in item:
                continue
            rows.append(dict(tag=tag, start=item["start"], end=item["end"],
                             val=float(item["val"]), filed=item["filed"]))
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for col in ("start", "end", "filed"):
        df[col] = pd.to_datetime(df[col])
    df["days"] = (df["end"] - df["start"]).dt.days
    return df


def _first_reported(df: pd.DataFrame) -> pd.DataFrame:
    """One value per (start, end): earliest filing per tag, then the largest tag."""
    df = df.sort_values("filed").drop_duplicates(["tag", "start", "end"], keep="first")
    df = df.sort_values("val").drop_duplicates(["start", "end"], keep="last")
    return df


def quarterly_revenue(js: dict) -> pd.DataFrame:
    """Return columns: period_start, period_end, revenue, filed, derived."""
    df = _raw_facts(js)
    if df.empty:
        return pd.DataFrame(columns=["period_start", "period_end", "revenue", "filed", "derived"])
    df = _first_reported(df)

    quarters = df[df["days"].between(80, 100)].copy()
    annual = df[df["days"].between(350, 380)]

    # Derive the missing 4th quarter from each annual figure.
    derived = []
    for _, yr in annual.iterrows():
        inside = quarters[(quarters["start"] >= yr["start"]) & (quarters["end"] <= yr["end"])]
        inside = inside.sort_values("end")
        if len(inside) != 3:
            continue
        q4_start = inside["end"].iloc[-1] + pd.Timedelta(days=1)
        if (yr["end"] - q4_start).days < 75:
            continue  # the three quarters don't leave a full quarter at the end
        if ((quarters["start"] == q4_start) & (quarters["end"] == yr["end"])).any():
            continue  # already reported directly
        derived.append(dict(start=q4_start, end=yr["end"],
                            val=yr["val"] - inside["val"].sum(),
                            filed=yr["filed"], derived=True))

    quarters["derived"] = False
    out = pd.concat([quarters[["start", "end", "val", "filed", "derived"]],
                     pd.DataFrame(derived)], ignore_index=True)

    # If two quarters share an end date (rare odd filings), keep the one
    # closest to a normal 91-day quarter.
    out["dist"] = ((out["end"] - out["start"]).dt.days - 91).abs()
    out = out.sort_values("dist").drop_duplicates("end", keep="first")
    out = out.sort_values("end").reset_index(drop=True)

    return pd.DataFrame({
        "period_start": out["start"].dt.strftime("%Y-%m-%d"),
        "period_end": out["end"].dt.strftime("%Y-%m-%d"),
        "revenue": out["val"],
        "filed": pd.to_datetime(out["filed"]).dt.strftime("%Y-%m-%d"),
        "derived": out["derived"].astype(bool),
    })
