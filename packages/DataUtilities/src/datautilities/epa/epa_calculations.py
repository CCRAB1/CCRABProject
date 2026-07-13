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