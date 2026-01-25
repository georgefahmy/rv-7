import sqlite3
import webbrowser
from pathlib import Path

home_path = str(Path.home())
base_path = f"{home_path}/Desktop/RV-7/Airmate/AirmateData/ChartData/Plates/"
db_path = base_path + "Plates.sqlite"
file_path = base_path + "US/"

airport = input("Enter Airport ICAO Code: ")
chart_name = input(
    "Enter Chart Type to Lookup (APD, AFD, MIN, IAC, STAR, DPO, DP, TEXT): "
)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

query = f"SELECT Chart_Name, Chart_Code, File_Name FROM Charts WHERE Airport_Name_ID = (SELECT Airport_Name_ID from Airports WHERE ICAO_Ident = '{airport.upper()}')"

if chart_name:
    query = f"{query} AND Chart_Code = '{chart_name.upper()}'"

files = cur.execute(query).fetchall()

if not files:
    print("Empty Query - Try Again")

for row in files:
    name, code, filename = row
    print(f"{name} - ({code}): {filename}")
    full_file = file_path + filename
    webbrowser.open_new_tab("file://" + full_file)
