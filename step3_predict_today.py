"""
STEP 3: Get today's % chance for every stock, plus WHY the model thinks that.

Run:  python step3_predict_today.py            (shows the top and bottom 10)
      python step3_predict_today.py NVDA AAPL  (shows specific stocks)
Needs: data/prices.csv (step 1) and output/model.joblib (step 2)
Makes: output/predictions_today.csv

Tip: re-run step 1 first to get the latest prices.
"""

import os
import sys
import joblib
import numpy as np
import pandas as pd

from config import DATA_DIR, OUTPUT_DIR, MODEL_PATH, HORIZON_DAYS
from features import build_features, FEATURES


def explain(model, features, row, n=3):
    """For logistic regression: each clue's push = (its scaled value) x (its weight)."""
    scaler, lr = model[0], model[-1]
    scaled = scaler.transform(row[features].to_frame().T.astype(float))[0]
    pushes = pd.Series(scaled * lr.coef_[0], index=features)
    top = pushes.reindex(pushes.abs().sort_values(ascending=False).index)[:n]
    return ", ".join(f"({'+' if v > 0 else '-'}) {FEATURES[f]}" for f, v in top.items())


def track_record(cal, p):
    """Look up how often the model was right in the test period at this confidence level."""
    for bucket, r in cal.iterrows():
        if p in bucket:
            return f"{r['actual']:.0%} went up when it said ~{r['predicted']:.0%}"
    return "not enough history at this level"


def main():
    bundle = joblib.load(MODEL_PATH)
    model, features, cal = bundle["model"], bundle["features"], bundle["calibration"]

    prices = pd.read_csv(os.path.join(DATA_DIR, "prices.csv"), parse_dates=["date"])
    feats = build_features(prices)
    latest_date = feats["date"].max()
    today = feats[feats["date"] == latest_date].copy()

    today["chance_up"] = model.predict_proba(today[features])[:, 1]
    today["why"] = [explain(model, features, r) for _, r in today.iterrows()]
    today["track_record"] = [track_record(cal, p) for p in today["chance_up"]]
    today = today.sort_values("chance_up", ascending=False)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out = today[["ticker", "close", "chance_up", "why", "track_record"]]
    out.to_csv(os.path.join(OUTPUT_DIR, "predictions_today.csv"), index=False)

    print(f"\nPredictions using prices from {latest_date.date()}")
    print(f"Chance each stock closes HIGHER {HORIZON_DAYS} trading days from now")
    print("'why' = the 3 clues that mattered most. (+) raised the chance, (-) lowered it.\n")

    def show(df):
        for _, r in df.iterrows():
            print(f"  {r['ticker']:<6} {r['chance_up']:5.1%}   why: {r['why']}")
            print(f"  {'':<6} {'':5}    track record: {r['track_record']}")

    picks = [t.upper() for t in sys.argv[1:]]
    if picks:
        found = today[today["ticker"].isin(picks)]
        missing = set(picks) - set(found["ticker"])
        show(found)
        if missing:
            print(f"\n  Not in the list: {', '.join(sorted(missing))}")
    else:
        print("Most likely to go up:")
        show(today.head(10))
        print("\nLeast likely to go up:")
        show(today.tail(10))

    print(f"\nAll {len(today)} stocks saved to {OUTPUT_DIR}/predictions_today.csv")
    print("Reminder: these are small edges, not sure things. Practice with paper trading first.")


if __name__ == "__main__":
    main()
