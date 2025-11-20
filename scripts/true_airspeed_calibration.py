from math import atan2, cos, pi, sin, sqrt

from dotmap import DotMap

data = DotMap(v1=0, trk1=0, v2=0, trk2=0, v3=0, trk3=0)

data.v1, data.trk1 = (
    int(x)
    for x in input(
        "Enter First leg gps speed and heading (gps_speed, heading): "
    ).split(", ")
)

data.v2, data.trk2 = (
    int(x)
    for x in input(
        "Enter Second leg gps speed and heading (gps_speed, heading): "
    ).split(", ")
)

data.v3, data.trk3 = (
    int(x)
    for x in input(
        "Enter Third leg gps speed and heading (gps_speed, heading): "
    ).split(", ")
)

data.pprint(pformat="json")

calcs1 = DotMap(
    x1=data.v1 * sin(pi * (360 - data.trk1) / 180),
    y1=data.v1 * cos(pi * (360 - data.trk1) / 180),
    x2=data.v2 * sin(pi * (360 - data.trk2) / 180),
    y2=data.v2 * cos(pi * (360 - data.trk2) / 180),
    x3=data.v3 * sin(pi * (360 - data.trk3) / 180),
    y3=data.v3 * cos(pi * (360 - data.trk3) / 180),
)
calcs2 = DotMap(
    m1=-1 * (calcs1.x2 - calcs1.x1) / (calcs1.y2 - calcs1.y1),
    m2=-1 * (calcs1.x3 - calcs1.x1) / (calcs1.y3 - calcs1.y1),
)

calcs3 = DotMap(
    b1=(calcs1.y1 + calcs1.y2) / 2 - calcs2.m1 * (calcs1.x1 + calcs1.x2) / 2,
    b2=(calcs1.y1 + calcs1.y3) / 2 - calcs2.m2 * (calcs1.x1 + calcs1.x3) / 2,
)

wx = (calcs3.b1 - calcs3.b2) / (calcs2.m2 - calcs2.m1)
wy = calcs2.m1 * wx + calcs3.b1

outputs = DotMap(
    v_wind=round(sqrt(wx**2 + wy**2), 1),
    wind_dir=round((540 - (180 / pi * atan2(wy, wx))) % 360, 0),
    v_true=round(sqrt((calcs1.x1 - wx) ** 2 + (calcs1.y1 - wy) ** 2), 1),
)


outputs.pprint(pformat="json")
