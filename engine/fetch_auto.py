"""
Extra signals collected automatically from free, public sources.

Each one is saved as a reading file in the same format as the readings you add
by hand (date,value,note), but under data/auto/ instead of data/readings/:

    data/auto/<signal>/<TICKER>.csv

The GitHub workflow saves these files back into the repository after every run,
so the history keeps growing even for sources that only show today's number.

    news_tone    GDELT Project: average tone of world news about the company,
                 one value per month (history from 2017)
    app_rating   Apple App Store: total number of ratings for the company's
                 main app (today's number; history builds up from now on)
    app_rank     Apple App Store: rank in the US top-200 free apps chart
                 (only recorded on days the app is in the top 200)
    patents      USPTO PatentsView: US patents granted per quarter. Needs a free
                 API key saved as the PATENTSVIEW_API_KEY repository secret.

A source that fails (rate limit, outage) never stops the website from updating:
the files from the previous run simply stay as they are.
"""
import csv
import json
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import requests

AUTO_DIR = Path(__file__).resolve().parent.parent / "data" / "auto"
UA = "Mozilla/5.0 (signal-engine research project; github.com/samairasharma-2010/signal-engine)"

# --- Who to look up -----------------------------------------------------------
# GDELT search terms. Quoted phrases, OR inside brackets. Chosen to avoid other
# meanings of the word (the Amazon rainforest, the fruit).
NEWS_QUERY = {
    "NKE": '"Nike"',
    "ADS": '"Adidas"',
    "NFLX": '"Netflix"',
    "AAPL": '("Apple Inc" OR "iPhone" OR "Tim Cook")',
    "MSFT": '"Microsoft"',
    "AMZN": '("Amazon.com" OR "Amazon Web Services" OR "Amazon Prime")',
    "TSLA": '"Tesla"',
    "MCD": '"McDonald\'s"',
    "SBUX": '"Starbucks"',
    "KO": '"Coca-Cola"',
}

# Main iPhone app of each company (the number in its App Store web address).
APP_ID = {
    "NKE": 1095459556,   # Nike: Shoes, Apparel & Stories
    "ADS": 1266591536,   # adidas: Shop Shoes & Clothing
    "NFLX": 363590051,   # Netflix
    "AMZN": 297606951,   # Amazon Shopping
    "TSLA": 582007913,   # Tesla
    "MCD": 922103212,    # McDonald's
    "SBUX": 331177714,   # Starbucks
}

# Company names exactly as they appear on US patents.
PATENT_OWNER = {
    "AAPL": ["Apple Inc."],
    "MSFT": ["Microsoft Technology Licensing, LLC", "Microsoft Corporation"],
    "TSLA": ["Tesla, Inc.", "Tesla Motors, Inc."],
    "NKE": ["Nike, Inc.", "NIKE, Inc."],
    "AMZN": ["Amazon Technologies, Inc."],
}


# --- Reading files --------------------------------------------------------------
def _path(signal: str, cid: str) -> Path:
    return AUTO_DIR / signal / f"{cid}.csv"


def _load(signal: str, cid: str) -> dict:
    """{date: (value, note)} from an existing file."""
    p = _path(signal, cid)
    if not p.exists():
        return {}
    out = {}
    for row in csv.DictReader(p.read_text(encoding="utf-8").splitlines()):
        try:
            out[row["date"]] = (float(row["value"]), row.get("note") or "")
        except (TypeError, ValueError, KeyError):
            pass
    return out


def _save(signal: str, cid: str, points: dict) -> None:
    p = _path(signal, cid)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "value", "note"])
        for d in sorted(points):
            v, n = points[d]
            w.writerow([d, round(v, 4) if isinstance(v, float) and not v.is_integer() else int(v), n])


def _record_today(signal: str, cid: str, value: float, note: str) -> None:
    """Keep one reading per month: today's number replaces any earlier
    reading from the same month."""
    today = date.today().isoformat()
    pts = {d: x for d, x in _load(signal, cid).items() if d[:7] != today[:7]}
    pts[today] = (float(value), note)
    _save(signal, cid, pts)


# --- News tone (GDELT) ----------------------------------------------------------
def news_tone(cid: str) -> int:
    """Monthly average tone of news coverage, from GDELT's free DOC 2.0 API.
    Tone runs from about -10 (very negative) to +10 (very positive)."""
    params = dict(
        query=f"{NEWS_QUERY[cid]} sourcelang:english",
        mode="timelinetone", format="json",
        startdatetime="20170101000000",
        enddatetime=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
    )
    for attempt in range(3):
        r = requests.get("https://api.gdeltproject.org/api/v2/doc/doc",
                         params=params, headers={"User-Agent": UA}, timeout=120)
        if r.status_code == 429 or "limit requests" in r.text[:200].lower():
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        break
    try:
        js = r.json()
    except ValueError:
        raise RuntimeError("GDELT replied: " + r.text[:150].strip())
    data = (js.get("timeline") or [{}])[0].get("data") or []
    if not data:
        raise RuntimeError("GDELT returned no articles")
    df = pd.DataFrame(data)
    df["month"] = pd.to_datetime(df["date"].str[:8]).dt.strftime("%Y-%m-01")
    monthly = df.groupby("month")["value"].mean()
    this_month = date.today().replace(day=1).isoformat()
    monthly = monthly[monthly.index < this_month]  # current month is incomplete

    pts = _load("news_tone", cid)
    for m, v in monthly.items():
        pts[m] = (float(v), "GDELT, monthly average tone")
    _save("news_tone", cid, pts)
    return len(monthly)


