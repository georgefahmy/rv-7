import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta

# import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, redirect, render_template, request

from scripts.fuel_prices import scrape_airnav_to_json

app = Flask(__name__)

NAV_CACHE = {"data": None, "timestamp": 0}

NAV_CACHE_TTL = 6 * 60 * 60  # 6 hours

NAV_CACHE_LOCK = threading.Lock()

DB = "scripts/maintenance.db"

# -----------------------------
# Field maps for safe updates
# -----------------------------
FLIGHT_FIELDS = [
    "date",
    "takeoff_airport",
    "landing_airport",
    "hobbs",
    "tach",
    "hobbs_delta",
    "tach_delta",
    "landings",
    "notes",
]

MAINT_FIELDS = [
    "date",
    "tach_time",
    "airframe_time",
    "notes",
    "recurrent_item",
    "category",
]

FUEL_FIELDS = [
    "date",
    "hours",
    "gallons",
    "price_per_gallon",
    "total_cost",
    "gal_per_hour",
]

# -----------------------------
# Maintenance Intelligence Rules
# -----------------------------
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


# -----------------------------
# DB helper
# -----------------------------
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def validate_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except:
        return default


def parse_date_safe(value):
    """
    Normalize all incoming dates to ISO format (YYYY-MM-DD).
    Accepts:
    - YYYY-MM-DD
    - MM/DD/YYYY
    - invalid values fallback to today
    """
    if not value:
        return datetime.today().strftime("%Y-%m-%d")

    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except:
            continue

    return datetime.today().strftime("%Y-%m-%d")


# -----------------------------
# Flight recalculation
# -----------------------------
def recompute_flight_history(conn):
    cur = conn.execute(
        "SELECT rowid, hobbs, tach FROM flight_log ORDER BY date ASC, rowid ASC"
    )
    rows = cur.fetchall()

    prev_hobbs = 0.0
    prev_tach = 0.0

    for r in rows:
        rowid, hobbs, tach = r
        hobbs = validate_float(hobbs)
        tach = validate_float(tach)

        conn.execute(
            """
            UPDATE flight_log
            SET hobbs_delta = ?, tach_delta = ?
            WHERE rowid = ?
            """,
            (hobbs - prev_hobbs, tach - prev_tach, rowid),
        )

        prev_hobbs = hobbs
        prev_tach = tach

    conn.commit()


# -----------------------------
# Auto maintenance logic
# -----------------------------
def check_auto_maintenance(conn):
    cur = conn.execute("SELECT MAX(tach_time) FROM maintenance_entries")
    last = validate_float(cur.fetchone()[0])

    cur2 = conn.execute("SELECT MAX(tach) FROM flight_log")
    current = validate_float(cur2.fetchone()[0])

    if current - last >= 25:
        conn.execute(
            """
            INSERT INTO maintenance_entries
            (date, tach_time, airframe_time, notes, recurrent_item, category)
            VALUES (date('now'), ?, ?, ?, ?, ?)
            """,
            (
                current,
                current,
                "AUTO",
                "Auto oil change reminder",
                "oil_change",
                "auto",
            ),
        )
        conn.commit()


