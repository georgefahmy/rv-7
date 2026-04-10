import math
import textwrap
import time

# import webbrowser
from urllib.parse import quote

import airportsdata
import networkx as nx
import pyperclip
import requests
from bs4 import BeautifulSoup


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


def calculate_routing_weight(
    distance, alt1, alt2, min_leg, max_leg, altitude_penalty_factor
):
    """Custom weights to influence the TSP solver, including altitude optimization."""
    weight = distance
    weight += 30.0  # Base penalty for every stop

    # Altitude Penalty
    alt_diff = abs(alt1 - alt2)
    weight += (alt_diff / 1000.0) * altitude_penalty_factor

    # Range Penalties
    if min_leg is not None and distance < min_leg:
        weight += (min_leg - distance) * 10000.0
    if max_leg is not None and distance > max_leg:
        weight += (distance - max_leg) * 10000.0

    return weight


def calculate_path_weight(path, G):
    return sum(G[path[i]][path[i + 1]]["weight"] for i in range(len(path) - 1))


def apply_2opt_optimization(path, G):
    """Iteratively untangles 'crossed' routes to eliminate doubling back."""
    improved = True
    best_path = path
    best_weight = calculate_path_weight(best_path, G)

    while improved:
        improved = False
        for i in range(1, len(best_path) - 2):
            for j in range(i + 1, len(best_path) - 1):
                new_path = best_path[:i] + best_path[i:j][::-1] + best_path[j:]
                new_weight = calculate_path_weight(new_path, G)

                if new_weight < best_weight:
                    best_weight = new_weight
                    best_path = new_path
                    improved = True
                    break
            if improved:
                break

    return best_path


def find_optimal_route(
    airport_codes,
    start_airport=None,
    min_leg=None,
    max_leg=None,
    altitude_penalty_factor=0,
    max_radius_from_start=None,
):
    # --- START TOTAL TIMER ---
    start_time = time.time()

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

    # --- OPTIONAL FILTER: LIMIT DISTANCE FROM START AIRPORT ---
    if resolved_start and max_radius_from_start is not None:
        print(
            f"Filtering airports within {max_radius_from_start} nm of {resolved_start}..."
        )

        start_lat = valid_airports[resolved_start]["lat"]
        start_lon = valid_airports[resolved_start]["lon"]

        filtered_airports = {}
        for code, data in valid_airports.items():
            lat, lon = data["lat"], data["lon"]
            dist_from_start = haversine_distance(start_lat, start_lon, lat, lon)

            if dist_from_start <= max_radius_from_start or code == resolved_start:
                filtered_airports[code] = data

        removed_count = len(valid_airports) - len(filtered_airports)
        if removed_count > 0:
            print(f"-> Removed {removed_count} airports outside radius")

        valid_airports = filtered_airports
        codes = list(valid_airports.keys())

        if len(codes) < 2:
            print(
                "Not enough airports within the specified radius to calculate a route."
            )
            return

    print(f"Building distance matrix for {len(codes)} airports...")
    if altitude_penalty_factor > 0:
        print(
            f"-> Altitude Optimization ACTIVE (Penalty: {altitude_penalty_factor}nm per 1,000ft change)"
        )

    # --- START ALGORITHM TIMER ---
    algo_start_time = time.time()

    G = nx.Graph()
    for i in range(len(codes)):
        for j in range(i + 1, len(codes)):
            code1 = codes[i]
            code2 = codes[j]

            lat1, lon1 = valid_airports[code1]["lat"], valid_airports[code1]["lon"]
            lat2, lon2 = valid_airports[code2]["lat"], valid_airports[code2]["lon"]

            alt1 = float(valid_airports[code1].get("elevation", 0.0) or 0.0)
            alt2 = float(valid_airports[code2].get("elevation", 0.0) or 0.0)

            dist = haversine_distance(lat1, lon1, lat2, lon2)
            route_weight = calculate_routing_weight(
                dist, alt1, alt2, min_leg, max_leg, altitude_penalty_factor
            )

            G.add_edge(
                code1,
                code2,
                weight=route_weight,
                actual_distance=dist,
                alt_diff=abs(alt1 - alt2),
            )

    print("Calculating initial route approximation...")
    initial_path = nx.approximation.traveling_salesman_problem(
        G, weight="weight", cycle=True
    )

    print("Applying 2-Opt optimization...")
    tsp_path = apply_2opt_optimization(initial_path, G)

    # --- END ALGORITHM TIMER ---
    algo_duration = time.time() - algo_start_time

    if resolved_start and resolved_start in tsp_path:
        cycle_nodes = tsp_path[:-1]
        start_idx = cycle_nodes.index(resolved_start)
        tsp_path = cycle_nodes[start_idx:] + cycle_nodes[:start_idx]
        tsp_path.append(resolved_start)

    total_distance = 0
    longest_leg = 0
    shortest_leg = float("inf")
    total_alt_changes = 0
    violations = 0

    for i in range(len(tsp_path) - 1):
        edge_data = G[tsp_path[i]][tsp_path[i + 1]]
        dist = edge_data["actual_distance"]
        total_distance += dist
        total_alt_changes += edge_data["alt_diff"]

        if dist > longest_leg:
            longest_leg = dist
        if dist < shortest_leg:
            shortest_leg = dist

        if (min_leg and dist < min_leg) or (max_leg and dist > max_leg):
            violations += 1

    # --- END TOTAL TIMER ---
    total_duration = time.time() - start_time

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
    print(f"True Distance Flown:      {total_distance:,.2f} nm")
    print(f"Cumulative Alt Changes:   {total_alt_changes:,.0f} feet")
    print(f"Shortest / Longest Leg:   {shortest_leg:,.1f} nm / {longest_leg:,.1f} nm")

    if violations > 0:
        print(
            f"⚠️ Rule Violations:       {violations} leg(s) broke your min/max limits."
        )
    else:
        print("✅ Rule Violations:       0 (All routing constraints met perfectly)")

    print(
        f"⏱️ Calculation Time:      {algo_duration:.3f} seconds (Total Script: {total_duration:.3f}s)"
    )
    print("=" * 80)
    return tsp_path


