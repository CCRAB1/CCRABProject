/** State for one observation channel within a platform. */
export class ObservationDisplayState {
  constructor(obsStandardName, sensorOrder, isChecked = false) {
    this.obsStandardName = obsStandardName;
    this.sensorOrder = sensorOrder;
    // Visibility in Current Observations is independent of graph selection.
    this.isChecked = isChecked;
    this.isGraphed = false;
    // Requested bounds of successfully loaded data, as UTC ISO strings.
    // Null until data is loaded, and whenever the channel is off.
    this.startDataTime = null;
    this.endDataTime = null;
  }

  get obsStandardName() {
    return this._obsStandardName;
  }

  set obsStandardName(value) {
    this._obsStandardName = value;
  }

  get sensorOrder() {
    return this._sensorOrder;
  }

  set sensorOrder(value) {
    this._sensorOrder = value;
  }

  get isChecked() {
    return this._isChecked;
  }

  set isChecked(value) {
    this._isChecked = Boolean(value);
  }

  get isGraphed() {
    return this._isGraphed;
  }

  set isGraphed(value) {
    this._isGraphed = Boolean(value);
  }

  get startDataTime() {
    return this._startDataTime;
  }

  set startDataTime(value) {
    this._startDataTime = value;
  }

  get endDataTime() {
    return this._endDataTime;
  }

  set endDataTime(value) {
    this._endDataTime = value;
  }

  get seriesId() {
    return this.obsStandardName + " " + this.sensorOrder;
  }
  get graphed() {
    return this.isGraphed;
  }
  set graphed(value) {
    this.isGraphed = value;
  }
  get checked() {
    return this.isChecked;
  }
  set checked(value) {
    this.isChecked = value;
  }
  setChecked(isChecked) {
    this.isChecked = isChecked;
  }
  setGraphed(isGraphed, startDataTime = null, endDataTime = null) {
    this.isGraphed = isGraphed;
    this.startDataTime = startDataTime;
    this.endDataTime = endDataTime;
  }
  setGraphDateRange(startDataTime, endDataTime) {
    this.startDataTime = startDataTime;
    this.endDataTime = endDataTime;
  }
}
