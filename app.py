import calendar
import os
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta

import matplotlib
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from scripts.analysis import process_flights
from scripts.fuel_prices import scrape_airnav_to_json

# Force matplotlib to not use any Xwindows backend
matplotlib.use("Agg")
app = Flask(__name__)
DB_PATH = "scripts/maintenance.db"

# --- Directory for saving processed dataframes ---
SAVE_DIR = "clean_flights"
os.makedirs(SAVE_DIR, exist_ok=True)

# Constants
OIL_CHANGE_INTERVAL_HOURS = 25
MAINTENANCE_RULES = {
    "Condition Inspection": {"type": "date", "days": 365},
    "ELT Test": {"type": "date", "days": 90},
    "ELT Batteries": {"type": "date", "days": 365 * 7},
    "ELT Registration": {"type": "date", "days": 365 * 2},
    "Nav Data Update": {"type": "date", "days": 28},
    "Transponder Check": {"type": "date", "days": 365 * 2},
    "Oil Change": {"type": "tach", "hours": OIL_CHANGE_INTERVAL_HOURS},
}

# In-Memory Cache for Nav Data
NAV_CACHE = {"data": None, "timestamp": 0}
NAV_CACHE_TTL = 6 * 60 * 60
NAV_CACHE_LOCK = threading.Lock()


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def validate_float(value, default=0.0):
    if value is None:
        return default
    if isinstance(value, str) and value.strip().lower() in ["none", "null", ""]:
        return default
    try:
        return round(float(value), 1)
    except (ValueError, TypeError):
        return default


def parse_date_safe(value):
    if not value:
        return datetime.today().strftime("%Y-%m-%d")
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return datetime.today().strftime("%Y-%m-%d")


def recompute_flight_history(conn):
    cur = conn.execute(
        "SELECT id, hobbs, tach FROM flight_log ORDER BY date ASC, id ASC"
    )
    rows = cur.fetchall()
    prev_hobbs, prev_tach = None, None

    for r in rows:
        row_id, hobbs, tach = (
            r["id"],
            validate_float(r["hobbs"]),
            validate_float(r["tach"]),
        )
        hobbs_delta = round(hobbs - prev_hobbs, 1) if prev_hobbs is not None else 0.0
        tach_delta = round(tach - prev_tach, 1) if prev_tach is not None else 0.0
        if hobbs_delta < 0:
            hobbs_delta = 0.0
        if tach_delta < 0:
            tach_delta = 0.0

        conn.execute(
            "UPDATE flight_log SET hobbs_delta = ?, tach_delta = ? WHERE id = ?",
            (hobbs_delta, tach_delta, row_id),
        )
        prev_hobbs, prev_tach = hobbs, tach
    conn.commit()


def check_auto_maintenance(conn):
    cur = conn.execute(
        "SELECT MAX(tach_time) FROM maintenance_entries WHERE recurrent_item='Oil Change'"
    )
    last_row = cur.fetchone()
    last = validate_float(last_row[0] if last_row and last_row[0] else 0)

    cur2 = conn.execute("SELECT MAX(tach) FROM flight_log")
    curr_row = cur2.fetchone()
    current = validate_float(curr_row[0] if curr_row and curr_row[0] else 0)

    if current - last >= OIL_CHANGE_INTERVAL_HOURS:
        conn.execute(
            "INSERT INTO maintenance_entries (date, tach_time, airframe_time, notes, recurrent_item, category) VALUES (date('now'), ?, ?, ?, ?, ?)",
            (
                current,
                current,
                "AUTO",
                f"Auto oil change reminder (>{OIL_CHANGE_INTERVAL_HOURS} hrs)",
                "Oil Change",
                "Engine",
            ),
        )
        conn.commit()


