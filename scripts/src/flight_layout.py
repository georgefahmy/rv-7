import FreeSimpleGUI as sg

sg.theme("Reddit")
sg.set_options(font=("Arial", 14))


flight_layout = [
    [
        sg.Text("Date"),
        sg.Input(key="flight_date", size=(10, 1)),
        sg.Text("Takeoff Airport"),
        sg.Input(key="flight_takeoff", size=(10, 1)),
        sg.Text("Landing Airport"),
        sg.Input(key="flight_landing", size=(10, 1)),
        sg.Text("Hobbs"),
        sg.Input(key="flight_hobbs", size=(10, 1)),
        sg.Text("Tach"),
        sg.Input(key="flight_tach", size=(10, 1)),
        sg.Text("Landings"),
        sg.Input(key="flight_landings", size=(10, 1)),
        sg.Text("Notes"),
        sg.Input(key="flight_notes", size=(10, 1)),
    ],
    [sg.Button("Submit"), sg.Button("Cancel")],
]
