// src/util.ts
function generateRandomId() {
  return Math.random().toString(36).slice(2);
}
function deepCopy(instance) {
  if (instance == null) {
    return instance;
  }
  if (instance instanceof Date) {
    return new Date(instance.getTime());
  }
  if (instance instanceof Array) {
    const cloneArr = [];
    instance.forEach((value) => {
      cloneArr.push(value);
    });
    return cloneArr.map((value) => deepCopy(value));
  }
  if (instance instanceof Object) {
    const copyInstance = { ...instance };
    for (const attr in instance) {
      if (Object.prototype.hasOwnProperty.call(instance, attr)) {
        copyInstance[attr] = deepCopy(instance[attr]);
      }
    }
    return copyInstance;
  }
  return instance;
}

// src/TimeSeries.ts
var TimeSeries = class _TimeSeries {
  constructor(props) {
    this._records = this.cloneRecords((props == null ? void 0 : props.records) || []);
    this._id = (props == null ? void 0 : props.id) !== void 0 ? props.id : generateRandomId();
    this._name = props == null ? void 0 : props.name;
    this._units = props == null ? void 0 : props.units;
    this._type = (props == null ? void 0 : props.type) !== void 0 ? props.type : "NUMBER";
  }
  // PROPERTIES
  get id() {
    return this._id;
  }
  set id(val) {
    this._id = val;
  }
  get name() {
    return this._name;
  }
  set name(val) {
    this._name = val;
  }
  get units() {
    return this._units;
  }
  set units(val) {
    this._units = val;
  }
  get type() {
    return this._type;
  }
  set type(val) {
    this._type = val;
  }
  get length() {
    return this._records.length;
  }
  get first() {
    return this._records[0] || null;
  }
  get last() {
    return this._records[this.length - 1] || null;
  }
  get records() {
    return this._records;
  }
  get timestamps() {
    return this._records.map((record) => record.timestamp);
  }
  get values() {
    return this._records.map((record) => record.value).filter((attr) => attr !== void 0);
  }
  get qualities() {
    return this._records.map((record) => record.quality).filter((attr) => attr !== void 0);
  }
  get annotations() {
    return this._records.map((record) => record.annotation).filter((attr) => attr !== void 0);
  }
  // METHODS
  toJSON() {
    return {
      id: this._id,
      ...this._name ? { name: this._name } : null,
      ...this._units ? { units: this._units } : null,
      ...this._type ? { type: this._type } : null,
      records: this._records.map((record) => this.recordToJSON(record))
    };
  }
  insert(records) {
    if (!Array.isArray(records)) {
      records = [records];
    }
    this._records.push(...records);
    return this;
  }
  sort() {
    this._records.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
    return this;
  }
  clone() {
    return new _TimeSeries({ id: this._id, records: this._records });
  }
  recordToJSON(record) {
    const { value, quality, annotation } = record;
    const jsonValue = this.valueToJSON(value);
    return {
      timestamp: record.timestamp.toISOString(),
      ...jsonValue !== void 0 ? { value: jsonValue } : null,
      ...quality !== void 0 ? { quality } : null,
      ...annotation !== void 0 ? { annotation } : null
    };
  }
  valueToJSON(value) {
    var _a;
    if (value == null || !this.type) {
      return value;
    }
    if (this.type === "TIME") {
      return ((_a = value.toISOString) == null ? void 0 : _a.call(value)) || "invalid date";
    }
    return value;
  }
  cloneRecords(records) {
    return records.map((record) => deepCopy(record));
  }
};

