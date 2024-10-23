from dotmap import DotMap

# Designed CG envelope - 15% - 29% of chord - 8.7" -16.82" aft of LE - 78.7" - 86.82" of datum

# Update all numbers to be real distances

# distances
DATUM = 0
WING_LE = 70
FRONT_LEFT_DIST = 68.45
FRONT_RIGHT_DIST = 68.45
TAILWHEEL_DIST = 249.19
FUEL_DIST = 80
CABIN_SEATS_DIST = 97.48
BAGGAGE_DIST = 126.78
FWD_CG_LIMIT = 78.7
AFT_CG_LIMIT = 86.82
AFT_AEROBATIC_CG_LIMIT = 84.5
MAX_WEIGHT_LIMIT = 1850
CHORD_LENGTH = 58


def sum(*args):
    x = 0
    for val in args:
        x += val
    return x


def multiply(x, y):
    return x * y


def divide(x, y):
    return x / y


def calc_cg_percent_of_chord(cg):
    return (cg - WING_LE) / CHORD_LENGTH * 100


def calc_cg_percent(cg):
    return (cg - FWD_CG_LIMIT) / (AFT_CG_LIMIT - FWD_CG_LIMIT) * 100


def _round(x):
    return round(x, 2)


def calc_cg(
    left_front_weight,
    right_front_weight,
    tailwheel_weight,
    fuel_gal_start=0,
    fuel_gal_use=0,
    pilot_weight=0,
    passenger_weight=0,
    baggage_weight=0,
    chord=False,
):
    fuel_start_weight = multiply(fuel_gal_start, 6)
    fuel_use_weight = multiply(fuel_gal_use, 6)

    empty_weight = sum(
        left_front_weight,
        right_front_weight,
        tailwheel_weight,
    )

    start_weight = sum(
        empty_weight,
        fuel_start_weight,
        pilot_weight,
        passenger_weight,
        baggage_weight,
    )

    end_weight = sum(
        empty_weight,
        fuel_start_weight - fuel_use_weight,
        pilot_weight,
        passenger_weight,
        baggage_weight,
    )

    empty_moment = sum(
        multiply(left_front_weight, FRONT_LEFT_DIST),
        multiply(right_front_weight, FRONT_RIGHT_DIST),
        multiply(tailwheel_weight, TAILWHEEL_DIST),
    )

    start_moment = sum(
        empty_moment,
        multiply(fuel_start_weight, FUEL_DIST),
        multiply(pilot_weight, CABIN_SEATS_DIST),
        multiply(passenger_weight, CABIN_SEATS_DIST),
        multiply(baggage_weight, BAGGAGE_DIST),
    )

    end_moment = sum(
        empty_moment,
        multiply(fuel_start_weight - fuel_use_weight, FUEL_DIST),
        multiply(pilot_weight, CABIN_SEATS_DIST),
        multiply(passenger_weight, CABIN_SEATS_DIST),
        multiply(baggage_weight, BAGGAGE_DIST),
    )
    start_cg = divide(start_moment, start_weight)
    if chord:

        start_cg_percent = calc_cg_percent_of_chord(start_cg)
    else:
        start_cg_percent = calc_cg_percent(start_cg)

    end_cg = divide(end_moment, end_weight)
    if chord:
        end_cg_percent = calc_cg_percent_of_chord(end_cg)
    else:
        end_cg_percent = calc_cg_percent(end_cg)

    if start_weight > MAX_WEIGHT_LIMIT:
        raise Exception(
            f"Max Gross Weight {int(start_weight)} must be less than {MAX_WEIGHT_LIMIT}lb - {int(start_weight - MAX_WEIGHT_LIMIT)}lbs overweight"
        )

    if end_weight > MAX_WEIGHT_LIMIT:
        raise Exception(
            f"Max Gross Weight {int(end_weight)} must be less than {MAX_WEIGHT_LIMIT}lb - {int(end_weight - MAX_WEIGHT_LIMIT)}lbs overweight"
        )

    if 0 > any([start_cg_percent, end_cg_percent]) > 100:
        raise Exception("CG outside CG envelope")

    if fuel_gal_start > 42:
        raise Exception(f"Fuel QTY {fuel_gal_start} exceeds max allowable of 42 gal")

    chord_limit = " of chord" if chord else " of CG envelope"

    results = DotMap(
        weight_begin=f"{_round(start_weight)} lbs",
        moment_begin=f"{_round(start_moment)} in-lbs",
        cg_location_begin=f"{_round(start_cg)} inches",
        cg_percent_begin=f"{_round(start_cg_percent)}%{chord_limit}",
    )

    if fuel_gal_use:
        results["weight_end"] = f"{_round(end_weight)} lbs"
        results["moment_end"] = f"{_round(end_moment)} in-lbs"
        results["cg_location_end"] = f"{_round(end_cg)} inches"
        results["cg_percent_end"] = f"{_round(end_cg_percent)}%{chord_limit}"

    return results


input_flag = 1
left_front_weight = 522.89
right_front_weight = 522.89
tailwheel_weight = 65.22
empty_weight = sum(left_front_weight, right_front_weight, tailwheel_weight)
fuel_gal_start = 0
fuel_gal_use = 0
pilot_weight = 0
passenger_weight = 0
baggage_weight = 0
config_name = "Default"
chord_flag = False

if input_flag:
    print(f"Empty Weight: {empty_weight}lbs")
    fuel_gal_start = input("Starting Fuel Gallons: ") or fuel_gal_start
    fuel_gal_use = input("Fuel usage: ") or fuel_gal_use
    pilot_weight = input("Pilot Weight: ") or pilot_weight
    passenger_weight = input("Passenger Weight: ") or passenger_weight
    baggage_weight = input("Baggage Weight: ") or baggage_weight
    config_name = input("Config name: ") or config_name
    chord_flag = bool(input("Chord Flag: "))

result = DotMap(
    {
        config_name: calc_cg(
            left_front_weight=left_front_weight,
            right_front_weight=right_front_weight,
            tailwheel_weight=tailwheel_weight,
            fuel_gal_start=int(fuel_gal_start),
            fuel_gal_use=int(fuel_gal_use),
            pilot_weight=int(pilot_weight),
            passenger_weight=int(passenger_weight),
            baggage_weight=int(baggage_weight),
            chord=chord_flag,
        )
    }
)
result.pprint(pformat="json")