def calculate_overdue(conn):
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT recurrent_item, date
        FROM maintenance_entries
    """
    )
    rows = cursor.fetchall()

    today = datetime.today().date()
    overdue_count = 0

    cursor.execute("SELECT MAX(tach) FROM flight_log")
    current_tach = validate_float(cursor.fetchone()[0])

    for item, last_date in rows:
        if not item or not last_date:
            continue

        rule = MAINTENANCE_RULES.get(item)
        if not rule:
            continue

        # SAFE: now ALL dates are ISO
        try:
            last_dt = datetime.strptime(last_date, "%Y-%m-%d").date()
        except:
            continue

        if rule["type"] == "date":
            due_date = last_dt + timedelta(days=rule["days"])
            if today > due_date:
                overdue_count += 1

        elif rule["type"] == "tach":
            cursor.execute(
                """
                SELECT MAX(tach_time)
                FROM maintenance_entries
                WHERE recurrent_item=?
            """,
                (item,),
            )

            last_tach_row = cursor.fetchone()
            last_tach = validate_float(last_tach_row[0])

            due_tach = last_tach + rule["hours"]

            if current_tach > due_tach:
                overdue_count += 1

    return overdue_count


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


def _get_nav_database_status_live(conn):
    url = "https://dynonavionics.com/us-aviation-obstacle-data.php"

    aviation_status = "--"
    obstacle_status = "--"
    aviation_days_remaining = None
    obstacle_days_remaining = None

    try:
        from playwright.sync_api import sync_playwright

        html = None

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                html = page.content()

                browser.close()

        except Exception as e:
            print("Playwright fetch failed:", e)
            html = None

        if not html:
            return {
                "aviation_status": aviation_status,
                "obstacle_status": obstacle_status,
                "aviation_days_remaining": aviation_days_remaining,
                "obstacle_days_remaining": obstacle_days_remaining,
            }

        soup = BeautifulSoup(html, "html.parser")

        spans = soup.find_all(string=lambda t: "Valid:" in t)

        if len(spans) >= 2:
            aviation_valid_text = spans[0].split("Valid:")[-1].strip()
            obstacle_valid_text = spans[1].split("Valid:")[-1].strip()

            today = datetime.today().date()

            match_aviation = re.search(r"([A-Za-z]+ \d{1,2})", aviation_valid_text)
            match_obstacle = re.search(r"([A-Za-z]+ \d{1,2})", obstacle_valid_text)

            date_aviation = None
            date_obstacle = None

            if match_aviation:
                date_aviation = datetime.strptime(
                    match_aviation.group(1) + f" {today.year}", "%B %d %Y"
                ).date()

            if match_obstacle:
                date_obstacle = datetime.strptime(
                    match_obstacle.group(1) + f" {today.year}", "%B %d %Y"
                ).date()

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT date
                FROM maintenance_entries
                WHERE recurrent_item='Nav Data Update'
                ORDER BY date DESC
                LIMIT 1
                """
            )
            nav_entry = cursor.fetchone()

            if nav_entry and nav_entry[0] and date_aviation and date_obstacle:
                try:
                    nav_date = datetime.strptime(nav_entry[0], "%m/%d/%Y").date()
                except:
                    nav_date = None

                if nav_date:
                    if date_aviation:
                        aviation_status = (
                            "Current" if nav_date >= date_aviation else "Overdue"
                        )
                    if date_obstacle:
                        obstacle_status = (
                            "Current" if nav_date >= date_obstacle else "Overdue"
                        )
                else:
                    aviation_status = "Overdue"
                    obstacle_status = "Overdue"
            else:
                aviation_status = "Overdue"
                obstacle_status = "Overdue"

            # Always compute expiry countdown (EFB-style)
            if date_aviation:
                aviation_expiry = date_aviation + timedelta(days=28)
                aviation_days_remaining = (aviation_expiry - today).days

            if date_obstacle:
                obstacle_expiry = date_obstacle + timedelta(days=56)
                obstacle_days_remaining = (obstacle_expiry - today).days

    except Exception as e:
        print("Nav DB fetch failed:", e)

    return {
        "aviation_status": aviation_status,
        "obstacle_status": obstacle_status,
        "aviation_days_remaining": aviation_days_remaining,
        "obstacle_days_remaining": obstacle_days_remaining,
    }


# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def index():
    conn = get_db()

    flights = conn.execute(
        """
        SELECT rowid, date, takeoff_airport, landing_airport, hobbs, tach,
               hobbs_delta, tach_delta, landings, notes
        FROM flight_log
        ORDER BY date DESC
        """
    ).fetchall()

    maintenance = conn.execute(
        "SELECT * FROM maintenance_entries ORDER BY id DESC"
    ).fetchall()

    fuel = conn.execute(
        """
        SELECT rowid, date, hours, gallons, price_per_gallon, total_cost, gal_per_hour
        FROM fuel_tracker
        ORDER BY rowid DESC
        """
    ).fetchall()

    return render_template(
        "index.html",
        flights=flights,
        maintenance=maintenance,
        fuel=fuel,
    )


@app.route("/add_flight", methods=["POST"])
def add_flight():
    data = request.form
    conn = get_db()

    conn.execute(
        """
        INSERT INTO flight_log
        (date, takeoff_airport, landing_airport, hobbs, tach,
         hobbs_delta, tach_delta, landings, notes)
        VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?)
        """,
        (
            parse_date_safe(data["date"]),
            data["takeoff"],
            data["landing"],
            data["hobbs"],
            data["tach"],
            data["landings"],
            data["notes"],
        ),
    )

    conn.commit()
    recompute_flight_history(conn)
    check_auto_maintenance(conn)
    return redirect("/")


