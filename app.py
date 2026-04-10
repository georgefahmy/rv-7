import calendar
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from flask import Flask, jsonify, redirect, render_template, request, url_for

# Import your scraper function
from scripts.fuel_prices import scrape_airnav_to_json

app = Flask(__name__)
DB_PATH = "scripts/maintenance.db"
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
OIL_CHANGE_INTERVAL_HOURS = 10

MAINTENANCE_RULES = {
    "Condition Inspection": {"type": "date", "days": 365},
    "ELT Test": {"type": "date", "days": 90},
    "ELT Batteries": {"type": "date", "days": 365 * 7},
    "ELT Registration": {"type": "date", "days": 365 * 2},
    "Nav Data Update": {"type": "date", "days": 28},
    "Transponder Check": {"type": "date", "days": 365 * 2},
    "Oil Change": {"type": "tach", "hours": OIL_CHANGE_INTERVAL_HOURS},
}
NAV_CACHE = {"data": None, "timestamp": 0}

NAV_CACHE_TTL = 6 * 60 * 60  # 6 hours

NAV_CACHE_LOCK = threading.Lock()


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def validate_float(value, default=0.0):
    if value is None:
        return default

    # Catch literal strings like "None", "Null", or empty strings
    if isinstance(value, str) and value.strip().lower() in ["None", None]:
        return default

    try:
        return round(float(value), 1)
    except (ValueError, TypeError):
        return default


def recompute_flight_history(conn):
    """Recalculates deltas across all flights sequentially."""
    cur = conn.execute(
        "SELECT rowid, hobbs, tach FROM flight_log ORDER BY date ASC, rowid ASC"
    )
    rows = cur.fetchall()

    # Start these as None so we know when we are on the very first row
    prev_hobbs = None
    prev_tach = None

    for r in rows:
        rowid = r
        hobbs = validate_float(r)
        tach = validate_float(r)

        # If this is the first entry, delta is 0.
        # Otherwise, subtract the previous value from the current value.
        if prev_hobbs is None:
            hobbs_delta = 0.0
            tach_delta = 0.0
        else:
            hobbs_delta = round(hobbs - prev_hobbs, 1)
            tach_delta = round(tach - prev_tach, 1)

        # Optional safeguard: Prevent negative deltas if out-of-order entries occur
        if hobbs_delta < 0:
            hobbs_delta = 0.0
        if tach_delta < 0:
            tach_delta = 0.0

        conn.execute(
            "UPDATE flight_log SET hobbs_delta = ?, tach_delta = ? WHERE rowid = ?",
            (hobbs_delta, tach_delta, rowid),
        )

        # Update previous values for the next loop iteration
        prev_hobbs = hobbs
        prev_tach = tach

    conn.commit()


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


