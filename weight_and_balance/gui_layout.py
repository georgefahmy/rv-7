import PySimpleGUI as sg

from weight_and_balance.functions import calc_cg, load_params

params = load_params()
results = calc_cg(params.Default)
sg.theme("Reddit")
sg.set_options(font=("Arial", 16))

layout = [
    [
        sg.Text("Load Config Name:", expand_x=True),
        sg.Combo(
            values=list(params.keys()),
            size=20,
            key="load_config_name",
            enable_events=True,
        ),
    ],
    [
        sg.Text("Save Config Name:", expand_x=True),
        sg.Button("Save Params", font=("Arial", 14), key="save_params_button"),
        sg.Input(size=21, key="save_config_name"),
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
                    sg.Text("", expand_x=True),
                    sg.Slider(
                        size=(10, 12),
                        key="pilot_weight_input_slider",
                        enable_events=True,
                        orientation="h",
                        disable_number_display=True,
                        range=(0, 300),
                        pad=0,
                        border_width=0,
                        resolution=1,
                    ),
                    sg.Text(expand_x=True),
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
                    sg.Text("", expand_x=True),
                    sg.Slider(
                        size=(10, 12),
                        key="copilot_weight_input_slider",
                        enable_events=True,
                        orientation="h",
                        disable_number_display=True,
                        range=(0, 300),
                        pad=0,
                        border_width=0,
                        resolution=1,
                    ),
                    sg.Text(expand_x=True),
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
                    sg.Text("", expand_x=True),
                    sg.Slider(
                        size=(10, 12),
                        key="baggage_weight_input_slider",
                        enable_events=True,
                        orientation="h",
                        disable_number_display=True,
                        range=(0, 100),
                        pad=0,
                        border_width=0,
                        resolution=1,
                    ),
                    sg.Text(expand_x=True),
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
                    sg.Text("", expand_x=True),
                    sg.Slider(
                        size=(10, 12),
                        key="fuel_start_weight_input_slider",
                        enable_events=True,
                        orientation="h",
                        disable_number_display=True,
                        range=(0, 42),
                        pad=0,
                        border_width=0,
                        resolution=1,
                    ),
                    sg.Text(expand_x=True),
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
                    sg.Text("", expand_x=True),
                    sg.Slider(
                        size=(10, 12),
                        key="fuel_use_input_slider",
                        enable_events=True,
                        orientation="h",
                        disable_number_display=True,
                        range=(0, 42),
                        pad=0,
                        border_width=0,
                        resolution=1,
                    ),
                    sg.Text(expand_x=True),
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
                [
                    sg.Text("Fwd CG Limit:", expand_x=True),
                    sg.Input(
                        size=10,
                        disabled=True,
                        disabled_readonly_background_color="white",
                        border_width=0,
                        pad=(6, 0),
                        key=None,
                    ),
                    sg.Input(
                        size=10,
                        key="forward_cg_limit_input",
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Aft CG Limit:", expand_x=True),
                    sg.Input(
                        size=10,
                        disabled=True,
                        disabled_readonly_background_color="white",
                        border_width=0,
                        pad=(6, 0),
                        key=None,
                    ),
                    sg.Input(
                        size=10,
                        key="aft_cg_limit_input",
                        enable_events=True,
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
                        graph_bottom_left=(78.7, results.empty_weight),
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
