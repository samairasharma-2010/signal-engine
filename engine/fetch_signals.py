"""
Alternative-data signals. Every fetcher returns the same shape:

    month (YYYY-MM-01), value

so that any new signal plugs into the same analysis.
"""
from datetime import date
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests

MANUAL_DIR = Path(__file__).resolve().parent.parent / "data" / "manual"


# --- Wikipedia page views (official Wikimedia API, free, from July 2015) ------
def wikipedia_monthly(article: str, start: str, user_agent: str) -> pd.DataFrame:
    s = pd.Timestamp(start).strftime("%Y%m01")
    e = date.today().replace(day=1).strftime("%Y%m01")
    url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
           f"en.wikipedia.org/all-access/user/{quote(article, safe='')}/monthly/{s}00/{e}00")
    r = requests.get(url, headers={"User-Agent": user_agent}, timeout=60)
    r.raise_for_status()
    items = r.json().get("items", [])
    df = pd.DataFrame({
        "month": [pd.to_datetime(i["timestamp"][:8]).strftime("%Y-%m-01") for i in items],
        "value": [float(i["views"]) for i in items],
    })
    # The current month is incomplete - drop it.
    this_month = date.today().replace(day=1).strftime("%Y-%m-01")
    return df[df["month"] < this_month]


# --- Google Trends (unofficial pytrends library; may be rate-limited) ---------
def google_trends_monthly(keyword: str, start: str) -> pd.DataFrame:
    """A window longer than 5 years makes Google return monthly values.
    Values are 0-100, scaled per search term - so only compare a company with
    its own past, never Nike's 80 with Apple's 80."""
    from pytrends.request import TrendReq  # imported here: optional dependency

    # No retries/backoff arguments: in pytrends 4.9 they crash with urllib3 2.x.
    py = TrendReq(hl="en-US", tz=0)
    py.build_payload([keyword], timeframe=f"{start} {date.today():%Y-%m-%d}", geo="")
    raw = py.interest_over_time()
    if raw.empty:
        return pd.DataFrame(columns=["month", "value"])
    raw = raw[raw.get("isPartial", False) != True]  # noqa: E712
    return pd.DataFrame({"month": raw.index.strftime("%Y-%m-01"),
                         "value": raw[keyword].astype(float).values})


# --- Manual CSVs: any signal you collect by hand --------------------------------
def manual_signal(signal: str, company_id: str) -> pd.DataFrame | None:
    """Reads data/manual/<signal>/<company_id>.csv with columns month,value.
    Also accepts a raw Google Trends download (two header lines, then
    'Month,<term>: (Worldwide)')."""
    path = MANUAL_DIR / signal / f"{company_id}.csv"
    if not path.exists():
        return None
    first = path.read_text(encoding="utf-8-sig").splitlines()[0].lower()
    skip = 0 if first.startswith("month,value") else 2
    df = pd.read_csv(path, skiprows=skip, encoding="utf-8-sig")
    df.columns = ["month", "value"] + list(df.columns[2:])
    df["value"] = pd.to_numeric(df["value"].astype(str).str.replace("<1", "0.5"), errors="coerce")
    df["month"] = pd.to_datetime(df["month"]).dt.strftime("%Y-%m-01")
    return df[["month", "value"]].dropna()


READINGS_DIR = Path(__file__).resolve().parent.parent / "data" / "readings"
NOTES_FILE = Path(__file__).resolve().parent.parent / "data" / "notes.md"


AUTO_DIR = Path(__file__).resolve().parent.parent / "data" / "auto"


def owner_readings(folder: Path = READINGS_DIR, auto: bool = False) -> dict:
    """Readings the owner records by hand, one CSV per company and signal:
    data/readings/<signal_id>/<TICKER>.csv with columns date,value,note.
    Returns {"TICKER__signal": {"company", "signal", "points": [...]}}.
    Files whose name starts with '_' are templates and are skipped.
    With folder=AUTO_DIR, reads the automatically collected readings instead."""
    import csv
    out = {}
    if not folder.exists():
        return out
    for f in sorted(folder.glob("*/*.csv")):
        if f.name.startswith("_"):
            continue
        sig, cid = f.parent.name, f.stem.upper()
        pts = {}
        lines = [l for l in f.read_text(encoding="utf-8-sig").splitlines()
                 if l.strip() and not l.lstrip().startswith("#")]
        for row in csv.reader(lines):
            if len(row) < 2 or row[0].strip().lower() == "date":
                continue
            d, v = row[0].strip(), row[1].strip().replace(",", "")
            if len(d) == 7:
                d += "-01"
            try:
                d = pd.Timestamp(d).strftime("%Y-%m-%d")
                v = float(v)
            except (ValueError, TypeError):
                print(f"  skipped unreadable line in {f.relative_to(folder)}: {','.join(row)}")
                continue
            pts[d] = dict(d=d, v=v, n=",".join(row[2:]).strip())
        if pts:
            out[f"{cid}__{sig}"] = dict(company=cid, signal=sig, auto=auto,
                                        points=[pts[k] for k in sorted(pts)])
    return out


def owner_notes() -> list:
    """Research notes from data/notes.md. Each note starts with a line
    '## YYYY-MM-DD | Title' followed by its text."""
    import re
    if not NOTES_FILE.exists():
        return []
    notes, cur = [], None
    for line in NOTES_FILE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^##\s+(\d{4}-\d{2}-\d{2})\s*\|\s*(.+?)\s*$", line)
        if m:
            cur = dict(createdAt=m.group(1), title=m.group(2), body=[])
            notes.append(cur)
        elif cur is not None:
            cur["body"].append(line)
    for n in notes:
        n["body"] = "\n".join(n["body"]).strip()
    return notes


def manual_revenue(company_id: str) -> pd.DataFrame | None:
    """Reads data/manual/revenue/<company_id>.csv with columns
    period_start,period_end,revenue,filed (filed = date results were published)."""
    path = MANUAL_DIR / "revenue" / f"{company_id}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, comment="#")
    if df.empty:
        return None
    for col in ("period_start", "period_end", "filed"):
        df[col] = pd.to_datetime(df[col]).dt.strftime("%Y-%m-%d")
    df["derived"] = False
    return df[["period_start", "period_end", "revenue", "filed", "derived"]]
