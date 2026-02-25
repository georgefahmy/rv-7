import matplotlib
import matplotlib.pyplot as plt

# import numpy as np
import pandas as pd

# import FreeSimpleGUI as sg
import PySimpleGUI as sg
from airspeed_calibration import analyze_flight_data
from geopy.distance import geodesic
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.widgets import RectangleSelector

matplotlib.use("TkAgg")
ground_track = {
    "lat": None,
    "lon": None,
    "time": None,
    "marker": None,
    "canvas": None,
}
# --- Ground track sync globals ---
ground_track_lat = None
ground_track_lon = None
ground_track_time = None
ground_track_marker = None
ground_track_canvas = None


def load_data(filepath):
    """Loads the CSV file."""
    try:
        # Skip metadata rows if necessary, but standard read_csv usually works
        df = pd.read_csv(filepath, low_memory=False)
        return df
    except Exception as e:
        print(f"Error loading file: {e}")
        return None


def process_flights(df):
    """
    Groups data into flights and marks if the engine was run.
    """
    # Remove rows where System Time is NaN or blank
    df = df[df["System Time"].notna() & (df["System Time"] != "")]

    # Remove rows where GPS Date & Time is NaN or blank
    df = df[df["GPS Date & Time"].notna() & (df["GPS Date & Time"] != "")]

    # Convert all temperature columns from deg C to deg F
    temp_cols = [col for col in df.columns if "(deg C)" in col]

    for col in temp_cols:
        try:
            # Force numeric conversion to prevent string math errors
            df[col] = pd.to_numeric(df[col], errors="coerce")

            # Convert C to F
            df[col] = df[col] * 9.0 / 5.0 + 32.0

            # Rename column to deg F
            new_name = col.replace("(deg C)", "(deg F)")
            df.rename(columns={col: new_name}, inplace=True)

        except Exception as e:
            print(f"Warning: Temperature conversion failed for column '{col}': {e}")

    # 1. Identify Flights based on Session Time resets
    df["_orig_flight_num"] = (df["Session Time"].diff() < 0).cumsum()
    # Ensure System Time is numeric and fill NaNs with 0 to prevent aggregation errors
    df["System Time"] = pd.to_numeric(df["System Time"], errors="coerce").fillna(0)

    # Ensure RPM L and RPM R are numeric and fill NaNs with 0
    for col in ["RPM L", "RPM R"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    # Create combined RPM signal as average of left and right
    df["RPM"] = (df["RPM L"] + df["RPM R"]) / 2

    # --- Compute Fuel Flow Integral (gallons) per flight ---
    # Ensure Fuel Flow 1 is numeric
    if "Fuel Flow 1 (gal/hr)" in df.columns:
        df["Fuel Flow 1 (gal/hr)"] = pd.to_numeric(
            df["Fuel Flow 1 (gal/hr)"], errors="coerce"
        ).fillna(0)

        # Compute integral (gallons) per flight using trapezoidal rule over Session Time
        df["Fuel Flow Integral"] = 0.0

        for fid, group in df.groupby("_orig_flight_num"):
            times = group["Session Time"].values
            flow = group["Fuel Flow 1 (gal/hr)"].values

            if len(times) > 1:
                # Convert gal/hr to gal/sec before integrating
                flow_gps = flow / 3600.0
                integral = [0.0]
                for i in range(1, len(times)):
                    dt = times[i] - times[i - 1]
                    area = 0.5 * (flow_gps[i] + flow_gps[i - 1]) * dt
                    integral.append(integral[-1] + area)
                df.loc[group.index, "Fuel Flow Integral"] = integral
            else:
                df.loc[group.index, "Fuel Flow Integral"] = 0.0

    # 2. Determine if Engine was Run for each flight
    # Calculate max RPM for each flight
    flight_max_rpm = df.groupby("_orig_flight_num")[["RPM L", "RPM R"]].max()
    flight_max_cht = df.groupby("_orig_flight_num")[
        [
            "CHT 1 (deg F)",
            "CHT 2 (deg F)",
            "CHT 3 (deg F)",
            "CHT 4 (deg F)",
        ]
    ].max()
    df["Max CHT"] = df["_orig_flight_num"].map(flight_max_cht.max(axis=1))

    # Create a boolean Series: True if any RPM > 0 and CHT > 125
    flights_with_engine = (
        (flight_max_rpm["RPM L"] > 0) | (flight_max_rpm["RPM R"] > 0)
    ) & (flight_max_cht.max(axis=1) > 125)

    # Compute first GPS Date & Time for each flight
    flight_start_gps = df.groupby("_orig_flight_num")["GPS Date & Time"].first()

    # Map this status back to the original DataFrame
    df["Engine Run"] = df["_orig_flight_num"].map(flights_with_engine)

    # Assign sequential Flight IDs as "<seq> - <GPS Date & Time>" for engine-run flights, else NaN
    engine_flight_ids = [
        fid
        for fid in df["_orig_flight_num"].unique()
        if flights_with_engine.get(fid, False)
    ]

    # Map: _orig_flight_num -> "<seq> - <GPS Date & Time>"
    flightid_map = {
        fid: f"{flight_start_gps.get(fid, '')} - Flight {idx + 1}"
        for idx, fid in enumerate(engine_flight_ids)
    }

    df["Flight ID"] = df["_orig_flight_num"].map(lambda x: flightid_map.get(x, None))
    df.drop(columns=["_orig_flight_num"], inplace=True)

    # Fill any null or NaN values in the DataFrame with 0 to ensure consistent datatypes
    df.fillna(0, inplace=True)

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
    # print("\n--- Detected Flights ---")
    # print(stats)
    return stats


def list_signals(df):
    """Lists all available signal columns."""
    columns = [
        col
        for col in df.columns
        if col not in ["Flight ID", "Unnamed: 103", "Engine Run"]
    ]
    # print("\n--- Available Signals ---")
    # for i, col in enumerate(columns):
    #     print(f"{i}: {col}")
    return columns


# --- Helper function to export each flight to its own CSV file ---
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
        date_part = fid_str.split()[0]  # First token should be date

        # Create subfolder for that date
        date_folder = os.path.join(output_dir, date_part)
        if not os.path.exists(date_folder):
            os.makedirs(date_folder)

        # Clean filename
        safe_name = fid_str.replace("/", "-").replace(":", "-")
        filepath = os.path.join(date_folder, f"{safe_name}.csv")

        flight_data.to_csv(filepath, index=False)


def plot_flight(df, flight_id, left_signal, right_signal, canvas):
    """Plots two selected signals on dual y-axes inside the GUI canvas."""
    flight_data = df[df["Flight ID"] == flight_id]

    if flight_data.empty:
        return

    fig = plt.Figure(figsize=(8, 4), dpi=100)
    fig.subplots_adjust(right=0.75)
    ax_left = fig.add_subplot(111)
    ax_right = ax_left.twinx()

    # Plot left axis signal
    if left_signal and left_signal != "None":
        if left_signal == "CHT":
            cht_columns = [
                "CHT 1 (deg F)",
                "CHT 2 (deg F)",
                "CHT 3 (deg F)",
                "CHT 4 (deg F)",
            ]
            for col in cht_columns:
                if col in flight_data.columns:
                    ax_left.plot(
                        flight_data["Session Time"],
                        flight_data[col],
                        label=col,
                    )
            ax_left.set_ylabel("CHT (deg F)")
        elif left_signal == "EGT":
            egt_columns = [
                "EGT 1 (deg F)",
                "EGT 2 (deg F)",
                "EGT 3 (deg F)",
                "EGT 4 (deg F)",
            ]
            for col in egt_columns:
                if col in flight_data.columns:
                    ax_left.plot(
                        flight_data["Session Time"],
                        flight_data[col],
                        label=col,
                    )
            ax_left.set_ylabel("EGT (deg F)")
        else:
            ax_left.plot(
                flight_data["Session Time"],
                flight_data[left_signal],
                label=left_signal,
            )
            ax_left.set_ylabel(left_signal)

    # Plot right axis signal
    if right_signal and right_signal != "None":
        if right_signal == "CHT":
            cht_columns = [
                "CHT 1 (deg F)",
                "CHT 2 (deg F)",
                "CHT 3 (deg F)",
                "CHT 4 (deg F)",
            ]
            for col in cht_columns:
                if col in flight_data.columns:
                    ax_right.plot(
                        flight_data["Session Time"],
                        flight_data[col],
                        linestyle="dashed",
                        label=col,
                    )
            ax_right.set_ylabel("CHT (deg F)")
        elif right_signal == "EGT":
            egt_columns = [
                "EGT 1 (deg F)",
                "EGT 2 (deg F)",
                "EGT 3 (deg F)",
                "EGT 4 (deg F)",
            ]
            for col in egt_columns:
                if col in flight_data.columns:
                    ax_right.plot(
                        flight_data["Session Time"],
                        flight_data[col],
                        linestyle="dashed",
                        label=col,
                    )
            ax_right.set_ylabel("EGT (deg F)")
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

    # Combine legends and place completely outside plot on the right
    lines_left, labels_left = ax_left.get_legend_handles_labels()
    lines_right, labels_right = ax_right.get_legend_handles_labels()
    ax_left.legend(
        lines_left + lines_right,
        labels_left + labels_right,
        loc="lower left",
        bbox_to_anchor=(1.05, 0.5),
        borderaxespad=3,
    )

    # Clear previous canvas content
    for child in canvas.winfo_children():
        child.destroy()

    figure_canvas = FigureCanvasTkAgg(fig, master=canvas)
    figure_canvas.draw()
    widget = figure_canvas.get_tk_widget()
    widget.pack(fill="both", expand=1)

    # Add real-time hover vertical cursor with value display
    ylim_left = ax_left.get_ylim()
    ylim_right = ax_right.get_ylim()
    # xlim = ax_left.get_xlim()
    (cursor_line,) = ax_left.plot(
        [flight_data["Session Time"].iloc[0]] * 2, ylim_left, linestyle="--"
    )

    # Text box for displaying values
    value_text = ax_left.text(
        0,
        1,
        "",
        transform=ax_left.transData,
        verticalalignment="top",
        horizontalalignment="left",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
    )

    session_time = flight_data["Session Time"].values

    def on_motion(event):
        if event.inaxes in (ax_left, ax_right) and event.xdata is not None:
            # Move vertical line
            cursor_line.set_xdata([event.xdata, event.xdata])

            # Find nearest index
            idx = (abs(session_time - event.xdata)).argmin()
            global ground_track

            if (
                ground_track["time"] is not None
                and ground_track["marker"] is not None
                and event.xdata is not None
            ):
                idx = (abs(ground_track["time"] - event.xdata)).argmin()
                if idx < len(ground_track["lat"]):
                    x_val = float(ground_track["lon"][idx])
                    y_val = float(ground_track["lat"][idx])

                    marker = ground_track["marker"]
                    marker.set_data([x_val], [y_val])
                    ground_track["canvas"].draw_idle()
            # Prepare display string
            display_lines = [f"Time: {session_time[idx]:.2f} sec"]

            # Left axis signals
            if left_signal and left_signal != "None":
                if left_signal == "CHT":
                    for col in [
                        "CHT 1 (deg F)",
                        "CHT 2 (deg F)",
                        "CHT 3 (deg F)",
                        "CHT 4 (deg F)",
                    ]:
                        if col in flight_data.columns:
                            display_lines.append(
                                f"{col}: {flight_data[col].iloc[idx]:.1f}"
                            )
                elif left_signal == "EGT":
                    for col in [
                        "EGT 1 (deg F)",
                        "EGT 2 (deg F)",
                        "EGT 3 (deg F)",
                        "EGT 4 (deg F)",
                    ]:
                        if col in flight_data.columns:
                            display_lines.append(
                                f"{col}: {flight_data[col].iloc[idx]:.1f}"
                            )
                else:
                    display_lines.append(
                        f"{left_signal}: {flight_data[left_signal].iloc[idx]:.2f}"
                    )

            # Right axis signals
            if right_signal and right_signal != "None":
                if right_signal == "CHT":
                    for col in [
                        "CHT 1 (deg F)",
                        "CHT 2 (deg F)",
                        "CHT 3 (deg F)",
                        "CHT 4 (deg F)",
                    ]:
                        if col in flight_data.columns:
                            display_lines.append(
                                f"{col}: {flight_data[col].iloc[idx]:.1f}"
                            )
                elif right_signal == "EGT":
                    for col in [
                        "EGT 1 (deg F)",
                        "EGT 2 (deg F)",
                        "EGT 3 (deg F)",
                        "EGT 4 (deg F)",
                    ]:
                        if col in flight_data.columns:
                            display_lines.append(
                                f"{col}: {flight_data[col].iloc[idx]:.1f}"
                            )
                else:
                    display_lines.append(
                        f"{right_signal}: {flight_data[right_signal].iloc[idx]:.2f}"
                    )

            # Update text box to appear on the right side of the cursor, slightly below the top of the axis
            x = event.xdata
            ylim_top = ax_left.get_ylim()[1]
            y = ylim_top - 0.60 * (ylim_top - ax_left.get_ylim()[0])  # 70% below top
            value_text.set_position(
                (x + 0.01 * (ax_left.get_xlim()[1] - ax_left.get_xlim()[0]), y)
            )
            value_text.set_text("\n".join(display_lines))

            figure_canvas.draw_idle()

    figure_canvas.mpl_connect("motion_notify_event", on_motion)

    # --- Add RectangleSelector for click-and-drag zoom ---
    def on_select(eclick, erelease):
        # eclick and erelease are matplotlib events at press and release
        x1, y1 = eclick.xdata, eclick.ydata
        x2, y2 = erelease.xdata, erelease.ydata
        if x1 is None or x2 is None or y1 is None or y2 is None:
            return
        # Set new X limits for both axes
        new_xlim = (min(x1, x2), max(x1, x2))

        # --- Compute new Y-limits for left axis based on the selected left signal(s) ---
        if left_signal and left_signal != "None":
            if left_signal == "CHT":
                left_cols = [
                    "CHT 1 (deg F)",
                    "CHT 2 (deg F)",
                    "CHT 3 (deg F)",
                    "CHT 4 (deg F)",
                ]
                ydata_left = []
                mask = (flight_data["Session Time"] >= new_xlim[0]) & (
                    flight_data["Session Time"] <= new_xlim[1]
                )
                for col in left_cols:
                    if col in flight_data.columns:
                        ydata_left.extend(flight_data.loc[mask, col].values.tolist())
                if ydata_left:
                    new_ylim_left = (min(ydata_left), max(ydata_left))
                else:
                    new_ylim_left = ax_left.get_ylim()
            elif left_signal == "EGT":
                left_cols = [
                    "EGT 1 (deg F)",
                    "EGT 2 (deg F)",
                    "EGT 3 (deg F)",
                    "EGT 4 (deg F)",
                ]
                ydata_left = []
                mask = (flight_data["Session Time"] >= new_xlim[0]) & (
                    flight_data["Session Time"] <= new_xlim[1]
                )
                for col in left_cols:
                    if col in flight_data.columns:
                        ydata_left.extend(flight_data.loc[mask, col].values.tolist())
                if ydata_left:
                    new_ylim_left = (min(ydata_left), max(ydata_left))
                else:
                    new_ylim_left = ax_left.get_ylim()
            else:
                mask = (flight_data["Session Time"] >= new_xlim[0]) & (
                    flight_data["Session Time"] <= new_xlim[1]
                )
                ydata_left = flight_data.loc[mask, left_signal].values
                if len(ydata_left) > 0:
                    new_ylim_left = (min(ydata_left), max(ydata_left))
                else:
                    new_ylim_left = ax_left.get_ylim()
        else:
            new_ylim_left = ax_left.get_ylim()

        # --- Compute new Y-limits for right axis based on the selected right signal(s) ---
        if right_signal and right_signal != "None":
            if right_signal == "CHT":
                right_cols = [
                    "CHT 1 (deg F)",
                    "CHT 2 (deg F)",
                    "CHT 3 (deg F)",
                    "CHT 4 (deg F)",
                ]
                ydata_right = []
                mask = (flight_data["Session Time"] >= new_xlim[0]) & (
                    flight_data["Session Time"] <= new_xlim[1]
                )
                for col in right_cols:
                    if col in flight_data.columns:
                        ydata_right.extend(flight_data.loc[mask, col].values.tolist())
                if ydata_right:
                    new_ylim_right = (min(ydata_right), max(ydata_right))
                else:
                    new_ylim_right = ax_right.get_ylim()
            elif right_signal == "EGT":
                right_cols = [
                    "EGT 1 (deg F)",
                    "EGT 2 (deg F)",
                    "EGT 3 (deg F)",
                    "EGT 4 (deg F)",
                ]
                ydata_right = []
                mask = (flight_data["Session Time"] >= new_xlim[0]) & (
                    flight_data["Session Time"] <= new_xlim[1]
                )
                for col in right_cols:
                    if col in flight_data.columns:
                        ydata_right.extend(flight_data.loc[mask, col].values.tolist())
                if ydata_right:
                    new_ylim_right = (min(ydata_right), max(ydata_right))
                else:
                    new_ylim_right = ax_right.get_ylim()
            else:
                mask = (flight_data["Session Time"] >= new_xlim[0]) & (
                    flight_data["Session Time"] <= new_xlim[1]
                )
                ydata_right = flight_data.loc[mask, right_signal].values
                if len(ydata_right) > 0:
                    new_ylim_right = (min(ydata_right), max(ydata_right))
                else:
                    new_ylim_right = ax_right.get_ylim()
        else:
            new_ylim_right = ax_right.get_ylim()

        # Avoid identical y-limits (singularity), expand by small epsilon if needed
        def fix_ylim(lim):
            if lim[0] == lim[1]:
                eps = 1e-6
                return (lim[0] - eps, lim[1] + eps)
            else:
                return (lim[0] - (lim[0] * 0.01), lim[1] + (lim[1] * 0.01))
            return lim

        new_ylim_left = fix_ylim(new_ylim_left)
        new_ylim_right = fix_ylim(new_ylim_right)
        ax_left.set_xlim(*new_xlim)
        ax_left.set_ylim(*new_ylim_left)
        ax_right.set_xlim(*new_xlim)
        ax_right.set_ylim(*new_ylim_right)
        figure_canvas.draw_idle()

    # RectangleSelector for zoom
    # Connect to the axes, set interactive=True, do not use useblit for TkAgg
    selector = RectangleSelector(
        ax_left,  # connect to the axes, not the figure canvas
        on_select,
        button=[1],  # Left mouse button
        spancoords="data",
        interactive=False,
        props=dict(facecolor="blue", alpha=0.3),
    )
    # Make sure selector is not garbage-collected: attach to the figure or canvas
    # Attach to the underlying Tk widget so it persists as long as the plot is visible
    widget.selector = selector
    # Explicitly draw the canvas after creating the selector to ensure it appears
    figure_canvas.draw_idle()

    # Add left double-click to reset zoom
    def on_press(event):
        # Respond to left double-clicks (button 1) anywhere on the figure
        if event.dblclick and event.button == 1:
            # Reset both axes (left and right) to full x/y range
            x_min = flight_data["Session Time"].min()
            x_max = flight_data["Session Time"].max()
            # Left axis
            ax_left.set_xlim(x_min, x_max)
            ax_left.set_ylim(ylim_left)
            # Right axis
            ax_right.set_xlim(x_min, x_max)
            ax_right.set_ylim(ylim_right)
            figure_canvas.draw_idle()
            # Hide rectangle after selection so it does not block right-clicks
            selector.set_visible(False)

    # Connect to button_press_event to detect left double-clicks
    figure_canvas.mpl_connect("button_press_event", on_press)


def main():
    df = None
    flight_stats = None
    flight_ids = []
    available_signals = []

    layout = [
        [
            sg.Text("Input CSV File:", font=("Arial", 16)),
            sg.Input(
                key="-FILE-",
                enable_events=True,
                readonly=True,
                size=(60, 1),
                font=("Arial", 16),
                disabled_readonly_background_color="white",
            ),
            sg.FileBrowse(file_types=(("CSV Files", "*.csv"),), font=("Arial", 16)),
        ],
        [sg.HorizontalSeparator()],
        [
            sg.Text("Select Flight ID:", font=("Arial", 22)),
            sg.Combo(
                [],
                key="-FLIGHT-",
                readonly=True,
                enable_events=True,
                font=("Arial", 18),
                size=(30, 1),
            ),
            sg.Text(expand_x=True),
            sg.Button("Export Flights", font=("Arial", 16)),
            sg.Button("Exit", font=("Arial", 16)),
        ],
        [sg.HorizontalSeparator()],
        [
            sg.Text(
                "Flight Summary: ",
                font=("Arial", 18),
            ),
            sg.Text(expand_x=True),
            sg.Text(
                "Start",
                font=("Arial", 16),
            ),
            sg.Input(
                key="-START_MANUEVER-",
                size=(10, 1),
                font=("Arial", 16),
            ),
            sg.Text(
                "End",
                font=("Arial", 16),
            ),
            sg.Input(
                key="-END_MANUEVER-",
                size=(10, 1),
                font=("Arial", 16),
            ),
            sg.Button(
                "Airspeed Calibration",
                key="-AIRSPEED_CALIBRATION-",
                font=("Arial", 16),
            ),
        ],
        [
            sg.Text(size=(50, 8), key="-SUMMARY-", font=("Arial", 14)),
            sg.Text(expand_x=True),
            sg.Text(size=(50, 8), key="-ASI_CALIBRATION-", font=("Arial", 14)),
        ],
        [sg.HorizontalSeparator()],
        [
            sg.Column(
                expand_x=True,
                expand_y=True,
                layout=[
                    [
                        sg.Text("Left Axis Signal:", font=("Arial", 16)),
                        sg.Combo(
                            [],
                            key="-LEFT_SIGNAL_1-",
                            readonly=True,
                            enable_events=True,
                            size=(30, 1),
                            font=("Arial", 16),
                        ),
                        sg.Text(expand_x=True),
                        sg.Text("Right Axis Signal:", font=("Arial", 16)),
                        sg.Combo(
                            [],
                            key="-RIGHT_SIGNAL_1-",
                            readonly=True,
                            enable_events=True,
                            size=(30, 1),
                            font=("Arial", 16),
                        ),
                    ],
                    [sg.HorizontalSeparator()],
                    [
                        sg.Canvas(key="-CANVAS_1-", expand_x=True, expand_y=True),
                    ],
                ],
            ),
            sg.VerticalSeparator(),
            sg.Column(
                expand_x=True,
                expand_y=True,
                layout=[
                    [
                        sg.Text("Flight Path", font=("Arial", 16), expand_x=True),
                    ],
                    [sg.HorizontalSeparator()],
                    [
                        sg.Canvas(key="-CANVAS_2-", expand_x=True, expand_y=True),
                    ],
                ],
            ),
        ],
        [
            sg.HorizontalSeparator(),
        ],
        [
            sg.Text(
                "No file loaded",
                key="-STATUS-",
                font=("Arial", 14),
                expand_x=True,
                justification="left",
            )
        ],
    ]

    window = sg.Window(
        "Dynon Flight Analyzer", layout=layout, resizable=True, finalize=True
    )
    window.maximize()
    # window.write_event_value(key="-FLIGHT-", value=flight_ids[-1])  # <--- REMOVE this line
    # window.write_event_value(key="-LEFT_SIGNAL_1-", value="CHT")

    while True:
        event, values = window.read()
        if event in (sg.WINDOW_CLOSED, "Exit"):
            break

        # --- Handle file selection and load ---
        if event == "-FILE-" and values["-FILE-"]:
            filename = values["-FILE-"]

            # Show loading spinner
            sg.popup_animated(
                sg.DEFAULT_BASE64_LOADING_GIF,
                message="Loading file...",
                time_between_frames=50,
            )
            window.refresh()

            df_loaded = load_data(filename)
            if df_loaded is None:
                sg.popup_animated(None)
                sg.popup_error("Failed to load file.")
                continue

            df = process_flights(df_loaded)

            # Stop loading spinner
            sg.popup_animated(None)

            # Update status bar with current file
            window["-STATUS-"].update(f"Current File: {filename}")

            flight_stats = df.groupby("Flight ID").agg(
                Start_Time=("Session Time", "min"),
                End_Time=("Session Time", "max"),
                Duration=("Session Time", lambda x: x.max() - x.min()),
                Data_Points=("Session Time", "count"),
                Engine_Run=("Engine Run", "first"),
                Max_RPM=("RPM L", "max"),
                Max_CHT=("Max CHT", "max"),
            )

            flight_ids = sorted(flight_stats[flight_stats["Engine_Run"]].index.tolist())

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
                        "RPM L",
                        "RPM R",
                        "Fuel Flow 2 (gal/hr)",
                    ]
                ]
            )

            if "CHT" not in available_signals:
                available_signals.append("CHT")
            if "EGT" not in available_signals:
                available_signals.append("EGT")
            available_signals = sorted(available_signals)

            if "None" not in available_signals:
                available_signals = ["None"] + available_signals

            window["-FLIGHT-"].update(values=flight_ids)
            window["-LEFT_SIGNAL_1-"].update(values=available_signals)
            window["-RIGHT_SIGNAL_1-"].update(values=available_signals)

            # Set default signals
            if "CHT" in available_signals:
                window["-LEFT_SIGNAL_1-"].update(value="CHT")
                window.write_event_value(key="-LEFT_SIGNAL_1-", value="CHT")

            if "EGT" in available_signals:
                window["-RIGHT_SIGNAL_1-"].update(value="EGT")
                window.write_event_value(key="-RIGHT_SIGNAL_1-", value="EGT")

            if flight_ids:
                window["-FLIGHT-"].update(value=flight_ids[-1])
                window.write_event_value("-FLIGHT-", flight_ids[-1])

        if event == "Export Flights":
            folder = sg.popup_get_folder("Select folder to save flight CSV files")
            if folder and df is not None:
                save_flights_to_csv(df, folder)
                sg.popup("Flights exported successfully.")

        if (
            event == "-FLIGHT-"
            and values["-FLIGHT-"] is not None
            and flight_stats is not None
        ):
            fid = values["-FLIGHT-"]
            stats = flight_stats.loc[fid]
            summary_text = (
                f"Flight ID: {fid}\n"
                f"Start Time: {stats['Start_Time']}\n"
                f"End Time: {stats['End_Time']}\n"
                f"Duration: {stats['Duration']} sec - {round(stats['Duration'] / 60 , 2)} min\n"
                f"Data Points: {stats['Data_Points']}\n"
                f"Max RPM: {stats['Max_RPM']}\n"
                f"Max CHT: {stats['Max_CHT']}\n"
            )
            window["-SUMMARY-"].update(summary_text)

        if event in ("-LEFT_SIGNAL_1-", "-RIGHT_SIGNAL_1-", "-FLIGHT-"):
            flight_id = values["-FLIGHT-"]
            left_signal_1 = values["-LEFT_SIGNAL_1-"]
            right_signal_1 = values["-RIGHT_SIGNAL_1-"]

            if df is None or flight_id is None:
                continue

            plot_flight(
                df,
                flight_id,
                left_signal_1,
                right_signal_1,
                window["-CANVAS_1-"].TKCanvas,
            )

            # --- Plot 2D GPS Ground Track (Relative Distance in NM) Colored by IAS ---
            if "Latitude (deg)" in df.columns and "Longitude (deg)" in df.columns:
                # from geopy.distance import geodesic

                flight_data = df[df["Flight ID"] == flight_id]
                lat = flight_data["Latitude (deg)"].values
                lon = flight_data["Longitude (deg)"].values
                session_time_gt = flight_data["Session Time"].values

                # Compute relative distances from the first point in nautical miles
                origin = (lat[0], lon[0])
                x_dist = []  # East-West relative distance in NM
                y_dist = []  # North-South relative distance in NM

                for la, lo in zip(lat, lon):
                    # Compute North-South distance
                    north_south = geodesic((la, lon[0]), origin).nautical
                    # Compute East-West distance
                    east_west = geodesic((lat[0], lo), origin).nautical

                    # Adjust sign based on relative position
                    if la < lat[0]:
                        north_south *= -1
                    if lo < lon[0]:
                        east_west *= -1

                    y_dist.append(north_south)
                    x_dist.append(east_west)

                fig2, ax2 = plt.subplots()

                # Color by Indicated Airspeed if available
                if "Indicated Airspeed (knots)" in flight_data.columns:
                    ias = flight_data["Indicated Airspeed (knots)"].values
                    sc = ax2.scatter(x_dist, y_dist, c=ias, cmap="viridis", s=8)
                    cbar = fig2.colorbar(sc, ax=ax2, pad=0.1)
                    cbar.set_label("True Airspeed (knots)")
                else:
                    ax2.plot(x_dist, y_dist)

                ax2.set_xlabel("Relative East-West Distance (NM)")
                ax2.set_ylabel("Relative North-South Distance (NM)")
                ax2.set_title("GPS Ground Track (Relative Distance Colored by IAS)")
                ax2.grid(True)

                # Moving position marker (start at origin)
                (ground_track_marker,) = ax2.plot(
                    [x_dist[0]], [y_dist[0]], "ro", zorder=10
                )

                # Clear existing canvas
                for child in window["-CANVAS_2-"].TKCanvas.winfo_children():
                    child.destroy()

                canvas2 = FigureCanvasTkAgg(fig2, window["-CANVAS_2-"].TKCanvas)
                canvas2.draw()
                canvas2.get_tk_widget().pack(side="top", fill="both", expand=1)

                # Store globals for syncing
                ground_track["lat"] = y_dist
                ground_track["lon"] = x_dist
                ground_track["time"] = session_time_gt
                ground_track["marker"] = ground_track_marker
                ground_track["canvas"] = canvas2

        if event == "-AIRSPEED_CALIBRATION-":
            as_cal_df = df.rename(
                columns={
                    "Session Time": "session_time",
                    "Indicated Airspeed (knots)": "ias",
                    "Pressure Altitude (ft)": "press_alt",
                    "Magnetic Heading (deg)": "hdg",
                    "Ground Speed (knots)": "gps_gs",
                    "Ground Track (deg)": "gps_trk",
                    "OAT (deg F)": "oat",
                    "Barometer Setting (inHg)": "baro",
                }
            )

            essential_columns = [
                "session_time",
                "ias",
                "press_alt",
                "hdg",
                "gps_gs",
                "gps_trk",
                "oat",
                "baro",
                "Wind Speed (knots)",
                "Wind Direction (deg)",
            ]

            as_cal_df = as_cal_df[essential_columns].copy()

            as_cal_df = as_cal_df.dropna()
            as_cal_df = as_cal_df[as_cal_df["ias"] > 40.0]

            as_cal_df = as_cal_df.reset_index(drop=True)
            output = analyze_flight_data(
                as_cal_df,
                start_time=float(values["-START_MANUEVER-"]),
                end_time=float(values["-END_MANUEVER-"]),
                show_plot=False,
            )
            start_time = float(values["-START_MANUEVER-"])
            end_time = float(values["-END_MANUEVER-"])

            # Filter the DataFrame to only include the selected maneuver window
            maneuver_df = as_cal_df[
                (as_cal_df["session_time"] >= start_time)
                & (as_cal_df["session_time"] <= end_time)
            ]

            avg_wind_speed = (
                maneuver_df["Wind Speed (knots)"].mean()
                if not maneuver_df.empty and "Wind Speed (knots)" in maneuver_df.columns
                else float("nan")
            )
            avg_wind_dir = (
                maneuver_df["Wind Direction (deg)"].mean()
                if not maneuver_df.empty
                and "Wind Direction (deg)" in maneuver_df.columns
                else float("nan")
            )

            asi_calibration_summary = (
                f"Data Points Analyzed:  {output['analyzed_data_points']}\n"
                f"CAS Correction:        {output['calibrated_airspeed_correction_kts']} kts\n"
                f"Airspeed Error:        {output['airspeed_error_kts']} kts\n"
                f"HDG Correction:        {output['calibrated_heading_correction_deg']} deg\n"
                f"Wind Direction:        {output['wind_direction_deg']} deg (Avg: {avg_wind_dir:.1f} deg)\n"
                f"Wind Speed:            {output['wind_speed_kts']} kts (Avg: {avg_wind_speed:.1f} kts)\n"
                f"Uncorr. Avg TAS:       {output['uncorrected_average_true_airspeed_kts']} kts\n"
                f"Corrected Avg TAS:     {output['corrected_average_true_airspeed_kts']} kts\n"
            )
            window["-ASI_CALIBRATION-"].update(asi_calibration_summary)

    window.close()


if __name__ == "__main__":
    main()
