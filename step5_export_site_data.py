"""
STEP 5: Export everything the website needs into docs/data.json.

Run:  python step5_export_site_data.py
Needs: data/prices.csv (step 1) and output/model.joblib (step 2)
Makes: docs/data.json  (the website in docs/ reads this file)

To see the site on your own computer:
    python -m http.server 8000 --directory docs
then open http://localhost:8000 in your browser.
"""

import os
import json
import warnings
import numpy as np
import pandas as pd
import joblib
from sklearn.metrics import roc_auc_score, brier_score_loss

from config import DATA_DIR, MODEL_PATH, HORIZON_DAYS, TOP_N
from features import build_features, FEATURE_COLS, FEATURES
from step2_train_and_test import make_models, split, calibration_table
from step4_robustness_checks import run_strategy, equal_weight, rebalance_dates, by_date, total, t_stat, COST_PER_TRADE

warnings.filterwarnings("ignore")

SITE_DIR = "docs"
HISTORY_DAYS = 126  # ~6 months of prices for the little chart on each stock

NAMES = {
    "AAPL": "Apple", "ABBV": "AbbVie", "ABT": "Abbott Laboratories", "ACN": "Accenture", "ADBE": "Adobe",
    "AIG": "AIG", "AMD": "AMD", "AMGN": "Amgen", "AMT": "American Tower", "AMZN": "Amazon",
    "AVGO": "Broadcom", "AXP": "American Express", "BA": "Boeing", "BAC": "Bank of America",
    "BK": "BNY", "BKNG": "Booking Holdings", "BLK": "BlackRock", "BMY": "Bristol Myers Squibb",
    "BRK-B": "Berkshire Hathaway", "C": "Citigroup", "CAT": "Caterpillar", "CHTR": "Charter Communications",
    "CL": "Colgate-Palmolive", "CMCSA": "Comcast", "COF": "Capital One", "COP": "ConocoPhillips",
    "COST": "Costco", "CRM": "Salesforce", "CSCO": "Cisco", "CVS": "CVS Health", "CVX": "Chevron",
    "DE": "Deere", "DHR": "Danaher", "DIS": "Disney", "DUK": "Duke Energy", "EMR": "Emerson Electric",
    "FDX": "FedEx", "GD": "General Dynamics", "GE": "GE Aerospace", "GILD": "Gilead Sciences",
    "GM": "General Motors", "GOOG": "Alphabet (Class C)", "GOOGL": "Alphabet (Class A)",
    "GS": "Goldman Sachs", "HD": "Home Depot", "HON": "Honeywell", "IBM": "IBM", "INTC": "Intel",
    "INTU": "Intuit", "ISRG": "Intuitive Surgical", "JNJ": "Johnson & Johnson", "JPM": "JPMorgan Chase",
    "KO": "Coca-Cola", "LIN": "Linde", "LLY": "Eli Lilly", "LMT": "Lockheed Martin", "LOW": "Lowe's",
    "MA": "Mastercard", "MCD": "McDonald's", "MDLZ": "Mondelez", "MDT": "Medtronic", "MET": "MetLife",
    "META": "Meta Platforms", "MMM": "3M", "MO": "Altria", "MRK": "Merck", "MS": "Morgan Stanley",
    "MSFT": "Microsoft", "NEE": "NextEra Energy", "NFLX": "Netflix", "NKE": "Nike", "NOW": "ServiceNow",
    "NVDA": "Nvidia", "ORCL": "Oracle", "PEP": "PepsiCo", "PFE": "Pfizer", "PG": "Procter & Gamble",
    "PLTR": "Palantir", "PM": "Philip Morris", "PYPL": "PayPal", "QCOM": "Qualcomm", "RTX": "RTX",
    "SBUX": "Starbucks", "SCHW": "Charles Schwab", "SO": "Southern Company", "SPG": "Simon Property Group",
    "T": "AT&T", "TGT": "Target", "TMO": "Thermo Fisher Scientific", "TMUS": "T-Mobile US", "TSLA": "Tesla",
    "TXN": "Texas Instruments", "UBER": "Uber", "UNH": "UnitedHealth", "UNP": "Union Pacific", "UPS": "UPS",
    "USB": "U.S. Bancorp", "V": "Visa", "VZ": "Verizon", "WFC": "Wells Fargo", "WMT": "Walmart",
    "XOM": "ExxonMobil",
}


