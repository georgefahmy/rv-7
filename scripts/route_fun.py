import math
import textwrap

import airportsdata
import networkx as nx


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculates the great-circle distance between two points in nautical miles."""
    R = 3440.065  # Radius of the Earth in nautical miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def find_optimal_route(airport_codes, start_airport=None):
    print("Loading airport databases...")
    icao_db = airportsdata.load("ICAO")
    lid_db = airportsdata.load("LID")

    valid_airports = {}
    missing_airports = []

    # 1. Resolve coordinates for the provided codes
    for code in airport_codes:
        code = code.strip().upper()
        if code in icao_db:
            valid_airports[code] = icao_db[code]
        elif code in lid_db:
            valid_airports[code] = lid_db[code]
        elif f"K{code}" in icao_db:
            valid_airports[code] = icao_db[f"K{code}"]
        else:
            missing_airports.append(code)

    if missing_airports:
        print(
            f"Warning: Could not find coordinates for {len(missing_airports)} airports: {', '.join(missing_airports)}\n"
        )

    codes = list(valid_airports.keys())
    if len(codes) < 2:
        print("Not enough valid airports found to calculate a route.")
        return

    # 2. Validate and resolve the starting airport
    resolved_start = None
    if start_airport:
        start_code = start_airport.strip().upper()
        if start_code in valid_airports:
            resolved_start = start_code
        elif f"K{start_code}" in valid_airports:
            resolved_start = f"K{start_code}"
        else:
            print(
                f"Error: The starting airport '{start_airport}' was not found in the valid routing list."
            )
            return

    print(f"Building distance matrix for {len(codes)} airports...")

    # 3. Build a complete graph with distances as edge weights
    G = nx.Graph()
    for i in range(len(codes)):
        for j in range(i + 1, len(codes)):
            code1 = codes[i]
            code2 = codes[j]

            lat1, lon1 = valid_airports[code1]["lat"], valid_airports[code1]["lon"]
            lat2, lon2 = valid_airports[code2]["lat"], valid_airports[code2]["lon"]

            dist = haversine_distance(lat1, lon1, lat2, lon2)
            G.add_edge(code1, code2, weight=dist)

    print("Calculating optimal route (TSP Approximation)...")

    # 4. Solve the TSP problem
    tsp_path = nx.approximation.traveling_salesman_problem(
        G, weight="weight", cycle=True
    )

    # 5. Rotate the loop to begin at the specified starting airport
    if resolved_start and resolved_start in tsp_path:
        # Remove the duplicate last element (since it's a closed loop)
        cycle_nodes = tsp_path[:-1]

        # Find the index of our desired start
        start_idx = cycle_nodes.index(resolved_start)

        # Slice and recombine the list to rotate it
        tsp_path = cycle_nodes[start_idx:] + cycle_nodes[:start_idx]

        # Append the start node back to the end to close the loop
        tsp_path.append(resolved_start)

    # 6. Calculate the total distance of the resulting route
    total_distance = 0
    for i in range(len(tsp_path) - 1):
        total_distance += G[tsp_path[i]][tsp_path[i + 1]]["weight"]

    print("\n" + "=" * 80)
    if resolved_start:
        print(f"                 OPTIMAL ROUTE (STARTING AT {resolved_start})")
    else:
        print("                 OPTIMAL ROUTE")
    print("=" * 80)

    # Format the output into manageable lines
    path_str = " ".join(tsp_path)
    wrapped_path = textwrap.fill(path_str, width=80)
    print(wrapped_path)

    print("-" * 80)
    print(f"Total Estimated Distance: {total_distance:,.2f} nautical miles")
    print("=" * 80)


if __name__ == "__main__":
    raw_input = "A26 L70 KAAT A24 2O3 KAPV KACV KMER KAUN KAVX 0O2 KBFL L45 KBNG O02 O55 L35 KBIH KBLH D83 L08 KBWC O57 KBUR L62 C83 KCXL L71 KCLR KCMA O61 KCRQ O59 49X O05 KCIC KCNO L77 2O6 O60 3O8 C80 O22 O08 KCPM KCCR 0O4 KAJO O09 KCEC KDAG KEDU KDWA L06 L09 KDLO D63 A32 1O6 KEMT KBLU KEKA O19 O33 O89 L18 L73 F34 A28 A30 KFOT F72 KFAT KFCH E79 KFUL O16 0O9 E36 KGOO E45 E55 3O1 KHAF KHJO 36S KHHR F62 KHWD KHES KHMT H37 L26 KCVH 1C9 O21 H47 KIPL 2O7 KIYK KJAQ L78 L05 KKIC S51 KPOC 1O2 KWJF O24 KLHM KLLR KLVK 1O3 O20 L53 KLPC O26 L80 KLGB KWHP KLAX KLSN KMAE KMMH KOAR KMPI M45 KMYV KMCE KMOD KMHV KSIY 1O5 KMRY F70 KAPC KEED L88 KDVO O27 KOAK L52 KOKB L90 KONT O37 KOVE KOXR KPSP KTRM KUDD KPMD KPAO KPRB L65 O69 KPVF KPTV 2O1 KRNM KRIU O39 KRBL KRDD O85 KREI O32 L36 O88 KRAL KRIV KRIR L00 T42 KSMF KSAC KMHR KMCC KSNS KSAS KCPU KSBD KSQL KMYF KSDM KSAN KSEE KSFO KSJC KRHV KSBP E16 KSNA KSBA KSMX KSMO KSZP KSTS KIZA 0Q3 0Q4 KMIT 0Q5 L61 O79 0Q9 KTVL KSCK 1Q1 KSVE 1Q2 L17 KTSP L94 KTOA KTCY 1Q4 O86 L72 KTRK KTLR O81 O15 KTNP KUKI KCCB 1Q5 KVCB KVNY KVCV KVIS D86 L19 KWVI O54 O46 O28 KWLW O42 O41 O52 L22"

    airport_list = raw_input.split()

    # Pass your desired starting airport here (e.g., KLAX, KSFO, E16)
    find_optimal_route(airport_list, start_airport="E16")
