"""
Turns raw prices into the "clues" (features) the model looks at.

Every feature for a given day only uses data from THAT day or earlier.
That's important: if a feature accidentally used tomorrow's price, the model
would look amazing in testing and be useless in real life (this is called "leakage").
"""

import numpy as np
import pandas as pd

from config import HORIZON_DAYS
from tickers import MARKET_TICKER, VIX_TICKER

# Feature name -> plain-English description (used to explain predictions)
FEATURES = {
    "ret_1d":        "move yesterday",
    "ret_5d":        "move over the past week",
    "ret_20d":       "move over the past month",
    "ret_60d":       "move over the past 3 months",
    "dist_ma20":     "price vs. 20-day average",
    "dist_ma50":     "price vs. 50-day average",
    "dist_ma200":    "price vs. 200-day average",
    "rsi_14":        "RSI (overbought/oversold)",
    "vol_20d":       "how jumpy the price has been",
    "range_pct":     "size of the daily high-low range",
    "volume_ratio":  "volume vs. normal",
    "mkt_ret_5d":    "whole market's move this week",
    "mkt_ret_20d":   "whole market's move this month",
    "vix_level":     "market fear level (VIX)",
    "vix_change_5d": "change in market fear this week",
}
FEATURE_COLS = list(FEATURES.keys())


def rsi(close, period=14):
    """Relative Strength Index: 0-100. Above 70 = rose fast, below 30 = fell fast."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def stock_features(df):
    """Features for one stock. df = that stock's rows, sorted by date."""
    df = df.sort_values("date").copy()
    c = df["close"]

    df["ret_1d"] = c.pct_change(1)
    df["ret_5d"] = c.pct_change(5)
    df["ret_20d"] = c.pct_change(20)
    df["ret_60d"] = c.pct_change(60)

    df["dist_ma20"] = c / c.rolling(20).mean() - 1
    df["dist_ma50"] = c / c.rolling(50).mean() - 1
    df["dist_ma200"] = c / c.rolling(200).mean() - 1

    df["rsi_14"] = rsi(c, 14)
    df["vol_20d"] = df["ret_1d"].rolling(20).std()
    df["range_pct"] = ((df["high"] - df["low"]) / c).rolling(5).mean()
    df["volume_ratio"] = df["volume"] / df["volume"].rolling(20).mean()

    # The answer we're trying to predict (uses FUTURE prices, so it's only the label, never a feature)
    df["fwd_return"] = c.shift(-HORIZON_DAYS) / c - 1
    df["target"] = (df["fwd_return"] > 0).astype(float)
    df.loc[df["fwd_return"].isna(), "target"] = np.nan
    return df


def market_features(prices):
    """Market-wide clues from SPY and VIX, one row per date."""
    spy = prices[prices["ticker"] == MARKET_TICKER].set_index("date")["close"].sort_index()
    vix = prices[prices["ticker"] == VIX_TICKER].set_index("date")["close"].sort_index()
    mkt = pd.DataFrame(index=spy.index)
    mkt["mkt_ret_5d"] = spy.pct_change(5)
    mkt["mkt_ret_20d"] = spy.pct_change(20)
    mkt["vix_level"] = vix.reindex(spy.index).ffill()
    mkt["vix_change_5d"] = mkt["vix_level"].pct_change(5)
    return mkt.reset_index()


def build_features(prices):
    """Raw prices (long format) -> one row per stock per day with all features + target."""
    prices = prices.copy()
    prices["date"] = pd.to_datetime(prices["date"])

    stocks = prices[~prices["ticker"].isin([MARKET_TICKER, VIX_TICKER])]
    per_stock = [stock_features(g) for _, g in stocks.groupby("ticker")]
    feats = pd.concat(per_stock, ignore_index=True)

    feats = feats.merge(market_features(prices), on="date", how="left")
    feats = feats.replace([np.inf, -np.inf], np.nan)

    # Drop the early rows where long averages (like the 200-day) aren't ready yet
    feats = feats.dropna(subset=FEATURE_COLS)
    return feats.sort_values(["date", "ticker"]).reset_index(drop=True)
