import FreeSimpleGUI as sg

sg.theme("Reddit")
sg.set_options(font=("Arial", 14))


def entry_layout(recurrent_items=None, mx_categories=None):
    return [
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
                            recurrent_items,
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
                            mx_categories,
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
