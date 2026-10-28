"""
STEP 2: Train the model on older data, then test it honestly on newer data it has never seen.

Run:  python step2_train_and_test.py
Needs: data/prices.csv (from step 1)
Makes: output/results.txt, output/*.png charts, output/model.joblib

Two models get compared:
  - Logistic regression: simple, and easy to explain WHY it gave a number
  - Gradient boosting:   fancier, can find more complex patterns (but also overfit more easily)
"""

import os
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, brier_score_loss, accuracy_score

from config import DATA_DIR, OUTPUT_DIR, MODEL_PATH, TEST_START, HORIZON_DAYS, TOP_N
from features import build_features, FEATURE_COLS, FEATURES
from charts import style, save, BLUE, ORANGE, AQUA, INK_2


def make_models():
    logreg = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=1000))
    gboost = HistGradientBoostingClassifier(
        max_depth=3, learning_rate=0.05, max_iter=200, min_samples_leaf=200, random_state=42
    )
    return {"Logistic regression": logreg, "Gradient boosting": gboost}


def split(feats):
    """Train = before TEST_START, Test = TEST_START onward.
    We also drop the last few training days right before the test period, because their
    answers (5 days later) would peek into the test period. This gap is called a 'purge'."""
    labeled = feats.dropna(subset=["target"])
    dates = np.sort(labeled["date"].unique())
    test_start = pd.Timestamp(TEST_START)
    train_dates = dates[dates < test_start]
    cutoff = train_dates[-HORIZON_DAYS] if len(train_dates) > HORIZON_DAYS else train_dates[0]
    train = labeled[labeled["date"] < cutoff]
    test = labeled[labeled["date"] >= test_start]
    return train, test


def calibration_table(y, p, bins=(0, .45, .48, .50, .52, .54, .56, .58, .60, 1.0)):
    """When the model says X%, how often did the stock actually go up?"""
    df = pd.DataFrame({"y": y, "p": p})
    df["bucket"] = pd.cut(df["p"], bins=list(bins), include_lowest=True)
    t = df.groupby("bucket", observed=True).agg(
        predicted=("p", "mean"), actual=("y", "mean"), count=("y", "size")
    )
    return t[t["count"] > 0]