@app.route("/add_maintenance", methods=["POST"])
def add_maintenance():
    data = request.form
    conn = get_db()

    conn.execute(
        """
        INSERT INTO maintenance_entries
        (date, tach_time, airframe_time, notes, recurrent_item, category)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            parse_date_safe(data["date"]),
            data["tach"],
            data["airframe"],
            data["notes"],
            data["item"],
            data["category"],
        ),
    )

    conn.commit()
    return redirect("/")


@app.route("/add_fuel", methods=["POST"])
def add_fuel():
    data = request.form
    conn = get_db()

    hours = validate_float(data["hours"])
    gallons = validate_float(data["gallons"])
    price = validate_float(data["price"])

    total = gallons * price
    gph = gallons / hours if hours else 0

    conn.execute(
        """
        INSERT INTO fuel_tracker
        (date, hours, gallons, price_per_gallon, total_cost, gal_per_hour)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (data["date"], hours, gallons, price, total, gph),
    )

    conn.commit()
    return redirect("/")


@app.route("/delete_flight/<int:id>")
def delete_flight(id):
    conn = get_db()
    conn.execute("DELETE FROM flight_log WHERE rowid = ?", (id,))
    conn.commit()
    return redirect("/")


@app.route("/delete_maintenance/<int:id>")
def delete_maintenance(id):
    conn = get_db()
    conn.execute("DELETE FROM maintenance_entries WHERE id = ?", (id,))
    conn.commit()
    return redirect("/")


@app.route("/delete_fuel/<int:id>")
def delete_fuel(id):
    conn = get_db()
    conn.execute("DELETE FROM fuel_tracker WHERE rowid = ?", (id,))
    conn.commit()
    return redirect("/")


@app.route("/summary")
def summary():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT SUM(gallons) FROM fuel_tracker")
    total_gallons = cur.fetchone()[0] or 0

    cur.execute("SELECT SUM(gallons * price_per_gallon) FROM fuel_tracker")
    total_cost = cur.fetchone()[0] or 0

    cur.execute("SELECT AVG(gal_per_hour) FROM fuel_tracker")
    avg_gph = cur.fetchone()[0] or 0

    return jsonify(
        {
            "total_gallons": total_gallons,
            "total_cost": total_cost,
            "avg_gph": avg_gph,
            "maint_overdue": calculate_overdue(conn),
            **get_nav_database_status(conn),
        }
    )


# -----------------------------
# Inline update endpoints
# -----------------------------
@app.route("/update_flight/<int:rowid>", methods=["POST"])
def update_flight(rowid):
    data = request.get_json()
    field = FLIGHT_FIELDS[int(data["field"])]
    value = data["value"]

    if field in ["hobbs", "tach", "landings", "hobbs_delta", "tach_delta"]:
        value = validate_float(value)

    conn = get_db()
    conn.execute(f"UPDATE flight_log SET {field} = ? WHERE rowid = ?", (value, rowid))
    conn.commit()

    recompute_flight_history(conn)
    check_auto_maintenance(conn)
    return jsonify({"status": "ok"})


@app.route("/update_maintenance/<int:rowid>", methods=["POST"])
def update_maintenance(rowid):
    data = request.get_json()
    field = MAINT_FIELDS[int(data["field"])]
    value = data["value"]

    conn = get_db()
    conn.execute(
        f"UPDATE maintenance_entries SET {field} = ? WHERE id = ?", (value, rowid)
    )
    conn.commit()

    return jsonify({"status": "ok"})


@app.route("/update_fuel/<int:rowid>", methods=["POST"])
def update_fuel(rowid):
    data = request.get_json()
    field = FUEL_FIELDS[int(data["field"])]
    value = data["value"]

    if field in ["hours", "gallons", "price_per_gallon"]:
        value = validate_float(value)

    conn = get_db()
    conn.execute(f"UPDATE fuel_tracker SET {field} = ? WHERE rowid = ?", (value, rowid))
    conn.commit()

    return jsonify({"status": "ok"})


@app.route("/api/fuel_prices", methods=["GET"])
def api_fuel_prices():
    airport = request.args.get("airport", "").strip()
    if not airport:
        return jsonify({"error": "No airport provided"}), 400

    try:
        # Calls the scraper. Returns (options, output_string)
        options, _ = scrape_airnav_to_json(airport)

        if options:
            return jsonify({"options": options[0:5]})
        else:
            return jsonify({"error": f"No fuel data found for {airport}"}), 404

    except Exception as e:
        print(f"Scraping Error: {e}")
        return jsonify({"error": "An error occurred while fetching fuel prices."}), 500


def nav_background_updater():
    while True:
        try:
            conn = get_db()
            _ = _get_nav_database_status_live(conn)
            conn.close()
        except Exception as e:
            print("NAV background update failed:", e)

        time.sleep(6 * 60 * 60)  # 6 hours


if __name__ == "__main__":
    thread = threading.Thread(target=nav_background_updater, daemon=True)
    thread.start()

    app.run(debug=True)
