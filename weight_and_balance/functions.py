from dotmap import DotMap


def sum(*args):
    x = 0
    for val in args:
        x += val
    return round(x, 2)


def multiply(x, y):
    return round(x * y, 2)


def divide(x, y):
    return round(x / y, 2)


def calc_cg_percent(cg, fwd_limit, aft_limit):
    return (cg - fwd_limit) / (aft_limit - fwd_limit) * 100


def _round(x):
    return round(x, 2)


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
