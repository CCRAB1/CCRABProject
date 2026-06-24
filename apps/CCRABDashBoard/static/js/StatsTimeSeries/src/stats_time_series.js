import { TimeSeries } from "../../timeseries-ts/esm/index.js";

export class StatsTimeSeries extends TimeSeries {
  constructor(props = {}) {
    super(props);
  }

  static fromTimeSeries(timeSeries) {
    return new StatsTimeSeries({
      id: timeSeries.id,
      name: timeSeries.name,
      units: timeSeries.units,
      type: timeSeries.type,
      records: timeSeries.records,
    });
  }
}