def calculate_overdue(conn):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT recurrent_item, MAX(date) FROM maintenance_entries GROUP BY recurrent_item"
    )
    rows = cursor.fetchall()
    today = datetime.today().date()
    overdue_items = []

    cursor.execute("SELECT MAX(tach) FROM flight_log")
    tach_row = cursor.fetchone()
    current_tach = validate_float(tach_row[0] if tach_row and tach_row[0] else 0)

    for item, last_date in rows:
        if not item or not last_date or item == "None":
            continue
        rule = MAINTENANCE_RULES.get(item)
        if not rule:
            continue
        try:
            last_dt = datetime.strptime(parse_date_safe(last_date), "%Y-%m-%d").date()
        except:
            continue

        if rule["type"] == "date" and today > (last_dt + timedelta(days=rule["days"])):
            overdue_items.append(item)
        elif rule["type"] == "tach":
            cursor.execute(
                "SELECT MAX(tach_time) FROM maintenance_entries WHERE recurrent_item=?",
                (item,),
            )
            last_tach_row = cursor.fetchone()
            last_tach = validate_float(
                last_tach_row[0] if last_tach_row and last_tach_row[0] else 0
            )
            if current_tach > (last_tach + rule["hours"]):
                overdue_items.append(item)
    return overdue_items


def _get_nav_database_status_live(conn):
    url = "https://dynonavionics.com/us-aviation-obstacle-data.php"
    aviation_status, obstacle_status = "--", "--"
    aviation_days_remaining, obstacle_days_remaining = None, None
    html = None

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        print("Requests fetch failed:", e)

    if html:
        try:
            soup = BeautifulSoup(html, "html.parser")
            spans = soup.find_all(string=lambda t: t and "Valid:" in t)
            if len(spans) >= 2:
                today = datetime.today().date()
                match_aviation = re.search(
                    r"([A-Za-z]+ \d{1,2})", spans[0].split("Valid:")[-1].strip()
                )
                match_obstacle = re.search(
                    r"([A-Za-z]+ \d{1,2})", spans[1].split("Valid:")[-1].strip()
                )

                date_aviation = (
                    datetime.strptime(
                        match_aviation.group(1) + f" {today.year}", "%B %d %Y"
                    ).date()
                    if match_aviation
                    else None
                )
                date_obstacle = (
                    datetime.strptime(
                        match_obstacle.group(1) + f" {today.year}", "%B %d %Y"
                    ).date()
                    if match_obstacle
                    else None
                )

                cursor = conn.cursor()
                cursor.execute(
                    "SELECT date FROM maintenance_entries WHERE recurrent_item='Nav Data Update' ORDER BY date DESC LIMIT 1"
                )
                nav_entry = cursor.fetchone()

                if nav_entry and nav_entry[0] and date_aviation and date_obstacle:
                    nav_date = datetime.strptime(
                        parse_date_safe(nav_entry[0]), "%Y-%m-%d"
                    ).date()
                    aviation_status = (
                        "Current" if nav_date >= date_aviation else "Overdue"
                    )
                    obstacle_status = (
                        "Current" if nav_date >= date_obstacle else "Overdue"
                    )
                else:
                    aviation_status = obstacle_status = "Overdue"

                if date_aviation:
                    aviation_days_remaining = (
                        (date_aviation + timedelta(days=28)) - today
                    ).days
                if date_obstacle:
                    obstacle_days_remaining = (
                        (date_obstacle + timedelta(days=56)) - today
                    ).days
        except Exception as e:
            print("Nav parsing failed:", e)

    return {
        "aviation_status": aviation_status,
        "obstacle_status": obstacle_status,
        "aviation_days_remaining": aviation_days_remaining,
        "obstacle_days_remaining": obstacle_days_remaining,
    }


def get_nav_database_status(conn):
    global NAV_CACHE
    now = time.time()
    with NAV_CACHE_LOCK:
        if NAV_CACHE["data"] and (now - NAV_CACHE["timestamp"] < NAV_CACHE_TTL):
            return NAV_CACHE["data"]
    live = _get_nav_database_status_live(conn)
    with NAV_CACHE_LOCK:
        NAV_CACHE["data"] = live
        NAV_CACHE["timestamp"] = now
    return live


