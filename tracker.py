import base64
import sqlite3
from datetime import datetime, timedelta

import FreeSimpleGUI as sg
from numpy import mean

from scripts.fuel_prices import scrape_airnav_to_json
from scripts.src.constants import (
    CURRENT_COLOR,
    DEFAULT_COLOR,
    ELT_TEST_INTERVAL_DAYS,
    MX_CATEGORIES,
    OAS_AVIATION_DB_INTERVAL_DAYS,
    OIL_CHANGE_INTERVAL_HOURS,
    OVERDUE_COLOR,
    RECURRENT_ITEMS,
    WARNING_COLOR,
)
from scripts.src.entry_layout import entry_layout
from scripts.src.flight_layout import flight_layout
from scripts.src.fuel_layout import fuel_layout
from scripts.src.tracker_layout import main_layout

sg.theme("Reddit")
sg.set_options(font=("Arial", 14))
sg.set_options(icon=base64.b64encode(open(str("paint_logo.png"), "rb").read()))


# --- Override for Total Airframe Hours ---
current_total_hours_override = None


def update_database_due_dates(window):
    today = datetime.today().date()
    url = "https://dynonavionics.com/us-aviation-obstacle-data.php"

    aviation_status = "--"
    obstacle_status = "--"

    try:
        import re

        import requests
        from bs4 import BeautifulSoup

        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Parse the external web dates for current window
        spans = soup.find_all(string=lambda t: "Valid:" in t)
        if len(spans) >= 2:
            aviation_valid_text = spans[0].split("Valid:")[-1].strip()
            obstacle_valid_text = spans[1].split("Valid:")[-1].strip()

            # Extract the first date in the range as the start of the cycle
            match_aviation = re.search(r"([A-Za-z]+ \d{1,2})", aviation_valid_text)
            match_obstacle = re.search(r"([A-Za-z]+ \d{1,2})", obstacle_valid_text)
            today = datetime.today().date()

            if match_aviation:
                date_aviation = datetime.strptime(
                    match_aviation.group(1) + f" {today.year}", "%B %d %Y"
                ).date()
            else:
                date_aviation = None

            if match_obstacle:
                date_obstacle = datetime.strptime(
                    match_obstacle.group(1) + f" {today.year}", "%B %d %Y"
                ).date()
            else:
                date_obstacle = None

            # Fetch most recent Nav Data Update entry
            cursor.execute(
                "SELECT date FROM maintenance_entries WHERE recurrent_item='Nav Data Update' ORDER BY date DESC LIMIT 1"
            )
            nav_entry = cursor.fetchone()

            if nav_entry and nav_entry[0] and date_aviation and date_obstacle:
                nav_date = datetime.strptime(nav_entry[0], "%m/%d/%Y").date()

                # Check if nav_date falls within current web window
                aviation_status = "Current" if nav_date >= date_aviation else "Overdue"
                obstacle_status = "Current" if nav_date >= date_obstacle else "Overdue"
            else:
                aviation_status = "Overdue"
                obstacle_status = "Overdue"

        else:
            aviation_status = "--"
            obstacle_status = "--"

        aviation_color = (
            CURRENT_COLOR
            if aviation_status == "Current"
            else OVERDUE_COLOR if aviation_status == "Overdue" else DEFAULT_COLOR
        )
        obstacle_color = (
            CURRENT_COLOR
            if obstacle_status == "Current"
            else OVERDUE_COLOR if obstacle_status == "Overdue" else DEFAULT_COLOR
        )

        window["aviation_db_due_text"].update(
            aviation_status, text_color=aviation_color
        )
        window["obstacle_db_due_text"].update(
            obstacle_status, text_color=obstacle_color
        )
        window["aviation_valid_dates"].update(
            aviation_valid_text, text_color=DEFAULT_COLOR
        )
        window["obstacle_valid_dates"].update(
            obstacle_valid_text, text_color=DEFAULT_COLOR
        )

    except Exception as e:
        print("Failed to fetch aviation/obstacle dates:", e)
        window["aviation_db_due_text"].update("--")
        window["obstacle_db_due_text"].update("--")


