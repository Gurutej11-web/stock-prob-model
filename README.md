# Stock Probability Model

A machine learning model that looks at the ~100 biggest US stocks and estimates the **% chance each one closes higher 5 trading days from now**, explains which clues drove that number, and shows how accurate it has been on data it never trained on.

By Gurutej Bandla.

---

## Setup (one time, ~15 minutes)

### 1. Install Python
- Go to **https://www.python.org/downloads/** and download the latest Python 3.
- **Windows:** when the installer opens, check the box **"Add python.exe to PATH"** at the bottom *before* clicking Install. This is the step people miss most.
- **Mac:** just run the installer normally.

Check it worked: open a terminal (**Windows:** search "Command Prompt" or "PowerShell"; **Mac:** search "Terminal") and type:
```
python --version
```
You should see something like `Python 3.13.x`. On Mac, if that doesn't work, use `python3` instead of `python` everywhere below.

### 2. Get a code editor (recommended)
Download **VS Code** from https://code.visualstudio.com. When you open a `.py` file it will offer to install the Python extension. Say yes.

### 3. Unzip the project
Unzip `stock-prob-model.zip` somewhere easy, like your Documents folder.

### 4. Open a terminal in the project folder
- **VS Code:** File → Open Folder → pick `stock-prob-model`, then Terminal → New Terminal.
- **Or** in a normal terminal: `cd` into the folder, e.g. `cd Documents/stock-prob-model`

### 5. Install the libraries
```
python -m pip install -r requirements.txt
```
(Mac: `python3 -m pip install -r requirements.txt`)

---

## Running it

Run these in order, from the project folder:

| Step | Command | What it does | Time |
|---|---|---|---|
| 1 | `python step1_download_data.py` | Downloads ~12 years of daily prices for all the stocks | ~1 min |
| 2 | `python step2_train_and_test.py` | Builds the clues, trains the model, tests it, makes charts | ~10 sec |
| 3 | `python step3_predict_today.py` | Today's % chance for every stock + why | ~5 sec |

Look up specific stocks: `python step3_predict_today.py NVDA AAPL TSLA`

**Each day:** re-run step 1 (new prices) then step 3. Re-run step 2 every few weeks to retrain.

Results land in the `output` folder:
- `results.txt`: all the numbers
- `calibration.png`: does "55%" actually mean 55%?
- `strategy_vs_baseline.png`: would following the model have beaten buying everything?
- `feature_weights.png`: which clues matter most
- `predictions_today.csv`: today's predictions (opens in Excel/Google Sheets)

---

## How it works

**Data:** daily Open, High, Low, Close, Volume for each stock, plus SPY (the whole market) and VIX (the fear index), from Yahoo Finance.

**15 clues per stock per day** (`features.py`):
- Momentum: returns over 1 day, 1 week, 1 month, 3 months
- Trend: price vs. its 20, 50, and 200-day averages
- RSI (overbought/oversold)
- Volatility and daily high-low range
- Volume vs. normal
- Market's weekly and monthly move, VIX level and weekly change

**Label:** did the stock close higher 5 trading days later? (yes/no)

**Models:** logistic regression (simple, explainable) vs. gradient boosting (fancier).

**Honest testing:**
- Trained on 2014–2022, tested on 2023–today, data the model never saw.
- A 5-day "purge" gap between train and test, so no training answers peek into the test period.
- Every feature only uses data available that day (no leakage).
- Compared against a baseline that always guesses the average "up" rate.

---
## Results

![Calibration chart](output/calibration.png)

![Strategy vs baseline](output/strategy_vs_baseline.png)

![Feature weights](output/feature_weights.png)

## What I found (first run, Oct 2026)

- **The market is really hard to predict.** The logistic regression's AUC was ~0.51 (0.50 = coin flip). Gradient boosting did no better, and was worse calibrated. Simpler won.
- **The probabilities are mostly honest.** Most predictions land between 50–60%, and the calibration chart roughly follows the diagonal.
- **The strongest clue** was momentum: stocks up over the past month tended to keep going a bit, but stocks stretched far above their 50-day average tended to cool off.
- **The strategy test looked good** (top 10 picks grew $1,000 to ~$2,600 vs. ~$2,000 for buying all of them), but I'm skeptical of it. See limitations.

## Limitations (important)

- **Survivorship bias:** I used *today's* biggest companies. In 2023 nobody knew PLTR or NVDA would be on this list, so testing on them makes past results look better than they would have been.
- **No trading costs or taxes** in the strategy test. Trading every week adds up.
- **The model may just be picking riskier stocks** that happened to go up in a strong market. A down market could flip that.
- The S&P 100 list in `tickers.py` changes over time and may be slightly out of date.

## Ideas for next versions
- Fix survivorship bias using historical index membership
- Add earnings dates and news sentiment
- Add sector info (is all of tech moving, or just one stock?)
- Build a website: type a ticker, see the % chance, the "why," and the track record

*This is a learning project, not financial advice.*
