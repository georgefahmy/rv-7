import pandas as pd

raw = pd.read_csv(
    "/Users/GFahmy/Desktop/RV-7/data_logs/2025-11-07-N890GF-SN35347-17.3.0.19825-TEST-USER_LOG_DATA-PART_05.csv"
)
raw = raw.fillna("0")
data = raw[raw["GPS Date & Time"].str.contains("2025-11-06")]

data["Session Time"].to_list()[-1] - data["Session Time"].to_list()[0]