def r(x, n=4):
    """Round for JSON, turning NaN into None."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    return round(float(x), n)


def reasons(model, row, n=3):
    scaler, lr = model[0], model[-1]
    scaled = scaler.transform(row[FEATURE_COLS].to_frame().T.astype(float))[0]
    pushes = pd.Series(scaled * lr.coef_[0], index=FEATURE_COLS)
    top = pushes.reindex(pushes.abs().sort_values(ascending=False).index)[:n]
    return [{"key": f, "label": FEATURES[f], "value": r(row[f]), "dir": 1 if v > 0 else -1}
            for f, v in top.items()]


def track_record(cal, p):
    for bucket, row in cal.iterrows():
        if p in bucket:
            return {"said": r(row["predicted"]), "actual": r(row["actual"]), "count": int(row["count"])}
    return None


def main():
    os.makedirs(SITE_DIR, exist_ok=True)
    print("Loading data...")
    prices = pd.read_csv(os.path.join(DATA_DIR, "prices.csv"), parse_dates=["date"])
    feats = build_features(prices)
    bundle = joblib.load(MODEL_PATH)
    final_model, cal = bundle["model"], bundle["calibration"]

    # ---------- Today's predictions ----------
    latest = feats["date"].max()
    today = feats[feats["date"] == latest].copy()
    today["p"] = final_model.predict_proba(today[FEATURE_COLS])[:, 1]

    px = prices.pivot(index="date", columns="ticker", values="close").sort_index()
    px = px[px.index <= latest]
    stocks = []
    for _, row in today.sort_values("p", ascending=False).iterrows():
        t = row["ticker"]
        hist = px[t].dropna().iloc[-HISTORY_DAYS:]
        stocks.append({
            "t": t,
            "name": NAMES.get(t, t),
            "close": r(row["close"], 2),
            "chg1d": r(row["ret_1d"]),
            "p": r(row["p"]),
            "why": reasons(final_model, row),
            "record": track_record(cal, row["p"]),
            "clues": {
                "ret_5d": r(row["ret_5d"]), "ret_20d": r(row["ret_20d"]), "ret_60d": r(row["ret_60d"]),
                "dist_ma50": r(row["dist_ma50"]), "dist_ma200": r(row["dist_ma200"]),
                "rsi_14": r(row["rsi_14"], 1), "volume_ratio": r(row["volume_ratio"], 2),
            },
            "hist": [r(v, 2) for v in hist.values],
            "hist_start": str(hist.index[0].date()),
        })

    # ---------- Honest test-period evaluation ----------
    print("Re-running the out-of-sample test...")
    train, test = split(feats)
    models = make_models()
    probs = {}
    for name, m in models.items():
        m.fit(train[FEATURE_COLS], train["target"])
        probs[name] = m.predict_proba(test[FEATURE_COLS])[:, 1]
    y = test["target"]
    base_rate = train["target"].mean()
    p_lr = probs["Logistic regression"]
    test = test.assign(p_model=p_lr, s_jumpy=test["vol_20d"])
    test_cal = calibration_table(y, p_lr)

    dates = rebalance_dates(test)
    days = by_date(test, dates)
    model_r, _ = run_strategy(test, "p_model", dates, days=days)
    model_cost_r, turnover = run_strategy(test, "p_model", dates, cost=COST_PER_TRADE, days=days)
    jumpy_r, _ = run_strategy(test, "s_jumpy", dates, days=days)
    base_r = equal_weight(test, dates)

    first = test["date"].min()
    sub = px.loc[px.index >= first, test["ticker"].unique()]
    gain = sub.ffill().iloc[-1] / sub.bfill().iloc[0] - 1
    winners = gain.nlargest(10).index.tolist()
    test_nw = test[~test["ticker"].isin(winners)]
    days_nw = by_date(test_nw, dates)
    model_nw_r, _ = run_strategy(test_nw, "p_model", dates, days=days_nw)
    base_nw_r = pd.Series([days_nw[d]["fwd_return"].mean() for d in dates], index=dates)

    def growth(s):
        return [r(v, 1) for v in ((1 + s).cumprod() * 1000).values]

    data = {
        "as_of": str(latest.date()),
        "horizon": HORIZON_DAYS,
        "top_n": TOP_N,
        "stocks": stocks,
        "metrics": {
            "auc_lr": r(roc_auc_score(y, p_lr)),
            "auc_gb": r(roc_auc_score(y, probs["Gradient boosting"])),
            "brier_lr": r(brier_score_loss(y, p_lr)),
            "brier_base": r(brier_score_loss(y, np.full(len(y), base_rate))),
            "up_rate": r(y.mean()),
            "n_test": int(len(test)),
            "test_start": str(test["date"].min().date()),
            "test_end": str(test["date"].max().date()),
        },
        "calibration": [{"said": r(row["predicted"]), "actual": r(row["actual"]), "count": int(row["count"])}
                        for _, row in test_cal.iterrows()],
        "backtest": {
            "dates": [str(pd.Timestamp(d).date()) for d in dates],
            "model": growth(model_r),
            "model_cost": growth(model_cost_r),
            "jumpy": growth(jumpy_r),
            "all": growth(base_r),
            "model_nw": growth(model_nw_r),
            "all_nw": growth(base_nw_r),
        },
        "robustness": {
            "winners_removed": winners,
            "model": r(total(model_r)), "all": r(total(base_r)), "jumpy": r(total(jumpy_r)),
            "model_cost": r(total(model_cost_r)), "turnover": r(turnover),
            "model_nw": r(total(model_nw_r)), "all_nw": r(total(base_nw_r)),
            "t": r(t_stat(model_r - base_r), 2),
            "t_cost": r(t_stat(model_cost_r - base_r), 2),
            "t_nw": r(t_stat(model_nw_r - base_nw_r), 2),
        },
    }

    path = os.path.join(SITE_DIR, "data.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"Saved {path} ({os.path.getsize(path) / 1024:.0f} KB) with {len(stocks)} stocks, prices from {latest.date()}")


if __name__ == "__main__":
    main()
