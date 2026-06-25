import assert from "node:assert/strict";
import test from "node:test";

import { JtsDocument, TimeSeries } from "../../timeseries-ts/esm/index.js";
import { StatsJtsDocument, StatsTimeSeries } from "../src/index.js";

test("extends timeseries-ts TimeSeries", function () {
  const series = new StatsTimeSeries({
    id: "pm25",
    name: "PM2.5",
    units: "ug/m3",
    type: "NUMBER",
    records: [
      { timestamp: new Date("2026-01-01T00:00:00.000Z"), value: 5 },
    ],
  });

  assert.ok(series instanceof StatsTimeSeries);
  assert.ok(series instanceof TimeSeries);
  assert.equal(series.id, "pm25");
  assert.equal(series.name, "PM2.5");
  assert.equal(series.units, "ug/m3");
  assert.equal(series.type, "NUMBER");
  assert.equal(series.length, 1);
});

test("wraps an existing TimeSeries", function () {
  const baseSeries = new TimeSeries({
    id: "temperature",
    name: "Temperature",
    units: "degC",
    type: "NUMBER",
    records: [
      { timestamp: new Date("2026-01-01T00:00:00.000Z"), value: 21 },
    ],
  });

  const series = StatsTimeSeries.fromTimeSeries(baseSeries);

  assert.ok(series instanceof StatsTimeSeries);
  assert.ok(series instanceof TimeSeries);
  assert.equal(series.id, baseSeries.id);
  assert.equal(series.name, baseSeries.name);
  assert.equal(series.units, baseSeries.units);
  assert.equal(series.records[0].value, 21);
});

test("parses JTS documents into StatsTimeSeries instances", function () {
  const document = StatsJtsDocument.from({
    docType: "jts",
    version: "1.0",
    header: {
      startTime: "2026-01-01T00:00:00.000Z",
      endTime: "2026-01-01T01:00:00.000Z",
      recordCount: 2,
      columns: {
        0: {
          id: "pm25",
          name: "PM2.5",
          units: "ug/m3",
          dataType: "NUMBER",
        },
      },
    },
    data: [
      {
        ts: "2026-01-01T00:00:00.000Z",
        f: {
          0: { v: "5", q: 0 },
        },
      },
      {
        ts: "2026-01-01T01:00:00.000Z",
        f: {
          0: { v: 10 },
        },
      },
    ],
  });

  assert.ok(document instanceof StatsJtsDocument);
  assert.ok(document instanceof JtsDocument);
  assert.ok(document.series[0] instanceof StatsTimeSeries);
  assert.ok(document.series[0] instanceof TimeSeries);
  assert.ok(document.header.startTime instanceof Date);
  assert.ok(document.header.endTime instanceof Date);
  assert.equal(document.header.startTime.toISOString(), "2026-01-01T00:00:00.000Z");
  assert.equal(document.header.endTime.toISOString(), "2026-01-01T01:00:00.000Z");
  assert.equal(document.header.recordCount, 2);
  assert.deepEqual(document.header.columns[0], {
    id: "pm25",
    name: "PM2.5",
    units: "ug/m3",
    dataType: "NUMBER",
  });
  assert.equal(document.series[0].id, "pm25");
  assert.equal(document.series[0].units, "ug/m3");
  assert.deepEqual(document.series[0].values, [5, 10]);
});