def get_upcoming_maintenance(conn):
    cursor = conn.cursor()
    today = datetime.today().date()

    # 1. Get Current Aircraft Tach
    cursor.execute("SELECT MAX(tach) FROM flight_log")
    tach_row = cursor.fetchone()
    current_tach = validate_float(tach_row[0] if tach_row and tach_row[0] else 0)

    # 2. Condition Inspection Calculation
    cond_due_str = "--"
    cond_class = "status-default"
    cursor.execute(
        "SELECT date FROM maintenance_entries WHERE recurrent_item='Condition Inspection' ORDER BY date DESC LIMIT 1"
    )
    ci_row = cursor.fetchone()

    if ci_row and ci_row[0]:
        try:
            last_dt = datetime.strptime(ci_row[0], "%m/%d/%Y").date()
            prelim_due = last_dt + timedelta(
                days=MAINTENANCE_RULES["Condition Inspection"]["days"]
            )

            # Aviation rule: Inspections are due on the last day of the month
            last_day = calendar.monthrange(prelim_due.year, prelim_due.month)[1]
            due_date = prelim_due.replace(day=last_day)

            days_left = (due_date - today).days
            cond_due_str = f"{due_date.strftime('%m/%d/%Y')} ({days_left} days)"

            if days_left < 0:
                cond_class = "status-overdue"
            elif days_left <= 30:
                cond_class = "status-warning"
            else:
                cond_class = "status-current"
        except Exception as e:
            print(e)
            pass

    # 3. Oil Change Calculation
    oil_due_str = "--"
    oil_class = "status-default"
    cursor.execute(
        "SELECT tach_time FROM maintenance_entries WHERE recurrent_item='Oil Change' ORDER BY date DESC, tach_time DESC LIMIT 1"
    )
    oil_row = cursor.fetchone()

    if oil_row and oil_row[0] is not None:
        last_tach = validate_float(oil_row[0])
        due_tach = last_tach + MAINTENANCE_RULES["Oil Change"]["hours"]
        hrs_left = round(due_tach - current_tach, 1)

        oil_due_str = f"{due_tach:.1f} hrs ({hrs_left:.1f} hrs left)"

        if hrs_left < 0:
            oil_class = "status-overdue"
        elif hrs_left <= 5.0:
            oil_class = "status-warning"
        else:
            oil_class = "status-current"

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

    # Helper function to sort and create dual-format dates
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
                # 'date' stays ISO for HTML5 <input type="date"> fields
                log["date"] = dt.strftime("%Y-%m-%d")
                # 'display_date' becomes American format for UI tables
                log["display_date"] = dt.strftime("%m/%d/%Y")
            else:
                log["display_date"] = log.get("date", "")

        return sorted_logs

    # 1. Fetch Flight Logs
    cursor.execute(
        """
        SELECT id, date, takeoff_airport, landing_airport, hobbs, tach,
               hobbs_delta, tach_delta, landings, notes
        FROM flight_log
    """
    )
    flight_logs = sort_and_format_logs([dict(row) for row in cursor.fetchall()])

    # 2. Fetch Maintenance Logs
    cursor.execute("SELECT * FROM maintenance_entries")
    mx_logs = sort_and_format_logs([dict(row) for row in cursor.fetchall()])

    # 3. Fetch Fuel Logs
    cursor.execute("SELECT * FROM fuel_tracker")
    fuel_logs = sort_and_format_logs([dict(row) for row in cursor.fetchall()])

    # 4. Fetch Totals
    cursor.execute("SELECT hobbs FROM flight_log ORDER BY hobbs DESC LIMIT 1")
    hobbs_res = cursor.fetchone()
    total_hours = hobbs_res["hobbs"] if hobbs_res and hobbs_res["hobbs"] else 0.0

    cursor.execute("SELECT SUM(landings) as total_ldgs FROM flight_log")
    l_res = cursor.fetchone()
    total_landings = l_res["total_ldgs"] if l_res and l_res["total_ldgs"] else 0

    overdue_count = calculate_overdue(conn)
    nav_status = get_nav_database_status(conn)

    # FETCH LIVE MAINTENANCE STATUS HERE
    upcoming_mx = get_upcoming_maintenance(conn)

    conn.close()

    # 5. Extract Nav Status and Days Remaining
    aviation_status = nav_status.get("aviation_status", "--")
    aviation_days = nav_status.get("aviation_days_remaining")
    aviation_text = aviation_status
    if aviation_days is not None and aviation_status != "--":
        aviation_text += f" ({aviation_days} days)"

    obstacle_status = nav_status.get("obstacle_status", "--")
    obstacle_days = nav_status.get("obstacle_days_remaining")
    obstacle_text = obstacle_status
    if obstacle_days is not None and obstacle_status != "--":
        obstacle_text += f" ({obstacle_days} days)"

    return render_template(
        "index.html",
        flight_logs=flight_logs,
        mx_logs=mx_logs,
        fuel_logs=fuel_logs,
        total_hours=total_hours,
        total_landings=total_landings,
        overdue_count=overdue_count,
        aviation_db_text=aviation_text,
        aviation_status_class=(
            "status-current" if aviation_status == "Current" else "status-overdue"
        ),
        obstacle_db_text=obstacle_text,
        obstacle_status_class=(
            "status-current" if obstacle_status == "Current" else "status-overdue"
        ),
        # REPLACE STATIC PLACEHOLDERS WITH LIVE DATA
        cond_due=upcoming_mx["cond_due"],
        cond_status_class=upcoming_mx["cond_status_class"],
        oil_due=upcoming_mx["oil_due"],
        oil_status_class=upcoming_mx["oil_status_class"],
    )


@app.route("/add_flight", methods=["POST"])
def add_flight():
    date = request.form.get("date")
    takeoff = request.form.get("takeoff")
    landing = request.form.get("landing")
    hobbs = request.form.get("hobbs")
    tach = request.form.get("tach")
    landings = request.form.get("landings")
    notes = request.form.get("notes")

    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO flight_log (date, takeoff_airport, landing_airport, hobbs, tach, landings, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (date, takeoff, landing, hobbs, tach, landings, notes),
    )
    conn.commit()
    conn.close()

    return redirect(url_for("index"))


