import json
import re
from pprint import pprint

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.airnav.com/cgi-bin/"
session = requests.Session()

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}
plan_url = BASE_URL + "fuelplan"
origin = input("Origin Airport: ")
print(origin)
destination = input("Destination (US) Airport: ")
payload = {
    "origin": origin.upper(),  # Replace 'origin' with the actual input name
    "destination": destination.upper(),  # Replace 'destination' with the actual input name
    "aptsel": "a-u-0----1-A",
    "method": "cheap",
    "range": "400",
    "rangeunits": "nm",
    "speed": "160",
    "speedunits": "kt",
    "fuelburn": "10",
    "cheapstrategy": "safe",
    "nroutes": "10",
}

response = session.post(plan_url, data=payload, headers=headers)
soup = BeautifulSoup(response.text, "html.parser")
pre_text = soup.find("pre").decode_contents()
pattern = re.compile(
    r'<a href="([^"]+)">([^<]+)</a>\s+(\d+(?:\s+\[[+-]?\d+%\])?)\s+(.*?)\s+([ -][\d.]+)'
)
parsed_routes = []

# 3. Process line by line
for line in pre_text.split("\n"):
    # Skip empty lines, headers, or the divider line
    if not line.strip() or "ROUTE" in line or "---" in line:
        continue

    match = pattern.search(line)
    if match:
        route_data = {
            "url": BASE_URL + match.group(1),
            "route": match.group(2),
            "distance": match.group(3).strip(),
            "longest_leg": match.group(4).strip(),
            "savings": float(match.group(5)),
        }
        parsed_routes.append(route_data)
pprint(parsed_routes)
selected_route = input("Which route? ")


route_data = BeautifulSoup(
    requests.get(parsed_routes[int(selected_route)]["url"]).text, "html.parser"
)

rows = route_data.center.table.find_all("tr")[1:]

route_data = []

# Process rows in pairs (step=2)
for i in range(0, len(rows), 2):
    airport_tds = rows[i].find_all("td")

    # Safety check
    if not airport_tds or len(airport_tds) < 2:
        continue

    # --- NEW: Extract the URL from the <a> tag ---
    a_tag = airport_tds[0].find("a")
    # If the tag exists, grab the href and prepend the domain
    airport_url = (
        f"https://www.airnav.com{a_tag['href']}"
        if a_tag and a_tag.has_attr("href")
        else None
    )

    # 1. Extract Airport Code and Price
    # Using separator='|' turns "LWL<br>$6.2" into "LWL|$6.2"
    code_price_raw = airport_tds[0].get_text(separator="|", strip=True).split("|")
    airport_code = code_price_raw[0] if len(code_price_raw) > 0 else None
    price = code_price_raw[1] if len(code_price_raw) > 1 else None

    # 2. Extract Location and Name
    loc_name_raw = airport_tds[1].get_text(separator="|", strip=True).split("|")
    location = loc_name_raw[0] if len(loc_name_raw) > 0 else None
    airport_name = loc_name_raw[1] if len(loc_name_raw) > 1 else None

    # 3. Extract Leg Data (Distance & Heading) from the subsequent row
    distance = None
    heading = None

    # Check if the next row exists (avoids index errors on the last row)
    if i + 1 < len(rows):
        leg_tds = rows[i + 1].find_all("td")
        # If length is 2, it contains distance/heading.
        # If length is 1, it's the final empty <td colspan="2">
        if len(leg_tds) == 2:
            distance = leg_tds[0].get_text(strip=True)
            # Replaces the <br> between "true" and "magnetic" with a space
            heading = leg_tds[1].get_text(separator=" ", strip=True)

    # Append to our list
    route_data.append(
        {
            "airport_code": airport_code,
            "airport_url": airport_url,
            "price": price,
            "location": location,
            "airport_name": airport_name,
            "distance_to_next": distance,
            "heading_to_next": heading,
        }
    )

# Print the parsed dictionary cleanly
print(json.dumps(route_data, indent=2))

route_string = "-".join(f"{val['airport_code']}" for val in route_data)
print(route_string)
