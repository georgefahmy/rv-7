# --- Maintenance Interval Configuration ---
OIL_CHANGE_INTERVAL_HOURS = 50
CONDITION_INSPECTION_INTERVAL_MONTHS = 12
ELT_TEST_INTERVAL_DAYS = 90
TRANSPONDER_CHECK_MONTHS = 24

# --- FAA Aviation/Obstacle DB Intervals ---
OAS_AVIATION_DB_INTERVAL_DAYS = 28  # example 28-day FAA cycle
OAS_OBSTACLE_DB_INTERVAL_DAYS = 56


# --- Colors ---
DEFAULT_COLOR = "black"
OVERDUE_COLOR = "red"
WARNING_COLOR = "orange"
CURRENT_COLOR = "green"

RECURRENT_ITEMS = [
    "Condition Inspection",
    "Oil Change",
    "ELT Test",
    "ELT Batteries",
    "ELT Registration",
    "Nav Data Update",
    "Batteries",
    "Transponder Check",
]

MX_CATEGORIES = ["Airframe", "Engine", "Propeller", "Avionics"]
