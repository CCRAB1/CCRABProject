function CalculateAqiPM25EPA(pm25_1, pm25_2, humidity)
{
    /*
    1. Apply the USNowCast Correction FormulaFor standard outdoor environments,
    the US EPA recommends the following correction formula to adjust raw PurpleAir
    \(PM_{2.5}\) data (μ g/m³):\(\text{Corrected\ }PM_{2.5}=(0.524\times \text{Raw\ }PM_{2.5})-(0.0862\times \text{Humidity})+5.75\)Raw \(PM_{2.5}\):
    The average of Channel A and Channel B \(PM_{2.5}\) fields (cf=1).Humidity:
    The relative humidity percentage recorded by the sensor.
    */
    //Corrected 𝑃𝑀2.5=(0.524×Raw 𝑃𝑀2.5)−(0.0862×Humidity)+5.75
    var avg_pm25 = (pm25_1 + pm25_2) / 2;
    var corrected_pm25 = (0.524 * avg_pm25) - (0.0862 * humidity) + 5.75;
    return corrected_pm25;
}

/**
 * Determines the official US EPA PM2.5 breakpoint range and its associated color code.
 *
 * @param {number} pm25 - The corrected PM2.5 concentration value (µg/m³).
 * @returns {Object|null} The breakpoint range parameters, or null if out of bounds.
 */
function getEPABreakpoint(pm25) {
  // Round to 1 decimal place to align with official EPA breakpoint precision
  const roundedPm = Math.round(pm25 * 10) / 10;

  const breakpoints = [
    { cLow: 0.0,   cHigh: 9.0,   iLow: 0,   iHigh: 50,  category: "Good",                           color: "#00E400" },
    { cLow: 9.1,   cHigh: 35.4,  iLow: 51,  iHigh: 100, category: "Moderate",                       color: "#FFFF00" },
    { cLow: 35.5,  cHigh: 55.4,  iLow: 101, iHigh: 150, category: "Unhealthy for Sensitive Groups", color: "#FF7E00" },
    { cLow: 55.5,  cHigh: 125.4, iLow: 151, iHigh: 200, category: "Unhealthy",                      color: "#FF0000" },
    { cLow: 125.5, cHigh: 225.4, iLow: 201, iHigh: 300, category: "Very Unhealthy",                 color: "#8F3F97" },
    { cLow: 225.5, cHigh: 325.4, iLow: 301, iHigh: 400, category: "Hazardous",                      color: "#7E0023" },
    { cLow: 325.5, cHigh: 500.4, iLow: 401, iHigh: 500, category: "Hazardous",                      color: "#7E0023" }
  ];

  // Find the matching range where the concentration falls between cLow and cHigh
  const range = breakpoints.find(b => roundedPm >= b.cLow && roundedPm <= b.cHigh);

  return range || null;
}
