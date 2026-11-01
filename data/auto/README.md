# Readings collected automatically

The "Update website" workflow fills this folder every day. Don't edit these
files by hand: your own readings go in `data/readings/`, and if both have a
reading for the same date, yours wins.

| Folder | Source | How often |
| --- | --- | --- |
| `news_tone` | GDELT Project, average tone of English-language news (from 2017) | monthly |
| `app_rating` | Apple App Store (US), total ratings of the main app | one reading a month, from Nov 2026 |
| `app_rank` | Apple App Store (US), position in the top-200 free apps | one reading a month, only when in the top 200 |
| `patents` | USPTO PatentsView, US patents granted | per quarter; needs the `PATENTSVIEW_API_KEY` secret |
