"""
All the settings in one place. Change things here instead of digging through the code.
"""

# How far back to download price history
START_DATE = "2014-01-01"

# What we're predicting: will the stock be higher this many trading days from now?
HORIZON_DAYS = 5

# Train on data before this date, test on data from this date onward.
# The test period is data the model has NEVER seen while learning.
TEST_START = "2023-01-01"

# Folders
DATA_DIR = "data"
OUTPUT_DIR = "output"
MODEL_PATH = "output/model.joblib"

# For the simple strategy test: each week, "buy" the top N stocks by predicted probability
TOP_N = 10