@app.route("/add_mx", methods=["POST"])
def add_mx():
    date = request.form.get("date")
    tach = request.form.get("tach")
    airframe = request.form.get("airframe")
    recurrent_item = request.form.get("recurrent_item")
    category = request.form.get("category")
    notes = request.form.get("notes")

    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO maintenance_entries (date, tach_time, airframe_time, recurrent_item, category, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (date, tach, airframe, recurrent_item, category, notes),
    )
    conn.commit()
    conn.close()

    return redirect(url_for("index"))


@app.route("/add_fuel", methods=["POST"])
def add_fuel():
    date = request.form.get("date")
    hours = float(request.form.get("hours", 0))
    gallons = float(request.form.get("gallons", 0))
    price = float(request.form.get("price", 0))

    total_cost = round(gallons * price, 2)
    gal_per_hour = round(gallons / hours, 2) if hours > 0 else 0

    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO fuel_tracker (date, hours, gallons, price_per_gallon, total_cost, gal_per_hour)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (date, hours, gallons, price, total_cost, gal_per_hour),
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
        # Calls the scraper. Returns (options, output_string)
        options, _ = scrape_airnav_to_json(airport)

        if options:
            return jsonify({"options": options[0:5]})
        else:
            return jsonify({"error": f"No fuel data found for {airport}"}), 404

    except Exception as e:
        print(f"Scraping Error: {e}")
        return jsonify({"error": "An error occurred while fetching fuel prices."}), 500


@app.route("/edit_flight/<int:id>", methods=["POST"])
def edit_flight(id):
    # 1. Grab all the inputs from the HTML form
    date = parse_date_safe(request.form.get("date"))
    takeoff = request.form.get("takeoff")
    landing = request.form.get("landing")
    hobbs = validate_float(request.form.get("hobbs"))
    tach = validate_float(request.form.get("tach"))
    landings = request.form.get("landings", 0)
    notes = request.form.get("notes")

    # 2. Update the specific row in the database
    conn = get_db_connection()
    conn.execute(
        """
        UPDATE flight_log
        SET date = ?, takeoff_airport = ?, landing_airport = ?,
            hobbs = ?, tach = ?, landings = ?, notes = ?
        WHERE id = ?
        """,
        (date, takeoff, landing, hobbs, tach, landings, notes, id),
    )
    conn.commit()

    # 3. Recalculate everything and close up
    # recompute_flight_history(conn)
    check_auto_maintenance(conn)
    conn.close()

    return redirect(url_for("index"))


@app.route("/edit_mx/<int:id>", methods=["POST"])
def edit_mx(id):
    date = request.form.get("date")
    tach = request.form.get("tach")
    airframe = request.form.get("airframe")
    recurrent_item = request.form.get("recurrent_item")
    category = request.form.get("category")
    notes = request.form.get("notes")

    conn = get_db_connection()
    conn.execute(
        """
        UPDATE maintenance_entries
        SET date = ?, tach_time = ?, airframe_time = ?,
            recurrent_item = ?, category = ?, notes = ?
        WHERE id=?
        """,
        (date, tach, airframe, recurrent_item, category, notes, id),
    )
    conn.commit()
    conn.close()

    return redirect(url_for("index"))


@app.route("/edit_fuel/<int:id>", methods=["POST"])
def edit_fuel(id):
    date = request.form.get("date")
    hours = float(request.form.get("hours", 0))
    gallons = float(request.form.get("gallons", 0))
    price = float(request.form.get("price", 0))

    total_cost = round(gallons * price, 2)
    gal_per_hour = round(gallons / hours, 2) if hours > 0 else 0

    conn = get_db_connection()
    conn.execute(
        """
        UPDATE fuel_tracker
        SET date =?, hours =?, gallons =?, price_per_gallon =?,
            total_cost =?, gal_per_hour =?
        WHERE id = ?
        """,
        (date, hours, gallons, price, total_cost, gal_per_hour, id),
    )
    conn.commit()
    conn.close()

    return redirect(url_for("index"))


@app.route("/delete_flight/<int:id>")
def delete_flight(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM flight_log WHERE id = ?", (id,))
    conn.commit()
    return redirect(url_for("index"))


@app.route("/delete_maintenance/<int:id>")
def delete_maintenance(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM maintenance_entries WHERE id = ?", (id,))
    conn.commit()
    return redirect(url_for("index"))


@app.route("/delete_fuel/<int:id>")
def delete_fuel(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM fuel_tracker WHERE rowid = ?", (id,))
    conn.commit()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=False)
