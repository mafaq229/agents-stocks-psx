import asyncio
import json
import os
import argparse
from datetime import datetime
from agents.scraper_agent import PSXScraper

def save_data(data, symbol):
    """Saves the scraped data to a JSON file."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    directory = f"data/processed/{symbol}"
    os.makedirs(directory, exist_ok=True)
    
    filename = f"{directory}/{date_str}_data.json"
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Data saved to {filename}")

async def main():
    parser = argparse.ArgumentParser(description="Stock Analysis Framework Agent")
    parser.add_argument("symbol", help="Stock Symbol (e.g., LSECL)")
    parser.add_argument("--headless", action="store_true", default=True, help="Run browser in headless mode")
    
    args = parser.parse_args()
    
    print(f"Starting analysis for {args.symbol}...")
    
    # Initialize Agents
    scraper = PSXScraper(headless=args.headless)
    
    # 1. Scrape Data
    print("Step 1: Scraping PSX Data...")
    scraped_data = await scraper.scrape_company(args.symbol)
    
    if "error" in scraped_data:
        print(f"Error scraping data: {scraped_data['error']}")
        return

    # Save raw data
    save_data(scraped_data, args.symbol)
    
    # Output Summary
    quote = scraped_data.get("quote", {})
    profile = scraped_data.get("profile", {})
    equity = scraped_data.get("equity", {})
    
    print("\n" + "="*40)
    print(f" REPORT: {args.symbol}")
    print("="*40)
    
    print(f"\n[Profile]")
    print(f"Description: {profile.get('description', 'N/A')[:100]}...")
    
    print(f"\n[Market Data]")
    print(f"Price:  {quote.get('price')}")
    print(f"Change: {quote.get('change')}")
    print(f"Volume: {quote.get('volume')}")
    print(f"Market Cap: {equity.get('Market Cap', 'N/A')}")
    print(f"Shares: {equity.get('Shares', 'N/A')}")

    print(f"\n[Financials]")
    fin = scraped_data.get("financials", {})
    annual = fin.get("annual", [])
    if annual:
        print(f"Latest Annual (Top Row): {json.dumps(annual[0], indent=2)}")
    else:
        print("No annual financials found.")

    print(f"\n[Ratios]")
    ratios = scraped_data.get("ratios", [])
    if ratios:
        print(f"Latest Ratios (Top Row): {json.dumps(ratios[0], indent=2)}")

    print(f"\n[Announcements]")
    ann = scraped_data.get("announcements", {})
    for category, items in ann.items():
        print(f"  > {category.title()} ({len(items)} items)")
        if items:
            print(f"    Latest: {items[0]['date']} - {items[0]['title']}")

    print(f"\n[Financial Reports]")
    reps = scraped_data.get("financial_reports", [])
    print(f"Found {len(reps)} reports.")
    if reps:
        print(f"Latest: {reps[0]['date']} - {reps[0]['title']} -> {reps[0]['url']}")

    print("\n" + "="*40)

if __name__ == "__main__":
    asyncio.run(main())