def recalculate_flight_deltas():
    cursor.execute(
        "SELECT id, hobbs, tach FROM flight_log ORDER BY date ASC, hobbs ASC"
    )
    rows = cursor.fetchall()

    previous_hobbs = None
    previous_tach = None

    for entry_id, hobbs, tach in rows:
        hobbs_delta = None
        tach_delta = None

        if previous_hobbs is not None and hobbs is not None:
            hobbs_delta = round(float(hobbs) - float(previous_hobbs), 2)

        if previous_tach is not None and tach is not None:
            tach_delta = round(float(tach) - float(previous_tach), 2)

        cursor.execute(
            "UPDATE flight_log SET hobbs_delta=?, tach_delta=? WHERE id=?",
            (hobbs_delta, tach_delta, entry_id),
        )

        previous_hobbs = hobbs
        previous_tach = tach

    conn.commit()


def refresh_flight_log_table(window):
    cursor.execute(
        "SELECT date, takeoff_airport, landing_airport, hobbs, tach, hobbs_delta, tach_delta, landings, notes FROM flight_log ORDER BY date DESC, hobbs DESC"
    )
    rows = cursor.fetchall()
    window["flight_log_table"].update(values=rows)
    return rows


def refresh_table(window):
    cursor.execute(
        "SELECT * FROM maintenance_entries ORDER BY airframe_time DESC, id DESC, date DESC"
    )
    rows = cursor.fetchall()
    window["maintenance_table"].update(values=rows)


def calculate_overdue():
    cursor.execute(
        "SELECT recurrent_item, MAX(date) FROM maintenance_entries GROUP BY recurrent_item"
    )
    rows = cursor.fetchall()

    overdue_count = 0
    today = datetime.today().date()

    for item, last_date in rows:
        if not last_date:
            continue

        try:
            last_dt = datetime.strptime(last_date, "%m/%d/%Y").date()
        except:
            continue

        if item == "Condition Inspection":
            due_date = last_dt + timedelta(days=365)
            if today > due_date:
                overdue_count += 1

        elif item == "ELT Test":
            due_date = last_dt + timedelta(days=ELT_TEST_INTERVAL_DAYS)
            if today > due_date:
                overdue_count += 1

        elif item == "ELT Batteries":
            due_date = last_dt + timedelta(days=365 * 7)
            if today > due_date:
                overdue_count += 1

        elif item == "ELT Registration":
            due_date = last_dt + timedelta(days=365 * 2)
            if today > due_date:
                overdue_count += 1

        elif item == "Nav Data Update":
            # Use aviation/obstacle DB intervals to determine overdue
            if today - last_dt > timedelta(days=OAS_AVIATION_DB_INTERVAL_DAYS):
                overdue_count += 1

        elif item == "Transponder Check":
            # Use aviation/obstacle DB intervals to determine overdue
            if today - last_dt > timedelta(days=365 * 2):
                overdue_count += 1

    return overdue_count


