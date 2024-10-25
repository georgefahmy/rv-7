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
    for config in params:
        for key in params[config].keys():
            if params[config][key]:
                params[config][key] = float(params[config][key])
            else:
                params[config][key] = 0


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
    zero_fuel_weight = start_weight - fuel_start_weight

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
    zero_fuel_moment = sum(
        empty_moment,
        multiply(params.pilot_weight_input, params.pilot_arm_input),
        multiply(params.copilot_weight_input, params.copilot_arm_input),
        multiply(params.baggage_weight_input, params.baggage_arm_input),
    )
    start_cg = divide(start_moment, start_weight)
    start_cg_percent = calc_cg_percent(start_cg)

    end_cg = divide(end_moment, end_weight)
    end_cg_percent = calc_cg_percent(end_cg)
    zero_fuel_cg = divide(zero_fuel_moment, zero_fuel_weight)

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
        zero_fuel_cg=_round(zero_fuel_cg),
        zero_fuel_weight=_round(zero_fuel_weight),
    )

    return results


results = calc_cg(params.Default)

layout = [
    [
        sg.Text("Load Config Name:"),
        sg.Combo(
            values=list(params.keys()),
            size=20,
            key="load_config_name",
            enable_events=True,
        ),
    ],
    [
        sg.Text("Save Config Name:"),
        sg.Input(size=20, key="save_config_name"),
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
                        size=10,
                        key="left_main_weight_input",
                        enable_events=True,
                    ),
                    sg.Input(
                        size=10,
                        key="left_main_arm_input",
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Right Main Wheel:", expand_x=True),
                    sg.Input(
                        size=10,
                        key="right_main_weight_input",
                        enable_events=True,
                    ),
                    sg.Input(
                        size=10,
                        key="right_main_arm_input",
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Tailwheel:", expand_x=True),
                    sg.Input(
                        size=10,
                        key="tailwheel_weight_input",
                        enable_events=True,
                    ),
                    sg.Input(
                        size=10,
                        key="tailwheel_arm_input",
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Pilot:", expand_x=True),
                    sg.Input(
                        size=10,
                        key="pilot_weight_input",
                        enable_events=True,
                    ),
                    sg.Input(
                        size=10,
                        key="pilot_arm_input",
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Copilot:", expand_x=True),
                    sg.Input(
                        size=10,
                        key="copilot_weight_input",
                        enable_events=True,
                    ),
                    sg.Input(
                        size=10,
                        key="copilot_arm_input",
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Baggage:", expand_x=True),
                    sg.Input(
                        size=10,
                        key="baggage_weight_input",
                        enable_events=True,
                    ),
                    sg.Input(
                        size=10,
                        key="baggage_arm_input",
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Fuel Start (gal):", expand_x=True),
                    sg.Input(
                        size=10,
                        key="fuel_start_weight_input",
                        enable_events=True,
                    ),
                    sg.Input(
                        size=10,
                        key="fuel_arm_input",
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Fuel Use (gal):", expand_x=True),
                    sg.Input(
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
            expand_x=True,
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
                        canvas_size=(600, 300),
                        graph_bottom_left=(78.7, 1111),
                        graph_top_right=(86.82, params.Default.max_gross_weight_input),
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
    graph.draw_text(
        "Starting CG",
        (results.cg_location_begin + 0.1, results.weight_begin),
        text_location=sg.TEXT_LOCATION_LEFT,
    )
    graph.draw_circle(
        (results.cg_location_end, results.weight_end), 0.05, fill_color="blue"
    )
    graph.draw_text(
        "Ending CG",
        (results.cg_location_end + 0.1, results.weight_end),
        text_location=sg.TEXT_LOCATION_LEFT,
    )
    graph.draw_line(
        point_from=(results.cg_location_begin, results.weight_begin),
        point_to=(results.cg_location_end, results.weight_end),
    )
    graph.draw_circle(
        (results.zero_fuel_cg, results.zero_fuel_weight), 0.05, fill_color="red"
    )
    graph.draw_text(
        "Zero Fuel CG",
        (results.zero_fuel_cg, results.zero_fuel_weight - 20),
        text_location=sg.TEXT_LOCATION_TOP,
    )
    graph.draw_line(
        point_from=(results.cg_location_end, results.weight_end),
        point_to=(results.zero_fuel_cg, results.zero_fuel_weight),
        color="gray",
    )
    graph.draw_lines(
        [
            (78.7, results.empty_weight),
            (86.82, results.empty_weight),
            (78.7, results.empty_weight),
            (78.7, values.max_gross_weight_input),
        ],
        color="black",
        width=2,
    )
    graph.draw_text(
        f"{results.empty_weight} lbs\n{78.7}in",
        (78.7, results.empty_weight),
        text_location=sg.TEXT_LOCATION_BOTTOM_LEFT,
    )
    graph.draw_text(
        f"{86.82} in",
        (86.82, results.empty_weight),
        text_location=sg.TEXT_LOCATION_BOTTOM_RIGHT,
    )
    graph.draw_text(
        f"{values.max_gross_weight_input} lbs",
        (78.7, values.max_gross_weight_input),
        text_location=sg.TEXT_LOCATION_TOP_LEFT,
    )


while True:
    event, values = window.read()
    values = DotMap(values)

    if event in (None, "Quit", sg.WIN_CLOSED):
        window.close()
        break

    if event == "load_config_name":
        with open("weight_and_balance/params.json", "r") as fp:
            params = DotMap(json.load(fp))
            for config in params:
                for key in params[config].keys():
                    if params[config][key]:
                        params[config][key] = float(params[config][key])
                    else:
                        params[config][key] = 0

        for key in params[values["load_config_name"]].keys():
            sg.fill_form_with_values(window, params[values["load_config_name"]])
            window.write_event_value(key, params[values["load_config_name"]][key])

    if event == "save_params_button":
        if not values.save_config_name:
            continue

        save_params = values.copy()
        del save_params[0]
        del save_params[1]
        del save_params["wb_graph"]
        del save_params["load_config_name"]
        del save_params["save_config_name"]

        params[values["save_config_name"]] = save_params.toDict()
        with open("weight_and_balance/params.json", "w") as fp:
            json.dump(
                params,
                fp,
                indent=4,
                sort_keys=True,
            )
        window["save_config_name"].update(value="")

    if "input" in event:
        # values.pprint()
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
