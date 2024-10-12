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


def sum(*args):
    x = 0
    for val in args:
        x += val
    return x


def multiply(x, y):
    return x * y


def divide(x, y):
    return x / y


def calc_cg_percent(cg):
    return (cg - FWD_CG_LIMIT) / (AFT_CG_LIMIT - FWD_CG_LIMIT) * 100


def _round(x):
    return round(x, 2)


def calc_cg(
    left_front_weight,
    right_front_weight,
    tailwheel_weight,
    fuel_gal=0,
    pilot_weight=0,
    passenger_weight=0,
    baggage_weight=0,
):
    fuel_weight = multiply(fuel_gal, 6)
    weight = sum(
        left_front_weight,
        right_front_weight,
        tailwheel_weight,
        fuel_weight,
        pilot_weight,
        passenger_weight,
        baggage_weight,
    )
    moment = sum(
        multiply(left_front_weight, FRONT_LEFT_DIST),
        multiply(right_front_weight, FRONT_RIGHT_DIST),
        multiply(tailwheel_weight, TAILWHEEL_DIST),
        multiply(fuel_weight, FUEL_DIST),
        multiply(pilot_weight, CABIN_SEATS_DIST),
        multiply(passenger_weight, CABIN_SEATS_DIST),
        multiply(baggage_weight, BAGGAGE_DIST),
    )
    cg = divide(moment, weight)
    cg_percent = calc_cg_percent(cg)

    if weight > 1800:
        raise f"Max Gross Weight {weight} must be less than 1800lb"

    if 0 > cg_percent > 100:
        raise f"CG {cg} outside CG envelope"

    if fuel_gal > 42:
        raise f"Fuel QTY {fuel_gal} exceeds max allowable of 42 gal"

    return DotMap(
        weight=f"{_round(weight)} lbs",
        moment=f"{_round(moment)} in-lbs",
        cg_location=f"{_round(cg)} inches",
        cg_percent=f"{_round(cg_percent)}%",
    )


input_flag = 1
left_front_weight = 522.89
right_front_weight = 522.89
tailwheel_weight = 65.22

if input_flag:
    fuel_gal = input("Fuel Gallons: ") or 42
    pilot_weight = input("Pilot Weight: ") or 210
    passenger_weight = input("Passenger Weight: ") or 130
    baggage_weight = input("Baggage Weight: ") or 97
    config_name = input("Config name: ")

result = DotMap(
    {
        config_name: calc_cg(
            left_front_weight=left_front_weight,
            right_front_weight=right_front_weight,
            tailwheel_weight=tailwheel_weight,
            fuel_gal=int(fuel_gal),
            pilot_weight=int(pilot_weight),
            passenger_weight=int(passenger_weight),
            baggage_weight=int(baggage_weight),
        )
    }
)
result.pprint(pformat="json")
exit()

empty_weight = calc_cg(
    left_front_weight=left_front_weight,
    right_front_weight=right_front_weight,
    tailwheel_weight=tailwheel_weight,
)

max_gross_weight = calc_cg(
    left_front_weight=left_front_weight,
    right_front_weight=right_front_weight,
    tailwheel_weight=tailwheel_weight,
    fuel_gal=42,
    pilot_weight=210,
    passenger_weight=130,
    baggage_weight=97,
)

most_aft_cg = calc_cg(
    left_front_weight=left_front_weight,
    right_front_weight=right_front_weight,
    tailwheel_weight=tailwheel_weight,
    fuel_gal=5,
    pilot_weight=210,
    passenger_weight=130,
    baggage_weight=97,
)

most_forward_cg = calc_cg(
    left_front_weight=left_front_weight,
    right_front_weight=right_front_weight,
    tailwheel_weight=tailwheel_weight,
    fuel_gal=42,
    pilot_weight=210,
)

first_flight_config = calc_cg(
    left_front_weight=left_front_weight,
    right_front_weight=right_front_weight,
    tailwheel_weight=tailwheel_weight,
    fuel_gal=42,
    pilot_weight=210,
)

aircraft_configs = DotMap(
    empty_weight=empty_weight,
    max_gross_weight=max_gross_weight,
    most_aft_cg=most_aft_cg,
    most_forward_cg=most_forward_cg,
    first_flight_config=first_flight_config,
)

aircraft_configs.pprint(pformat="json")
