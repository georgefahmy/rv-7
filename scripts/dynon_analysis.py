import sys

import matplotlib.pyplot as plt
import pandas as pd


def load_data(filepath):
    """Loads the CSV file."""
    try:
        # Skip metadata rows if necessary, but standard read_csv usually works
        df = pd.read_csv(filepath)
        return df
    except Exception as e:
        print(f"Error loading file: {e}")
        return None


def process_flights(df):
    """
    Groups data into flights and marks if the engine was run.
    """
    # 1. Identify Flights based on Session Time resets
    df["Flight ID"] = (df["Session Time"].diff() < 0).cumsum()

    # 2. Determine if Engine was Run for each flight
    # Calculate max RPM for each flight
    flight_max_rpm = df.groupby("Flight ID")[["RPM L", "RPM R"]].max()

    # Create a boolean Series: True if any RPM > 0
    flights_with_engine = (flight_max_rpm["RPM L"] > 0) | (flight_max_rpm["RPM R"] > 0)

    # Map this status back to the original DataFrame
    df["Engine Run"] = df["Flight ID"].map(flights_with_engine)

    return df


def list_flights(df):
    """Prints a summary of all detected flights with Engine Run status."""
    stats = df.groupby("Flight ID").agg(
        Start_Time=("Session Time", "min"),
        End_Time=("Session Time", "max"),
        Duration=("Session Time", lambda x: x.max() - x.min()),
        Data_Points=("Session Time", "count"),
        Engine_Run=("Engine Run", "first"),  # All rows in a flight have the same value
        Max_RPM=("RPM L", "max"),  # showing RPM L as an example
    )
    print("\n--- Detected Flights ---")
    print(stats)
    return stats


def list_signals(df):
    """Lists all available signal columns."""
    columns = [
        col
        for col in df.columns
        if col not in ["Flight ID", "Unnamed: 103", "Engine Run"]
    ]
    print("\n--- Available Signals ---")
    for i, col in enumerate(columns):
        print(f"{i}: {col}")
    return columns


def plot_flight(df, flight_id, signal_names):
    """Plots the selected signals for a specific flight."""
    flight_data = df[df["Flight ID"] == flight_id]

    if flight_data.empty:
        print(f"No data found for Flight ID {flight_id}")
        return

    num_signals = len(signal_names)
    fig, axes = plt.subplots(num_signals, 1, figsize=(12, 4 * num_signals), sharex=True)

    if num_signals == 1:
        axes = [axes]

    for ax, signal in zip(axes, signal_names):
        ax.plot(flight_data["Session Time"], flight_data[signal])
        ax.set_ylabel(signal)
        ax.grid(True)
        ax.set_title(f"{signal} over Time")

    axes[-1].set_xlabel("Session Time (seconds)")
    fig.suptitle(
        f"Flight {flight_id} Analysis (Engine Run: {flight_data['Engine Run'].iloc[0]})",
        fontsize=16,
    )
    plt.tight_layout()
    plt.show()


def main():
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = input("Enter the path to your CSV file: ")

    df = load_data(filename)
    if df is not None:
        df = process_flights(df)

        while True:
            list_flights(df)

            try:
                flight_input = input("\nEnter Flight ID to analyze (or 'q' to quit): ")
                if flight_input.lower() == "q":
                    break
                flight_id = int(flight_input)

                available_cols = list_signals(df)

                signal_input = input(
                    "\nEnter signal numbers or names to plot (comma separated, e.g., '6,7' or 'Pitch (deg),Roll (deg)'): "
                )
                selected_signals = []

                # Parse signal input
                parts = [p.strip() for p in signal_input.split(",")]
                for p in parts:
                    if p.isdigit() and int(p) < len(available_cols):
                        selected_signals.append(available_cols[int(p)])
                    elif p in available_cols:
                        selected_signals.append(p)
                    else:
                        print(f"Warning: Signal '{p}' not recognized.")

                if selected_signals:
                    plot_flight(df, flight_id, selected_signals)
                else:
                    print("No valid signals selected.")

            except ValueError:
                print("Invalid input. Please enter a number.")
            except Exception as e:
                print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
