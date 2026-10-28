"""
Assembles the public website into _site/ (used by the GitHub workflow):
    _site/index.html       full HTML document
    _site/site_data.json   latest research data from the pipeline
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"

HEAD = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<meta name="description" content="Alternative Investment Signal Engine: testing whether '
        'public alternative data (hiring, app usage, web traffic, search interest, pricing) '
        'tells investors where company revenue is heading.">\n')

OUT.mkdir(exist_ok=True)
page = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
(OUT / "index.html").write_text(HEAD + page + "\n</html>\n", encoding="utf-8")
shutil.copy(ROOT / "data" / "site_data.json", OUT / "site_data.json")
(OUT / ".nojekyll").write_text("")
print("Built", OUT, [p.name for p in OUT.iterdir()])
