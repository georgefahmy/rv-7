import math

import airportsdata

lid = airportsdata.load("LID")


def to_rad(value):
    return (value * math.pi) / 180


def calculate_distance(ap1: str, ap2: str):
    airport1 = lid[ap1]
    airport2 = lid[ap2]
    if not airport1 or not airport2:
        return None
    try:
        R = 6371  # Radius of the Earth in kilometers
        lat1 = float(airport1["lat"])
        lon1 = float(airport1["lon"])
        lat2 = float(airport2["lat"])
        lon2 = float(airport2["lon"])
        d_lat = to_rad(lat2 - lat1)
        d_lon = to_rad(lon2 - lon1)
        a = math.sin(d_lat / 2) * math.sin(d_lat / 2) + math.cos(
            to_rad(lat1)
        ) * math.cos(to_rad(lat2)) * math.sin(d_lon / 2) * math.sin(d_lon / 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c / 1.852  # nautical miles
    except (ValueError, TypeError, KeyError):
        return None
