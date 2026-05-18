# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx", "python-dotenv"]
# ///
"""Pull KSAOs and RIASEC from O*NET Web Services API (v2)."""

import os
import sys

import httpx
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

BASE = "https://api-v2.onetcenter.org"
API_KEY = os.environ["ONET_API_KEY"]
HEADERS = {"Accept": "application/json", "X-API-Key": API_KEY}

KSAO_ENDPOINTS = ["knowledge", "skills", "abilities", "work_styles"]


def search_occupation(client: httpx.Client, keyword: str) -> list[dict]:
    """Search O*NET for an occupation keyword, return top results."""
    r = client.get(f"{BASE}/online/search", params={"keyword": keyword, "end": 5})
    r.raise_for_status()
    return r.json().get("occupation", [])


def get_ksao(client: httpx.Client, soc: str) -> dict:
    """Fetch all KSAO categories for a SOC code."""
    result = {}
    for endpoint in KSAO_ENDPOINTS:
        r = client.get(f"{BASE}/online/occupations/{soc}/details/{endpoint}")
        r.raise_for_status()
        items = r.json().get("element", [])
        result[endpoint] = [
            {"name": el["name"], "importance": el.get("importance", 0)} for el in items
        ]
        result[endpoint].sort(key=lambda x: x["importance"], reverse=True)
    return result


def get_riasec(client: httpx.Client, soc: str) -> list[dict]:
    """Fetch RIASEC/Holland interest codes for a SOC code."""
    r = client.get(f"{BASE}/online/occupations/{soc}/details/interests")
    r.raise_for_status()
    items = r.json().get("element", [])
    return sorted(
        [{"name": el["name"], "score": el.get("occupational_interest", 0)} for el in items],
        key=lambda x: x["score"],
        reverse=True,
    )


def main():
    keywords = sys.argv[1:] if len(sys.argv) > 1 else ["teacher", "marine biologist"]

    with httpx.Client(headers=HEADERS, timeout=30) as client:
        for kw in keywords:
            print(f"\n{'=' * 60}")
            print(f"  SEARCH: {kw}")
            print(f"{'=' * 60}")

            results = search_occupation(client, kw)
            if not results:
                print(f"  No results for '{kw}'")
                continue

            for i, occ in enumerate(results):
                print(f"  [{i}] {occ['code']} — {occ['title']}")

            soc = results[0]["code"]
            title = results[0]["title"]
            print(f"\n  Using: {soc} — {title}\n")

            # RIASEC
            riasec = get_riasec(client, soc)
            print("  RIASEC (Holland Codes):")
            for item in riasec:
                bar = "#" * int(item["score"] / 2)
                print(f"    {item['name']:20s}  {item['score']:3d}  {bar}")

            # KSAOs
            ksao = get_ksao(client, soc)
            for category, items in ksao.items():
                print(f"\n  {category.upper().replace('_', ' ')} (top 10):")
                for item in items[:10]:
                    bar = "#" * int(item["importance"] / 2)
                    print(f"    {item['name']:35s}  {item['importance']:3d}  {bar}")

            print()


if __name__ == "__main__":
    main()
