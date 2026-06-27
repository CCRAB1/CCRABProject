import { TimeSeries } from "../../../vendor/timeseries-ts/1.0.7/index.js";


export class StatsTimeSeries extends TimeSeries {
  constructor(props = {}) {
    super(props);
    this.min_record = null;
    this.max_record = null;
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

  insert(recordOrRecords, value, attributes = {}) {
    if (arguments.length > 1) {
      return super.insert(this.normalizeRecords({
        ...attributes,
        timestamp: recordOrRecords,
        value,
      }));
    }

    return super.insert(this.normalizeRecords(recordOrRecords));
  }

    /**
    * Returns the most recent record.
    *
    * @returns {{}} An object that the most recent date/time in the series.
    */
  getLatestRecord() {
    var value = null;
    if(this._records.length) {
      value = this._records[this._records.length-1];
    }

    return value;
  }
    /**
    * Returns the most recent record.
    *
    * @returns {{}} An object that the most oldest date/time in the series.
    */
  getOldestRecord() {
    var value = null;
    if(this._records.length) {
      value = this._records[0];
    }
    return value;

  }
    /**
    * Calculates statistics on the current series.
    *
    * @returns {{}} An object that contains the min, max and most recent values.
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
  normalizeRecords(recordOrRecords) {
    if (Array.isArray(recordOrRecords)) {
      return recordOrRecords.map((record) => {
        return this.normalizeRecord(record);
      });
    }

    return this.normalizeRecord(recordOrRecords);
  }

  normalizeRecord(record) {
    if (record === null || typeof record !== "object") {
      throw new TypeError("StatsTimeSeries.insert requires a record object or array of record objects.");
    }
    var normalized_rec = {
      ...record,
      timestamp: this.normalizeTimestamp(record.timestamp),
    };
    if(this.min_record == null || normalized_rec.value < this.min_record.value) {
      this.min_record = normalized_rec;
    }
    if(this.max_record == null || normalized_rec.value > this.max_record.value) {
      this.max_record = normalized_rec;
    }

    return normalized_rec;
  }

  normalizeTimestamp(timestamp) {
    if (timestamp instanceof Date) {
      if (Number.isNaN(timestamp.getTime())) {
        throw new RangeError("StatsTimeSeries.insert received an invalid Date timestamp.");
      }

      return new Date(timestamp.getTime());
    }

    if (timestamp && typeof timestamp.toJSDate === "function") {
      return normalizeTimestamp(timestamp.toJSDate());
    }

    const parsed = new Date(timestamp);
    if (Number.isNaN(parsed.getTime())) {
      throw new RangeError("StatsTimeSeries.insert requires a valid timestamp.");
    }

    return parsed;
  }

}

/*
function normalizeRecords(recordOrRecords) {
  if (Array.isArray(recordOrRecords)) {
    return recordOrRecords.map(function (record) {
      return normalizeRecord(record);
    });
  }

  return normalizeRecord(recordOrRecords);
}

function normalizeRecord(record) {
  if (record === null || typeof record !== "object") {
    throw new TypeError("StatsTimeSeries.insert requires a record object or array of record objects.");
  }

  return {
    ...record,
    timestamp: normalizeTimestamp(record.timestamp),
  };
}

function normalizeTimestamp(timestamp) {
  if (timestamp instanceof Date) {
    if (Number.isNaN(timestamp.getTime())) {
      throw new RangeError("StatsTimeSeries.insert received an invalid Date timestamp.");
    }

    return new Date(timestamp.getTime());
  }

  if (timestamp && typeof timestamp.toJSDate === "function") {
    return normalizeTimestamp(timestamp.toJSDate());
  }

  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) {
    throw new RangeError("StatsTimeSeries.insert requires a valid timestamp.");
  }

  return parsed;
}
*/
