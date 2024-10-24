import json

import PySimpleGUI as sg
from dotmap import DotMap
from weightbalance import _round, calc_cg_percent, divide, multiply, sum

sg.theme("Reddit")
sg.set_options(font=("Arial", 16))


with open("weight_and_balance/default_params.json", "r") as fp:
    default_params = DotMap(json.load(fp))

with open("weight_and_balance/params.json", "r") as fp:
    params = DotMap(json.load(fp))
    for key in params.keys():
        if params[key]:
            params[key] = float(params[key])
        else:
            params[key] = 0


def calc_cg(
    params,
):
    fuel_start_weight = multiply(params.fuel_start_weight_input, 6)
    fuel_use_weight = multiply(params.fuel_use_input, 6)

    empty_weight = sum(
        params.left_main_weight_input,
        params.right_main_weight_input,
        params.tailwheel_weight_input,
    )

    start_weight = sum(
        empty_weight,
        fuel_start_weight,
        params.pilot_weight_input,
        params.copilot_weight_input,
        params.baggage_weight_input,
    )
    end_weight = start_weight - fuel_use_weight

    empty_moment = sum(
        multiply(params.left_main_weight_input, params.left_main_arm_input),
        multiply(params.right_main_weight_input, params.right_main_arm_input),
        multiply(params.tailwheel_weight_input, params.tailwheel_arm_input),
    )

    start_moment = sum(
        empty_moment,
        multiply(fuel_start_weight, params.fuel_arm_input),
        multiply(params.pilot_weight_input, params.pilot_arm_input),
        multiply(params.copilot_weight_input, params.copilot_arm_input),
        multiply(params.baggage_weight_input, params.baggage_arm_input),
    )

    end_moment = sum(
        empty_moment,
        multiply(fuel_start_weight - fuel_use_weight, params.fuel_arm_input),
        multiply(params.pilot_weight_input, params.pilot_arm_input),
        multiply(params.copilot_weight_input, params.copilot_arm_input),
        multiply(params.baggage_weight_input, params.baggage_arm_input),
    )
    start_cg = divide(start_moment, start_weight)
    start_cg_percent = calc_cg_percent(start_cg)

    end_cg = divide(end_moment, end_weight)
    end_cg_percent = calc_cg_percent(end_cg)

    results = DotMap(
        empty_weight=empty_weight,
        weight_begin=_round(start_weight),
        moment_begin=_round(start_moment),
        cg_location_begin=_round(start_cg),
        cg_percent_begin=_round(start_cg_percent),
        fuel_start_weight=_round(fuel_start_weight),
        weight_end=_round(end_weight),
        moment_end=_round(end_moment),
        cg_location_end=_round(end_cg),
        cg_percent_end=_round(end_cg_percent),
        fuel_end_weight=_round(fuel_start_weight - fuel_use_weight),
        fuel_use_weight=_round(fuel_use_weight),
    )

    return results


results = calc_cg(params)

