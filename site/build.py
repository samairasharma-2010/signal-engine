"""
Assembles the public website into _site/ (used by the GitHub workflow):
    _site/index.html       full HTML document, with search-engine tags
    _site/site_data.json   latest research data from the pipeline
    _site/robots.txt       tells search engines they may index the site
    _site/sitemap.xml      tells search engines which page to index
    _site/google*.html     Google Search Console verification file, if you add one to site/
"""
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"
URL = "https://samairasharma-2010.github.io/signal-engine/"
TITLE = "Alternative Investment Signal Engine"
DESC = ("Alternative Investment Signal Engine: a research project testing whether alternative "
        "data such as hiring, app usage, web traffic, Google searches, Wikipedia readership and "
        "pricing tells investors where company revenue is heading. Covers Nike, Adidas, Netflix, "
        "Apple, Microsoft, Amazon, Tesla, McDonald's, Starbucks and Coca-Cola.")

ld = {"@context": "https://schema.org", "@type": "WebSite", "name": TITLE, "url": URL,
      "description": DESC,
      "about": ["Alternative data", "Investment research", "Equity research", "Fintech"]}

HEAD = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="description" content="{DESC}">
<meta name="keywords" content="alternative data, alternative investment research, investment signals, equity research, fintech, hiring data, app data, web traffic, Google Trends, Wikipedia page views, revenue nowcasting">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{URL}">
<meta property="og:type" content="website">
<meta property="og:title" content="{TITLE}">
<meta property="og:description" content="{DESC}">
<meta property="og:url" content="{URL}">
<meta name="twitter:card" content="summary">
<script type="application/ld+json">{json.dumps(ld)}</script>
"""

# Plain text for search engines and for anyone with JavaScript switched off.
NOSCRIPT = f"""<noscript><div style="max-width:720px;margin:40px auto;padding:0 16px;font-family:sans-serif">
<h1>{TITLE}</h1><p>{DESC}</p>
<p>Signals tracked: job openings, employee headcount, employee satisfaction, Google search interest,
customer reviews, store visits, app popularity, app reviews, website traffic, Wikipedia readership,
social media following, news tone, product prices, stores and new markets, and patents.</p>
<p>Turn on JavaScript to use the interactive research terminal.</p></div></noscript>
"""

if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir()
page = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
(OUT / "index.html").write_text(HEAD + page + NOSCRIPT + "\n</html>\n", encoding="utf-8")
shutil.copy(ROOT / "data" / "site_data.json", OUT / "site_data.json")
(OUT / ".nojekyll").write_text("")
(OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {URL}sitemap.xml\n")
today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
(OUT / "sitemap.xml").write_text(
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    f"  <url><loc>{URL}</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq></url>\n"
    "</urlset>\n")
for f in (ROOT / "site").glob("google*.html"):   # Search Console verification
    shutil.copy(f, OUT / f.name)
print("Built", OUT, sorted(p.name for p in OUT.iterdir()))
