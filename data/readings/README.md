# Signal readings you collect by hand

Each file holds one signal for one company:

```
data/readings/<signal>/<TICKER>.csv
```

for example `data/readings/hiring/NKE.csv` for Nike's job openings.

Each line is one reading: `date,value,note`

```
date,value,note
2026-09-01,1385,careers.nike.com
2026-10-01,1510,careers.nike.com
```

- **date**: `YYYY-MM-DD`, or `YYYY-MM` for a monthly figure.
- **value**: a plain number, no units or currency signs.
- **note**: optional; where the number came from. Visitors can see it.

To add a reading on GitHub, open the file, click the pencil icon, add a line at
the bottom and click **Commit changes**. To start a new file, use
**Add file → Create new file** and type the full path, such as
`data/readings/app_rank/SBUX.csv`. The website updates about 3 minutes later.

## Signal folder names

| Folder | Signal | Unit |
| --- | --- | --- |
| `hiring` | Job openings | open roles |
| `headcount` | Employee headcount | employees |
| `employee_sentiment` | Employee satisfaction | Glassdoor rating out of 5 |
| `customer_reviews` | Customer review score | rating out of 5 |
| `foot_traffic` | Store visits | visits index |
| `app_rank` | App popularity | chart rank, lower is better |
| `app_rating` | App reviews | total reviews |
| `web_traffic` | Website traffic | monthly visits |
| `social_following` | Social media following | followers |
| `news_tone` | News coverage and tone | tone from −10 to +10 |
| `pricing` | Product prices | price in USD |
| `expansion` | Stores and new markets | locations |
| `patents` | Patents granted | patents per quarter |

`wiki_views` and `search_interest` are collected automatically, so they need no files here.

## Company tickers

NKE (Nike), ADS (Adidas), NFLX (Netflix), AAPL (Apple), MSFT (Microsoft),
AMZN (Amazon), TSLA (Tesla), MCD (McDonald's), SBUX (Starbucks), KO (Coca-Cola),
plus any you add in `data/companies.csv`.
