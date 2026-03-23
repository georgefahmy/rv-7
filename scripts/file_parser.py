import re


def parse_dynon_filename(filename):
    """
    Parse Dynon log filename into components.

    Example:
    2026-03-11-N890GF-SN35347-17.4.0.23677-USER_LOG_DATA.csv
    """

    pattern = re.compile(
        r"(?P<date>\d{4}-\d{2}-\d{2})-"
        r"(?P<tail_number>N\d+[A-Z]*)-"
        r"(?P<serial_number>SN\d+)-"
        r"(?P<firmware>[\d\.]+)"
        r"(?:-(?P<user_value>[A-Z0-9_]+))?-"
        r"(?P<log_type>.+)\.csv"
    )

    match = pattern.match(filename)

    if not match:
        raise ValueError(f"Filename format not recognized: {filename}")

    return match.groupdict()


# Example usage
if __name__ == "__main__":
    filename = "2026-02-21-N890GF-SN35347-17.4.0.23677-REAL_FLITE-USER_LOG_DATA.csv"
    parsed = parse_dynon_filename(filename)

    for key, value in parsed.items():
        print(f"{key}: {value}")
