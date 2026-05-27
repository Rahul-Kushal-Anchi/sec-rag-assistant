"""Download SEC filings for the RAG project corpus.

Pulls 10-K and 10-Q filings from EDGAR for 25 well-known public companies
across multiple sectors. Output goes to ./data/filings/sec-edgar-filings/.

Run once: `python download_filings.py`
Takes 15-25 minutes depending on network.
"""

from sec_edgar_downloader import Downloader

# EDGAR requires user-agent identification
dl = Downloader(
    company_name="AnchiLabs",
    email_address="rahul@anchilabs.com",
    download_folder="./data/filings",
)

# Mix of sectors for diverse retrieval testing
TICKERS = [
    # Tech
    "AAPL", "MSFT", "GOOGL", "NVDA", "META", "AMZN", "TSLA",
    # Banking / finance (relevant to Citi)
    "JPM", "GS", "MS", "C", "BAC", "WFC",
    # Healthcare
    "JNJ", "PFE", "UNH",
    # Energy / industrials
    "XOM", "CVX",
    # Consumer
    "WMT", "KO", "PG",
    # Media / aerospace
    "DIS", "BA", "GE", "F",
]

for ticker in TICKERS:
    print(f"Downloading {ticker}...")
    try:
        # Most recent 2 10-Ks and 3 10-Qs per company
        dl.get("10-K", ticker, limit=2)
        dl.get("10-Q", ticker, limit=3)
    except Exception as e:
        print(f"  failed: {e}")

print("\nDone.")
print("Filings are in: ./data/filings/sec-edgar-filings/")