def update_due_dates(window):
    today = datetime.today().date()

    # --- Find latest Condition Inspection entry ---
    cursor.execute(
        """
        SELECT date
        FROM maintenance_entries
        WHERE recurrent_item=?
        ORDER BY date DESC
        LIMIT 1
        """,
        ("Condition Inspection",),
    )
    ci_result = cursor.fetchone()
    if ci_result and ci_result[0]:
        last_date = ci_result[0]
        try:
            from calendar import monthrange

            last_dt = datetime.strptime(last_date, "%m/%d/%Y").date()
            preliminary_due = last_dt + timedelta(days=365)

            # Set due date to last day of that month
            last_day = monthrange(preliminary_due.year, preliminary_due.month)[1]
            due_date = preliminary_due.replace(day=last_day)

            days_remaining = (due_date - today).days
            cond_due = f"{due_date.strftime('%Y-%m-%d')} ({days_remaining} days)"
            if days_remaining < 0:
                cond_color = OVERDUE_COLOR
            elif days_remaining <= 30:
                cond_color = WARNING_COLOR
            else:
                cond_color = DEFAULT_COLOR
        except:
            cond_due = "--"
            cond_color = DEFAULT_COLOR
    else:
        cond_due = "--"
        cond_color = DEFAULT_COLOR

    # --- Find latest Transponder Check entry ---
    cursor.execute(
        """
        SELECT date
        FROM maintenance_entries
        WHERE recurrent_item=?
        ORDER BY date DESC
        LIMIT 1
        """,
        ("Transponder Check",),
    )
    ci_result = cursor.fetchone()
    if ci_result and ci_result[0]:
        last_date = ci_result[0]
        try:
            from calendar import monthrange

            last_dt = datetime.strptime(last_date, "%m/%d/%Y").date()
            preliminary_due = last_dt + timedelta(days=365 * 2)

            # Set due date to last day of that month
            last_day = monthrange(preliminary_due.year, preliminary_due.month)[1]
            due_date = preliminary_due.replace(day=last_day)

            days_remaining = (due_date - today).days
            xpndr_due = f"{due_date.strftime('%Y-%m-%d')} ({days_remaining} days)"
            if days_remaining < 0:
                xpndr_color = OVERDUE_COLOR
            elif days_remaining <= 30:
                xpndr_color = WARNING_COLOR
            else:
                xpndr_color = DEFAULT_COLOR
        except:
            xpndr_due = "--"
            xpndr_color = DEFAULT_COLOR
    else:
        xpndr_due = "--"
        xpndr_color = DEFAULT_COLOR

    # --- Find latest Oil Change entry ---
    cursor.execute(
        """
        SELECT date, tach_time
        FROM maintenance_entries
        WHERE recurrent_item=?
        ORDER BY date DESC
        LIMIT 1
        """,
        ("Oil Change",),
    )
    oil_result = cursor.fetchone()
    oil_due = "--"
    oil_color = DEFAULT_COLOR
    if oil_result and oil_result[1] is not None:
        last_tach = oil_result[1]
        try:
            tach_val = float(last_tach)
            if tach_val < 50:
                interval = 10
            else:
                interval = OIL_CHANGE_INTERVAL_HOURS

            next_due_tach = tach_val + interval
            # Determine current aircraft tach (max tach in DB)
            cursor.execute("SELECT MAX(tach) FROM flight_log")
            current_tach = cursor.fetchone()[0]
            hours_remaining = None
            if current_tach is not None:
                hours_remaining = next_due_tach - float(current_tach)
            if hours_remaining is not None:
                oil_due = f"{next_due_tach:.1f} hrs ({hours_remaining:.1f} hrs left)"
                if hours_remaining < 0:
                    oil_color = OVERDUE_COLOR
                elif hours_remaining <= 5:
                    oil_color = WARNING_COLOR
                else:
                    oil_color = DEFAULT_COLOR
            else:
                oil_due = f"{next_due_tach:.1f} hrs"
        except:
            oil_due = "--"
            oil_color = DEFAULT_COLOR
    else:
        oil_due = "--"
        oil_color = DEFAULT_COLOR

    # --- ELT Test (90 days) ---
    cursor.execute(
        """
        SELECT date
        FROM maintenance_entries
        WHERE recurrent_item=?
        ORDER BY date DESC
        LIMIT 1
        """,
        ("ELT Test",),
    )
    elt_test_result = cursor.fetchone()

    elt_test_due = "--"
    elt_test_color = DEFAULT_COLOR

    if elt_test_result and elt_test_result[0]:
        try:
            last_dt = datetime.strptime(elt_test_result[0], "%m/%d/%Y").date()
            due_date = last_dt + timedelta(days=ELT_TEST_INTERVAL_DAYS)
            days_remaining = (due_date - today).days
            elt_test_due = (
                f"Test: {due_date.strftime('%Y-%m-%d')} ({days_remaining} days)"
            )

            if days_remaining < 0:
                elt_test_color = OVERDUE_COLOR
            elif days_remaining <= 30:
                elt_test_color = WARNING_COLOR
        except:
            elt_test_due = "Test: --"

    # --- ELT Batteries (7 years) ---
    cursor.execute(
        """
        SELECT date
        FROM maintenance_entries
        WHERE recurrent_item=?
        ORDER BY date DESC
        LIMIT 1
        """,
        ("ELT Batteries",),
    )
    elt_batt_result = cursor.fetchone()

    elt_batt_due = "Bat: --"
    if elt_batt_result and elt_batt_result[0]:
        try:
            last_dt = datetime.strptime(elt_batt_result[0], "%m/%d/%Y").date()
            due_date = last_dt + timedelta(days=365 * 5)
            days_remaining = (due_date - today).days
            elt_batt_due = (
                f"Bat: {due_date.strftime('%Y-%m-%d')} ({days_remaining} days)"
            )
        except:
            pass

    # --- ELT Registration (2 years) ---
    cursor.execute(
        """
        SELECT date
        FROM maintenance_entries
        WHERE recurrent_item=?
        ORDER BY date DESC
        LIMIT 1
        """,
        ("ELT Registration",),
    )
    elt_reg_result = cursor.fetchone()

    elt_reg_due = "Reg: --"
    if elt_reg_result and elt_reg_result[0]:
        try:
            last_dt = datetime.strptime(elt_reg_result[0], "%m/%d/%Y").date()
            due_date = last_dt + timedelta(days=365 * 2)
            days_remaining = (due_date - today).days
            elt_reg_due = (
                f"Reg: {due_date.strftime('%Y-%m-%d')} ({days_remaining} days)"
            )
        except:
            pass

    elt_due = f"{elt_test_due}\n{elt_batt_due}\n{elt_reg_due}"
    elt_color = elt_test_color

    window["cond_due_text"].update(cond_due, text_color=cond_color)
    window["xpndr_due_text"].update(xpndr_due, text_color=xpndr_color)
    window["oil_due_text"].update(oil_due, text_color=oil_color)
    window["elt_due_text"].update(elt_due, text_color=elt_color)