layout = [
    [
        sg.Button("Load Params", font=("Arial", 14), key="load_params_button"),
        sg.Button("Save Params", font=("Arial", 14), key="save_params_button"),
    ],
    [
        sg.Frame(
            title="Inputs",
            background_color="white",
            key="input_frame",
            layout=[
                [
                    sg.Text("Name", expand_x=True, justification="l"),
                    sg.Text("Weight (lbs)", expand_x=True, justification="r"),
                    sg.Text("Arm (in)", expand_x=True, justification="c"),
                ],
                [
                    sg.Text("Left Main Wheel:", expand_x=True),
                    sg.Input(
                        default_text=params.left_main_weight_input,
                        size=10,
                        key="left_main_weight_input",
                        enable_events=True,
                    ),
                    sg.Input(
                        default_text=params.left_main_arm_input,
                        size=10,
                        key="left_main_arm_input",
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Right Main Wheel:", expand_x=True),
                    sg.Input(
                        default_text=params.right_main_weight_input,
                        size=10,
                        key="right_main_weight_input",
                        enable_events=True,
                    ),
                    sg.Input(
                        default_text=params.right_main_arm_input,
                        size=10,
                        key="right_main_arm_input",
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Tailwheel:", expand_x=True),
                    sg.Input(
                        default_text=params.tailwheel_weight_input,
                        size=10,
                        key="tailwheel_weight_input",
                        enable_events=True,
                    ),
                    sg.Input(
                        default_text=params.tailwheel_arm_input,
                        size=10,
                        key="tailwheel_arm_input",
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Pilot:", expand_x=True),
                    sg.Input(
                        default_text=params.pilot_weight_input,
                        size=10,
                        key="pilot_weight_input",
                        enable_events=True,
                    ),
                    sg.Input(
                        default_text=params.pilot_arm_input,
                        size=10,
                        key="pilot_arm_input",
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Copilot:", expand_x=True),
                    sg.Input(
                        default_text=params.copilot_weight_input,
                        size=10,
                        key="copilot_weight_input",
                        enable_events=True,
                    ),
                    sg.Input(
                        default_text=params.copilot_arm_input,
                        size=10,
                        key="copilot_arm_input",
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Baggage:", expand_x=True),
                    sg.Input(
                        default_text=params.baggage_weight_input,
                        size=10,
                        key="baggage_weight_input",
                        enable_events=True,
                    ),
                    sg.Input(
                        default_text=params.baggage_arm_input,
                        size=10,
                        key="baggage_arm_input",
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Fuel Start (gal):", expand_x=True),
                    sg.Input(
                        default_text=params.fuel_start_weight_input,
                        size=10,
                        key="fuel_start_weight_input",
                        enable_events=True,
                    ),
                    sg.Input(
                        default_text=params.fuel_arm_input,
                        size=10,
                        key="fuel_arm_input",
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Fuel Use (gal):", expand_x=True),
                    sg.Input(
                        default_text=params.fuel_use_input,
                        size=10,
                        key="fuel_use_input",
                        enable_events=True,
                    ),
                    sg.Input(
                        size=10,
                        disabled=True,
                        disabled_readonly_background_color="white",
                        border_width=0,
                        pad=(6, 0),
                        key=None,
                    ),
                ],
                [
                    sg.Text("Max Gross Weight:", expand_x=True),
                    sg.Input(
                        default_text=params.max_gross_weight_input,
                        size=10,
                        key="max_gross_weight_input",
                        enable_events=True,
                    ),
                    sg.Input(
                        size=10,
                        disabled=True,
                        disabled_readonly_background_color="white",
                        border_width=0,
                        pad=(6, 0),
                        key=None,
                    ),
                ],
            ],
        ),
        sg.Frame(
            title="Outputs",
            expand_y=True,
            background_color="white",
            key="output_frame",
            layout=[
                [
                    sg.Text("Start Weight:", expand_x=True),
                    sg.Text(
                        text=f"{results.weight_begin} lbs", key="start_weight_output"
                    ),
                ],
                [
                    sg.Text("End Weight:", expand_x=True),
                    sg.Text(text=f"{results.weight_end} lbs", key="end_weight_output"),
                ],
                [sg.HorizontalSeparator()],
                [
                    sg.Text("CG Envelope:", expand_x=True),
                    sg.Text(text='78.7" - 86.82"'),
                ],
                [sg.HorizontalSeparator()],
                [
                    sg.Text("Start CG:", expand_x=True),
                    sg.Text(
                        text=f"{results.cg_location_begin} in", key="start_CG_output"
                    ),
                ],
                [
                    sg.Text("End CG:", expand_x=True),
                    sg.Text(text=f"{results.cg_location_end} in", key="end_CG_output"),
                ],
                [sg.HorizontalSeparator()],
                [
                    sg.Text("Start CG Percent:", expand_x=True),
                    sg.Text(
                        text=f"{results.cg_percent_begin}%",
                        key="start_cg_percent_output",
                    ),
                ],
                [
                    sg.Text("End CG Percent:", expand_x=True),
                    sg.Text(
                        text=f"{results.cg_percent_end}%", key="end_cg_percent_output"
                    ),
                ],
                [sg.HorizontalSeparator()],
                [
                    sg.Text("Fuel Start:", expand_x=True),
                    sg.Text(
                        text=f"{results.fuel_start_weight} lbs",
                        key="fuel_start_weight_output",
                    ),
                ],
                [
                    sg.Text("Fuel Use:", expand_x=True),
                    sg.Text(
                        text=f"{results.fuel_use_weight} lbs",
                        key="fuel_end_weight_output",
                    ),
                ],
            ],
        ),
    ],
    [
        sg.Frame(
            title="W&B Graph",
            layout=[
                [
                    sg.Graph(
                        canvas_size=(500, 300),
                        graph_bottom_left=(78.7, 1111),
                        graph_top_right=(86.82, 1800),
                        background_color="light gray",
                        expand_x=True,
                        expand_y=True,
                        key="wb_graph",
                    )
                ]
            ],
            expand_x=True,
            expand_y=True,
            key="graph_frame",
        )
    ],
]


window = sg.Window("Weight & Balance", layout=layout, finalize=True)
graph = window["wb_graph"]

# Draw axes
graph.draw_line((78.7, 1111), (86.82, 1111), color="black", width=2)  # X-axis
graph.draw_line(
    (78.7, 1111 + 1), (78.7, params.max_gross_weight_input - 1), color="black", width=2
)  # Y-axis
graph.change_coordinates(
    graph_bottom_left=(78.7, 1111),
    graph_top_right=(86.82, 1800),
)
# window.refresh()


def draw_graph(window, results, values):
    graph = window["wb_graph"]

    graph.erase()
    graph.change_coordinates(
        graph_bottom_left=(78.7, results.empty_weight),
        graph_top_right=(86.82, values.max_gross_weight_input),
    )
    graph.draw_circle(
        (results.cg_location_begin, results.weight_begin), 0.05, fill_color="green"
    )
    graph.draw_circle(
        (results.cg_location_end, results.weight_end), 0.05, fill_color="blue"
    )
    graph.draw_line(
        point_from=(results.cg_location_begin, results.weight_begin),
        point_to=(results.cg_location_end, results.weight_end),
    )
    graph.draw_line((78.7, 1111), (86.82, 1111), width=5)  # X-axis
    graph.draw_line(
        (78.7, 1111),
        (78.7, params.max_gross_weight_input),
        width=2,
    )  # Y-axis


while True:
    event, values = window.read()
    values = DotMap(values)

    if event in (None, "Quit", sg.WIN_CLOSED):
        window.close()
        break

    if event == "load_params_button":
        with open("weight_and_balance/params.json", "r") as fp:
            params = DotMap(json.load(fp))
            for key in params.keys():
                if params[key]:
                    params[key] = float(params[key])
                else:
                    params[key] = 0

        for key in params.keys():
            sg.fill_form_with_values(window, params)
            window.write_event_value(key, params[key])

    if event == "save_params_button":
        del values[0]
        del values[1]
        with open("weight_and_balance/params.json", "w") as fp:
            json.dump(values.toDict(), fp, indent=4, sort_keys=True)

    if "input" in event:
        values.pprint()
        for element in window.element_list():
            if type(element.key) is str:
                if "input" in element.key:
                    specific_element = values[element.key]
                    try:
                        values[element.key] = float(specific_element)
                    except Exception:
                        values[element.key] = 0

        results = calc_cg(values)
        draw_graph(window, results, values)

        window["start_weight_output"].update(value=f"{results.weight_begin} lbs")
        window["end_weight_output"].update(value=f"{results.weight_end} lbs")
        window["start_CG_output"].update(value=f"{results.cg_location_begin} in")
        window["start_cg_percent_output"].update(value=f"{results.cg_percent_begin}%")
        window["end_CG_output"].update(value=f"{results.cg_location_end} in")
        window["end_cg_percent_output"].update(value=f"{results.cg_percent_end}%")
        window["fuel_start_weight_output"].update(
            value=f"{results.fuel_start_weight} lbs"
        )
        window["fuel_end_weight_output"].update(value=f"{results.fuel_use_weight} lbs")

        if results.weight_begin > values.max_gross_weight_input:
            window["start_weight_output"].update(background_color="red")
        else:
            window["start_weight_output"].update(background_color="white")

        if results.cg_percent_begin > 100:
            window["start_cg_percent_output"].update(background_color="red")
        else:
            window["start_cg_percent_output"].update(background_color="white")

        if results.cg_percent_end > 100:
            window["end_cg_percent_output"].update(background_color="red")
        else:
            window["end_cg_percent_output"].update(background_color="white")
