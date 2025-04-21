import csv
import os
import sys
import time
import re
import html
import urllib.parse
from typing import Optional, Tuple
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS 

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
DDG_HTML_SEARCH = "https://duckduckgo.com/lite" 

EXCLUDE_DOMAINS = {
    "wikipedia.org", "facebook.com", "instagram.com", "youtube.com", "twitter.com",
    "linkedin.com", "amazon.com", "etsy.com", "pinterest.com", "reddit.com", "sephora.com", "ulta.com", "walmart.com"
}

def fetch_wikidata_site(name: str) -> Optional[str]:
    """Return official website from Wikidata or None"""
    print(f"\n[DEBUG] Searching Wikidata for brand: {name}")
    query = f"""SELECT ?website WHERE {{
      ?entity rdfs:label "{name}"@en .
      ?entity wdt:P856 ?website .
    }} LIMIT 1"""
    try:
        print("[DEBUG] Making Wikidata API request...")
        r = requests.get(
            WIKIDATA_ENDPOINT,
            params={"query": query, "format": "json"},
            headers=HEADERS,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        bindings = data.get("results", {}).get("bindings", [])
        if bindings:
            website = bindings[0]["website"]["value"]
            print(f"[DEBUG] Found Wikidata website: {website}")
            return website
        print("[DEBUG] No website found in Wikidata")
    except Exception as e:
        print(f"[DEBUG] Wikidata API error: {str(e)}")
    return None

def fetch_wikipedia_site(name: str) -> Optional[str]:
    """Search Wikipedia and attempt to parse Website field"""
    print(f"\n[DEBUG] Searching Wikipedia for brand: {name}")
    try:
        print("[DEBUG] Making Wikipedia search API request...")
        search = requests.get(
            WIKIPEDIA_API,
            params={
                "action": "query",
                "list": "search",
                "srsearch": name,
                "format": "json",
                "srlimit": 1,
                "srprop": "",
            },
            headers=HEADERS,
            timeout=20,
        )
        search.raise_for_status()
        sdata = search.json()
        if not sdata["query"]["search"]:
            print("[DEBUG] No Wikipedia page found")
            return None
        pageid = sdata["query"]["search"][0]["pageid"]
        print(f"[DEBUG] Found Wikipedia page ID: {pageid}")
        
        print("[DEBUG] Making Wikipedia parse API request...")
        parse = requests.get(
            WIKIPEDIA_API,
            params={"action": "parse", "pageid": pageid, "prop": "text", "format": "json"},
            headers=HEADERS,
            timeout=20,
        )
        parse.raise_for_status()
        html_text = parse.json()["parse"]["text"]["*"]
        soup = BeautifulSoup(html_text, "html.parser")
        infobox = soup.find("table", class_="infobox")
        if not infobox:
            print("[DEBUG] No infobox found in Wikipedia page")
            return None
        print("[DEBUG] Searching for website in infobox...")
        for row in infobox.find_all("tr"):
            header = row.find("th")
            if not header:
                continue
            if "website" in header.get_text(strip=True).lower():
                link = row.find("a", href=True)
                if link and link["href"].startswith("http") and _looks_official(link["href"], name):
                    print(f"[DEBUG] Found Wikipedia website: {link['href']}")
                    return link["href"]
        print("[DEBUG] No website found in Wikipedia infobox")
    except Exception as e:
        print(f"[DEBUG] Wikipedia API error: {str(e)}")
    return None

def _looks_official(url: str, brand: str) -> bool:
    """Heuristic to guess if url is the brand's own domain"""
    brand_slug = re.sub(r"[^a-z0-9]+", "", brand.lower())
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    # return false if domain is sus.
    if domain.endswith(".ru"):
        return False
    
    domain_nw = domain[4:] if domain.startswith("www.") else domain
    if any(domain_nw.endswith(bad) for bad in EXCLUDE_DOMAINS):
        return False
    # must contain brand slug
    return brand_slug[:6] in domain_nw  

def fetch_duckduckgo_site(name: str) -> str :
    query = f"{name} official US website"
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=10, region="wt-wt", safesearch="Off"):
            url = r["href"]
            if _looks_official(url, name):
                return url
    return None

def get_website(brand: str) -> Tuple[Optional[str], str]:
    """Try all sources and return (website, source)"""
    site = fetch_wikidata_site(brand)
    if site:
        return site, "wikidata"
    site = fetch_wikipedia_site(brand)
    if site:
        return site, "wikipedia"
    site = fetch_duckduckgo_site(brand)
    if site:
        return site, "duckduckgo"
    return None, "not_found"

def send_csv_to_discord(webhook_url, file_path, message="CSV done processing: "):
    with open(file_path, 'rb') as f:
        files = {
            'file': (file_path, f),
        }
        data = {
            'content': message,
        }
        response = requests.post(webhook_url, data=data, files=files)

    if response.status_code == 204:
        print("CSV sent to Discord successfully.")
    else:
        print(f"Failed to send CSV: {response.status_code} - {response.text}")

def main():
    if len(sys.argv) != 3:
        print("Usage: python website_finder.py <brands.txt> <output.csv>")
        sys.exit(1)

    input_file, output_file = sys.argv[1], sys.argv[2]
    with open(input_file, encoding="utf-8") as f:
        brands = [line.strip() for line in f if line.strip()]
    brands = list(set(brands))
    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["brand", "website", "source"])
        for idx, brand in enumerate(brands, 1):
            website, source = get_website(brand)
            writer.writerow([brand, website or "", source])
            print(f"[{idx}/{len(brands)}] {brand}: {website or 'N/A'} ({source})")
            # be kind to public services
            time.sleep(3)
    send_csv_to_discord(
        webhook_url=f"https://discord.com/api/webhooks/{os.getenv("DISCORD_WEBHOOK_ID")}/{os.getenv("DISCORD_WEBHOOK_TOKEN")}",
        file_path=output_file
    )

if __name__ == "__main__":
    main()
