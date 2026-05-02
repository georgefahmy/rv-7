import os
import warnings

import matplotlib.pyplot as plt
import pandas as pd
from analysis import process_flights

warnings.filterwarnings("ignore")

# ====== CONFIG ======
FOLDER_PATH = "/Users/GFahmy/Documents/projects/dynon/clean_flights"
CHT_COLUMNS = [
    "CHT 1 (deg F)",
    "CHT 2 (deg F)",
    "CHT 3 (deg F)",
    "CHT 4 (deg F)",
]
OAT_COLUMN = "OAT (deg F)"
POWER_COLUMN = "Percent Power"
FUEL_FLOW_COLUMN = "Total Fuel Flow (gal/hr)"
OIL_COLUMN = "Oil Temp (deg F)"

CHT_ALERT_THRESHOLD = 420  # deg F
ALT_FILTER = 3000
POWER_FILTER = 10
REF_IAS = 120


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
    # needed_cols = CHT_COLUMNS + [OAT_COLUMN, POWER_COLUMN, FUEL_FLOW_COLUMN]
    # df = df.dropna(subset=needed_cols)
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
    df["AVG_CHT"] = df[CHT_COLUMNS].mean(axis=1)
    # Print average CHT for each file
    print("\nAverage CHT by file:")
    avg_cht_per_file = df.groupby("source_file")["AVG_CHT"].mean()
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
    print("CHT vs % Power:", df["AVG_CHT"].corr(df[POWER_COLUMN]))
    print("CHT vs OAT:", df["AVG_CHT"].corr(df[OAT_COLUMN]))
    print("Fuel Flow vs % Power:", df[FUEL_FLOW_COLUMN].corr(df[POWER_COLUMN]))

    print("\n=== HIGH CHT EVENTS ===")
    hot = df[df["AVG_CHT"] > CHT_ALERT_THRESHOLD]
    print(f"Number of high CHT samples: {len(hot)}")
    if not hot.empty:
        print(hot[["AVG_CHT", POWER_COLUMN, OAT_COLUMN, FUEL_FLOW_COLUMN]].head())

    print("\n=== EFFICIENCY (Fuel Flow per % Power) ===")
    df["efficiency"] = df[FUEL_FLOW_COLUMN] / df[POWER_COLUMN]
    print(df["efficiency"].describe())


def break_in_trend(df):
    CRUISE_RPM_MIN = 2200
    CRUISE_RPM_MAX = 2550
    CRUISE_MAP_MIN = 21.0  # Manifold Pressure in inches Hg
    CRUISE_MAP_MAX = 26.0
    CRUISE_IAS_MIN = 110  # Minimum Indicated Airspeed (knots)
    CRUISE_GPS_ALT_MIN = 3000
    MIN_CRUISE_POWER = 65
    MAX_CRUISE_POWER = 85

    # Apply the combined filter to lock in on cruise data only
    df = df[
        (df["RPM"] >= CRUISE_RPM_MIN)
        & (df["RPM"] <= CRUISE_RPM_MAX)
        & (df["Manifold Pressure (inHg)"] >= CRUISE_MAP_MIN)
        & (df["Manifold Pressure (inHg)"] <= CRUISE_MAP_MAX)
        & (df["Indicated Airspeed (knots)"] >= CRUISE_IAS_MIN)
        & (df["GPS Altitude (feet)"] >= CRUISE_GPS_ALT_MIN)
        & (df["Percent Power"] >= MIN_CRUISE_POWER)
        & (df["Percent Power"] <= MAX_CRUISE_POWER)
    ].copy()
    # 1. Calculate Oil Delta

    df["Sigma"] = df["Density Altitude (ft)"].apply(
        lambda x: ((518.67 - 0.003566 * x) / 518.67) ** 4.256
    )

    df["AVG_CHT_density_corr"] = (df["AVG_CHT"] - df[OAT_COLUMN]) / df["Sigma"]
    df["CHT_Per_Power"] = df["AVG_CHT_density_corr"] / df["Percent Power"]
    df["Fuel_Efficiency_Index"] = df["Total Fuel Flow (gal/hr)"] / df["Percent Power"]

    df["AVG_CHT_Final_Normalized"] = (
        df["AVG_CHT_density_corr"] * (df["Indicated Airspeed (knots)"] / REF_IAS) ** 2
    )
    df["Oil_Friction_Index"] = (df["Oil Pressure (PSI)"] / (df["RPM"] / 1000)) / (
        df[OIL_COLUMN] - df[OAT_COLUMN]
    )
    final_analysis = (
        df.groupby("source_file")
        .agg(
            {
                "CHT_Per_Power": "mean",  # Lower trend == break in complete
                "Fuel_Efficiency_Index": "mean",  # Lower trend == break in complete
                "Oil_Friction_Index": "mean",  # Higher == break in complete
                "AVG_CHT_Final_Normalized": "mean",  # Lower == break in complete
                "Percent Power": "mean",
            }
        )
        .reset_index()
    )

    print("--- ENGINE BREAK-IN PERFORMANCE DATA ---")
    print(final_analysis.to_string(index=False))


# ====== PLOTS ======
def plot(df):
    fig = plt.figure(figsize=(14, 8))
    ax1 = fig.add_subplot(131)
    ax2 = fig.add_subplot(132)
    ax3 = fig.add_subplot(133)

    ax1.scatter(df[POWER_COLUMN], df["AVG_CHT"], alpha=0.3)
    ax1.set_xlabel("% Power")
    ax1.set_ylabel("Avg CHT")
    ax1.set_title("CHT vs % Power")

    ax2.scatter(df[OAT_COLUMN], df["AVG_CHT"], alpha=0.3)
    ax2.set_xlabel("OAT")
    ax2.set_ylabel("Avg CHT")
    ax2.set_title("CHT vs OAT")

    ax3.scatter(df[POWER_COLUMN], df[FUEL_FLOW_COLUMN], alpha=0.3)
    ax3.set_xlabel("% Power")
    ax3.set_ylabel("Fuel Flow")
    ax3.set_title("Fuel Flow vs % Power")
    plt.show()


def save_flights_to_csv(df, output_dir):
    """
    Saves each flight to its own CSV file, grouping exports into subfolders based on their GPS date.
    """
    import os

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Only keep valid flight IDs
    flight_ids = [fid for fid in df["Flight ID"].unique() if fid not in (None, 0, "")]

    for fid in flight_ids:
        flight_data = df[df["Flight ID"] == fid]
        if flight_data.empty:
            continue

        # Extract date from Flight ID (assumes format: "YYYY-MM-DD ... - Flight X")
        fid_str = str(fid)
        filename = fid_str.split(" - ")[0]

        # Create subfolder for that date
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Clean filename
        safe_name = filename.replace("/", "-").replace(":", "-")
        filepath = os.path.join(output_dir, f"{safe_name}.csv")

        flight_data.to_csv(filepath, index=False)


# ====== MAIN ======
def main():
    df = load_flights(FOLDER_PATH)
    df = process_flights(df)
    analyze(df)
    # plot(df)
    # print("exporting")
    # save_flights_to_csv(df, "/Users/GFahmy/Documents/projects/dynon/clean_flights_2")
    break_in_trend(df)


if __name__ == "__main__":
    main()
