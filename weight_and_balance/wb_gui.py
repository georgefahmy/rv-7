import json

import PySimpleGUI as sg
from dotmap import DotMap
from weightbalance import divide, multiply, sum

with open("weight_and_balance/default_params.json", "r") as fp:
    default_params = DotMap(json.load(fp))

layout = [
    [
        sg.Button("Set Full Config"),
    ],
    [
        sg.Frame(
            title="Input Weights",
            layout=[
                [
                    sg.Text("Name", expand_x=True, justification="l"),
                    sg.Text("Weight (lbs)", expand_x=True, justification="r"),
                    sg.Text("Arm (in)", expand_x=True, justification="c"),
                ],
                [
                    sg.Text("Left Main Wheel:", expand_x=True),
                    sg.Input(
                        default_text=default_params.FRONT_LEFT_WEIGHT,
                        size=10,
                        key="left_main_weight_input",
                        enable_events=True,
                    ),
                    sg.Input(
                        default_text=default_params.FRONT_LEFT_DIST,
                        size=10,
                        key="left_main_arm_input",
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Right Main Wheel:", expand_x=True),
                    sg.Input(
                        default_text=default_params.FRONT_RIGHT_WEIGHT,
                        size=10,
                        key="right_main_weight_input",
                        enable_events=True,
                    ),
                    sg.Input(
                        default_text=default_params.FRONT_RIGHT_DIST,
                        size=10,
                        key="right_main_arm_input",
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Tailwheel:", expand_x=True),
                    sg.Input(
                        default_text=default_params.TAILWHEEL_WEIGHT,
                        size=10,
                        key="tailwheel_weight_input",
                        enable_events=True,
                    ),
                    sg.Input(
                        default_text=default_params.TAILWHEEL_DIST,
                        size=10,
                        key="tailwheel_arm_input",
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Pilot:", expand_x=True),
                    sg.Input(size=10, key="pilot_weight_input", enable_events=True),
                    sg.Input(
                        default_text=default_params.CABIN_SEATS_DIST,
                        size=10,
                        key="pilot_arm_input",
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Copilot:", expand_x=True),
                    sg.Input(size=10, key="copilot_weight_input", enable_events=True),
                    sg.Input(
                        default_text=default_params.CABIN_SEATS_DIST,
                        size=10,
                        key="copilot_arm_input",
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Baggage:", expand_x=True),
                    sg.Input(size=10, key="baggage_weight_input", enable_events=True),
                    sg.Input(
                        default_text=default_params.BAGGAGE_DIST,
                        size=10,
                        key="baggage_arm_input",
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Fuel Start (gal):", expand_x=True),
                    sg.Input(
                        size=10, key="fuel_start_weight_input", enable_events=True
                    ),
                    sg.Input(
                        default_text=default_params.FUEL_DIST,
                        size=10,
                        key="fuel_arm_input",
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Fuel Use (gal):", expand_x=True),
                    sg.Input(size=10, key="fuel_use_input", enable_events=True),
                ],
            ],
        ),
        sg.Frame(
            title="Outputs",
            expand_y=True,
            layout=[
                [
                    sg.Text("Empty weight:", expand_x=True),
                    sg.Text(key="empty_weight_output"),
                ],
                [
                    sg.Text("Empty CG:", expand_x=True),
                    sg.Text(key="empty_CG_output"),
                ],
                [
                    sg.Text("Copilot:", expand_x=True),
                    sg.Text(key="copilot_weight_output"),
                ],
                [
                    sg.Text("Baggage:", expand_x=True),
                    sg.Text(key="baggage_weight_output"),
                ],
                [
                    sg.Text("Fuel Start:", expand_x=True),
                    sg.Text(key="fuel_start_weight_output"),
                ],
                [
                    sg.Text("Fuel Use:", expand_x=True),
                    sg.Text(key="fuel_end_weight_output"),
                ],
            ],
        ),
    ],
]

sg.theme("Reddit")
sg.set_options(font=("Arial", 16))

window = sg.Window("Weight & Balance", layout=layout, finalize=True)

while True:
    event, values = window.read()

    if event in (None, "Quit", sg.WIN_CLOSED):
        window.close()
        break

    if "input" in event:
        for element in window.element_list():
            if element.key and "input" in element.key:
                specific_element = values[element.key]
                try:
                    values[element.key] = float(specific_element)
                except Exception:
                    values[element.key] = 0

        left_main_weight, right_main_weight, tailwheel_weight = (
            values["left_main_weight_input"],
            values["right_main_weight_input"],
            values["tailwheel_weight_input"],
        )
        empty_weight = sum(
            left_main_weight,
            right_main_weight,
            tailwheel_weight,
        )
        empty_moment = sum(
            multiply(left_main_weight, values["left_main_arm_input"]),
            multiply(right_main_weight, values["right_main_arm_input"]),
            multiply(tailwheel_weight, values["tailwheel_arm_input"]),
        )
        empty_cg = divide(empty_moment, empty_weight)

        window["empty_weight_output"].update(value=f"{empty_weight} lbs")
        window["empty_CG_output"].update(value=f"{empty_cg} in")
