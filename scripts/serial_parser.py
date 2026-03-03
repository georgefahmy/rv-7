import socket

adahrs_example = (
    "!1121144703-014+00003310811+01736+003-03+1013-033+110831245+01650023176C"
)
system_example = "!2221144704359XXXXX1600+010XXX00XXXXXXXX00X0X+00-99990+00+99990+00XXXXX00104543XXXXXXXXXX3A"

ADAHRS_PARSER = [  # position, width description
    (1, 1, "start"),
    (2, 1, "data_type"),
    (3, 1, "data_version"),
    (4, 8, "system_time"),
    (12, 4, "pitch_deg"),
    (16, 5, "roll_deg"),
    (21, 3, "magnetic_heading_deg"),
    (24, 4, "indicated_airspeed_knots"),
    (28, 6, "pressure_altitude_ft"),
    (34, 4, "turn_rate_deg_s"),
    (38, 3, "lateral_accel_g"),
    (41, 3, "vertical_accel_g"),
    (44, 2, "angle_of_attack_%"),
    (46, 4, "vertical_speed_ft_min"),
    (50, 3, "outside_air_temp_c"),
    (53, 4, "true_airspeed_knots"),
    (57, 3, "baro_setting_in_hg"),
    (60, 6, "density_altitude_ft"),
    (66, 3, "wind_direction_deg"),
    (69, 2, "wind_speed_knots"),
    (71, 2, "checksum"),
    (73, 2, "cr_lf"),
]

SYSTEM_PARSER = [
    (1, 1, "Start"),
    (2, 1, "data_type"),
    (3, 1, "data_version"),
    (2, 8, "system_time"),
    (12, 3, "heading_bug_deg"),
    (13, 5, "altitude_bug_ft"),
    (20, 4, "airspeed_bug_knots"),
    (24, 4, "verticla_speed_bug_ft_min"),
    (28, 3, "course"),
    (31, 1, "cdi_source_type"),
    (32, 1, "cdi_source_port"),
    (33, 2, "cdi_scale_nm"),
    (35, 3, "cdi_defelction_%"),
    (38, 3, "glideslope_%"),
    (41, 1, "ap_engaged"),
    (42, 1, "ap_roll_mode"),
    (43, 1, "unused"),
    (44, 1, "ap_pitch_mode"),
    (45, 1, "unused"),
    (46, 3, "ap_roll_force"),
    (49, 5, "ap_roll_position_steps"),
    (54, 1, "ap_roll_slip_bool"),
    (55, 3, "ap_pitch_force"),
    (58, 5, "ap_pitch_position_steps"),
    (63, 1, "ap_pitch_slip_bool"),
    (64, 3, "ap_yaw_force"),
    (67, 5, "ap_yaw_position"),
    (72, 1, "ap_yaw_slip_bool"),
    (73, 1, "transponder_status"),
    (74, 1, "transponder_reply_bool"),
    (75, 1, "transponder_identing_bool"),
    (76, 4, "transponder_code_octal"),
    (80, 10, "unused"),
    (90, 2, "checksum"),
    (92, 2, "cr_lf"),
]

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# s.connect(("ip address", 49155))


def parse_serial_stream(data_stream, parser_config):
    """
    Parses a fixed-width serial data stream based on a provided configuration.
    """
    parsed_data = {}
    for pos, width, description in parser_config:
        # Convert 1-based position to Python's 0-based index
        start_idx = pos - 1
        end_idx = start_idx + width
        # Extract the data slice
        # (Python handles out-of-bounds slicing gracefully if the string is short)
        extracted_value = data_stream[start_idx:end_idx]
        parsed_data[description] = extracted_value
    return parsed_data


parsed_data = parse_serial_stream(system_example, SYSTEM_PARSER)

print("Parsed Serial Data:")
print("-" * 45)
for key, value in parsed_data.items():
    # Displaying the extracted value in quotes to show exact extraction
    print(f"{key:<30}: '{value}'")