def get_upcoming_maintenance(conn):
    cursor = conn.cursor()
    today = datetime.today().date()
    cursor.execute("SELECT MAX(tach) FROM flight_log")
    tach_row = cursor.fetchone()
    current_tach = validate_float(tach_row[0] if tach_row and tach_row[0] else 0)

    cond_due_str, cond_class = "--", "status-default"
    cursor.execute(
        "SELECT date FROM maintenance_entries WHERE recurrent_item='Condition Inspection' ORDER BY date DESC LIMIT 1"
    )
    ci_row = cursor.fetchone()
    if ci_row and ci_row[0]:
        try:
            last_dt = datetime.strptime(parse_date_safe(ci_row[0]), "%Y-%m-%d").date()
            prelim_due = last_dt + timedelta(
                days=MAINTENANCE_RULES["Condition Inspection"]["days"]
            )
            due_date = prelim_due.replace(
                day=calendar.monthrange(prelim_due.year, prelim_due.month)[1]
            )
            days_left = (due_date - today).days
            cond_due_str = f"{due_date.strftime('%m/%d/%Y')} ({days_left} days)"
            cond_class = (
                "status-overdue"
                if days_left < 0
                else "status-warning" if days_left <= 30 else "status-current"
            )
        except Exception:
            pass

    oil_due_str, oil_class = "--", "status-default"
    cursor.execute(
        "SELECT tach_time FROM maintenance_entries WHERE recurrent_item='Oil Change' ORDER BY date DESC, tach_time DESC LIMIT 1"
    )
    oil_row = cursor.fetchone()
    if oil_row and oil_row[0] is not None:
        hrs_left = round(
            (validate_float(oil_row[0]) + MAINTENANCE_RULES["Oil Change"]["hours"])
            - current_tach,
            1,
        )
        oil_due_str = f"{(validate_float(oil_row[0]) + MAINTENANCE_RULES['Oil Change']['hours']):.1f} hrs ({hrs_left:.1f} hrs left)"
        oil_class = (
            "status-overdue"
            if hrs_left < 0
            else "status-warning" if hrs_left <= 5.0 else "status-current"
        )

    return {
        "cond_due": cond_due_str,
        "cond_status_class": cond_class,
        "oil_due": oil_due_str,
        "oil_status_class": oil_class,
    }


@app.route("/")
def index():
    conn = get_db_connection()
    cursor = conn.cursor()

    def sort_and_format_logs(logs_list):
        def parse_to_datetime(d):
            if not d:
                return datetime.min
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
                try:
                    return datetime.strptime(d, fmt)
                except ValueError:
                    continue
            return datetime.min

        sorted_logs = sorted(
            logs_list, key=lambda x: parse_to_datetime(x["date"]), reverse=True
        )
        for log in sorted_logs:
            dt = parse_to_datetime(log["date"])
            if dt != datetime.min:
                log["date"] = dt.strftime("%Y-%m-%d")
                log["display_date"] = dt.strftime("%m/%d/%Y")
            else:
                log["display_date"] = log.get("date", "")
        return sorted_logs

    cursor.execute("SELECT * FROM flight_log")
    flight_logs = sort_and_format_logs([dict(row) for row in cursor.fetchall()])
    cursor.execute("SELECT * FROM maintenance_entries")
    mx_logs = sort_and_format_logs([dict(row) for row in cursor.fetchall()])
    cursor.execute("SELECT * FROM fuel_tracker")
    fuel_logs = sort_and_format_logs([dict(row) for row in cursor.fetchall()])

    cursor.execute("SELECT hobbs FROM flight_log ORDER BY hobbs DESC LIMIT 1")
    hobbs_res = cursor.fetchone()
    total_hours = hobbs_res["hobbs"] if hobbs_res and hobbs_res["hobbs"] else 0.0

    cursor.execute("SELECT SUM(landings) as total_ldgs FROM flight_log")
    l_res = cursor.fetchone()
    total_landings = l_res["total_ldgs"] if l_res and l_res["total_ldgs"] else 0

    overdue_items = calculate_overdue(conn)
    nav_status = get_nav_database_status(conn)
    upcoming_mx = get_upcoming_maintenance(conn)
    conn.close()

    if nav_status.get("aviation_status") == "Overdue":
        overdue_items.append("Aviation DB")
    if nav_status.get("obstacle_status") == "Overdue":
        overdue_items.append("Obstacle DB")
    if (
        "Aviation DB" in overdue_items or "Obstacle DB" in overdue_items
    ) and "Nav Data Update" in overdue_items:
        overdue_items.remove("Nav Data Update")

    aviation_text = nav_status.get("aviation_status", "--") + (
        f" ({nav_status['aviation_days_remaining']} days)"
        if nav_status.get("aviation_days_remaining") is not None
        and nav_status.get("aviation_status") != "--"
        else ""
    )
    obstacle_text = nav_status.get("obstacle_status", "--") + (
        f" ({nav_status['obstacle_days_remaining']} days)"
        if nav_status.get("obstacle_days_remaining") is not None
        and nav_status.get("obstacle_status") != "--"
        else ""
    )

    return render_template(
        "index.html",
        flight_logs=flight_logs,
        mx_logs=mx_logs,
        fuel_logs=fuel_logs,
        total_hours=total_hours,
        total_landings=total_landings,
        overdue_items=overdue_items,
        overdue_count=len(overdue_items),
        aviation_db_text=aviation_text,
        aviation_status_class=(
            "status-current"
            if nav_status.get("aviation_status") == "Current"
            else "status-overdue"
        ),
        obstacle_db_text=obstacle_text,
        obstacle_status_class=(
            "status-current"
            if nav_status.get("obstacle_status") == "Current"
            else "status-overdue"
        ),
        cond_due=upcoming_mx["cond_due"],
        cond_status_class=upcoming_mx["cond_status_class"],
        oil_due=upcoming_mx["oil_due"],
        oil_status_class=upcoming_mx["oil_status_class"],
    )


