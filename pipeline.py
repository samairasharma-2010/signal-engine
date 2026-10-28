"""
Run the whole pipeline from the command line.

    python pipeline.py demo      # synthetic data -> data/demo.db (works offline)
    python pipeline.py fetch     # real data from the internet -> data/live.db
    python pipeline.py analyze   # rebuild panel + scorecard for live data
    python pipeline.py export    # write data/site_data.json for the website

`fetch` and `demo` run `analyze` and `export` automatically at the end.
On GitHub, the "Update website" workflow runs all of this for you.
"""
import json
import math
import sys
import time

import pandas as pd

import config
from engine import db
from engine.analysis import company_breakdown, scorecard
from engine.build_panel import build_panel
from engine.demo_data import generate
from engine.fetch_sec import fetch_companyfacts, quarterly_revenue
from engine.fetch_signals import (google_trends_monthly, manual_revenue,
                                  manual_signal, owner_notes, owner_readings,
                                  wikipedia_monthly)


def analyze(mode: str) -> None:
    fin = db.read_table(mode, "financials")
    sig = db.read_table(mode, "signals_monthly")
    if fin.empty:
        print("No financial data yet - run `python pipeline.py fetch` first.")
        return
    panel = build_panel(fin, sig)
    db.write_table(mode, "panel", panel)
    print(f"Panel: {len(panel)} company-quarters, {panel['company_id'].nunique()} companies")

    card = scorecard(panel)
    db.write_table(mode, "scorecard", card)
    db.write_table(mode, "company_breakdown", company_breakdown(panel))
    db.write_table(mode, "meta", pd.DataFrame([dict(
        mode=mode, built_at=pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"))]))

    if not card.empty:
        show = card[["signal", "measure", "horizon", "n", "corr_within",
                     "p_adjusted", "hit_rate", "oos_r2"]]
        print("\nScorecard (pooled across companies):")
        print(show.round(3).to_string(index=False))


def _num(v, nd=5):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else round(v, nd)


def export(mode: str) -> None:
    """Write the compact JSON file the website reads."""
    panel = db.read_table(mode, "panel")
    if panel.empty:
        print(f"No {mode} panel to export - run analyze first.")
        return
    card = db.read_table(mode, "scorecard")
    brk = db.read_table(mode, "company_breakdown")
    meta = db.read_table(mode, "meta")
    signals = sorted(c[:-6] for c in panel.columns if c.endswith("_level"))

    quarters = {}
    for cid, g in panel.sort_values("period_end").groupby("company_id"):
        quarters[cid] = [dict(
            end=r["period_end"], rev=_num(r["revenue"], 0),
            rev_yoy=_num(r["rev_yoy"]), rev_accel=_num(r["rev_accel"]),
            sig={s: dict(yoy=_num(r[f"{s}_yoy"]), accel=_num(r[f"{s}_accel"]))
                 for s in signals},
        ) for _, r in g.iterrows()]

    out = dict(
        format="signal-engine/1",
        mode=mode,
        built_at=meta["built_at"].iloc[0] if not meta.empty else None,
        out_of_sample_start=config.OUT_OF_SAMPLE_START,
        companies=[{**{k: c[k] for k in ("id", "name", "sector", "customer", "currency")},
                    "hasFin": c["id"] in quarters}
                   for c in config.COMPANIES if c.get("base") or mode == "live"],
        signals={s: config.SIGNAL_LABELS.get(s, s) for s in signals},
        series=owner_readings(),
        notes=owner_notes(),
        quarters=quarters,
        scorecard=[{k: (_num(v) if isinstance(v, float) else v) for k, v in row.items()}
                   for row in card.to_dict("records")],
        breakdown=[{k: (_num(v) if isinstance(v, float) else v) for k, v in row.items()}
                   for row in brk.to_dict("records")],
    )
    path = db.DATA_DIR / "site_data.json"
    path.write_text(json.dumps(out, separators=(",", ":")))
    print(f"\nWrote {path} ({path.stat().st_size // 1024} KB, {mode} data, "
          f"{len(out['series'])} owner reading files, {len(out['notes'])} notes).")


def run_demo() -> None:
    fin, sig = generate()
    db.write_table("demo", "financials", fin)
    db.write_table("demo", "signals_monthly", sig)
    print("Wrote SYNTHETIC demo data (not real numbers).")
    analyze("demo")
    export("demo")


def fetch() -> None:
    if "example.com" in config.SEC_USER_AGENT:
        sys.exit("Set SEC_USER_AGENT in config.py to your name and email first.")
    ua = config.SEC_USER_AGENT
    problems = []

    for c in config.COMPANIES:
        cid = c["id"]
        print(f"\n== {c['name']} ({cid})")

        # --- Revenue ---
        try:
            if c["revenue"] == "none":
                raise RuntimeError("no SEC number (cik) in data/companies.csv, so no revenue")
            if c["revenue"] == "sec":
                rev = quarterly_revenue(fetch_companyfacts(c["cik"], ua))
            else:
                rev = manual_revenue(cid)
                if rev is None:
                    raise RuntimeError(f"fill in data/manual/revenue/{cid}.csv")
            rev.insert(0, "company_id", cid)
            db.upsert("live", "financials", rev, ["company_id", "period_end"])
            print(f"  revenue: {len(rev)} quarters "
                  f"({rev['period_end'].min()} to {rev['period_end'].max()})")
        except Exception as e:
            problems.append(f"{cid} revenue: {e}")
            print(f"  revenue FAILED: {e}")

        # --- Signals: a manual CSV always wins over the automatic fetch ---
        for signal, auto in [
            ("wiki_views", lambda: wikipedia_monthly(c["wiki"], config.START_DATE, ua)),
            ("search_interest", lambda: google_trends_monthly(c["trends"], config.START_DATE)),
        ]:
            try:
                df = manual_signal(signal, cid)
                source = "manual CSV"
                if df is None and not c.get("wiki" if signal == "wiki_views" else "trends"):
                    continue
                if df is None:
                    df = auto()
                    source = "API"
                df = df.assign(company_id=cid, signal=signal)
                db.upsert("live", "signals_monthly", df, ["company_id", "signal", "month"])
                print(f"  {signal}: {len(df)} months from {source}")
                if signal == "search_interest" and source == "API":
                    time.sleep(5)  # be gentle - Google Trends rate-limits hard
            except Exception as e:
                problems.append(f"{cid} {signal}: {e}")
                print(f"  {signal} FAILED: {e}")

    analyze("live")
    export("live")
    if problems:
        print("\nThings to fix (the rest of the data was saved):")
        for p in problems:
            print("  -", p)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "demo":
        run_demo()
    elif cmd == "fetch":
        fetch()
    elif cmd == "analyze":
        analyze("live")
        export("live")
    elif cmd == "export":
        export(sys.argv[2] if len(sys.argv) > 2 else "live")
    else:
        print(__doc__)