def resequence_ids():
    cursor.execute("SELECT id FROM maintenance_entries ORDER BY id")
    rows = cursor.fetchall()

    new_id = 1
    for (old_id,) in rows:
        cursor.execute(
            "UPDATE maintenance_entries SET id=? WHERE id=?",
            (new_id, old_id),
        )
        new_id += 1

    # Reset SQLite autoincrement counter
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='maintenance_entries'")
    conn.commit()


def update_total_airframe_hours(window):
    cursor.execute(
        "SELECT hobbs FROM flight_log ORDER BY date DESC, hobbs DESC LIMIT 1"
    )
    result = cursor.fetchone()

    total_hours = float(result[0]) if result and result[0] is not None else 0.0

    window["total_airframe_text"].update(f"Total Hours: {total_hours:.1f}")

    # Calculate total landings
    cursor.execute("SELECT SUM(landings) FROM flight_log")
    result = cursor.fetchone()
    total_landings = int(result[0]) if result and result[0] is not None else 0

    window["total_landings_text"].update(f"Total Landings: {total_landings}")


conn = sqlite3.connect("scripts/maintenance.db")
cursor = conn.cursor()

# --- Create Mx Entries table ---
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS maintenance_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date DATE NOT NULL,
        tach_time REAL,
        airframe_time REAL,
        notes TEXT,
        recurrent_item TEXT,
        category TEXT
    )
    """
)
conn.commit()
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS aircraft_totals (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        total_airframe_hours REAL
    )
    """
)
conn.commit()
cursor.execute("SELECT total_airframe_hours FROM aircraft_totals WHERE id=1")
if cursor.fetchone() is None:
    cursor.execute(
        "INSERT INTO aircraft_totals (id, total_airframe_hours) VALUES (1, 0.0)"
    )
    conn.commit()

# --- Create flight_log table ---
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS flight_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date DATE NOT NULL,
        takeoff_airport TEXT,
        landing_airport TEXT,
        hobbs REAL,
        tach REAL,
        hobbs_delta REAL,
        tach_delta REAL,
        landings INTEGER,
        notes TEXT
    )
    """
)
conn.commit()

# --- Create fuel_tracker table ---
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS fuel_tracker (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        hours REAL,
        gallons REAL,
        price_per_gallon REAL,
        total_cost REAL,
        gal_per_hour REAL
    )
    """
)
conn.commit()


window = sg.Window(title="N890GF", layout=main_layout, finalize=True)
# Bind double-click event for flight log table
window["flight_log_table"].bind("<Double-Button-1>", "_DOUBLE_CLICK")

# Initial load of table and summary
refresh_table(window)
update_due_dates(window)
update_total_airframe_hours(window)
update_database_due_dates(window)
rows = refresh_flight_log_table(window)

# Initialize overdue count on startup
initial_overdue = calculate_overdue()
window["overdue_text"].update(initial_overdue)