// src/JtsDocument.ts
var JtsDocument = class _JtsDocument {
  constructor(props) {
    this._version = 1;
    this._series = (props == null ? void 0 : props.series) || [];
  }
  // PROPERTIES
  get version() {
    return this._version;
  }
  get series() {
    return this._series;
  }
  // STATIC METHODS
  static from(json) {
    json = deepCopy(json);
    if (typeof json === "string") {
      json = JSON.parse(json || "{}");
    } else if (typeof json !== "object") return null;
    const validationError = this.validateJSON(json);
    if (validationError) {
      throw new Error(`Invalid JTS Document JSON: ${validationError}`);
    }
    return this.parse(json);
  }
  static parse(jts) {
    var _a, _b;
    const columnSeries = {};
    for (const columnIndex in (_a = jts.header) == null ? void 0 : _a.columns) {
      const column = (_b = jts.header) == null ? void 0 : _b.columns[columnIndex];
      if (column == null) {
        continue;
      }
      const { id, name, dataType } = column;
      columnSeries[columnIndex] = new TimeSeries({ id, name, type: dataType || "NUMBER" });
    }
    (jts.data || []).forEach((record) => {
      const timestamp = new Date(record.ts);
      if (isNaN(timestamp.valueOf())) return;
      if (!Object.keys(record.f || {}).length) return;
      for (const columnIndex in record.f) {
        if (!columnSeries[columnIndex]) {
          columnSeries[columnIndex] = new TimeSeries();
        }
        const seriesRecord = this.getTimeSeriesRecordFromDataColumn({ timestamp, dataColumn: record.f[columnIndex], type: columnSeries[columnIndex].type });
        columnSeries[columnIndex].insert(seriesRecord);
      }
    });
    const version = Number(jts.version) | 1;
    return new _JtsDocument({ version, series: Object.values(columnSeries) });
  }
  static getTimeSeriesRecordFromDataColumn(props) {
    const record = { timestamp: props.timestamp, quality: props.dataColumn.q, annotation: props.dataColumn.a };
    record.value = ((v, type) => {
      if (v == null) {
        return v;
      }
      switch (type) {
        case "NUMBER":
          return Number(v);
        case "TEXT":
          return String(v);
        case "TIME":
          return (v == null ? void 0 : v.$time) ? new Date(v.$time) : null;
        case "COORDINATES":
          return (v == null ? void 0 : v.$coords) ? v.$coords : null;
        default:
          return v;
      }
    })(props.dataColumn.v, props.type);
    return record;
  }
  static validateJSON(jts) {
    if (typeof jts !== "object") {
      return "object required";
    }
    if (jts.docType !== "jts") {
      return "invalid docType";
    }
    if (jts.version && Number(jts.version) !== 1) {
      return "version 1.0 expected";
    }
    return null;
  }
  // private static isValid (jts: IJtsDocument): boolean {
  //   const errorMessage = this.validateJSON(jts)
  //   return !errorMessage
  // }
  // METHODS
  addSeries(series) {
    if (!Array.isArray(series)) {
      series = [series];
    }
    this._series.push(...series);
    return this;
  }
  getSeries(seriesId) {
    return this.getSeriesById(seriesId);
  }
  clone() {
    return new _JtsDocument({
      version: this._version,
      series: this._series.map((series) => series.clone())
    });
  }
  toJSON() {
    return this.build();
  }
  toString() {
    return JSON.stringify(this.toJSON());
  }
  build() {
    const data = this.getData();
    return {
      docType: "jts",
      subType: "TIMESERIES",
      version: this._version.toFixed(1),
      header: this.getHeader(data),
      data
    };
  }
  getData() {
    const _this = this;
    const recordMap = {};
    this._series.forEach(function(series, seriesIndex) {
      series.records.forEach(function(record) {
        if (record.value === void 0 && record.annotation === void 0 && record.quality === void 0) return;
        const key = record.timestamp.valueOf();
        if (!recordMap[key]) {
          recordMap[key] = { ts: record.timestamp.toISOString(), f: {} };
        }
        recordMap[key].f[seriesIndex] = _this.getDataColumnFromRecord({ record, type: series.type });
      });
    });
    const recordMapKeys = Object.keys(recordMap).sort((a, b) => Number(a) - Number(b));
    return recordMapKeys.map((key) => recordMap[key]);
  }
  getHeader(data = []) {
    var _a, _b;
    return {
      startTime: ((_a = data[0]) == null ? void 0 : _a.ts) || null,
      endTime: ((_b = data[data.length - 1]) == null ? void 0 : _b.ts) || null,
      recordCount: data.length,
      columns: this.getHeaderColumns()
    };
  }
  getHeaderColumns() {
    const columns = {};
    this._series.forEach(function(series, seriesIndex) {
      columns[seriesIndex] = {
        id: series.id,
        ...series.name !== void 0 ? { name: series.name } : null,
        ...series.type !== void 0 ? { dataType: series.type } : null,
        ...series.units !== void 0 ? { units: series.units } : null
      };
    });
    return columns;
  }
  getDataColumnFromRecord(props) {
    const { value, quality, annotation } = props.record;
    const v = ((v2, type) => {
      var _a;
      if (v2 == null) {
        return v2;
      }
      switch (type) {
        case "NUMBER":
          return Number(v2);
        case "TEXT":
          return String(v2);
        case "TIME":
          return { $time: ((_a = v2.toISOString) == null ? void 0 : _a.call(v2)) || "invalid date" };
        case "COORDINATES":
          return { $coords: v2.length === 2 ? v2 : [] };
        default:
          return v2;
      }
    })(value, props.type);
    return {
      ...v !== void 0 ? { v } : null,
      ...quality !== void 0 ? { q: quality } : null,
      ...annotation !== void 0 ? { a: annotation } : null
    };
  }
  getSeriesById(seriesId) {
    return this._series.find((series) => series.id === seriesId);
  }
};
export {
  JtsDocument,
  TimeSeries
};
//# sourceMappingURL=index.js.map
