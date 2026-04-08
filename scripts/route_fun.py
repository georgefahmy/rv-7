import math
import textwrap

import airportsdata
import networkx as nx


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculates the great-circle distance between two points in nautical miles."""
    R = 3440.065
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def calculate_routing_weight(distance, code1, code2):
    """Custom weights to influence the TSP solver."""
    weight = distance
    weight += 30.0  # Stop penalty

    max_comfortable_range = 250.0
    if distance > max_comfortable_range:
        weight += (distance - max_comfortable_range) * 3.0

    return weight


def calculate_path_weight(path, G):
    """Helper to calculate the total algorithmic weight of a specific path sequence."""
    return sum(G[path[i]][path[i + 1]]["weight"] for i in range(len(path) - 1))


def apply_2opt_optimization(path, G):
    """
    Iteratively untangles 'crossed' routes to eliminate doubling back.
    """
    improved = True
    best_path = path
    best_weight = calculate_path_weight(best_path, G)

    while improved:
        improved = False
        # We ignore the very first and last nodes because they are the same (a closed loop)
        for i in range(1, len(best_path) - 2):
            for j in range(i + 1, len(best_path) - 1):
                # Reverse the segment between i and j to "untangle" a crossing
                new_path = best_path[:i] + best_path[i:j][::-1] + best_path[j:]
                new_weight = calculate_path_weight(new_path, G)

                # If untangling made it shorter, keep it and restart the search
                if new_weight < best_weight:
                    best_weight = new_weight
                    best_path = new_path
                    improved = True
                    break
            if improved:
                break

    return best_path


def find_optimal_route(airport_codes, start_airport=None):
    print("Loading airport databases...")
    icao_db = airportsdata.load("ICAO")
    lid_db = airportsdata.load("LID")

    valid_airports = {}
    missing_airports = []

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

    resolved_start = None
    if start_airport:
        start_code = start_airport.strip().upper()
        if start_code in valid_airports:
            resolved_start = start_code
        elif f"K{start_code}" in valid_airports:
            resolved_start = f"K{start_code}"
        else:
            print(f"Error: The starting airport '{start_airport}' was not found.")
            return

    print(f"Building distance matrix for {len(codes)} airports...")

    G = nx.Graph()
    for i in range(len(codes)):
        for j in range(i + 1, len(codes)):
            code1 = codes[i]
            code2 = codes[j]

            lat1, lon1 = valid_airports[code1]["lat"], valid_airports[code1]["lon"]
            lat2, lon2 = valid_airports[code2]["lat"], valid_airports[code2]["lon"]

            dist = haversine_distance(lat1, lon1, lat2, lon2)
            route_weight = calculate_routing_weight(dist, code1, code2)
            G.add_edge(code1, code2, weight=route_weight, actual_distance=dist)

    print("Calculating initial route approximation...")
    initial_path = nx.approximation.traveling_salesman_problem(
        G, weight="weight", cycle=True
    )

    print(
        "Applying 2-Opt algorithm to untangle crossed routes (minimizing doubling back)..."
    )
    tsp_path = apply_2opt_optimization(initial_path, G)

    # Rotate to starting airport
    if resolved_start and resolved_start in tsp_path:
        cycle_nodes = tsp_path[:-1]
        start_idx = cycle_nodes.index(resolved_start)
        tsp_path = cycle_nodes[start_idx:] + cycle_nodes[:start_idx]
        tsp_path.append(resolved_start)

    # Calculate totals
    total_distance = 0
    total_weight = 0
    longest_leg = 0

    for i in range(len(tsp_path) - 1):
        edge_data = G[tsp_path[i]][tsp_path[i + 1]]
        total_distance += edge_data["actual_distance"]
        total_weight += edge_data["weight"]

        if edge_data["actual_distance"] > longest_leg:
            longest_leg = edge_data["actual_distance"]

    print("\n" + "=" * 80)
    if resolved_start:
        print(f"                 OPTIMAL ROUTE (STARTING AT {resolved_start})")
    else:
        print("                 OPTIMAL ROUTE")
    print("=" * 80)

    path_str = " ".join(tsp_path)
    wrapped_path = textwrap.fill(path_str, width=80)
    print(wrapped_path)

    print("-" * 80)
    print(f"True Distance Flown: {total_distance:,.2f} nm")
    print(f"Algorithmic Cost:    {total_weight:,.2f} (Includes custom penalties)")
    print(f"Longest Single Leg:  {longest_leg:,.2f} nm")
    print("=" * 80)


if __name__ == "__main__":
    raw_input = "A26 L70 KAAT A24 2O3 KAPV KACV KMER KAUN KAVX 0O2 KBFL L45 KBNG O02 O55 L35 KBIH KBLH D83 L08 KBWC O57 KBUR L62 C83 KCXL L71 KCLR KCMA O61 KCRQ O59 49X O05 KCIC KCNO L77 2O6 O60 3O8 C80 O22 O08 KCPM KCCR 0O4 KAJO O09 KCEC KDAG KEDU KDWA L06 L09 KDLO D63 A32 1O6 KEMT KBLU KEKA O19 O33 O89 L18 L73 F34 A28 A30 KFOT F72 KFAT KFCH E79 KFUL O16 0O9 E36 KGOO E45 E55 3O1 KHAF KHJO 36S KHHR F62 KHWD KHES KHMT H37 L26 KCVH 1C9 O21 H47 KIPL 2O7 KIYK KJAQ L78 L05 KKIC S51 KPOC 1O2 KWJF O24 KLHM KLLR KLVK 1O3 O20 L53 KLPC O26 L80 KLGB KWHP KLAX KLSN KMAE KMMH KOAR KMPI M45 KMYV KMCE KMOD KMHV KSIY 1O5 KMRY F70 KAPC KEED L88 KDVO O27 KOAK L52 KOKB L90 KONT O37 KOVE KOXR KPSP KTRM KUDD KPMD KPAO KPRB L65 O69 KPVF KPTV 2O1 KRNM KRIU O39 KRBL KRDD O85 KREI O32 L36 O88 KRAL KRIV KRIR L00 T42 KSMF KSAC KMHR KMCC KSNS KSAS KCPU KSBD KSQL KMYF KSDM KSAN KSEE KSFO KSJC KRHV KSBP E16 KSNA KSBA KSMX KSMO KSZP KSTS KIZA 0Q3 0Q4 KMIT 0Q5 L61 O79 0Q9 KTVL KSCK 1Q1 KSVE 1Q2 L17 KTSP L94 KTOA KTCY 1Q4 O86 L72 KTRK KTLR O81 O15 KTNP KUKI KCCB 1Q5 KVCB KVNY KVCV KVIS D86 L19 KWVI O54 O46 O28 KWLW O42 O41 O52 L22"

    airport_list = raw_input.split()
    find_optimal_route(airport_list, start_airport="E16")
