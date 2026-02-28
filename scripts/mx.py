import sqlite3
from datetime import datetime, timedelta

import PySimpleGUI as sg

sg.theme("Reddit")
sg.set_options(font=("Arial", 14))

# --- Maintenance Interval Configuration ---
OIL_CHANGE_INTERVAL_HOURS = 50
CONDITION_INSPECTION_INTERVAL_MONTHS = 12
ELT_TEST_INTERVAL_DAYS = 90

# --- FAA Aviation/Obstacle DB Intervals ---
OAS_AVIATION_DB_INTERVAL_DAYS = 28  # example 28-day FAA cycle
OAS_OBSTACLE_DB_INTERVAL_DAYS = 56


# --- Colors ---
DEFAULT_COLOR = "black"
OVERDUE_COLOR = "red"
WARNING_COLOR = "yellow"
CURRENT_COLOR = "green"

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


def refresh_table(window):
    cursor.execute("SELECT * FROM maintenance_entries ORDER BY date DESC")
    rows = cursor.fetchall()

    updated_rows = []

    for row in rows:
        entry_id, date, tach, airframe, notes, recurrent_item, category = row
        updated_rows.append(
            [
                date,
                tach,
                airframe,
                notes,
                recurrent_item,
                category,
            ]
        )

    window["maintenance_table"].update(values=updated_rows)


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

        elif item == "Nav Data Update":
            # Use aviation/obstacle DB intervals to determine overdue
            if today - last_dt > timedelta(days=OAS_AVIATION_DB_INTERVAL_DAYS):
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
            cursor.execute("SELECT MAX(tach_time) FROM maintenance_entries")
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

    # --- Find latest ELT Test entry ---
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
    elt_result = cursor.fetchone()
    elt_due = "--"
    elt_color = DEFAULT_COLOR
    if elt_result and elt_result[0]:
        last_date = elt_result[0]
        try:
            last_dt = datetime.strptime(last_date, "%m/%d/%Y").date()
            due_date = last_dt + timedelta(days=ELT_TEST_INTERVAL_DAYS)
            days_remaining = (due_date - today).days
            elt_due = f"{due_date.strftime('%Y-%m-%d')} ({days_remaining} days)"
            if days_remaining < 0:
                elt_color = OVERDUE_COLOR
            elif days_remaining <= 30:
                elt_color = WARNING_COLOR
            else:
                elt_color = DEFAULT_COLOR
        except:
            elt_due = "--"
            elt_color = DEFAULT_COLOR
    else:
        elt_due = "--"
        elt_color = DEFAULT_COLOR

    window["cond_due_text"].update(cond_due, text_color=cond_color)
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
    cursor.execute("SELECT total_airframe_hours FROM aircraft_totals WHERE id=1")
    result = cursor.fetchone()
    total_hours = float(result[0]) if result and result[0] is not None else 0.0

    window["total_airframe_text"].update(f"Total Airframe Hours: {total_hours:.1f}")


conn = sqlite3.connect("scripts/maintenance.db")
cursor = conn.cursor()

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS maintenance_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
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

entry_layout = [
    [
        sg.Column(
            layout=[
                [sg.Text("Date", expand_x=True)],
                [sg.Input(key="date_input", expand_x=True, size=(10, 1))],
            ]
        ),
        sg.Column(
            layout=[
                [sg.Text("Total Hours", expand_x=True)],
                [sg.Input(key="total_hours_input", expand_x=True, size=(10, 1))],
            ]
        ),
        sg.Column(
            layout=[
                [sg.Text("Tach Hours", expand_x=True)],
                [sg.Input(key="tach_hours_input", expand_x=True, size=(10, 1))],
            ]
        ),
        sg.Column(
            layout=[
                [sg.Text("Notes", expand_x=True)],
                [sg.Input(key="notes_input", expand_x=True, size=(30, 1))],
            ]
        ),
        sg.Column(
            layout=[
                [sg.Text("Recurrent Item", expand_x=True)],
                [
                    sg.DropDown(
                        [
                            "Condition Inspection",
                            "Oil Change",
                            "ELT Test",
                            "Nav Data Update",
                        ],
                        key="recurrent_item_input",
                        expand_x=True,
                        size=(15, 1),
                    ),
                ],
            ]
        ),
        sg.Column(
            layout=[
                [sg.Text("Category", expand_x=True)],
                [
                    sg.DropDown(
                        ["Airframe", "Engine", "Propeller", "Avionics"],
                        key="category_input",
                        expand_x=True,
                        size=(15, 1),
                    ),
                ],
            ]
        ),
        sg.Column(
            layout=[
                [sg.Text("", expand_x=True)],
                [sg.Button("Submit", key="submit_entry", size=(10, 1))],
            ]
        ),
    ],
]