while True:
    event, values = window.read()
    if event in (sg.WINDOW_CLOSED, "Exit"):
        break

    if event == "sw_db_updates":
        exec(open("scripts/sw_db_updates.py", "r").read())

    if event == "analysis":
        exec(open("scripts/analysis.py", "r").read())

    if event == "flight_log_table_DOUBLE_CLICK":
        selected = values.get("flight_log_table")
        if selected:
            row_index = selected[0]
            table_data = rows
            row = table_data[row_index]

            details = (
                f"{row[0]}\n"
                f"From: {row[1]} to {row[2]}\n"
                f"Hobbs: +{row[5]}hrs (Tot: {row[3]}hrs)\n"
                f"Tach: +{row[6]}hrs (Tot: {row[4]}hrs)\n\n"
                f"Notes: {row[8]}"
            )

            sg.popup_ok(
                "Flight Details",
                details,
                title="Flight Log Details",
                non_blocking=True,
            )
    if event == "fuel_tracker_button":
        # Load existing fuel entries
        cursor.execute(
            "SELECT date, hours, gallons, price_per_gallon, total_cost, gal_per_hour FROM fuel_tracker ORDER BY id DESC"
        )
        fuel_rows = cursor.fetchall()

        total_gallons = sum(r[2] for r in fuel_rows) if fuel_rows else 0
        total_spent = sum(r[4] for r in fuel_rows) if fuel_rows else 0
        gal_per_hour_avg = mean(list(r[5] for r in fuel_rows) if fuel_rows else 0)
        dollar_per_hour_avg = (
            total_spent / total_gallons * gal_per_hour_avg if total_gallons else 0
        )

        fuel_window = sg.Window(
            "Fuel Tracker",
            fuel_layout(
                fuel_rows=fuel_rows,
                total_gallons=total_gallons,
                total_spent=total_spent,
                gal_per_hour_avg=gal_per_hour_avg,
                dollar_per_hour_avg=dollar_per_hour_avg,
            ),
            modal=True,
        )

        while True:
            f_event, f_values = fuel_window.read()

            if f_event in (sg.WINDOW_CLOSED, "Cancel"):
                fuel_window.close()
                break

            if f_event == "fuel_price_submit":
                airport = f_values["fuel_price_search"]
                options, output = scrape_airnav_to_json(airport)
                output_string = ""
                for i in output:
                    output_string += f"{i}\n"

                popup_layout = [
                    [
                        sg.Multiline(
                            default_text=output_string,
                            disabled=True,
                            background_color="white",
                            size=(120, 20),
                            selected_background_color="white",
                            selected_text_color="black",
                            no_scrollbar=True,
                        )
                    ]
                ]
                popup_window = sg.Window(
                    "Nearby Fuel Prices", layout=popup_layout, modal=True, finalize=True
                )
                popup_window.read()

            if (
                f_event == "fuel_price"
                or f_event == "fuel_gallons"
                or f_event == "fuel_hours"
            ):
                if f_values["fuel_gallons"] and f_values["fuel_price"]:
                    try:
                        hours = float(f_values["fuel_hours"])
                        gallons = float(f_values["fuel_gallons"])
                        price = float(f_values["fuel_price"])
                        total = round(gallons * price, 2)
                        gal_per_hour = round(gallons / hours, 2)
                        fuel_window["fuel_total"].update(total)
                        fuel_window["gal_per_hour"].update(gal_per_hour)
                    except:
                        sg.popup("Enter valid gallons and price.")

            if f_event == "Save":
                try:
                    date = f_values["fuel_date"]
                    hours = float(f_values["fuel_hours"])
                    gallons = float(f_values["fuel_gallons"])
                    price = float(f_values["fuel_price"])
                    total = round(gallons * price, 2)
                    gal_per_hour = round(gallons / hours, 2)

                    cursor.execute(
                        "INSERT INTO fuel_tracker (date, hours, gallons, price_per_gallon, total_cost, gal_per_hour) VALUES (?, ?, ?, ?, ?, ?)",
                        (date, hours, gallons, price, total, gal_per_hour),
                    )
                    conn.commit()

                    sg.popup("Fuel entry saved.")
                    # Refresh the table and totals after saving
                    fuel_window["fuel_date"].update("")
                    fuel_window["fuel_hours"].update("")
                    fuel_window["fuel_gallons"].update("")
                    fuel_window["fuel_price"].update("")
                    fuel_window["fuel_total"].update("")
                    fuel_window["gal_per_hour"].update("")
                    # fuel_window["dollar_per_hour"].update("")
                    cursor.execute(
                        "SELECT date, hours, gallons, price_per_gallon, total_cost, gal_per_hour FROM fuel_tracker ORDER BY id DESC"
                    )
                    fuel_rows = cursor.fetchall()
                    fuel_window["fuel_table"].update(values=fuel_rows)

                    total_gallons = sum(r[2] for r in fuel_rows) if fuel_rows else 0
                    total_spent = sum(r[4] for r in fuel_rows) if fuel_rows else 0
                    gal_per_hour_avg = mean(
                        list(r[5] for r in fuel_rows) if fuel_rows else 0
                    )
                    dollar_per_hour_avg = (
                        total_spent / total_gallons * gal_per_hour_avg
                        if total_gallons
                        else 0
                    )

                    fuel_window["fuel_total_gallons"].update(
                        f"Total Fuel Used: {round(total_gallons, 2)} gal"
                    )
                    fuel_window["fuel_total_spent"].update(
                        f"Total Money Spent: ${round(total_spent, 2)}"
                    )
                    fuel_window["gal_per_hour_avg"].update(
                        f"Average Fuel Consumption: {round(gal_per_hour_avg, 2)} gal/hr"
                    )
                    fuel_window["dollar_per_hour_avg"].update(
                        f"Average Cost Per Hour: ${round(dollar_per_hour_avg, 2)}/hr"
                    )
                except Exception as e:
                    sg.popup(f"Error saving fuel entry: {e}")

            if f_event == "Edit Selected":
                try:
                    selected = f_values["fuel_table"]
                    if not selected:
                        sg.popup("Select a row to edit.")
                        continue

                    row_index = selected[0]
                    date, hours, gallons, price, total, gal_per_hour = fuel_rows[
                        row_index
                    ]

                    # Populate fields with selected row values
                    fuel_window["fuel_date"].update(date)
                    fuel_window["fuel_hours"].update(hours)
                    fuel_window["fuel_gallons"].update(gallons)
                    fuel_window["fuel_price"].update(price)
                    fuel_window["fuel_total"].update(total)
                    fuel_window["gal_per_hour"].update(gal_per_hour)

                    # Store index being edited
                    editing_index = row_index

                except Exception as e:
                    sg.popup(f"Error selecting row: {e}")

            if f_event == "Delete Selected":
                try:
                    selected = f_values["fuel_table"]
                    if not selected:
                        sg.popup("Select a row to delete.")
                        continue

                    row_index = selected[0]
                    date, hours, gallons, price, total, gal_per_hour = fuel_rows[
                        row_index
                    ]

                    confirm = sg.popup_yes_no("Delete this fuel entry?")
                    if confirm != "Yes":
                        continue

                    cursor.execute(
                        "DELETE FROM fuel_tracker WHERE date=? AND hours=? AND gallons=? AND price_per_gallon=? AND total_cost=? AND gal_per_hour=?",
                        (date, hours, gallons, price, total, gal_per_hour),
                    )
                    conn.commit()

                    # Refresh table
                    cursor.execute(
                        "SELECT date, hours, gallons, price_per_gallon, total_cost, gal_per_hour FROM fuel_tracker ORDER BY id DESC"
                    )
                    fuel_rows = cursor.fetchall()
                    fuel_window["fuel_table"].update(values=fuel_rows)

                    total_gallons = sum(r[2] for r in fuel_rows) if fuel_rows else 0
                    total_spent = sum(r[4] for r in fuel_rows) if fuel_rows else 0
                    gal_per_hour_avg = mean(
                        list(r[5] for r in fuel_rows) if fuel_rows else 0
                    )
                    dollar_per_hour_avg = (
                        total_spent / total_gallons * gal_per_hour_avg
                        if total_gallons
                        else 0
                    )

                    fuel_window["fuel_total_gallons"].update(
                        f"Total Fuel Used: {round(total_gallons, 2)} gal"
                    )
                    fuel_window["fuel_total_spent"].update(
                        f"Total Money Spent: ${round(total_spent, 2)}"
                    )
                    fuel_window["gal_per_hour_avg"].update(
                        f"Average Fuel Consumption: {round(gal_per_hour_avg, 2)} gal/hr"
                    )
                    fuel_window["dollar_per_hour_avg"].update(
                        f"Average Cost Per Hour: ${round(dollar_per_hour_avg, 2)}/hr"
                    )

                except Exception as e:
                    sg.popup(f"Error deleting entry: {e}")

    if event == "add_entry_button":

        entry_window = sg.Window(
            "Add Maintenance Entry",
            entry_layout(recurrent_items=RECURRENT_ITEMS, mx_categories=MX_CATEGORIES),
            modal=True,
        )
        while True:
            e_event, e_values = entry_window.read()
            if e_event in (sg.WINDOW_CLOSED, "Cancel"):
                entry_window.close()
                break
            if e_event == "submit_entry":
                date = e_values.get("date_input")
                tach = e_values.get("tach_hours_input")
                airframe = e_values.get("total_hours_input")
                # If tach or airframe hours are missing, use the most recent values from the database
                if not tach:
                    cursor.execute(
                        "SELECT tach_time FROM maintenance_entries WHERE tach_time IS NOT NULL ORDER BY date DESC LIMIT 1"
                    )
                    last_tach = cursor.fetchone()
                    if last_tach:
                        tach = last_tach[0]

                if not airframe:
                    cursor.execute(
                        "SELECT airframe_time FROM maintenance_entries WHERE airframe_time IS NOT NULL ORDER BY date DESC LIMIT 1"
                    )
                    last_airframe = cursor.fetchone()
                    if last_airframe:
                        airframe = last_airframe[0]

                notes = e_values.get("notes_input")
                recurrent_item = e_values.get("recurrent_item_input")
                category = e_values.get("category_input")

                if date:
                    cursor.execute(
                        """
                        INSERT INTO maintenance_entries
                        (date, tach_time, airframe_time, notes, recurrent_item, category)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (date, tach, airframe, notes, recurrent_item, category),
                    )
                    conn.commit()

                    refresh_table(window)
                    update_due_dates(window)
                    update_total_airframe_hours(window)
                    update_database_due_dates(window)
                    overdue = calculate_overdue()
                    window["overdue_text"].update(overdue)
                    sg.popup("Maintenance entry saved.")

                    # Clear entry fields
                    entry_window["date_input"].update("")
                    entry_window["tach_hours_input"].update("")
                    entry_window["total_hours_input"].update("")
                    entry_window["notes_input"].update("")
                    entry_window["recurrent_item_input"].update("")
                    entry_window["category_input"].update("")
                    entry_window.close()
                    break

    if event == "flight_log_button":

        flight_window = sg.Window("Flight Log Entry", flight_layout, modal=True)

        while True:
            f_event, f_values = flight_window.read()
            if f_event in (sg.WINDOW_CLOSED, "Cancel"):
                flight_window.close()
                break

            if f_event == "Submit":
                try:
                    # Get most recent flight for delta calculation
                    cursor.execute(
                        "SELECT hobbs, tach FROM flight_log ORDER BY date DESC, hobbs DESC LIMIT 1"
                    )
                    previous = cursor.fetchone()

                    hobbs_val = (
                        float(f_values["flight_hobbs"])
                        if f_values["flight_hobbs"]
                        else None
                    )
                    tach_val = (
                        float(f_values["flight_tach"])
                        if f_values["flight_tach"]
                        else None
                    )

                    hobbs_delta = None
                    tach_delta = None

                    if previous and hobbs_val is not None and previous[0] is not None:
                        hobbs_delta = round(hobbs_val - float(previous[0]), 2)

                    if previous and tach_val is not None and previous[1] is not None:
                        tach_delta = round(tach_val - float(previous[1]), 2)

                    cursor.execute(
                        """
                        INSERT INTO flight_log
                        (date, takeoff_airport, landing_airport, hobbs, tach, hobbs_delta, tach_delta, landings, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            f_values["flight_date"],
                            f_values["flight_takeoff"],
                            f_values["flight_landing"],
                            hobbs_val,
                            tach_val,
                            hobbs_delta,
                            tach_delta,
                            f_values["flight_landings"],
                            f_values["flight_notes"],
                        ),
                    )
                    conn.commit()
                    recalculate_flight_deltas()
                    refresh_flight_log_table(window)
                    update_due_dates(window)
                    update_total_airframe_hours(window)
                except Exception as e:
                    sg.popup(f"Error saving flight log: {e}")

                flight_window.close()
                break

    if event == "Delete Selected":
        selected = values["maintenance_table"]
        if selected:
            row_index = selected[0]
            table_data = window["maintenance_table"].get()
            entry_id = table_data[row_index][0]

            cursor.execute("DELETE FROM maintenance_entries WHERE id=?", (entry_id,))
            conn.commit()

            resequence_ids()
            refresh_table(window)
            update_due_dates(window)
            update_total_airframe_hours(window)
            update_database_due_dates(window)

    if event == "Delete Flight Selected":
        selected = values["flight_log_table"]
        if selected:
            row_index = selected[0]
            table_data = window["flight_log_table"].get()
            row = table_data[row_index]

            date_val = row[0]
            hobbs_val = row[3]

            cursor.execute(
                "DELETE FROM flight_log WHERE date=? AND hobbs=?",
                (date_val, hobbs_val),
            )
            conn.commit()
            recalculate_flight_deltas()
            refresh_table(window)
            update_due_dates(window)
            update_total_airframe_hours(window)
            update_database_due_dates(window)

    if event == "Edit Flight Selected":
        selected = values["flight_log_table"]
        if selected:
            row_index = selected[0]
            table_data = window["flight_log_table"].get()
            row = table_data[row_index]

            original_date = row[0]
            original_hobbs = row[3]

            edit_layout = [
                [sg.Text("Date"), sg.Input(row[0], key="edit_flight_date")],
                [sg.Text("Takeoff"), sg.Input(row[1], key="edit_flight_takeoff")],
                [sg.Text("Landing"), sg.Input(row[2], key="edit_flight_landing")],
                [sg.Text("Hobbs"), sg.Input(row[3], key="edit_flight_hobbs")],
                [sg.Text("Tach"), sg.Input(row[4], key="edit_flight_tach")],
                [sg.Text("Landings"), sg.Input(row[7], key="edit_flight_landings")],
                [sg.Text("Notes"), sg.Input(row[8], key="edit_flight_notes")],
                [sg.Button("Save"), sg.Button("Cancel")],
            ]

            edit_window = sg.Window("Edit Flight Entry", edit_layout, modal=True)

            while True:
                e_event, e_values = edit_window.read()
                if e_event in (sg.WINDOW_CLOSED, "Cancel"):
                    edit_window.close()
                    break

                if e_event == "Save":
                    cursor.execute(
                        """
                        UPDATE flight_log
                        SET date=?, takeoff_airport=?, landing_airport=?, hobbs=?, tach=?, landings=?, notes=?
                        WHERE date=? AND hobbs=?
                        """,
                        (
                            e_values["edit_flight_date"],
                            e_values["edit_flight_takeoff"],
                            e_values["edit_flight_landing"],
                            e_values["edit_flight_hobbs"],
                            e_values["edit_flight_tach"],
                            e_values["edit_flight_landings"],
                            e_values["edit_flight_notes"],
                            original_date,
                            original_hobbs,
                        ),
                    )
                    conn.commit()
                    recalculate_flight_deltas()
                    refresh_table(window)
                    update_due_dates(window)
                    update_total_airframe_hours(window)
                    update_database_due_dates(window)
                    edit_window.close()
                    break

    if event == "Edit Selected":
        selected = values["maintenance_table"]
        if selected:
            row_index = selected[0]
            table_data = window["maintenance_table"].get()
            row = table_data[row_index]

            entry_id = row[0]

            # Pre-fill existing values
            edit_layout = [
                [sg.Text("Date"), sg.Input(row[1], key="edit_date")],
                [sg.Text("Tach Hours"), sg.Input(row[2], key="edit_tach")],
                [sg.Text("Airframe Hours"), sg.Input(row[3], key="edit_airframe")],
                [sg.Text("Notes"), sg.Input(row[4], key="edit_notes")],
                [
                    sg.Text("Recurrent Item"),
                    sg.DropDown(
                        RECURRENT_ITEMS,
                        default_value=row[5],
                        key="edit_recurrent_item",
                    ),
                ],
                [
                    sg.Text("Category"),
                    sg.DropDown(
                        MX_CATEGORIES,
                        default_value=row[6],
                        key="edit_category",
                    ),
                ],
                [sg.Button("Save"), sg.Button("Cancel")],
            ]

            edit_window = sg.Window(f"Edit Entry ID {entry_id}", edit_layout)

            while True:
                e_event, e_values = edit_window.read()
                if e_event in (sg.WINDOW_CLOSED, "Cancel"):
                    edit_window.close()
                    break
                if e_event == "Save":
                    cursor.execute(
                        """
                        UPDATE maintenance_entries
                        SET date=?, tach_time=?, airframe_time=?, notes=?, recurrent_item=?, category=?
                        WHERE id=?
                        """,
                        (
                            e_values["edit_date"],
                            e_values["edit_tach"],
                            e_values["edit_airframe"],
                            e_values["edit_notes"],
                            e_values["edit_recurrent_item"],
                            e_values["edit_category"],
                            entry_id,
                        ),
                    )
                    conn.commit()
                    refresh_table(window)
                    update_due_dates(window)
                    update_total_airframe_hours(window)
                    update_database_due_dates(window)
                    edit_window.close()
                    break
