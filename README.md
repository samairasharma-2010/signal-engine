# Alternative Investment Signal Engine

Tests whether public attention data - Wikipedia page views and Google searches -
tells us anything about a company's revenue before the company reports it.
10 companies: Nike, Adidas, Netflix, Apple, Microsoft, Amazon, Tesla, McDonald's,
Starbucks, Coca-Cola.

## Setup (once)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run it

```bash
python pipeline.py demo      # 1. synthetic test data - checks the maths works
streamlit run app.py         #    open the website (shows a SYNTHETIC banner)

# 2. edit config.py: put your name + email in SEC_USER_AGENT
# 3. commit HYPOTHESES.md to GitHub BEFORE the next step
python pipeline.py fetch     # 4. real data -> data/live.db (takes a few minutes)
streamlit run app.py         #    the website now uses real data automatically
```

`fetch` prints a list of anything that failed; everything else is still saved.
Expect two things to need you:

- **Adidas revenue** - fill in `data/manual/revenue/ADS.csv` (see `data/manual/README.md`).
- **Google Trends** - the library is unofficial and Google often blocks it. If it
  fails, download the CSVs by hand from trends.google.com into
  `data/manual/search_interest/` and run `python pipeline.py analyze`.

## The website

Live at **https://samairasharma-2010.github.io/signal-engine/** (source: `site/index.html`).

The workflow in `.github/workflows/update-site.yml` rebuilds and republishes it:
every day at 07:07 India time, every time a file in this repository changes,
and whenever you press **Run workflow** on the Actions tab. The site shows when
its data was last updated and checks for new data every 30 minutes.

### Updating the site from GitHub (no coding)

Open a file, click the pencil icon, edit, then **Commit changes**. The site
updates about 3 minutes later.

| To do this | Edit this file |
| --- | --- |
| Record a signal reading (job openings, prices, app rank…) | `data/readings/<signal>/<TICKER>.csv`; see `data/readings/README.md` |
| Post a research note | `data/notes.md` |
| Add a company | `data/companies.csv` |
| Enter Adidas revenue | `data/manual/revenue/ADS.csv` |

### One-time settings

1. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
2. **Settings → Secrets and variables → Actions → New repository secret.**
   Name `SEC_USER_AGENT`, value `Your Name your@email.com`. Until this exists,
   the site shows test data.

## How it fits together

```
SEC EDGAR (revenue)  ─┐
Wikipedia (views)    ─┼─> pipeline.py ─> SQLite ─> build_panel ─> analysis ─> app.py
Google Trends        ─┤                             (quarters,      (scorecard)
data/manual/*.csv    ─┘                              YoY, accel)
```

| File | What it does |
| --- | --- |
| `config.py` | Companies, search terms, dates |
| `engine/fetch_sec.py` | Quarterly revenue from SEC filings, as first reported; derives Q4 |
| `engine/fetch_signals.py` | Wikipedia, Google Trends, and manual CSV loaders |
| `engine/build_panel.py` | Matches months to fiscal quarters; YoY growth and acceleration |
| `engine/analysis.py` | Permutation tests, hit rates, BH correction, out-of-sample R² |
| `engine/demo_data.py` | Synthetic data with one planted signal and one pure-noise signal |
| `app.py` | The Streamlit website |

## Validation result (synthetic data)

| Signal | Truth | Correlation | Adjusted p | Out-of-sample R² |
| --- | --- | --- | --- | --- |
| Planted signal | real link | 0.61 | 0.001 | 0.41 |
| Noise signal | no link | -0.15 | 0.24 | -0.01 |

The pipeline finds the planted link and rejects the noise. An ordinary
correlation test would have called the noise signal significant (p = 0.002),
which is why the permutation test is used.

## Next signals to add

News volume/tone (GDELT), store counts from 10-K filings, hiring from archived
careers pages. Each one is just a new `data/manual/<signal>/` folder or a new
fetcher returning `month,value`.
