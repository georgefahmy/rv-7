import email
import json
import os
import sys
from datetime import date, datetime, timedelta
from email import policy

import requests
from bs4 import BeautifulSoup


def find_best_100ll_options(airports_data):
    """
    Analyzes the parsed data to find the lowest 100LL price at each airport.
    Sorts the results by Lowest Price -> Closest Distance and prints the top options.
    """
    print("\n--- Top 5 Best 100LL Options ---")
    options = []

    for airport in airports_data:
        min_price = float("inf")
        found_price = False

        # 1. Safely extract distance (Origin airport will be None, treated as 0.0)
        dist_nm = airport.get("distance", {}).get("nm")
        if dist_nm is None:
            dist_nm = 0.0
        else:
            try:
                dist_nm = float(dist_nm)
            except ValueError:
                dist_nm = 999.0  # Fallback for unexpected text

        # 2. Dig through all FBOs to find the absolute lowest 100LL price
        for fbo in airport.get("fbos", []):
            prices_100ll = fbo.get("prices", {}).get("100LL", [])
            for p_entry in prices_100ll:
                raw_price = (
                    p_entry.get("price", "").replace("$", "").replace(",", "").strip()
                )
                try:
                    price_val = float(raw_price)
                    if price_val < min_price:
                        min_price = price_val
                        found_price = True
                except ValueError:
                    continue

        # 3. Log valid findings
        if found_price:
            options.append(
                {
                    "airport": airport["airport_code"],
                    "name": airport["airport_name"],
                    "distance": dist_nm,
                    "price": min_price,
                    "date": fbo["last_updated"],
                }
            )

    if not options:
        print("No 100LL fuel prices found in this dataset.")
        return

    # 4. Sort: Primary by Price (ascending), Secondary by Distance (ascending)
    options.sort(key=lambda x: (x["price"], x["distance"]))

    # 5. Print the top 5 options
    for i, opt in enumerate(options[:5], 1):
        dist_str = f"{opt['distance']} nm" if opt["distance"] > 0 else "Origin"
        print(
            f"{i}. {opt['airport']:<4} - ${opt['price']:.2f} ({dist_str} away) [{opt['date']}] | {opt['name']}"
        )
    print("----------------------------------\n")