@app.route("/add_flight", methods=["POST"])
def add_flight():
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO flight_log (date, takeoff_airport, landing_airport, hobbs, tach, landings, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            parse_date_safe(request.form.get("date")),
            request.form.get("takeoff"),
            request.form.get("landing"),
            validate_float(request.form.get("hobbs")),
            validate_float(request.form.get("tach")),
            request.form.get("landings", 0),
            request.form.get("notes"),
        ),
    )
    conn.commit()
    recompute_flight_history(conn)
    check_auto_maintenance(conn)
    conn.close()
    return redirect(url_for("index"))


@app.route("/add_mx", methods=["POST"])
def add_mx():
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO maintenance_entries (date, tach_time, airframe_time, recurrent_item, category, notes) VALUES (?, ?, ?, ?, ?, ?)",
        (
            parse_date_safe(request.form.get("date")),
            validate_float(request.form.get("tach")),
            validate_float(request.form.get("airframe")),
            request.form.get("recurrent_item"),
            request.form.get("category"),
            request.form.get("notes"),
        ),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/add_fuel", methods=["POST"])
def add_fuel():
    hours, gallons, price = (
        validate_float(request.form.get("hours", 0)),
        validate_float(request.form.get("gallons", 0)),
        validate_float(request.form.get("price", 0)),
    )
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO fuel_tracker (date, hours, gallons, price_per_gallon, total_cost, gal_per_hour) VALUES (?, ?, ?, ?, ?, ?)",
        (
            parse_date_safe(request.form.get("date")),
            hours,
            gallons,
            price,
            round(gallons * price, 2),
            round(gallons / hours, 2) if hours > 0 else 0,
        ),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/api/fuel_prices", methods=["GET"])
def api_fuel_prices():
    airport = request.args.get("airport", "").strip()
    if not airport:
        return jsonify({"error": "No airport provided"}), 400
    try:
        options, _ = scrape_airnav_to_json(airport)
        return (
            jsonify({"options": options[0:5]})
            if options
            else jsonify({"error": f"No fuel data found for {airport}"})
        ), 404
    except Exception:
        return jsonify({"error": "An error occurred while fetching fuel prices."}), 500


