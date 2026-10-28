# Manual data

Anything you collect by hand goes here, and the pipeline picks it up automatically.

## New or replacement signals

`data/manual/<signal_name>/<COMPANY_ID>.csv` with two columns:

```
month,value
2015-07-01,123
2015-08-01,131
```

- A file here **overrides** the automatic fetch for that company and signal.
- Use it when Google Trends blocks the automatic download: on trends.google.com
  set the time range to "2015 - present", download the CSV, and save it as
  `search_interest/NKE.csv` (raw Trends downloads are recognised as they are).
- For a brand-new signal (e.g. `hiring`), create a new folder, add a label for it
  in `SIGNAL_LABELS` in `config.py`, and add it to the signal list in
  `pipeline.py`.

Company IDs: NKE, ADS, NFLX, AAPL, MSFT, AMZN, TSLA, MCD, SBUX, KO

## Revenue for non-SEC companies

`revenue/ADS.csv` - Adidas reports in Germany, so its numbers are not in the
SEC database. Columns: `period_start,period_end,revenue,filed`.
