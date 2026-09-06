def apply_epa_correction(pm25_cf1_a, humidity_a, pm25_cf1_b, humidity_b):
    """
    Applies EPA correction to PM2.5 concentration values.

    The function adjusts raw PM2.5 sensor readings using the U.S. Environmental
    Protection Agency (EPA) correction factors. It corrects the values based on
    the PM2.5 concentration and humidity. Different equations and weighting
    factors are applied depending on the PM2.5 concentration range.

    Parameters:
    pm25_cf1_a : float
        PM2.5 concentration value from sensor (raw value).
    humidity_a : float
        Current relative humidity in percentage.
    pm25_cf1_b : float
        PM2.5 concentration value from sensor (raw value), optional if there are 2 channels.
    humidity_b : float
        Current relative humidity in percentage.

    Returns:
    float
        Corrected PM2.5 concentration value.
    """
    pm25_cf1 = pm25_cf1_a
    if pm25_cf1_b is not None:
        pm25_cf1 = (pm25_cf1_a + pm25_cf1_b) / 2
    humidity = humidity_a
    if humidity_b is not None:
        humidity = (humidity_a + humidity_b) / 2
    if pm25_cf1 < 570:
        return (0.524 * pm25_cf1) - (0.0862 * humidity) + 5.75
    elif 570 <= pm25_cf1 < 611:
        eq1 = (0.524 * pm25_cf1) - (0.0862 * humidity) + 5.75
        eq3 = (4.21e-4 * (pm25_cf1 ** 2)) + (0.392 * pm25_cf1) + 3.44
        weight = (0.0244 * pm25_cf1) - 13.9
        return (weight * eq3) + ((1 - weight) * eq1)
    else:
        return (4.21e-4 * (pm25_cf1 ** 2)) + (0.392 * pm25_cf1) + 3.44


# Official US EPA PM2.5 AQI breakpoints (Updated May 2024 standards)
# Table format: (Min PM2.5, Max PM2.5, Min AQI, Max AQI)
PM25_BREAKPOINTS = [
    {"bp_low": 0.0, "bp_high": 9.0, "aqi_low": 0, "aqi_high": 50},  # Good
    {"bp_low": 9.1, "bp_high": 35.4, "aqi_low": 51, "aqi_high": 100},  # Moderate
    {"bp_low": 35.5, "bp_high": 55.4, "aqi_low": 101, "aqi_high": 150},  # USG
    {"bp_low": 55.5, "bp_high": 125.4, "aqi_low": 151, "aqi_high": 200},  # Unhealthy
    {"bp_low": 125.5, "bp_high": 225.4, "aqi_low": 201, "aqi_high": 300},  # Very Unhealthy
    {"bp_low": 225.5, "bp_high": 325.4, "aqi_low": 301, "aqi_high": 400},  # Hazardous
    {"bp_low": 325.5, "bp_high": 500.4, "aqi_low": 401, "aqi_high": 500}  # Hazardous
]


def calculate_aqi(pm25):
    """Calculates the US EPA PM2.5 AQI using a lookup table."""
    try:
        # Step 1: Ensure input is a float and truncate to 1 decimal place
        pm25 = int(float(pm25) * 10) / 10.0
    except (ValueError, TypeError):
        return None

    if pm25 < 0:
        return None

    # Step 2: Loop through the table to find the matching category
    for row in PM25_BREAKPOINTS:
        if row["bp_low"] <= pm25 <= row["bp_high"]:
            # Step 3: Apply the linear interpolation formula
            aqi = ((row["aqi_high"] - row["aqi_low"]) / (row["bp_high"] - row["bp_low"])) * (pm25 - row["bp_low"]) + \
                  row["aqi_low"]
            return round(aqi)

    # Return 501+ for concentrations beyond the official index scale
    if pm25 > 500.4:
        return round(pm25)

    return None