def strategy_test(test, prob_col):
    """Every HORIZON_DAYS, 'buy' the TOP_N stocks the model likes most and hold them.
    Compare to just buying all the stocks equally. (No trading costs, so real results would be worse.)"""
    dates = np.sort(test["date"].unique())[::HORIZON_DAYS]
    rows = []
    for d in dates:
        day = test[test["date"] == d]
        if len(day) < TOP_N:
            continue
        top = day.nlargest(TOP_N, prob_col)
        rows.append({
            "date": d,
            "model_pick": top["fwd_return"].mean(),
            "all_stocks": day["fwd_return"].mean(),
        })
    s = pd.DataFrame(rows).set_index("date")
    growth = (1 + s).cumprod()
    return s, growth


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("Loading prices and building features...")
    prices = pd.read_csv(os.path.join(DATA_DIR, "prices.csv"), parse_dates=["date"])
    feats = build_features(prices)
    train, test = split(feats)
    print(f"Training rows: {len(train):,} ({train['date'].min().date()} to {train['date'].max().date()})")
    print(f"Testing rows:  {len(test):,} ({test['date'].min().date()} to {test['date'].max().date()})")

    X_tr, y_tr = train[FEATURE_COLS], train["target"]
    X_te, y_te = test[FEATURE_COLS], test["target"]

    # Baseline: always guess the training-period "up" rate. A model has to beat this to be worth anything.
    base_rate = y_tr.mean()
    lines = []
    lines.append(f"STOCK PROBABILITY MODEL — RESULTS")
    lines.append(f"Question: will the stock be higher {HORIZON_DAYS} trading days from now?")
    lines.append(f"Test period: {test['date'].min().date()} to {test['date'].max().date()} "
                 f"({test['ticker'].nunique()} stocks, {len(test):,} predictions)\n")
    lines.append(f"Baseline (always guess {base_rate:.1%}): "
                 f"Brier = {brier_score_loss(y_te, np.full(len(y_te), base_rate)):.4f}, "
                 f"accuracy = {max(y_te.mean(), 1 - y_te.mean()):.1%}")
    lines.append(f"Stocks actually went up {y_te.mean():.1%} of the time in the test period.\n")
    lines.append("How to read this:")
    lines.append("  AUC: 0.50 = coin flip, 1.00 = perfect. Anything above ~0.52 on stocks is meaningful.")
    lines.append("  Brier: lower is better. Must be LOWER than the baseline to count as useful.\n")

    models = make_models()
    for name, model in models.items():
        print(f"Training {name}...")
        model.fit(X_tr, y_tr)
        p = model.predict_proba(X_te)[:, 1]
        col = "p_lr" if "Logistic" in name else "p_gb"
        test = test.assign(**{col: p})
        lines.append(f"{name}:")
        lines.append(f"  AUC      = {roc_auc_score(y_te, p):.4f}")
        lines.append(f"  Brier    = {brier_score_loss(y_te, p):.4f}")
        lines.append(f"  Accuracy = {accuracy_score(y_te, p > 0.5):.1%}")
        lines.append(f"  Prediction range: {p.min():.1%} to {p.max():.1%}\n")

    # ---- Calibration ----
    cal_lr = calibration_table(y_te, test["p_lr"])
    cal_gb = calibration_table(y_te, test["p_gb"])
    lines.append("Calibration (logistic regression): when it says X%, how often did it go up?")
    for _, r in cal_lr.iterrows():
        lines.append(f"  said {r['predicted']:.1%} -> actually up {r['actual']:.1%}  ({int(r['count']):,} predictions)")
    lines.append("")

    fig, ax = plt.subplots(figsize=(7, 6))
    lo = min(cal_lr["predicted"].min(), cal_lr["actual"].min(), cal_gb["predicted"].min()) - 0.02
    hi = max(cal_lr["predicted"].max(), cal_lr["actual"].max(), cal_gb["predicted"].max()) + 0.02
    ax.plot([lo, hi], [lo, hi], "--", color=INK_2, linewidth=1, label="Perfectly honest")
    ax.plot(cal_lr["predicted"], cal_lr["actual"], "-o", color=BLUE, linewidth=2, markersize=7, label="Logistic regression")
    ax.plot(cal_gb["predicted"], cal_gb["actual"], "-o", color=ORANGE, linewidth=2, markersize=7, label="Gradient boosting")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    style(ax, "Calibration: does 55% really mean 55%?", "Model's predicted chance of going up", "How often it actually went up")
    ax.legend(frameon=False)
    save(fig, os.path.join(OUTPUT_DIR, "calibration.png"))

    # ---- Strategy test ----
    s, growth = strategy_test(test, "p_lr")
    total_model = growth["model_pick"].iloc[-1] - 1
    total_all = growth["all_stocks"].iloc[-1] - 1
    lines.append(f"Strategy test (every {HORIZON_DAYS} days, hold the model's top {TOP_N} picks, no trading costs):")
    lines.append(f"  Model's top {TOP_N}:      {total_model:+.1%}")
    lines.append(f"  All stocks equally:   {total_all:+.1%}")
    lines.append(f"  Model beat the baseline in {(s['model_pick'] > s['all_stocks']).mean():.0%} of the {len(s)} periods")
    lines.append("  Reminder: real trading has costs and taxes, so the model's real edge would be smaller.\n")

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(growth.index, growth["model_pick"], color=BLUE, linewidth=2, label=f"Model's top {TOP_N}")
    ax.plot(growth.index, growth["all_stocks"], color=ORANGE, linewidth=2, label="All stocks equally")
    for col, color in (("model_pick", BLUE), ("all_stocks", ORANGE)):
        ax.annotate(f"${growth[col].iloc[-1] * 1000:,.0f}", (growth.index[-1], growth[col].iloc[-1]),
                    xytext=(6, 0), textcoords="offset points", color=color, va="center", fontweight="bold")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v * 1000:,.0f}"))
    style(ax, "What $1,000 would have grown to (test period)", None, None)
    ax.legend(frameon=False, loc="upper left")
    save(fig, os.path.join(OUTPUT_DIR, "strategy_vs_baseline.png"))

    # ---- Which clues matter most (logistic regression weights) ----
    coefs = models["Logistic regression"][-1].coef_[0]
    imp = pd.Series(coefs, index=[FEATURES[c] for c in FEATURE_COLS]).sort_values()
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(imp.index, imp.values, color=[BLUE if v > 0 else ORANGE for v in imp.values], height=0.6)
    ax.axvline(0, color=INK_2, linewidth=1)
    style(ax, "Which clues push the chance up (blue) or down (orange)", "Model weight", None)
    save(fig, os.path.join(OUTPUT_DIR, "feature_weights.png"))

    lines.append("Clue weights (logistic regression, positive = pushes chance up):")
    for name, v in imp.sort_values(key=abs, ascending=False).items():
        lines.append(f"  {v:+.4f}  {name}")

    # ---- Save the model for step 3 ----
    # For live predictions, retrain the simple model on ALL labeled data (train + test) so it's as up to date as possible.
    print("Retraining final model on all data for live predictions...")
    labeled = feats.dropna(subset=["target"])
    final = make_models()["Logistic regression"].fit(labeled[FEATURE_COLS], labeled["target"])
    joblib.dump({
        "model": final,
        "features": FEATURE_COLS,
        "calibration": cal_lr,            # the test-period track record, shown next to predictions
        "trained_through": str(labeled["date"].max().date()),
    }, MODEL_PATH)

    text = "\n".join(lines)
    with open(os.path.join(OUTPUT_DIR, "results.txt"), "w") as f:
        f.write(text)
    print("\n" + text)
    print(f"\nCharts and results saved in the '{OUTPUT_DIR}' folder.")


if __name__ == "__main__":
    main()
