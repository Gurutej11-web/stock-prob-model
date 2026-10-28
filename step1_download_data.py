"""
STEP 1: Download daily price data (Open, High, Low, Close, Volume) for every stock.

Run:  python step1_download_data.py
Makes: data/prices.csv

Takes a minute or two. Re-run it any day to get the newest prices.
"""

import os
import pandas as pd
import yfinance as yf

from config import START_DATE, DATA_DIR
from tickers import TICKERS, MARKET_TICKER, VIX_TICKER


def download(tickers):
    print(f"Downloading {len(tickers)} tickers from Yahoo Finance (since {START_DATE})...")
    raw = yf.download(
        tickers,
        start=START_DATE,
        auto_adjust=True,      # adjusts for stock splits and dividends
        group_by="ticker",
        progress=True,
        threads=True,
    )

    rows = []
    for t in tickers:
        if t not in raw.columns.get_level_values(0):
            print(f"  ! No data for {t}, skipping")
            continue
        df = raw[t].dropna(how="all").copy()
        if df.empty:
            print(f"  ! No data for {t}, skipping")
            continue
        df.columns = [c.lower() for c in df.columns]
        df["ticker"] = t
        df.index.name = "date"
        rows.append(df.reset_index())

    out = pd.concat(rows, ignore_index=True)
    return out[["date", "ticker", "open", "high", "low", "close", "volume"]]


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    all_tickers = TICKERS + [MARKET_TICKER, VIX_TICKER]
    prices = download(all_tickers)
    path = os.path.join(DATA_DIR, "prices.csv")
    prices.to_csv(path, index=False)

    n_stocks = prices["ticker"].nunique()
    first, last = prices["date"].min(), prices["date"].max()
    print(f"\nSaved {len(prices):,} rows for {n_stocks} tickers to {path}")
    print(f"Date range: {pd.to_datetime(first).date()} to {pd.to_datetime(last).date()}")


if __name__ == "__main__":
    main()
