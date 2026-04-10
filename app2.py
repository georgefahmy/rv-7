import sqlite3
from datetime import datetime

from flask import Flask, jsonify, redirect, render_template, request, url_for

# Import your scraper function
from scripts.fuel_prices import scrape_airnav_to_json

app = Flask(__name__)
DB_PATH = "scripts/maintenance.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def index():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Fetch Flight Logs (convert to standard dictionaries)
    cursor.execute(
        """
        SELECT date, takeoff_airport, landing_airport, hobbs, tach,
               hobbs_delta, tach_delta, landings, notes
        FROM flight_log ORDER BY date DESC, hobbs DESC
    """
    )
    flight_logs = [dict(row) for row in cursor.fetchall()]

    # 2. Fetch Maintenance Logs (convert to standard dictionaries)
    cursor.execute("SELECT * FROM maintenance_entries ORDER BY date DESC")
    mx_logs = [dict(row) for row in cursor.fetchall()]

    # 3. Fetch fuel logs
    cursor.execute("SELECT * FROM fuel_tracker ORDER BY date DESC")
    fuel_logs = [dict(row) for row in cursor.fetchall()]

    # 4. Fetch Totals
    cursor.execute(
        "SELECT hobbs FROM flight_log ORDER BY date DESC, hobbs DESC LIMIT 1"
    )
    hobbs_res = cursor.fetchone()
    total_hours = hobbs_res[0] if hobbs_res and hobbs_res else 0.0

    cursor.execute("SELECT SUM(landings) as total_ldgs FROM flight_log")
    l_res = cursor.fetchone()
    total_landings = l_res[0] if l_res and l_res else 0

    conn.close()

    # Render the template with placeholder due dates (update with your logic)
    return render_template(
        "index2.html",
        flight_logs=flight_logs,
        mx_logs=mx_logs,
        fuel_logs=fuel_logs,
        total_hours=total_hours,
        total_landings=total_landings,
        overdue_count=0,
        cond_due="2026-10-31 (180 days)",
        cond_status_class="status-current",
        oil_due="50.0 hrs (8.2 hrs left)",
        oil_status_class="status-warning",
        aviation_db_due="Current",
        nav_status_class="status-current",
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


if __name__ == "__main__":
    app.run(debug=True)
