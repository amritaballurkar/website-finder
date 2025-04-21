Brand Official Website Finder (Wikidata → Wikipedia → DuckDuckGo)

Given a list of brand names (one per line) this script tries to guess their official
website using only free, publicly available sources:

1. **Wikidata SPARQL**  (property P856 = official website)
2. **Wikipedia infobox** ("Website" field)
3. **DuckDuckGo Web Search** (first plausible organic result)

The script writes a CSV with: brand, website, source.
Use it responsibly: both Wikidata and DuckDuckGo rate‑limit automated traffic.

Usage:
    python brand_official_website_finder.py brands.txt output.csv
