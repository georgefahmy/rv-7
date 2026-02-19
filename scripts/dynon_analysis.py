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


def plot_flight(df, flight_id, left_signal, right_signal, canvas):
    """Plots two selected signals on dual y-axes inside the GUI canvas."""
    flight_data = df[df["Flight ID"] == flight_id]

    if flight_data.empty:
        return

    fig = plt.Figure(figsize=(8, 4), dpi=100)
    fig.subplots_adjust(right=0.85)
    ax_left = fig.add_subplot(111)
    ax_right = ax_left.twinx()

    # Plot left axis signal
    if left_signal:
        if left_signal == "CHT":
            cht_columns = [
                "CHT 1 (deg C)",
                "CHT 2 (deg C)",
                "CHT 3 (deg C)",
                "CHT 4 (deg C)",
            ]
            for col in cht_columns:
                if col in flight_data.columns:
                    ax_left.plot(
                        flight_data["Session Time"],
                        flight_data[col],
                        label=col,
                    )
            ax_left.set_ylabel("CHT (deg C)")
        elif left_signal == "EGT":
            egt_columns = [
                "EGT 1 (deg C)",
                "EGT 2 (deg C)",
                "EGT 3 (deg C)",
                "EGT 4 (deg C)",
            ]
            for col in egt_columns:
                if col in flight_data.columns:
                    ax_left.plot(
                        flight_data["Session Time"],
                        flight_data[col],
                        label=col,
                    )
            ax_left.set_ylabel("EGT (deg C)")
        else:
            ax_left.plot(
                flight_data["Session Time"],
                flight_data[left_signal],
                label=left_signal,
            )
            ax_left.set_ylabel(left_signal)

    # Plot right axis signal
    if right_signal:
        if right_signal == "CHT":
            cht_columns = [
                "CHT 1 (deg C)",
                "CHT 2 (deg C)",
                "CHT 3 (deg C)",
                "CHT 4 (deg C)",
            ]
            for col in cht_columns:
                if col in flight_data.columns:
                    ax_right.plot(
                        flight_data["Session Time"],
                        flight_data[col],
                        linestyle="dashed",
                        label=col,
                    )
            ax_right.set_ylabel("CHT (deg C)")
        elif right_signal == "EGT":
            egt_columns = [
                "EGT 1 (deg C)",
                "EGT 2 (deg C)",
                "EGT 3 (deg C)",
                "EGT 4 (deg C)",
            ]
            for col in egt_columns:
                if col in flight_data.columns:
                    ax_right.plot(
                        flight_data["Session Time"],
                        flight_data[col],
                        linestyle="dashed",
                        label=col,
                    )
            ax_right.set_ylabel("EGT (deg C)")
        else:
            ax_right.plot(
                flight_data["Session Time"],
                flight_data[right_signal],
                linestyle="dashed",
                label=right_signal,
                color="red",
            )
            ax_right.set_ylabel(right_signal)

    ax_left.set_xlabel("Session Time (seconds)")
    ax_left.set_title(
        f"Flight {flight_id} Analysis "
        f"(Engine Run: {flight_data['Engine Run'].iloc[0]})"
    )
    ax_left.grid(True)

    # Combine legends
    lines_left, labels_left = ax_left.get_legend_handles_labels()
    lines_right, labels_right = ax_right.get_legend_handles_labels()
    ax_left.legend(lines_left + lines_right, labels_left + labels_right)

    # Clear previous canvas content
    for child in canvas.winfo_children():
        child.destroy()

    figure_canvas = FigureCanvasTkAgg(fig, master=canvas)
    figure_canvas.draw()
    widget = figure_canvas.get_tk_widget()
    widget.pack(fill="both", expand=1)

    # Add scrubbable vertical cursor
    cursor_line = ax_left.axvline(x=flight_data["Session Time"].iloc[0], linestyle="--")

    def on_mouse_move(event):
        if event.inaxes == ax_left:
            cursor_line.set_xdata(event.xdata)
            figure_canvas.draw_idle()

    fig.canvas.mpl_connect("motion_notify_event", on_mouse_move)


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
    available_signals = sorted(
        [
            col
            for col in df.columns
            if col
            not in [
                "Flight ID",
                "Unnamed: 103",
                "Engine Run",
                "Max CHT",
                "AP Yaw Force",
                "AP Yaw Position",
                "AP Yaw Slip (bool)",
                "Session Time",
            ]
        ]
    )

    # Add synthetic combined CHT signal
    if "CHT" not in available_signals:
        available_signals.append("CHT")
        available_signals = sorted(available_signals)
        # Add synthetic combined CHT signal
    if "EGT" not in available_signals:
        available_signals.append("EGT")
        available_signals = sorted(available_signals)

    layout = [
        [
            sg.Text("Select Flight ID:"),
            sg.Combo(
                flight_ids,
                key="-FLIGHT-",
                readonly=True,
                enable_events=True,
            ),
            sg.Button("Exit"),
        ],
        [sg.Text("Flight Summary:", font=("Arial", 16))],
        [sg.Text(size=(50, 8), key="-SUMMARY-")],
        [
            sg.Text("Select Left Axis Signal:"),
            sg.Combo(
                available_signals,
                key="-LEFT_SIGNAL_1-",
                readonly=True,
                enable_events=True,
                size=(30, 1),
            ),
            sg.VerticalSeparator(),
            sg.Text("Select Right Axis Signal:"),
            sg.Combo(
                available_signals,
                key="-RIGHT_SIGNAL_1-",
                readonly=True,
                enable_events=True,
                size=(30, 1),
            ),
        ],
        [sg.Canvas(key="-CANVAS_1-", expand_x=True, expand_y=True)],
        [
            sg.Text("Select Left Axis Signal:"),
            sg.Combo(
                available_signals,
                key="-LEFT_SIGNAL_2-",
                readonly=True,
                enable_events=True,
                size=(30, 1),
            ),
            sg.VerticalSeparator(),
            sg.Text("Select Right Axis Signal:"),
            sg.Combo(
                available_signals,
                key="-RIGHT_SIGNAL_2-",
                readonly=True,
                enable_events=True,
                size=(30, 1),
            ),
        ],
        [sg.Canvas(key="-CANVAS_2-", expand_x=True, expand_y=True)],
    ]

    window = sg.Window(
        "Dynon Flight Analyzer", layout=layout, resizable=True, finalize=True
    )
    window.maximize()

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

        if event in ("-LEFT_SIGNAL_1-", "-RIGHT_SIGNAL_1-"):
            flight_id = values["-FLIGHT-"]
            left_signal_1 = values["-LEFT_SIGNAL_1-"]
            right_signal_1 = values["-RIGHT_SIGNAL_1-"]

            if flight_id is None:
                sg.popup("Please select a Flight ID.")
                continue

            if not left_signal_1 and not right_signal_1:
                sg.popup("Please select at least one signal.")
                continue

            plot_flight(
                df,
                flight_id,
                left_signal_1,
                right_signal_1,
                window["-CANVAS_1-"].TKCanvas,
            )
        if event in ("-LEFT_SIGNAL_2-", "-RIGHT_SIGNAL_2-"):
            flight_id = values["-FLIGHT-"]
            left_signal_2 = values["-LEFT_SIGNAL_2-"]
            right_signal_2 = values["-RIGHT_SIGNAL_2-"]

            if flight_id is None:
                sg.popup("Please select a Flight ID.")
                continue

            if not left_signal_2 and not right_signal_2:
                sg.popup("Please select at least one signal.")
                continue

            plot_flight(
                df,
                flight_id,
                left_signal_2,
                right_signal_2,
                window["-CANVAS_2-"].TKCanvas,
            )

    window.close()


if __name__ == "__main__":
    main()
