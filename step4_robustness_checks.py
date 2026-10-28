"""
STEP 4: Is the model's strategy result actually real? Stress-test it.

Run:  python step4_robustness_checks.py
Needs: data/prices.csv (from step 1)
Makes: output/robustness.txt, output/robustness_strategies.png

In step 2, the model's top 10 picks beat "buy everything" (+164% vs +102%).
That could be real skill, OR it could be something boring. This script checks:

  1. Dumb strategies: does "buy the 10 jumpiest stocks" or "buy last month's 10
     biggest winners" do just as well? If so, the model isn't adding much.
  2. Random picks: how often does picking 10 random stocks do this well?
  3. Survivorship bias: remove the 10 biggest winners of the test period
     (the companies we only included because we know they ended up huge) and re-test.
  4. Trading costs: subtract a realistic cost every time the picks change.
  5. Statistics: is the weekly edge big enough compared to its noise to be more than luck?
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from config import DATA_DIR, OUTPUT_DIR, HORIZON_DAYS, TOP_N
from features import build_features, FEATURE_COLS
from step2_train_and_test import make_models, split
from charts import style, save, BLUE, ORANGE, AQUA, INK_2

COST_PER_TRADE = 0.001   # 0.1% each time you buy or sell a stock (spread + slippage)
N_RANDOM = 500           # how many random portfolios to simulate


def rebalance_dates(test):
    return np.sort(test["date"].unique())[::HORIZON_DAYS]


def by_date(test, dates):
    """Split the test data into one small table per rebalance date (much faster to reuse)."""
    keep = test[test["date"].isin(dates)]
    return {d: g for d, g in keep.groupby("date")}


def run_strategy(test, score_col, dates, cost=0.0, days=None):
    """Every rebalance date, hold the TOP_N stocks with the highest score.
    Returns per-period returns (after costs) and average turnover."""
    days = days if days is not None else by_date(test, dates)
    rets, turnovers, prev = [], [], set()
    for d in dates:
        day = days[d]
        picks = set(day.nlargest(TOP_N, score_col)["ticker"])
        r = day[day["ticker"].isin(picks)]["fwd_return"].mean()
        changed = len(picks - prev) / TOP_N if prev else 1.0
        r -= 2 * changed * cost          # sell old ones + buy new ones
        rets.append(r)
        turnovers.append(changed)
        prev = picks
    return pd.Series(rets, index=dates), float(np.mean(turnovers[1:])) if len(turnovers) > 1 else 1.0


def equal_weight(test, dates):
    return pd.Series([test[test["date"] == d]["fwd_return"].mean() for d in dates], index=dates)


def total(r):
    return (1 + r).prod() - 1


def t_stat(excess):
    """How many 'standard errors' the average weekly edge is from zero.
    Rough rule: above 2 = probably not luck. Below 2 = could easily be luck."""
    return excess.mean() / (excess.std(ddof=1) / np.sqrt(len(excess)))


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("Loading data and training the model (same setup as step 2)...")
    prices = pd.read_csv(os.path.join(DATA_DIR, "prices.csv"), parse_dates=["date"])
    feats = build_features(prices)
    train, test = split(feats)
    model = make_models()["Logistic regression"].fit(train[FEATURE_COLS], train["target"])
    test = test.assign(
        p_model=model.predict_proba(test[FEATURE_COLS])[:, 1],
        s_jumpy=test["vol_20d"],          # dumb strategy: most volatile stocks
        s_momentum=test["ret_20d"],       # dumb strategy: last month's biggest winners
    )
    dates = rebalance_dates(test)
    base = equal_weight(test, dates)

    lines = ["ROBUSTNESS CHECKS — is the model's edge real?",
             f"Test period: {pd.Timestamp(dates[0]).date()} to {pd.Timestamp(dates[-1]).date()}, "
             f"{len(dates)} periods of {HORIZON_DAYS} trading days, top {TOP_N} picks each time\n"]

    # ---- 1. Model vs dumb strategies ----
    strategies = {}
    for name, col in [("Model's top 10", "p_model"),
                      ("10 jumpiest stocks", "s_jumpy"),
                      ("Last month's 10 biggest winners", "s_momentum")]:
        strategies[name], _ = run_strategy(test, col, dates)
    strategies["All stocks equally"] = base

    lines.append("1) MODEL vs. DUMB STRATEGIES (no trading costs)")
    for name, r in strategies.items():
        lines.append(f"   {name:<34} {total(r):+8.1%}")
    avg_vol_picks = np.mean([test[test['date'] == d].nlargest(TOP_N, 'p_model')['vol_20d'].mean() for d in dates])
    avg_vol_all = test[test["date"].isin(dates)]["vol_20d"].mean()
    lines.append(f"   Model's picks are {avg_vol_picks / avg_vol_all:.2f}x as jumpy as the average stock "
                 f"(1.00 = same risk).\n")

    # ---- 2. Random picks ----
    rng = np.random.default_rng(42)
    days = by_date(test, dates)
    rand_totals = []
    for _ in range(N_RANDOM):
        r = pd.Series([g["fwd_return"].sample(TOP_N, random_state=rng).mean() for g in days.values()])
        rand_totals.append(total(r))
    rand_totals = np.array(rand_totals)
    model_total = total(strategies["Model's top 10"])
    pct_beat = (rand_totals >= model_total).mean()
    lines.append(f"2) RANDOM PICKS ({N_RANDOM} random 10-stock portfolios)")
    lines.append(f"   Typical random result: {np.median(rand_totals):+.1%} "
                 f"(middle 90%: {np.percentile(rand_totals, 5):+.1%} to {np.percentile(rand_totals, 95):+.1%})")
    lines.append(f"   Random picks did as well as the model {pct_beat:.1%} of the time.\n")

    # ---- 3. Survivorship: drop the biggest winners ----
    first, last = test["date"].min(), test["date"].max()
    px = prices[prices["ticker"].isin(test["ticker"].unique())].pivot(index="date", columns="ticker", values="close")
    period_gain = px.loc[px.index >= first].ffill().iloc[-1] / px.loc[px.index >= first].bfill().iloc[0] - 1
    winners = period_gain.nlargest(10).index.tolist()
    test_nw = test[~test["ticker"].isin(winners)]
    model_nw, _ = run_strategy(test_nw, "p_model", dates)
    base_nw = equal_weight(test_nw, dates)
    lines.append("3) SURVIVORSHIP CHECK — remove the 10 biggest winners of the test period")
    lines.append(f"   Removed: {', '.join(winners)}")
    lines.append(f"   Model's top 10:      {total(model_nw):+.1%}")
    lines.append(f"   All stocks equally:  {total(base_nw):+.1%}")
    lines.append(f"   Gap: {total(model_nw) - total(base_nw):+.1%} "
                 f"(was {model_total - total(base):+.1%} with them included)\n")

    # ---- 4. Trading costs ----
    model_cost, turnover = run_strategy(test, "p_model", dates, cost=COST_PER_TRADE)
    lines.append(f"4) TRADING COSTS ({COST_PER_TRADE:.1%} per buy or sell)")
    lines.append(f"   The model replaces {turnover:.0%} of its picks every {HORIZON_DAYS} days on average.")
    lines.append(f"   Model's top 10 after costs: {total(model_cost):+.1%} (before: {model_total:+.1%})")
    lines.append(f"   All stocks equally:         {total(base):+.1%} (hardly ever trades)\n")

    # ---- 5. Statistics ----
    excess = strategies["Model's top 10"] - base
    excess_cost = model_cost - base
    lines.append("5) IS THE EDGE MORE THAN LUCK? (t-stat: above ~2 = probably real)")
    lines.append(f"   Average edge per period:  {excess.mean():+.2%} (t-stat {t_stat(excess):.2f})")
    lines.append(f"   After trading costs:      {excess_cost.mean():+.2%} (t-stat {t_stat(excess_cost):.2f})")
    lines.append(f"   Without the big winners:  {(model_nw - base_nw).mean():+.2%} "
                 f"(t-stat {t_stat(model_nw - base_nw):.2f})\n")

    # ---- Chart ----
    fig, ax = plt.subplots(figsize=(9, 5.5))
    series = [("Model's top 10", strategies["Model's top 10"], BLUE, "-"),
              ("Model after trading costs", model_cost, BLUE, "--"),
              ("10 jumpiest stocks", strategies["10 jumpiest stocks"], AQUA, "-"),
              ("All stocks equally", base, ORANGE, "-")]
    ends = []
    for label, r, color, ls in series:
        g = (1 + r).cumprod() * 1000
        ax.plot(g.index, g.values, color=color, linestyle=ls, linewidth=2, label=label)
        ends.append((g.iloc[-1], g.index[-1], color))
    # End labels, nudged apart so they don't overlap
    ends.sort(key=lambda e: e[0])
    min_gap = (max(e[0] for e in ends) - min(e[0] for e in ends)) * 0.09
    placed = []
    for val, x, color in ends:
        y = max(val, placed[-1] + min_gap) if placed else val
        placed.append(y)
        ax.annotate(f"${val:,.0f}", (x, val), xytext=(x, y), textcoords="data", color=color,
                    va="center", fontweight="bold", annotation_clip=False,
                    xycoords="data", horizontalalignment="left")
    ax.set_xlim(right=ax.get_xlim()[1] + (ax.get_xlim()[1] - ax.get_xlim()[0]) * 0.08)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    style(ax, "What $1,000 would have grown to: model vs. simple strategies")
    ax.legend(frameon=False, loc="upper left")
    save(fig, os.path.join(OUTPUT_DIR, "robustness_strategies.png"))

    text = "\n".join(lines)
    with open(os.path.join(OUTPUT_DIR, "robustness.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    print("\n" + text)
    print(f"Saved output/robustness.txt and output/robustness_strategies.png")


if __name__ == "__main__":
    main()
