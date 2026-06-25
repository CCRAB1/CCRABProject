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
    /**
    * Returns the most recent record.
    *
    * @returns {{}} An object that the most recent in the series.
    */
  getLatestRecord() {
    var value = this._records[-1];
    return value;
  }
    /**
    * Calculates statistics on the current series.
    *
    * @returns {{}} An object that containts the min, max and most recent values.
    */
    getStats() {
    const stats = {
      min: null,
      max: null,
      most_recent: null,
    };
    this._records.reduce(function(acc, record)
    {
      var value = record.value;

      if(acc.min === null || value < acc.min.value) {
        acc.min = record;
      }
      if(acc.max === null || value > acc.max.value) {
        acc.max = record;
      }
      if(acc.most_recent === null ||
          record.timestamp.getTime() > acc.most_recent.timestamp.getTime()) {
        acc.most_recent = record;
      }
      return acc;
    }, stats);

    return stats;
  }
}
