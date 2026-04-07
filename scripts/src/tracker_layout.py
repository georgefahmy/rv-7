import FreeSimpleGUI as sg

sg.theme("Reddit")
sg.set_options(font=("Arial", 14))

main_layout = [
    [
        sg.Text(
            "N890GF Maintenance and Flight Tracker", font=("Arial", 24), expand_x=True
        ),
        sg.Column(
            element_justification="right",
            layout=[
                [
                    sg.Text(
                        "Total Hours: 0",
                        font=("Arial", 18),
                        key="total_airframe_text",
                        justification="right",
                        expand_x=True,
                    ),
                ],
                [
                    sg.Text(
                        "Total Landings: 0",
                        font=("Arial", 16),
                        key="total_landings_text",
                        justification="right",
                        expand_x=True,
                    ),
                ],
                [
                    sg.Button("Fuel Tracker", key="fuel_tracker_button"),
                    sg.Button("SW DB Updates", key="sw_db_updates"),
                    sg.Button("Analysis", key="analysis"),
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
                        size=(120, 140),
                        expand_x=True,
                    ),
                    sg.Frame(
                        title="Inspections Due",
                        layout=[
                            [sg.Text("Condition Insp", font=("Arial", 12))],
                            [sg.Text("--", font=("Arial", 14), key="cond_due_text")],
                            [sg.Text("Transponder Check", font=("Arial", 12))],
                            [sg.Text("--", font=("Arial", 14), key="xpndr_due_text")],
                        ],
                        size=(180, 140),
                        expand_x=True,
                        pad=0,
                    ),
                    sg.Frame(
                        title="Oil Change Due",
                        layout=[
                            [sg.Text("--", font=("Arial", 14), key="oil_due_text")]
                        ],
                        size=(180, 140),
                        expand_x=True,
                    ),
                    sg.Frame(
                        title="ELT Due",
                        layout=[
                            [sg.Text("--", font=("Arial", 12), key="elt_due_text")]
                        ],
                        size=(180, 140),
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
                        size=(180, 140),
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
                        size=(180, 140),
                        expand_x=True,
                    ),
                ],
            ],
        )
    ],
    [
        sg.Button("Add Flight Log", key="flight_log_button"),
        sg.Button("Generate Logbook Entry", key="generate_logbook_entry"),
    ],
    [sg.HorizontalSeparator()],
    [
        sg.Text("Flight Log", font=("Arial", 16)),
    ],
    [
        sg.Table(
            values=[],
            headings=[
                "Date",
                "Takeoff",
                "Landing",
                "Hobbs",
                "Tach",
                "Hobbs Delta",
                "Tach Delta",
                "Landings",
                "Notes",
            ],
            key="flight_log_table",
            col_widths=[4, 3, 3, 3, 3, 5, 5, 3, 45],
            auto_size_columns=False,
            justification="left",
            alternating_row_color="light gray",
            enable_events=True,
            select_mode=sg.TABLE_SELECT_MODE_BROWSE,
            expand_x=True,
            num_rows=10,
        )
    ],
    [
        sg.Text(expand_x=True),
        sg.Button("Edit Flight Selected"),
        sg.Button("Delete Flight Selected"),
    ],
    [sg.HorizontalSeparator()],
    [
        sg.Button("Add Mx Log", key="add_entry_button"),
    ],
    [
        sg.Text("Maintenance Log", font=("Arial", 16)),
    ],
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
            ],
            key="maintenance_table",
            col_widths=[3, 7, 5, 5, 60, 12, 10],  # Notes column is wider
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
        sg.Text(expand_x=True),
        sg.Button("Edit Selected"),
        sg.Button("Delete Selected"),
    ],
]
