import { JtsDocument } from "../../timeseries-ts/esm/index.js";
import { StatsTimeSeries } from "./stats_time_series.js";

export class StatsJtsDocument extends JtsDocument {
  constructor(props = {}) {
    super(props);
  }

  static parse(jts) {
    const columnSeries = {};

    for (const columnIndex in jts.header?.columns) {
      const column = jts.header?.columns[columnIndex];
      if (column === null || column === undefined) continue;

      const { id, name, units, dataType } = column;
      columnSeries[columnIndex] = new StatsTimeSeries({
        id,
        name,
        units,
        type: dataType || "NUMBER",
      });
    }

    (jts.data || []).forEach(function (record) {
      const timestamp = new Date(record.ts);
      if (Number.isNaN(timestamp.valueOf())) return;
      if (!Object.keys(record.f || {}).length) return;

      for (const columnIndex in record.f) {
        if (!columnSeries[columnIndex]) {
          columnSeries[columnIndex] = new StatsTimeSeries();
        }

        columnSeries[columnIndex].insert(
          buildTimeSeriesRecord({
            timestamp,
            dataColumn: record.f[columnIndex],
            type: columnSeries[columnIndex].type,
          })
        );
      }
    });

    return new StatsJtsDocument({
      series: Object.values(columnSeries),
    });
  }

  clone() {
    return new StatsJtsDocument({
      series: this.series.map(function (series) {
        return StatsTimeSeries.fromTimeSeries(series);
      }),
    });
  }
}

function buildTimeSeriesRecord({ timestamp, dataColumn, type }) {
  return {
    timestamp,
    value: parseDataColumnValue(dataColumn.v, type),
    quality: dataColumn.q,
    annotation: dataColumn.a,
  };
}

function parseDataColumnValue(value, type) {
  if (value === null || value === undefined) return value;

  switch (type) {
    case "NUMBER":
      return Number(value);
    case "TEXT":
      return String(value);
    case "TIME":
      return value?.$time ? new Date(value.$time) : null;
    case "COORDINATES":
      return value?.$coords ? value.$coords : null;
    default:
      return value;
  }
}
