import numpy as np
import pandas as pd
from scipy.optimize import minimize


def calculate_density_ratio(pressure_alt_ft, oat_c):
    """Calculates the density ratio (sigma) based on standard atmosphere physics."""
    # Standard pressure ratio (delta)
    delta = (1 - 6.87559e-6 * pressure_alt_ft) ** 5.25588
    # Absolute temperature ratio (theta)
    t_abs = oat_c + 273.15
    t0_abs = 288.15
    theta = t_abs / t0_abs
    # Density ratio (sigma)
    sigma = delta / theta
    return sigma


def wind_triangle_residuals(params, df):
    """
    Objective function to minimize.
    params: [cas_correction, hdg_correction, wind_speed, wind_dir]
    """
    cas_corr, hdg_corr, w_spd, w_dir = params

    # Calculate CAS and TAS
    cas = df["ias"] + cas_corr
    tas = cas / np.sqrt(df["sigma"])

    # Calculate True Heading (in radians)
    true_hdg_rad = np.radians(df["hdg"] + hdg_corr)

    # Aircraft velocity vector components (relative to airmass)
    v_ax = tas * np.sin(true_hdg_rad)
    v_ay = tas * np.cos(true_hdg_rad)

    # Wind vector components (Meteorological convention: from direction W_dir)
    w_dir_rad = np.radians(w_dir)
    v_wx = -w_spd * np.sin(w_dir_rad)
    v_wy = -w_spd * np.cos(w_dir_rad)

    # Expected Ground velocity components
    v_gx_expected = v_ax + v_wx
    v_gy_expected = v_ay + v_wy

    # Measured GPS Ground velocity components
    trk_rad = np.radians(df["gps_trk"])
    v_gx_meas = df["gps_gs"] * np.sin(trk_rad)
    v_gy_meas = df["gps_gs"] * np.cos(trk_rad)

    # Calculate sum of squared errors
    error_x = v_gx_expected - v_gx_meas
    error_y = v_gy_expected - v_gy_meas

    return np.sum(error_x**2 + error_y**2)


def analyze_flight_data(df):
    """
    Processes the time-series dataframe and outputs the calibration parameters.
    Expected DataFrame columns:
    'ias' (knots), 'ialt' (feet), 'hdg' (degrees), 'gps_gs' (knots),
    'gps_trk' (degrees), 'oat' (Celsius), 'baro' (inHg)
    """
    # 1. Calculate Pressure Altitude and Density Ratio
    df["press_alt"] = df["ialt"] + (29.92 - df["baro"]) * 1000
    df["sigma"] = calculate_density_ratio(df["press_alt"], df["oat"])

    # 2. Initial guesses for the optimizer
    # [cas_correction (kts), hdg_correction (deg), wind_speed (kts), wind_dir (deg)]
    initial_guess = [0.0, 0.0, 10.0, 180.0]

    # Bounds to keep the optimizer in realistic ranges
    bounds = (
        (-20, 20),  # CAS correction +/- 20 kts
        (-15, 15),  # HDG correction +/- 15 deg
        (0, 150),  # Wind speed 0 to 150 kts
        (0, 360),  # Wind direction 0 to 360 deg
    )

    # 3. Run Optimization
    result = minimize(
        wind_triangle_residuals,
        initial_guess,
        args=(df,),
        bounds=bounds,
        method="L-BFGS-B",
    )

    if not result.success:
        print("Optimization failed:", result.message)
        return None

    cas_corr, hdg_corr, w_spd, w_dir = result.x

    # 4. Generate Output Data
    # Wrap wind direction to 0-360
    w_dir = w_dir % 360

    # Calculate the time-series arrays for the outputs
    cas = df["ias"] + cas_corr
    tas_array = cas / np.sqrt(df["sigma"])
    calibrated_hdg_array = (df["hdg"] + hdg_corr) % 360

    # Package the results
    results = {
        "calibrated_airspeed_correction_kts": round(cas_corr, 2),
        "calibrated_heading_correction_deg": round(hdg_corr, 2),
        "airspeed_error_kts": round(
            -cas_corr, 2
        ),  # If CAS = IAS + Corr, Error is usually IAS - CAS
        "wind_direction_deg": round(w_dir, 1),
        "wind_speed_kts": round(w_spd, 1),
        "average_true_airspeed_kts": round(np.mean(tas_array), 2),
        # You can also return the full time-series arrays if needed
        "ts_true_airspeed": tas_array.values,
        "ts_calibrated_heading": calibrated_hdg_array.values,
    }

    return results


# ==========================================
# Example Usage
# ==========================================
if __name__ == "__main__":
    # Mock data generation (replace this with loading your actual CSV/data)
    # Assuming the aircraft is flying a 4-leg box pattern
    np.random.seed(42)
    n_points = 100

    mock_data = pd.DataFrame(
        {
            "ias": np.random.normal(100, 1, n_points),
            "ialt": np.random.normal(5000, 20, n_points),
            "hdg": np.linspace(0, 360, n_points),  # Turning through a circle/box
            "gps_gs": np.random.normal(105, 5, n_points),
            "gps_trk": np.linspace(0, 360, n_points) + np.random.normal(0, 2, n_points),
            "oat": np.full(n_points, 5.0),
            "baro": np.full(n_points, 29.92),
        }
    )

    output = analyze_flight_data(mock_data)

    print("--- Calibration Results ---")
    print(f"CAS Correction: {output['calibrated_airspeed_correction_kts']} kts")
    print(f"Airspeed Error: {output['airspeed_error_kts']} kts")
    print(f"HDG Correction: {output['calibrated_heading_correction_deg']} deg")
    print(f"Wind Direction: {output['wind_direction_deg']} deg")
    print(f"Wind Speed:     {output['wind_speed_kts']} kts")
    print(f"Average TAS:    {output['average_true_airspeed_kts']} kts")
