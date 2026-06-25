# Stats Time Series

Small ESM extension point for the vendored `timeseries-ts` `TimeSeries` and
`JtsDocument` classes.

```js
import { StatsTimeSeries } from "../../js/StatsTimeSeries/src/index.js";

const series = new StatsTimeSeries({
  id: "pm25",
  name: "PM2.5",
  units: "ug/m3",
  type: "NUMBER",
  records: [
    { timestamp: new Date("2026-01-01T00:00:00.000Z"), value: 5 },
  ],
});
```

For parsed JTS documents, use `StatsJtsDocument` so parsed series are
`StatsTimeSeries` instances:

```js
import { StatsJtsDocument } from "../../js/StatsTimeSeries/src/index.js";

const statsDocument = StatsJtsDocument.from(jtsJson);
const statsSeries = statsDocument.getSeries("pm25");
const startTime = statsDocument.header.startTime;
```
