import pandas as pd

raw = pd.read_csv(input("Full file path: "))
raw = raw.fillna("0")
data = raw[raw["GPS Date & Time"].str.contains("2025-11-06")]

data["Session Time"].to_list()[-1] - data["Session Time"].to_list()[0]
