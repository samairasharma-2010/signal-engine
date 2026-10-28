"""
Settings for the Alternative Investment Signal Engine.

Edit SEC_USER_AGENT before fetching real data: the SEC asks every
automated request to identify who is making it (name + email).
"""

# --- Who you are (required by the SEC and Wikimedia APIs) -------------------
import os

# On GitHub, this comes from the repository secret SEC_USER_AGENT.
SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT") or "Your Name your.email@example.com"   # <-- change this

# --- Time window --------------------------------------------------------------
# Wikipedia page-view data starts in July 2015, so that is our common start.
START_DATE = "2015-07-01"

# Quarters ending before this date are the "training" period; quarters after it
# are only used to test whether a relationship holds on unseen data.
OUT_OF_SAMPLE_START = "2022-01-01"

# --- The 10 companies ---------------------------------------------------------
# id          short id used everywhere in the code and database
# cik         SEC company number (None = not filed with the SEC)
# wiki        English Wikipedia article title
# trends      Google Trends search term (chosen to avoid ambiguous words)
# revenue     where revenue comes from: "sec" or "manual" (a CSV you fill in)
COMPANIES = [
    dict(id="NKE",  name="Nike",       sector="Consumer apparel", customer="Consumer",
         cik=320187,  wiki="Nike,_Inc.",            trends="Nike",       revenue="sec",    currency="USD"),
    dict(id="ADS",  name="Adidas",     sector="Consumer apparel", customer="Consumer",
         cik=None,    wiki="Adidas",                trends="Adidas",     revenue="manual", currency="EUR"),
    dict(id="NFLX", name="Netflix",    sector="Entertainment",    customer="Consumer",
         cik=1065280, wiki="Netflix",               trends="Netflix",    revenue="sec",    currency="USD"),
    dict(id="AAPL", name="Apple",      sector="Technology",       customer="Consumer",
         cik=320193,  wiki="Apple_Inc.",            trends="iPhone",     revenue="sec",    currency="USD"),
    dict(id="MSFT", name="Microsoft",  sector="Technology",       customer="Business",
         cik=789019,  wiki="Microsoft",             trends="Microsoft",  revenue="sec",    currency="USD"),
    dict(id="AMZN", name="Amazon",     sector="E-commerce / cloud", customer="Mixed",
         cik=1018724, wiki="Amazon_(company)",      trends="Amazon",     revenue="sec",    currency="USD"),
    dict(id="TSLA", name="Tesla",      sector="Automotive",       customer="Consumer",
         cik=1318605, wiki="Tesla,_Inc.",           trends="Tesla",      revenue="sec",    currency="USD"),
    dict(id="MCD",  name="McDonald's", sector="Restaurants",      customer="Consumer",
         cik=63908,   wiki="McDonald's",            trends="McDonald's", revenue="sec",    currency="USD"),
    dict(id="SBUX", name="Starbucks",  sector="Restaurants",      customer="Consumer",
         cik=829224,  wiki="Starbucks",             trends="Starbucks",  revenue="sec",    currency="USD"),
    dict(id="KO",   name="Coca-Cola",  sector="Beverages",        customer="Consumer",
         cik=21344,   wiki="The_Coca-Cola_Company", trends="Coca-Cola",  revenue="sec",    currency="USD"),
]

for _c in COMPANIES:
    _c["base"] = True


def _extra_companies():
    """Companies added by the owner in data/companies.csv (editable on GitHub).
    Columns: id,name,sector,customer,cik,wiki,trends  (only id and name required).
    With a cik, revenue is fetched from the SEC automatically."""
    import csv
    from pathlib import Path
    path = Path(__file__).resolve().parent / "data" / "companies.csv"
    if not path.exists():
        return []
    lines = [l for l in path.read_text(encoding="utf-8-sig").splitlines()
             if l.strip() and not l.lstrip().startswith("#")]
    out = []
    for row in csv.DictReader(lines):
        row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
        cid, name = row.get("id", "").upper(), row.get("name", "")
        if not cid or not name or any(c["id"] == cid for c in COMPANIES + out):
            continue
        cik = row.get("cik", "")
        out.append(dict(id=cid, name=name, sector=row.get("sector") or "Other",
                        customer=row.get("customer") or "Consumer",
                        cik=int(cik) if cik.isdigit() else None,
                        wiki=row.get("wiki") or None, trends=row.get("trends") or None,
                        revenue="sec" if cik.isdigit() else "none",
                        currency="USD", base=False))
    return out


COMPANIES = COMPANIES + _extra_companies()
COMPANY_BY_ID = {c["id"]: c for c in COMPANIES}

# Human-readable names for each signal (add new ones here when you add data).
SIGNAL_LABELS = {
    "wiki_views": "Wikipedia page views",
    "search_interest": "Google search interest",
}
