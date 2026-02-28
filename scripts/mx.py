import sqlite3

import PySimpleGUI as sg

sg.theme("Reddit")

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
                [sg.Text("Hours", expand_x=True)],
                [sg.Input(key="hours_input", expand_x=True, size=(10, 1))],
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
                        layout=[
                            [
                                sg.Text("0", font=("Arial", 16)),
                            ]
                        ],
                        size=(80, 120),
                        expand_x=True,
                    ),
                    sg.Frame(
                        title="Due Soon",
                        layout=[
                            [
                                sg.Text("0", font=("Arial", 16)),
                            ]
                        ],
                        size=(80, 120),
                        expand_x=True,
                    ),
                    sg.Frame(
                        title="Open Squawks",
                        layout=[
                            [
                                sg.Text("0", font=("Arial", 16)),
                            ]
                        ],
                        size=(80, 120),
                        expand_x=True,
                    ),
                ],
            ],
        )
    ],
    [sg.Button("Add Entry", key="add_entry_button")],
    entry_layout,
]


conn = sqlite3.connect("scripts/maintenance.db")
cursor = conn.cursor()

cursor.execute(
    """
        CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    age INTEGER
)
    """
)

window = sg.Window(title="MX Tracker", layout=main_layout, finalize=True)

while True:
    event, values = window.read()
    if event in (sg.WINDOW_CLOSED, "Exit"):
        break
    print(event, values)
