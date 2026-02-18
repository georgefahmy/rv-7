import sys

import FreeSimpleGUI as sg
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


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
    flight_max_cht = df.groupby("Flight ID")[
        ["CHT 1 (deg C)", "CHT 2 (deg C)", "CHT 3 (deg C)", "CHT 4 (deg C)"]
    ].max()
    df["Max CHT"] = df["Flight ID"].map(flight_max_cht.max(axis=1))

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
        Max_CHT=("Max CHT", "max"),  # showing RPM L as an example
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


def plot_flight(df, flight_id, signal_names, canvas):
    """Plots the selected signals for a specific flight inside the GUI canvas."""
    flight_data = df[df["Flight ID"] == flight_id]

    if flight_data.empty:
        return

    fig = plt.Figure(figsize=(8, 4), dpi=100)
    ax = fig.add_subplot(111)

    for signal in signal_names:
        ax.plot(flight_data["Session Time"], flight_data[signal], label=signal)

    ax.set_xlabel("Session Time (seconds)")
    ax.set_ylabel("Signal Value")
    ax.set_title(
        f"Flight {flight_id} Analysis "
        f"(Engine Run: {flight_data['Engine Run'].iloc[0]})"
    )
    ax.grid(True)
    ax.legend()

    # Clear previous canvas content
    for child in canvas.winfo_children():
        child.destroy()

    figure_canvas = FigureCanvasTkAgg(fig, master=canvas)
    figure_canvas.draw()
    figure_canvas.get_tk_widget().pack(fill="both", expand=1)


def main():
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = sg.popup_get_file(
            "Select your CSV file", file_types=(("CSV Files", "*.csv"),)
        )
        if not filename:
            return

    df = load_data(filename)
    if df is None:
        sg.popup_error("Failed to load file.")
        return

    df = process_flights(df)

    flight_stats = df.groupby("Flight ID").agg(
        Start_Time=("Session Time", "min"),
        End_Time=("Session Time", "max"),
        Duration=("Session Time", lambda x: x.max() - x.min()),
        Data_Points=("Session Time", "count"),
        Engine_Run=("Engine Run", "first"),
        Max_RPM=("RPM L", "max"),
        Max_CHT=("Max CHT", "max"),
    )

    flight_ids = sorted(df["Flight ID"].unique())
    available_signals = [
        col
        for col in df.columns
        if col not in ["Flight ID", "Unnamed: 103", "Engine Run"]
    ]

    layout = [
        [sg.Text("Flight Summary:")],
        [
            sg.Multiline(
                size=(100, 6),
                key="-SUMMARY-",
                disabled=True,
                autoscroll=False,
            )
        ],
        [
            sg.Text("Select Flight ID:"),
            sg.Combo(
                flight_ids,
                key="-FLIGHT-",
                readonly=True,
                enable_events=True,
            ),
        ],
        [sg.Text("Select Signals to Plot:")],
        [
            sg.Listbox(
                available_signals,
                select_mode=sg.SELECT_MODE_MULTIPLE,
                size=(50, 8),
                key="-SIGNALS-",
            )
        ],
        [sg.Button("Plot"), sg.Button("Exit")],
        [sg.Canvas(key="-CANVAS-", expand_x=True, expand_y=True)],
    ]

    window = sg.Window("Dynon Flight Analyzer", layout)

    while True:
        event, values = window.read()
        if event in (sg.WINDOW_CLOSED, "Exit"):
            break

        if event == "-FLIGHT-" and values["-FLIGHT-"] is not None:
            fid = values["-FLIGHT-"]
            stats = flight_stats.loc[fid]
            summary_text = (
                f"Flight ID: {fid}\n"
                f"Start Time: {stats['Start_Time']}\n"
                f"End Time: {stats['End_Time']}\n"
                f"Duration: {stats['Duration']} sec\n"
                f"Data Points: {stats['Data_Points']}\n"
                f"Engine Run: {stats['Engine_Run']}\n"
                f"Max RPM: {stats['Max_RPM']}\n"
                f"Max CHT: {stats['Max_CHT']}\n"
            )
            window["-SUMMARY-"].update(summary_text)

        if event == "Plot":
            flight_id = values["-FLIGHT-"]
            selected_signals = values["-SIGNALS-"]

            if flight_id is None:
                sg.popup_warning("Please select a Flight ID.")
                continue

            if not selected_signals:
                sg.popup_warning("Please select at least one signal.")
                continue

            plot_flight(
                df,
                flight_id,
                selected_signals,
                window["-CANVAS-"].TKCanvas,
            )

    window.close()


if __name__ == "__main__":
    main()