# --- App Store ------------------------------------------------------------------
def app_lookup() -> dict:
    """Today's App Store numbers for every app in APP_ID (one request)."""
    ids = ",".join(str(i) for i in APP_ID.values())
    r = requests.get("https://itunes.apple.com/lookup", params=dict(id=ids, country="us"),
                     headers={"User-Agent": UA}, timeout=60)
    r.raise_for_status()
    return {x["trackId"]: x for x in r.json().get("results", [])}


def app_chart() -> dict:
    """{app id: rank} for the US App Store top-200 free iPhone apps today."""
    r = requests.get("https://itunes.apple.com/us/rss/topfreeapplications/limit=200/json",
                     headers={"User-Agent": UA}, timeout=60)
    r.raise_for_status()
    entries = r.json().get("feed", {}).get("entry", [])
    if len(entries) < 50:
        raise RuntimeError(f"chart had only {len(entries)} apps")
    return {int(e["id"]["attributes"]["im:id"]): i + 1 for i, e in enumerate(entries)}


# --- Patents (PatentsView) ---------------------------------------------------------
def patents(cid: str, key: str, start: str) -> int:
    """US patents granted per quarter, counted from PatentsView's PatentSearch API."""
    q = {"_and": [{"_gte": {"patent_date": start}},
                  {"_or": [{"assignees.assignee_organization": n} for n in PATENT_OWNER[cid]]}]}
    dates, after = [], None
    while True:
        o = {"size": 1000}
        if after:
            o["after"] = after
        r = requests.get("https://search.patentsview.org/api/v1/patent/",
                         params=dict(q=json.dumps(q), f=json.dumps(["patent_id", "patent_date"]),
                                     s=json.dumps([{"patent_id": "asc"}]), o=json.dumps(o)),
                         headers={"X-Api-Key": key, "User-Agent": UA}, timeout=120)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", "30")))
            continue
        r.raise_for_status()
        rows = r.json().get("patents") or []
        dates += [p["patent_date"] for p in rows if p.get("patent_date")]
        if len(rows) < 1000:
            break
        after = rows[-1]["patent_id"]
        time.sleep(1.5)  # PatentsView allows 45 requests a minute
    if not dates:
        raise RuntimeError("no patents found - check the owner names in PATENT_OWNER")
    s = pd.to_datetime(pd.Series(dates))
    counts = s.dt.to_period("Q").value_counts().sort_index()
    counts = counts.iloc[:-1]  # the newest quarter is usually still incomplete
    pts = {str(p.start_time.date()): (float(n), "USPTO PatentsView, patents granted in the quarter")
           for p, n in counts.items()}
    _save("patents", cid, pts)
    return len(pts)


# --- Run everything ----------------------------------------------------------------
def collect(company_ids: list[str], start: str) -> list[str]:
    """Collect every automatic signal. Returns a list of problems (never raises)."""
    problems = []

    print("\n== News tone (GDELT)")
    for cid in company_ids:
        if cid not in NEWS_QUERY:
            continue
        try:
            n = news_tone(cid)
            print(f"  {cid}: {n} months")
        except Exception as e:
            problems.append(f"{cid} news_tone: {e}")
            print(f"  {cid} FAILED: {e}")
        time.sleep(6)  # GDELT asks for at most one request every 5 seconds

    print("\n== App Store")
    try:
        apps = app_lookup()
        for cid, app_id in APP_ID.items():
            a = apps.get(app_id)
            if not a or not a.get("userRatingCount"):
                problems.append(f"{cid} app_rating: app {app_id} not found")
                continue
            _record_today("app_rating", cid, a["userRatingCount"],
                          f"App Store (US), {a.get('trackName', '')}, {a.get('averageUserRating', 0):.1f}★")
            print(f"  {cid}: {a['userRatingCount']:,} ratings ({a.get('trackName')})")
    except Exception as e:
        problems.append(f"app_rating: {e}")
        print(f"  ratings FAILED: {e}")
    try:
        chart = app_chart()
        for cid, app_id in APP_ID.items():
            if app_id in chart:
                _record_today("app_rank", cid, chart[app_id], "US App Store, top free iPhone apps")
                print(f"  {cid}: #{chart[app_id]} in top free apps")
    except Exception as e:
        problems.append(f"app_rank: {e}")
        print(f"  chart FAILED: {e}")

    key = os.environ.get("PATENTSVIEW_API_KEY", "").strip()
    print("\n== Patents (PatentsView)")
    if not key:
        print("  skipped: add a PATENTSVIEW_API_KEY repository secret to collect patents")
    else:
        for cid in company_ids:
            if cid not in PATENT_OWNER:
                continue
            try:
                print(f"  {cid}: {patents(cid, key, start)} quarters")
            except Exception as e:
                problems.append(f"{cid} patents: {e}")
                print(f"  {cid} FAILED: {e}")
    return problems