def get_airports(state="CA"):
    url = f"https://www.airnav.com/airports/us/{state}"

    # AirNav sometimes blocks default bot user-agents, so we specify a standard browser header
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an error for bad status codes
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the webpage: {e}")

    soup = BeautifulSoup(response.text, "html.parser")

    airport_ids = []

    # Find all table rows in the document
    rows = soup.find_all("tr")

    for row in rows:
        # Get all cells in the row
        cells = row.find_all(["th", "td"])
        # Check if this row matches the format of the airport list (ID, City, Name)
        # Often, the ID is in the first column and is wrapped in an anchor link
        if cells and len(cells) >= 3:
            first_cell = cells[0]
            # Look for an anchor tag (link) inside the first cell
            link = first_cell.find("a")
            if link and link.get("href", "").startswith("/airport/"):
                # Extract the text (the ID) and strip any surrounding whitespace
                airport_id = link.get_text(strip=True)
                airport_ids.append(airport_id)

    return airport_ids


if __name__ == "__main__":
    # raw_input = "A26 L70 KAAT A24 2O3 KAPV KACV KMER KAUN KAVX 0O2 KBFL L45 KBNG O02 O55 L35 KBIH KBLH D83 L08 KBWC O57 KBUR L62 C83 KCXL L71 KCLR KCMA O61 KCRQ O59 49X O05 KCIC KCNO L77 2O6 O60 3O8 C80 O22 O08 KCPM KCCR 0O4 KAJO O09 KCEC KDAG KEDU KDWA L06 L09 KDLO D63 A32 1O6 KEMT KBLU KEKA O19 O33 O89 L18 L73 F34 A28 A30 KFOT F72 KFAT KFCH E79 KFUL O16 0O9 E36 KGOO E45 E55 3O1 KHAF KHJO 36S KHHR F62 KHWD KHES KHMT H37 L26 KCVH 1C9 O21 H47 KIPL 2O7 KIYK KJAQ L78 L05 KKIC S51 KPOC 1O2 KWJF O24 KLHM KLLR KLVK 1O3 O20 L53 KLPC O26 L80 KLGB KWHP KLAX KLSN KMAE KMMH KOAR KMPI M45 KMYV KMCE KMOD KMHV KSIY 1O5 KMRY F70 KAPC KEED L88 KDVO O27 KOAK L52 KOKB L90 KONT O37 KOVE KOXR KPSP KTRM KUDD KPMD KPAO KPRB L65 O69 KPVF KPTV 2O1 KRNM KRIU O39 KRBL KRDD O85 KREI O32 L36 O88 KRAL KRIV KRIR L00 T42 KSMF KSAC KMHR KMCC KSNS KSAS KCPU KSBD KSQL KMYF KSDM KSAN KSEE KSFO KSJC KRHV KSBP E16 KSNA KSBA KSMX KSMO KSZP KSTS KIZA 0Q3 0Q4 KMIT 0Q5 L61 O79 0Q9 KTVL KSCK 1Q1 KSVE 1Q2 L17 KTSP L94 KTOA KTCY 1Q4 O86 L72 KTRK KTLR O81 O15 KTNP KUKI KCCB 1Q5 KVCB KVNY KVCV KVIS D86 L19 KWVI O54 O46 O28 KWLW O42 O41 O52 L22"
    # airport_list = raw_input.split()
    airport_list = get_airports(state="CA")

    route = find_optimal_route(
        airport_codes=airport_list,
        start_airport="E16",
        min_leg=1.0,
        max_leg=300.0,
        altitude_penalty_factor=0,
        max_radius_from_start=50,
    )

    session = requests.Session()
    route_string = " ".join(route)
    pyperclip.copy(route_string)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }

    plan_url = (
        f"https://skyvector.com/api/fpl?cmd=route&route={quote(route_string)}&mnl=1"
    )
    response = session.get(plan_url, headers=headers)
    # print(quote(route_string))
    # webbrowser.open(response.url)
    route_dict = response.json()
    # print(route_dict.keys())
