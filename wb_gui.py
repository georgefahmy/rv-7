import json

import PySimpleGUI as sg
from dotmap import DotMap

from weight_and_balance.functions import (
    calc_cg,
    draw_graph,
    load_params,
    set_graph_grid,
)
from weight_and_balance.gui_layout import layout

# sg.theme("Reddit")
# sg.set_options(font=("Arial", 16))


params = load_params()
results = calc_cg(params.Default)
window = sg.Window("Weight & Balance", layout=layout, finalize=True)


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
                    params[config][key] = (
                        float(params[config][key]) if params[config][key] else 0
                    )
        for key in params[values["load_config_name"]].keys():
            sg.fill_form_with_values(window, params[values["load_config_name"]])

        window.write_event_value(key, params[values["load_config_name"]][key])

    if event == "save_params_button":
        if not values.save_config_name:
            continue

        save_params = values.copy()
        del save_params[0]
        del save_params[1]
        del save_params[2]
        del save_params[3]
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
        window["load_config_name"].update(
            value=values["save_config_name"], values=list(params.keys())
        )
        window["save_config_name"].update(value="")

    if "input" in event:
        if "slider" in event:
            window[event[:-7]].update(value=values[event])
        # values.pprint()
        for element in window.element_list():
            if type(element.key) is str and "input" in element.key:
                specific_element = values[element.key]
                try:
                    values[element.key] = float(specific_element)
                except Exception:
                    values[element.key] = 0

        results = calc_cg(values)
        set_graph_grid(window, results, values)
        draw_graph(window, results, values)

        window["fuel_use_input_slider"].update(
            range=(0, values.fuel_start_weight_input)
        )
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
