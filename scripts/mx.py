import sqlite3
from datetime import datetime, timedelta

import PySimpleGUI as sg

sg.theme("Reddit")
# --- Maintenance Interval Configuration ---
OIL_CHANGE_INTERVAL_HOURS = 50
CONDITION_INSPECTION_INTERVAL_MONTHS = 12
ELT_TEST_INTERVAL_DAYS = 90

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
                        ["Condition Inspection", "Oil Change", "ELT Test"],
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
    [sg.Text("N890GF Maintenance Tracker", font=("Arial", 24), expand_x=True)],
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
                ],
            ],
        )
    ],
    [sg.Button("Add Entry", key="add_entry_button")],
    entry_layout,
    [sg.HorizontalSeparator()],
    [
        sg.Table(
            values=[],
            headings=[
                "ID",
                "Date",
                "Tach",
                "Airframe",
                "Notes",
                "Recurrent Item",
                "Category",
                "Next Due Tach",
            ],
            key="maintenance_table",
            auto_size_columns=True,
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


def refresh_table(window):
    cursor.execute("SELECT * FROM maintenance_entries ORDER BY id DESC")
    rows = cursor.fetchall()

    updated_rows = []

    for row in rows:
        entry_id, date, tach, airframe, notes, recurrent_item, category = row

        next_due_tach = ""

        if tach is not None:
            try:
                tach_val = float(tach)

                if recurrent_item == "Oil Change":
                    next_due_tach = tach_val + OIL_CHANGE_INTERVAL_HOURS
                elif recurrent_item == "Condition Inspection":
                    next_due_tach = "Calendar Based"
                else:
                    next_due_tach = ""
            except:
                next_due_tach = ""

        updated_rows.append(
            [
                entry_id,
                date,
                tach,
                airframe,
                notes,
                recurrent_item,
                category,
                next_due_tach,
            ]
        )

    window["maintenance_table"].update(values=updated_rows)


def calculate_overdue():
    cursor.execute(
        "SELECT recurrent_item, MAX(date) FROM maintenance_entries GROUP BY recurrent_item"
    )
    rows = cursor.fetchall()

    overdue_count = 0
    today = datetime.today()

    for item, last_date in rows:
        if not last_date:
            continue

        try:
            last_dt = datetime.strptime(last_date, "%Y-%m-%d")
        except:
            continue

        if item == "Condition Inspection":
            due_date = last_dt + timedelta(days=365)
            if today > due_date:
                overdue_count += 1

        if item == "ELT Test":
            due_date = last_dt + timedelta(days=ELT_TEST_INTERVAL_DAYS)
            if today > due_date:
                overdue_count += 1

    return overdue_count


def update_due_dates(window):
    today = datetime.today()

    cursor.execute("SELECT DISTINCT recurrent_item FROM maintenance_entries")
    items = cursor.fetchall()

    rows = []

    for (item,) in items:
        cursor.execute(
            """
            SELECT date, tach_time
            FROM maintenance_entries
            WHERE recurrent_item=?
            ORDER BY date DESC
            LIMIT 1
            """,
            (item,),
        )
        result = cursor.fetchone()
        if result:
            last_date, last_tach = result
            rows.append((item, last_date, last_tach))

    cond_due = "--"
    oil_due = "--"
    elt_due = "--"

    cond_color = "black"
    oil_color = "black"
    elt_color = "black"

    for item, last_date, last_tach in rows:
        if not last_date:
            continue

        try:
            last_dt = datetime.strptime(last_date, "%Y-%m-%d")
        except:
            continue

        # CONDITION INSPECTION (12 months calendar)
        if item == "Condition Inspection":
            due_date = last_dt + timedelta(days=365)
            days_remaining = (due_date - today).days

            cond_due = f"{due_date.strftime('%Y-%m-%d')} ({days_remaining} days)"

            if days_remaining < 0:
                cond_color = "red"
            elif days_remaining <= 30:
                cond_color = "yellow"

        # ELT TEST (calendar)
        if item == "ELT Test":
            due_date = last_dt + timedelta(days=ELT_TEST_INTERVAL_DAYS)
            days_remaining = (due_date - today).days

            elt_due = f"{due_date.strftime('%Y-%m-%d')} ({days_remaining} days)"

            if days_remaining < 0:
                elt_color = "red"
            elif days_remaining <= 30:
                elt_color = "yellow"

        # OIL CHANGE (tach based)
        if item == "Oil Change" and last_tach is not None:
            try:
                tach_val = float(last_tach)
                next_due_tach = tach_val + OIL_CHANGE_INTERVAL_HOURS

                # Determine current aircraft tach (max tach in DB)
                cursor.execute("SELECT MAX(tach_time) FROM maintenance_entries")
                current_tach = cursor.fetchone()[0]

                hours_remaining = None
                if current_tach is not None:
                    hours_remaining = next_due_tach - float(current_tach)

                if hours_remaining is not None:
                    oil_due = (
                        f"{next_due_tach:.1f} hrs ({hours_remaining:.1f} hrs left)"
                    )

                    if hours_remaining < 0:
                        oil_color = "red"
                    elif hours_remaining <= 5:
                        oil_color = "yellow"
                else:
                    oil_due = f"{next_due_tach:.1f} hrs"

            except:
                oil_due = "--"

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

window = sg.Window(title="MX Tracker", layout=main_layout, finalize=True)

# Initial load of table and summary
refresh_table(window)
update_due_dates(window)

# Initialize overdue count on startup
initial_overdue = calculate_overdue()
window["overdue_text"].update(initial_overdue)

while True:
    event, values = window.read()
    if event in (sg.WINDOW_CLOSED, "Exit"):
        break
    print(event, values)
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
    if event == "Edit Selected":
        selected = values["maintenance_table"]
        if selected:
            row_index = selected[0]
            table_data = window["maintenance_table"].get()
            row = table_data[row_index]

            entry_id = row[0]

            new_values = sg.popup_get_text(
                f"Edit Notes for Entry {entry_id}",
                default_text=row[4],
            )

            if new_values is not None:
                cursor.execute(
                    "UPDATE maintenance_entries SET notes=? WHERE id=?",
                    (new_values, entry_id),
                )
                conn.commit()
                refresh_table(window)
                update_due_dates(window)
