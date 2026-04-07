import FreeSimpleGUI as sg

sg.theme("Reddit")
sg.set_options(font=("Arial", 14))


def fuel_layout(
    fuel_rows=None,
    total_gallons=None,
    total_spent=None,
    gal_per_hour_avg=None,
    dollar_per_hour_avg=None,
):
    return [
        [
            sg.Text("Date"),
            sg.Input(key="fuel_date", size=(12, 1)),
            sg.Text("Hours"),
            sg.Input(key="fuel_hours", size=(10, 1), enable_events=True),
            sg.Text("Fuel Fill Up (Gallons)"),
            sg.Input(key="fuel_gallons", size=(10, 1), enable_events=True),
            sg.Text("Price Per Gallon"),
            sg.Input(key="fuel_price", size=(10, 1), enable_events=True),
            sg.VerticalSeparator(),
            sg.Text("Total Cost"),
            sg.Text(key="fuel_total", size=(10, 1), background_color="lightgray"),
            sg.Text("Gals Per Hour"),
            sg.Text(key="gal_per_hour", size=(10, 1), background_color="lightgray"),
        ],
        [
            sg.Button("Save"),
            sg.Button("Edit Selected"),
            sg.Button("Delete Selected"),
            sg.Button("Cancel"),
            sg.Text(expand_x=True),
            sg.Input("E16", key="fuel_price_search", size=(10, 1)),
            sg.Button("Search", key="fuel_price_submit"),
        ],
        [sg.HorizontalSeparator()],
        [sg.Text("Fuel Entries", font=("Arial", 12))],
        [
            sg.Table(
                values=fuel_rows,
                headings=[
                    "Date",
                    "Hours",
                    "Gallons",
                    "Price/Gal",
                    "Total Cost",
                    "Gallons Per Hour",
                ],
                key="fuel_table",
                auto_size_columns=False,
                col_widths=[10, 6, 10, 10, 10, 10],
                justification="left",
                num_rows=8,
                expand_x=True,
            )
        ],
        [
            sg.Text(
                f"Total Fuel Used: {round(total_gallons, 2)} gal",
                key="fuel_total_gallons",
            )
        ],
        [
            sg.Text(
                f"Total Money Spent: ${round(total_spent, 2)}",
                key="fuel_total_spent",
            )
        ],
        [
            sg.Text(
                f"Average Fuel Consumption: {round(gal_per_hour_avg, 2)} gal/hr",
                key="gal_per_hour_avg",
            )
        ],
        [
            sg.Text(
                f"Average Cost Per Hour: ${round(dollar_per_hour_avg, 2)}/hr",
                key="dollar_per_hour_avg",
            )
        ],
    ]