def parse_airnav_html(html_content):
    """
    Indestructible node-based horizontal DOM traversal parser.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    airports_dict = {}

    # 1. DYNAMICALLY EXTRACT FUEL TYPES
    # AirNav nests fuel names inside a secondary <th> tag
    dynamic_fuel_types = []
    for top_th in soup.find_all("th"):
        inner_th = top_th.find("th")
        if inner_th and inner_th.text.strip():
            fuel_name = inner_th.text.strip()
            if fuel_name not in dynamic_fuel_types:
                dynamic_fuel_types.append(fuel_name)

    # Fallback just in case parsing fails entirely
    if not dynamic_fuel_types:
        dynamic_fuel_types = ["100LL", "G100UL", "UL94", "Jet A", "Mogas", "SAF"]

    print(f"[DEBUG] Detected Fuel Columns: {', '.join(dynamic_fuel_types)}")
    num_fuels = len(dynamic_fuel_types)

    # 2. FIND ALL FBO BRAND ANCHORS
    brand_tds = soup.find_all(
        lambda tag: tag.name == "td"
        and tag.get("align") == "center"
        and not tag.get("bgcolor")
        and not tag.has_attr("nowrap")
    )

    # 3. EXTRACT DATA RELATIVE TO EACH ANCHOR
    for brand_td in brand_tds:

        siblings = brand_td.find_next_siblings("td")
        if len(siblings) < num_fuels:
            continue

        # --- A. Get the Airport Code (Bulletproof anchor link traversal) ---
        # Search backward for an href matching exactly "/airport/XXXX" (count('/') == 2)
        airport_a = brand_td.find_previous(
            "a", href=lambda h: h and h.startswith("/airport/") and h.count("/") == 2
        )
        if not airport_a:
            continue

        airport_code = airport_a.text.strip()

        if airport_code not in airports_dict:
            header_td = airport_a.find_parent("td")
            name_td = header_td.find_next_sibling("td") if header_td else None
            if not name_td:
                name_td = header_td.find_next("td") if header_td else None

            airport_name = (
                " ".join(name_td.text.split()) if name_td else "Unknown Airport"
            )

            distance_magnitude = None
            distance_direction = None

            if header_td:
                distance_font = header_td.find("font", attrs={"size": "-1"})
                if distance_font:
                    raw_distance = distance_font.text.strip()
                    parts = raw_distance.split()

                    if len(parts) >= 2:
                        try:
                            distance_magnitude = (
                                float(parts[0]) if "." in parts[0] else int(parts[0])
                            )
                        except ValueError:
                            distance_magnitude = parts[0]
                        distance_direction = " ".join(parts[1:])

                    elif len(parts) == 1:
                        try:
                            distance_magnitude = (
                                float(parts[0]) if "." in parts[0] else int(parts[0])
                            )
                        except ValueError:
                            distance_magnitude = parts[0]

            airports_dict[airport_code] = {
                "airport_code": airport_code,
                "airport_name": airport_name,
                "distance": {"nm": distance_magnitude, "direction": distance_direction},
                "fbos": [],
            }

        # --- B. Get the FBO Name ---
        fbo_name = "Unknown FBO"
        for p_td in brand_td.find_all_previous("td", limit=15):
            if p_td.has_attr("colspan"):
                continue

            # Look for explicit FBO link (count('/') == 3)
            fbo_a = p_td.find(
                "a",
                href=lambda h: h
                and h.startswith("/airport/")
                and h.count("/") == 3
                and "update-fuel" not in h,
            )
            if fbo_a:
                fbo_name = fbo_a.text.strip() or (
                    fbo_a.find("img").get("alt", "").strip()
                    if fbo_a.find("img")
                    else ""
                )
                break

            text = p_td.text.strip().replace("\xa0", "")
            if text and text != "Airport / FBO" and len(text) > 2:
                fbo_name = " ".join(text.split())
                break

        fbo_name = fbo_name.strip() if fbo_name else "Unknown FBO"

        # --- C. Get the Last Updated Date ---
        last_updated = None
        is_guaranteed = False

        for sib in siblings[num_fuels:]:
            if "GUARANTEED" in sib.text:
                is_guaranteed = True
                break

            date_font = sib.find("font", attrs={"size": "-2"})
            if date_font:
                last_updated = date_font.text.strip()
                break

        if is_guaranteed:
            last_updated = date.today().strftime("%d-%b")

        # --- D. Get the Fuel Prices ---
        fbo_data = {"fbo_name": fbo_name, "last_updated": last_updated, "prices": {}}

        curr_td = brand_td
        for fuel_type in dynamic_fuel_types:
            curr_td = curr_td.find_next_sibling("td")
            if not curr_td:
                break

            price_table = curr_td.find("table")
            if price_table:
                prices = []
                for p_row in price_table.find_all("tr"):
                    parts = [
                        p.text.strip() for p in p_row.find_all("td") if p.text.strip()
                    ]
                    if len(parts) >= 2:
                        service_type = parts[0]
                        raw_price = " ".join(parts[1].split())
                        prices.append({"service": service_type, "price": raw_price})

                if prices:
                    fbo_data["prices"][fuel_type] = prices

        if fbo_data["prices"]:
            airports_dict[airport_code]["fbos"].append(fbo_data)

    # Flatten and return
    final_data = list(airports_dict.values())
    found_airports = [data["airport_code"] for data in final_data]
    print(
        f"[DEBUG] Successfully mapped {len(found_airports)} airports: {', '.join(found_airports)}"
    )

    return final_data


def extract_html_from_file(filepath):
    if filepath.lower().endswith((".mhtml", ".mht")):
        with open(filepath, "rb") as f:
            msg = email.message_from_binary_file(f, policy=policy.default)
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    return part.get_content()
        return None
    else:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()


def process_local_file(filepath):
    try:
        print(f"Reading local file '{filepath}'...")
        html_content = extract_html_from_file(filepath)

        if not html_content:
            print("Error: Could not extract HTML content from the file.")
            return

        parsed_data = parse_airnav_html(html_content)

        if not parsed_data:
            print("Warning: Could not locate fuel data in the provided file.")
            return

        output_folder = "fuel_prices"
        os.makedirs(output_folder, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(filepath))[0]
        filename = os.path.join(output_folder, f"{base_name}_parsed.json")

        with open(filename, "w", encoding="utf-8") as json_file:
            json.dump(parsed_data, json_file, indent=4, ensure_ascii=False)

        print(f"Success! Local file parsed and saved to: {filename}")

        find_best_100ll_options(parsed_data)

    except FileNotFoundError:
        print(f"File not found: {filepath}")
    except Exception as e:
        print(f"An error occurred reading the file: {e}")


def check_exists(airport_code):
    output_folder = "fuel_prices"
    os.makedirs(output_folder, exist_ok=True)
    filename = os.path.join(output_folder, f"{airport_code.lower()}_fuel_prices.json")

    return os.path.isfile(filename), filename


def scrape_airnav_to_json(input_query):

    airport_code = input_query.upper()
    exists, filename = check_exists(airport_code)
    if exists:
        last_updated = datetime.fromtimestamp(os.path.getmtime(filename))
        print(f"Data last updated: {last_updated}")
        if (datetime.now() - last_updated) < timedelta(days=7):
            with open(filename, "r") as fp:
                parsed_data = json.load(fp)
                find_best_100ll_options(parsed_data)
            return
        else:
            print("Outdated information - fetching new data...")

    target_url = f"https://www.airnav.com/fuel/local.html?s={airport_code}&submit=true"

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )

    print(f"Fetching data from: {target_url}")

    try:
        response = session.get(target_url)
        response.raise_for_status()

        parsed_data = parse_airnav_html(response.text)

        if not parsed_data:
            print(f"Warning: Could not locate fuel data for '{airport_code}'.")
            return

        output_folder = "fuel_prices"
        os.makedirs(output_folder, exist_ok=True)
        filename = os.path.join(
            output_folder, f"{airport_code.lower()}_fuel_prices.json"
        )

        with open(filename, "w", encoding="utf-8") as json_file:
            json.dump(parsed_data, json_file, indent=4, ensure_ascii=False)

        print(f"Success! Data parsed and saved to: {filename}")

        find_best_100ll_options(parsed_data)

    except requests.exceptions.RequestException as e:
        print(f"Network error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during parsing: {e}")


if __name__ == "__main__":
    choice = input("Enter an airport code (e.g., KLAX): ").strip()

    if choice.upper() == "FILE":
        file_path = input(
            "Enter the full file name (e.g., AirNav_Fuel.mhtml): "
        ).strip()
        process_local_file(file_path)
    elif choice:
        scrape_airnav_to_json(choice)
    else:
        print("No input entered. Exiting.")
        sys.exit(1)