main_layout = [
    [
        sg.Text("N890GF Maintenance Tracker", font=("Arial", 24), expand_x=True),
        sg.Column(
            element_justification="right",
            layout=[
                [
                    sg.Text(
                        "Total Airframe Hours: 0",
                        font=("Arial", 18),
                        key="total_airframe_text",
                        justification="right",
                        expand_x=True,
                    ),
                ],
                [
                    sg.Button(
                        "Update",
                        font=("Arial", 12),
                        key="update_total_hours",
                    )
                ],
            ],
        ),
    ],
    [
        sg.Frame(
            title="MX Summary",
            expand_x=True,
            layout=[
                [
                    sg.Frame(
                        title="Overdue Items",
                        layout=[[sg.Text("0", font=("Arial", 16), key="overdue_text")]],
                        size=(120, 100),
                        expand_x=True,
                    ),
                    sg.Frame(
                        title="Condition Insp Due",
                        layout=[
                            [sg.Text("--", font=("Arial", 14), key="cond_due_text")]
                        ],
                        size=(180, 100),
                        expand_x=True,
                    ),
                    sg.Frame(
                        title="Oil Change Due",
                        layout=[
                            [sg.Text("--", font=("Arial", 14), key="oil_due_text")]
                        ],
                        size=(180, 100),
                        expand_x=True,
                    ),
                    sg.Frame(
                        title="ELT Due",
                        layout=[
                            [sg.Text("--", font=("Arial", 14), key="elt_due_text")]
                        ],
                        size=(180, 100),
                        expand_x=True,
                    ),
                    sg.Frame(
                        title="Aviation DB Due",
                        layout=[
                            [
                                sg.Text(
                                    "--", font=("Arial", 14), key="aviation_db_due_text"
                                )
                            ],
                            [
                                sg.Text(
                                    "--", font=("Arial", 9), key="aviation_valid_dates"
                                )
                            ],
                        ],
                        size=(180, 100),
                        expand_x=True,
                    ),
                    sg.Frame(
                        title="Obstacle DB Due",
                        layout=[
                            [
                                sg.Text(
                                    "--", font=("Arial", 14), key="obstacle_db_due_text"
                                )
                            ],
                            [
                                sg.Text(
                                    "--", font=("Arial", 9), key="obstacle_valid_dates"
                                )
                            ],
                        ],
                        size=(180, 100),
                        expand_x=True,
                    ),
                ],
            ],
        )
    ],
    [sg.Button("Add Entry", key="add_entry_button")],
    [sg.HorizontalSeparator()],
    [
        sg.Table(
            values=[],
            headings=[
                "Date",
                "Tach",
                "Airframe",
                "Notes",
                "Recurrent Item",
                "Category",
            ],
            key="maintenance_table",
            col_widths=[7, 5, 5, 60, 12, 10],  # Notes column is wider
            auto_size_columns=False,
            alternating_row_color="light gray",
            justification="left",
            enable_events=True,
            select_mode=sg.TABLE_SELECT_MODE_BROWSE,
            expand_x=True,
            expand_y=True,
            num_rows=10,
        )
    ],
    [
        sg.Button("Edit Selected"),
        sg.Button("Delete Selected"),
    ],
]

window = sg.Window(title="MX Tracker", layout=main_layout, finalize=True)

# Initial load of table and summary
refresh_table(window)
update_due_dates(window)
update_total_airframe_hours(window)
update_database_due_dates(window)

# Initialize overdue count on startup
initial_overdue = calculate_overdue()
window["overdue_text"].update(initial_overdue)

while True:
    event, values = window.read()
    if event in (sg.WINDOW_CLOSED, "Exit"):
        break

    if event == "update_total_hours":
        update_layout = [
            [sg.Text("Enter New Total Airframe Hours:")],
            [sg.Input(key="new_total_hours")],
            [sg.Button("Submit"), sg.Button("Cancel")],
        ]

        update_window = sg.Window(
            "Update Total Airframe Hours", update_layout, modal=True
        )

        while True:
            u_event, u_values = update_window.read()
            if u_event in (sg.WINDOW_CLOSED, "Cancel"):
                update_window.close()
                break

            if u_event == "Submit":
                try:
                    new_hours = float(u_values["new_total_hours"])

                    cursor.execute(
                        "UPDATE aircraft_totals SET total_airframe_hours=? WHERE id=1",
                        (new_hours,),
                    )
                    conn.commit()

                    update_total_airframe_hours(window)

                except Exception:
                    sg.popup("Please enter a valid number.")

                update_window.close()
                break
    if event == "add_entry_button":
        entry_window = sg.Window("Add Maintenance Entry", entry_layout, modal=True)
        while True:
            e_event, e_values = entry_window.read()
            if e_event in (sg.WINDOW_CLOSED, "Cancel"):
                entry_window.close()
                break
            if e_event == "submit_entry":
                date = e_values.get("date_input")
                tach = e_values.get("tach_hours_input")
                airframe = e_values.get("total_hours_input")
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

    if event == "submit_entry":
        date = values.get("date_input")
        tach = values.get("tach_hours_input")  # using same input for now
        airframe = values.get("total_hours_input")
        notes = values.get("notes_input")
        recurrent_item = values.get("recurrent_item_input")
        category = values.get("category_input")

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
                        ["Condition Inspection", "Oil Change", "ELT Test"],
                        default_value=row[5],
                        key="edit_recurrent_item",
                    ),
                ],
                [
                    sg.Text("Category"),
                    sg.DropDown(
                        ["Airframe", "Engine", "Propeller", "Avionics"],
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
