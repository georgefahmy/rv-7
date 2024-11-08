import json

import numpy as np
import PySimpleGUI as sg
from dotmap import DotMap


def sum(*args):
    x = 0
    for val in args:
        x += val
    return round(x, 2)


def multiply(x, y):
    return round(x * y, 2)


def divide(x, y):
    if y == 0:
        return 0
    return round(x / y, 2)


def calc_cg_percent(cg, fwd_limit, aft_limit):
    if (aft_limit - fwd_limit) == 0:
        return 0
    return (cg - fwd_limit) / (aft_limit - fwd_limit) * 100


def _round(x):
    return round(x, 2)


def load_params():
    with open("weight_and_balance/params.json", "r") as fp:
        params = DotMap(json.load(fp))
        for config in params:
            for key in params[config].keys():
                params[config][key] = (
                    float(params[config][key]) if params[config][key] else 0
                )
    return params


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
    start_cg_percent = calc_cg_percent(
        start_cg, params.forward_cg_limit_input, params.aft_cg_limit_input
    )

    end_cg = divide(end_moment, end_weight)
    end_cg_percent = calc_cg_percent(
        end_cg, params.forward_cg_limit_input, params.aft_cg_limit_input
    )
    zero_fuel_cg = divide(zero_fuel_moment, zero_fuel_weight)

    return DotMap(
        aft_cg_limit_input=params.aft_cg_limit_input,
        forward_cg_limit_input=params.forward_cg_limit_input,
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


def set_graph_grid(window, results, values):
    graph = window["wb_graph"]
    # Setup graph grid
    graph.erase()
    weight_ff = 50
    cg_ff = 0.9
    graph.change_coordinates(
        graph_bottom_left=(
            results.forward_cg_limit_input - cg_ff,
            results.empty_weight - weight_ff,
        ),
        graph_top_right=(
            results.aft_cg_limit_input + cg_ff,
            values.max_gross_weight_input + weight_ff,
        ),
    )
    x_markers = np.linspace(
        results.forward_cg_limit_input, results.aft_cg_limit_input, 10
    )
    y_markers = np.linspace(results.empty_weight, values.max_gross_weight_input, 10)
    for x_val in x_markers:
        graph.draw_lines(
            [
                (x_val, results.empty_weight),
                (x_val, values.max_gross_weight_input),
            ],
            color="gray",
            width=1,
        )
        graph.draw_text(
            f'{round(x_val, 2)}"',
            (x_val, results.empty_weight),
            text_location=sg.TEXT_LOCATION_TOP_LEFT,
        )
    for y_val in y_markers:
        graph.draw_lines(
            [
                (results.forward_cg_limit_input, y_val),
                (results.aft_cg_limit_input, y_val),
            ],
            color="gray",
            width=1,
        )
        graph.draw_text(
            f"{int(y_val)}lbs ",
            (results.forward_cg_limit_input, y_val),
            text_location=(
                sg.TEXT_LOCATION_RIGHT
                if y_val == y_markers[-1]
                else sg.TEXT_LOCATION_BOTTOM_RIGHT
            ),
        )

    # draw x and Y axes and make them a little thicker
    graph.draw_lines(
        [
            (results.forward_cg_limit_input, results.empty_weight),
            (results.aft_cg_limit_input, results.empty_weight),
            (results.forward_cg_limit_input, results.empty_weight),
            (results.forward_cg_limit_input, values.max_gross_weight_input),
        ],
        color="black",
        width=2,
    )
    window.refresh()


def draw_graph(window, results, values):
    graph = window["wb_graph"]
    circle_radius = round(
        (results.aft_cg_limit_input - results.forward_cg_limit_input) / 100, 2
    )
    # draw startng CG and label
    graph.draw_circle(
        (results.cg_location_begin, results.weight_begin),
        circle_radius,
        fill_color="green",
    )
    graph.draw_text(
        "Starting CG",
        (results.cg_location_begin + 0.1, results.weight_begin),
        text_location=(
            sg.TEXT_LOCATION_LEFT
            if results.weight_begin != results.zero_fuel_weight
            else sg.TEXT_LOCATION_BOTTOM_LEFT
        ),
    )
    # draw ending CG and label
    if results.fuel_use_weight > 0:
        graph.draw_circle(
            (results.cg_location_end, results.weight_end),
            circle_radius,
            fill_color="blue",
        )
        graph.draw_text(
            "Ending CG",
            (results.cg_location_end + 0.1, results.weight_end),
            text_location=sg.TEXT_LOCATION_LEFT,
        )
    # Connect the dots from start to eng CG
    graph.draw_line(
        point_from=(results.cg_location_begin, results.weight_begin),
        point_to=(results.cg_location_end, results.weight_end),
    )
    if results.zero_fuel_weight != results.weight_begin:
        # draw zero fuel CG and label
        graph.draw_circle(
            (results.zero_fuel_cg, results.zero_fuel_weight),
            circle_radius,
            fill_color="red",
        )
        graph.draw_text(
            "Zero Fuel CG",
            (results.zero_fuel_cg, results.zero_fuel_weight - 20),
            text_location=sg.TEXT_LOCATION_TOP,
        )
    # Connect the end CG and ZFCG dots
    graph.draw_line(
        point_from=(results.cg_location_end, results.weight_end),
        point_to=(results.zero_fuel_cg, results.zero_fuel_weight),
        color="gray",
    )
    window.refresh()
