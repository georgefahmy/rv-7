from math import asin, pi

airspeed = float(input("Enter airspeed in KIAS: "))
vs_fpm = float(input("Enter vertical speed in fpm: "))
airspeed_fpm = airspeed * 1.15 * 88  # convert to mph and then feet per minute
rad2deg = 180 / pi

angle = asin(vs_fpm / airspeed_fpm) * rad2deg

print(round(angle, 2))