@app.route("/edit_flight/<int:id>", methods=["POST"])
def edit_flight(id):
    conn = get_db_connection()
    conn.execute(
        "UPDATE flight_log SET date = ?, takeoff_airport = ?, landing_airport = ?, hobbs = ?, tach = ?, landings = ?, notes = ? WHERE id = ?",
        (
            parse_date_safe(request.form.get("date")),
            request.form.get("takeoff"),
            request.form.get("landing"),
            validate_float(request.form.get("hobbs")),
            validate_float(request.form.get("tach")),
            request.form.get("landings", 0),
            request.form.get("notes"),
            id,
        ),
    )
    conn.commit()
    recompute_flight_history(conn)
    check_auto_maintenance(conn)
    conn.close()
    return redirect(url_for("index"))


@app.route("/edit_mx/<int:id>", methods=["POST"])
def edit_mx(id):
    conn = get_db_connection()
    conn.execute(
        "UPDATE maintenance_entries SET date = ?, tach_time = ?, airframe_time = ?, recurrent_item = ?, category = ?, notes = ? WHERE id=?",
        (
            parse_date_safe(request.form.get("date")),
            validate_float(request.form.get("tach")),
            validate_float(request.form.get("airframe")),
            request.form.get("recurrent_item"),
            request.form.get("category"),
            request.form.get("notes"),
            id,
        ),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/edit_fuel/<int:id>", methods=["POST"])
def edit_fuel(id):
    hours, gallons, price = (
        validate_float(request.form.get("hours", 0)),
        validate_float(request.form.get("gallons", 0)),
        validate_float(request.form.get("price", 0)),
    )
    conn = get_db_connection()
    conn.execute(
        "UPDATE fuel_tracker SET date =?, hours =?, gallons =?, price_per_gallon =?, total_cost =?, gal_per_hour =? WHERE id = ?",
        (
            parse_date_safe(request.form.get("date")),
            hours,
            gallons,
            price,
            round(gallons * price, 2),
            round(gallons / hours, 2) if hours > 0 else 0,
            id,
        ),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/delete_flight/<int:id>")
def delete_flight(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM flight_log WHERE id = ?", (id,))
    conn.commit()
    recompute_flight_history(conn)
    conn.close()
    return redirect(url_for("index"))


@app.route("/delete_maintenance/<int:id>")
def delete_maintenance(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM maintenance_entries WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/delete_fuel/<int:id>")
def delete_fuel(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM fuel_tracker WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/analyzer")
def analyzer():
    return render_template("analyzer.html")


@app.route("/api/saved_flights", methods=["GET"])
def api_saved_flights():
    """Lists all previously uploaded and processed flight data files."""
    files = [f for f in os.listdir(SAVE_DIR) if f.endswith(".csv")]
    files.sort(key=lambda x: os.path.getmtime(os.path.join(SAVE_DIR, x)), reverse=True)
    return jsonify({"files": files})


@app.route("/api/get_signals", methods=["POST"])
def api_get_signals():
    """Parses a new CSV or loads an existing one to populate the UI dropdowns."""
    saved_filename = request.form.get("saved_filename")

    try:
        if saved_filename:
            filepath = os.path.join(SAVE_DIR, saved_filename)
            if not os.path.exists(filepath):
                return jsonify({"error": "Saved file not found."}), 404
            df = pd.read_csv(filepath, low_memory=False)

        else:
            if "file" not in request.files:
                return jsonify({"error": "No file part"}), 400
            file = request.files["file"]
            if file.filename == "" or not file.filename.endswith(".csv"):
                return jsonify({"error": "Invalid file. Please upload a CSV."}), 400

            df = pd.read_csv(file, low_memory=False)
            df = process_flights(df)

            if df is None or df.empty:
                return jsonify({"error": "No valid flight data found in the CSV."}), 400

            safe_name = secure_filename(file.filename)
            base_name, ext = os.path.splitext(safe_name)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            saved_filename = f"{base_name}_{timestamp}{ext}"

            filepath = os.path.join(SAVE_DIR, saved_filename)
            df.to_csv(filepath, index=False)

        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        excluded = ["Unnamed: 103", "Engine Run", "id"]
        signals = sorted([col for col in numeric_cols if col not in excluded])

        if "CHT" not in signals:
            signals.append("CHT")
        if "EGT" not in signals:
            signals.append("EGT")

        signals = sorted(signals)

        return jsonify({"signals": signals, "saved_filename": saved_filename})

    except Exception as e:
        print(f"Signal Parsing Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/analyze_flight", methods=["POST"])
def api_analyze_flight():
    """Loads the pre-saved dataframe and extracts plot data dynamically."""
    saved_filename = request.form.get("saved_filename")
    if not saved_filename:
        return jsonify({"error": "No data file specified."}), 400

    try:
        filepath = os.path.join(SAVE_DIR, saved_filename)
        if not os.path.exists(filepath):
            return jsonify({"error": "Saved file not found on server."}), 404

        df = pd.read_csv(filepath, low_memory=False)

        left_signal = request.form.get("left_signal", "RPM")
        right_signal = request.form.get("right_signal", "AVG_CHT")
        temp_unit = request.form.get("temp_unit", "F")

        flight_ids = [
            fid for fid in df["Flight ID"].unique() if pd.notna(fid) and fid != ""
        ]
        if not flight_ids:
            return (
                jsonify({"error": "No engine-run flights detected in this file."}),
                400,
            )

        target_flight = flight_ids[0]
        flight_data = df[df["Flight ID"] == target_flight].copy()

        # Sanitize data for JSON
        flight_data = flight_data.replace([np.inf, -np.inf], np.nan)
        flight_data = flight_data.fillna("")
        x_data = flight_data["Session Time"].tolist()

        def extract_traces(sig):
            traces = []
            deg_str = f"(deg {temp_unit})"

            if sig == "CHT":
                cols = [
                    c
                    for c in flight_data.columns
                    if c.startswith("CHT ") and deg_str in c
                ]
            elif sig == "EGT":
                cols = [
                    c
                    for c in flight_data.columns
                    if c.startswith("EGT ") and deg_str in c
                ]
            else:
                cols = [sig] if sig in flight_data.columns else []

            for col in sorted(cols):
                traces.append({"name": col, "y": flight_data[col].tolist()})
            return traces

        plot_data = {
            "x": x_data,
            "left_traces": extract_traces(left_signal),
            "right_traces": extract_traces(right_signal),
            "left_name": left_signal,
            "right_name": right_signal,
        }

        # --- Generate Summary Stats ---
        numeric_times = pd.to_numeric(flight_data["Session Time"], errors="coerce")
        duration = (
            numeric_times.max() - numeric_times.min() if not numeric_times.empty else 0
        )

        total_fuel = (
            flight_data["Fuel Flow Integral"].max()
            if "Fuel Flow Integral" in flight_data.columns
            and flight_data["Fuel Flow Integral"].max() != ""
            else 0
        )
        avg_flow = (total_fuel * 3600) / duration if duration > 0 else 0

        # Calculate Average MPG using the mean() of the MPG data column
        avg_mpg = "N/A"

        if "MPG" in flight_data.columns:
            try:
                valid_mpg = pd.to_numeric(flight_data["MPG"], errors="coerce").dropna()
                if not valid_mpg.empty:
                    avg_mpg = round(valid_mpg.mean(), 1)
            except Exception:
                pass

        def safe_max(col):
            if col in flight_data.columns:
                series = pd.to_numeric(flight_data[col], errors="coerce").dropna()
                return round(series.max(), 1) if not series.empty else "N/A"
            return "N/A"

        stats = {
            "flight_id": target_flight,
            "duration_min": round(duration / 60, 2),
            "max_rpm": safe_max("RPM"),
            "max_cht": safe_max("Max CHT"),
            "total_fuel": (
                round(total_fuel, 2) if isinstance(total_fuel, (int, float)) else "N/A"
            ),
            "avg_fuel_flow": round(avg_flow, 2),
            "avg_mpg": avg_mpg,
        }

        return jsonify({"plot_data": plot_data, "stats": stats})

    except Exception as e:
        print(f"Analysis Error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
