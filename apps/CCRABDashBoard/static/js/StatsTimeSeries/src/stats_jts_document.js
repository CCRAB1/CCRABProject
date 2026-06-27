import { JtsDocument } from "../../../vendor/timeseries-ts/1.0.7/index.js";
import { StatsTimeSeries } from "./stats_time_series.js";

export class StatsJtsDocument extends JtsDocument {
  constructor(props = {}) {
    super(props);
    this._header = parseHeader(props.header);
  }

  get header() {
    return cloneHeader(this._header);
  }

  static parse(jts) {
    const header = parseHeader(jts.header);
    const columnSeries = {};

    for (const columnIndex in header.columns) {
      const column = header.columns[columnIndex];
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
      header,
      series: Object.values(columnSeries),
    });
  }

  clone() {
    return new StatsJtsDocument({
      header: this.header,
      series: this.series.map(function (series) {
        return StatsTimeSeries.fromTimeSeries(series);
      }),
    });
  }
}

function parseHeader(header = {}) {
  const rawColumns = header?.columns || {};
  const columns = {};

  for (const columnIndex in rawColumns) {
    const column = rawColumns[columnIndex];
    if (column === null || column === undefined) continue;

    columns[columnIndex] = {
      id: column.id,
      name: column.name,
      units: column.units,
      dataType: column.dataType || "NUMBER",
    };
  }

  return {
    startTime: parseDateOrNull(header?.startTime),
    endTime: parseDateOrNull(header?.endTime),
    recordCount: parseRecordCount(header?.recordCount),
    columns,
  };
}

function cloneHeader(header) {
  return {
    startTime: cloneDateOrNull(header.startTime),
    endTime: cloneDateOrNull(header.endTime),
    recordCount: header.recordCount,
    columns: cloneColumns(header.columns),
  };
}

function cloneColumns(columns) {
  const clone = {};

  for (const columnIndex in columns) {
    clone[columnIndex] = { ...columns[columnIndex] };
  }

  return clone;
}

function parseDateOrNull(value) {
  if (value === null || value === undefined || value === "") return null;
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : new Date(value.getTime());
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function cloneDateOrNull(date) {
  return date instanceof Date ? new Date(date.getTime()) : null;
}

function parseRecordCount(value) {
  const recordCount = Number(value);
  return Number.isFinite(recordCount) ? recordCount : 0;
}

function buildTimeSeriesRecord({ timestamp, dataColumn, type }) {
  const column = dataColumn || {};

  return {
    timestamp,
    value: parseDataColumnValue(column.v, type),
    quality: column.q,
    annotation: column.a,
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
