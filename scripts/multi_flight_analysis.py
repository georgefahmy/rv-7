import os
import warnings

import matplotlib.pyplot as plt
import pandas as pd

warnings.filterwarnings("ignore")

# ====== CONFIG ======
FOLDER_PATH = (
    "/Users/GFahmy/Documents/projects/dynon/data_logs/clean_flights"  # <-- change this
)
CHT_COLUMNS = [
    "CHT 1 (deg F)",
    "CHT 2 (deg F)",
    "CHT 3 (deg F)",
    "CHT 4 (deg F)",
]  # adjust if needed
OAT_COLUMN = "OAT (deg F)"
POWER_COLUMN = "Percent Power"
FUEL_FLOW_COLUMN = "Total Fuel Flow (gal/hr)"
OIL_COLUMN = "Oil Temp (deg F)"

CHT_ALERT_THRESHOLD = 420  # deg F
ALT_FILTER = 2000
POWER_FILTER = 70


# ====== LOAD ALL CSV FILES ======
def load_flights(folder):
    all_data = []

    for file in os.listdir(folder):
        if file.endswith(".csv"):
            path = os.path.join(folder, file)
            try:
                df = pd.read_csv(path)
                df["source_file"] = file
                all_data.append(df)
            except Exception as e:
                print(f"Skipping {file}: {e}")

    combined = pd.concat(all_data, ignore_index=True)
    return combined


# ====== CLEAN + PREP ======
def preprocess(df):
    # Drop rows missing key data
    needed_cols = CHT_COLUMNS + [OAT_COLUMN, POWER_COLUMN, FUEL_FLOW_COLUMN]
    df = df.dropna(subset=needed_cols)
    # Filter to only include data where Percent Power > 50%
    df[POWER_COLUMN] = pd.to_numeric(df[POWER_COLUMN], errors="coerce")
    df = df[df[POWER_COLUMN] > POWER_FILTER]
    # Ensure altitude column is numeric (adjust name if needed)
    ALT_COLUMN = (
        "Pressure Altitude (ft)"
        if "Pressure Altitude (ft)" in df.columns
        else "GPS Altitude (ft)"
    )

    df[ALT_COLUMN] = pd.to_numeric(df[ALT_COLUMN], errors="coerce")

    # Filter each file to only include data >= (min altitude + 1000 ft)
    def filter_altitude(group):
        min_alt = group[ALT_COLUMN].min()
        return group[group[ALT_COLUMN] >= (min_alt + ALT_FILTER)]

    df = df.groupby("source_file", group_keys=True).apply(filter_altitude)
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Create average CHT
    df["CHT_avg"] = df[CHT_COLUMNS].mean(axis=1)
    # Print average CHT for each file
    print("\nAverage CHT by file:")
    avg_cht_per_file = df.groupby("source_file")["CHT_avg"].mean()
    avg_oat_per_file = df.groupby("source_file")[OAT_COLUMN].mean()
    avg_oil_per_file = df.groupby("source_file")[OIL_COLUMN].mean()
    for file, avg in avg_cht_per_file.items():
        print(
            f"{file} -- CHT: {avg:.1f} °F - OAT: {avg_oat_per_file[file]:.1f} °F - OIL: {avg_oil_per_file[file]:.1f} °F"
        )

    return df


# ====== ANALYSIS ======
def analyze(df):
    print("\n=== CORRELATIONS ===")
    print("CHT vs % Power:", df["CHT_avg"].corr(df[POWER_COLUMN]))
    print("CHT vs OAT:", df["CHT_avg"].corr(df[OAT_COLUMN]))
    print("Fuel Flow vs % Power:", df[FUEL_FLOW_COLUMN].corr(df[POWER_COLUMN]))

    print("\n=== HIGH CHT EVENTS ===")
    hot = df[df["CHT_avg"] > CHT_ALERT_THRESHOLD]
    print(f"Number of high CHT samples: {len(hot)}")
    if not hot.empty:
        print(hot[["CHT_avg", POWER_COLUMN, OAT_COLUMN, FUEL_FLOW_COLUMN]].head())

    print("\n=== EFFICIENCY (Fuel Flow per % Power) ===")
    df["efficiency"] = df[FUEL_FLOW_COLUMN] / df[POWER_COLUMN]
    print(df["efficiency"].describe())


# ====== PLOTS ======
def plot(df):
    fig = plt.figure(figsize=(14, 8))
    ax1 = fig.add_subplot(131)
    ax2 = fig.add_subplot(132)
    ax3 = fig.add_subplot(133)

    ax1.scatter(df[POWER_COLUMN], df["CHT_avg"], alpha=0.3)
    ax1.set_xlabel("% Power")
    ax1.set_ylabel("Avg CHT")
    ax1.set_title("CHT vs % Power")

    ax2.scatter(df[OAT_COLUMN], df["CHT_avg"], alpha=0.3)
    ax2.set_xlabel("OAT")
    ax2.set_ylabel("Avg CHT")
    ax2.set_title("CHT vs OAT")

    ax3.scatter(df[POWER_COLUMN], df[FUEL_FLOW_COLUMN], alpha=0.3)
    ax3.set_xlabel("% Power")
    ax3.set_ylabel("Fuel Flow")
    ax3.set_title("Fuel Flow vs % Power")
    plt.show()


# ====== MAIN ======
def main():
    df = load_flights(FOLDER_PATH)
    df = preprocess(df)
    analyze(df)
    plot(df)


if __name__ == "__main__":
    main()
