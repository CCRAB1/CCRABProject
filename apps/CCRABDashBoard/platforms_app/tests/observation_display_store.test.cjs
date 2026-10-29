const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { reactive, effect } = require('@vue/reactivity');
const { DateTime } = require('luxon');

const sourceDir = path.resolve(__dirname, '../static/platforms_app/js');

// Exercise the page with Alpine's reactive engine and a mocked API, without a DOM.
function createPage() {
  const stores = reactive({});
  const components = {};
  const events = [];
  let requested;
  let requestCount = 0;
  let failRequest = false;
  const Alpine = {
    store(name, value) {
      if (arguments.length === 2) stores[name] = value;
      return stores[name];
    },
    data(name, factory) { components[name] = factory; },
    start() {},
  };
  const context = vm.createContext({
    Alpine,
    DateTime,
    console: { log() {}, debug() {}, warn() {}, error() {} },
    window: { location: { origin: 'http://localhost' }, dispatchEvent(event) { events.push(event); } },
    CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options.detail; } },
    CCRABRestClient: class {
      async getPlatformData(start, end, platform, observations) {
        requested = observations;
        requestCount++;
        if (failRequest) throw new Error('API failure');
        return { properties: { timeseries: { series: observations.map(id => ({ id, _records: [] })) } } };
      }
    },
    StatsJtsDocument: class {
      constructor(props) { this.series = props.series; this.header = props.header; }
      static from(props) { return new this(props); }
      getSeries(id) { return this.series.find(series => series.id === id); }
    },

  });
  for (const filename of ['observation_display_state.js', 'alpine_store.js', 'graph.js', 'image_carousel.js']) {
    const source = fs.readFileSync(path.join(sourceDir, filename), 'utf8')
      .replace(/^import\s+[\s\S]*?;\s*$/gm, '')
      .replace(/export (class|function) /g, '$1 ');
    vm.runInContext(source, context, { filename });
  }
  const page = components.platformPage();
  page.selectedStartDateTime = '2026-10-27T00:00';
  page.selectedEndDateTime = '2026-10-28T00:00';
  page.platformInfo = { platformHandle: 'platform', displayedSensors: () => [
    { obsStandardName: 'pm2.5', order: 1 },
    { obsStandardName: 'pm2.5', order: 2 },
  ] };
  page.setupDisplayObservations();
  return { page, stores, events, context, components, requestCount: () => requestCount, requested: () => Array.from(requested || []), fail: () => { failRequest = true; } };
}

test('channel state is reactive and checkbox changes affect only that channel', () => {
  const { page, stores } = createPage();
  const first = stores.observationDisplayStates['pm2.5 1'];
  assert.equal(first.isChecked, true);
  assert.equal(first.isGraphed, true);
  assert.equal(stores.observationDisplayStates['pm2.5 2'].isChecked, false);
  let otherRuns = 0;
  effect(() => { page.initialObservationDisplayState('pm2.5', 2); otherRuns++; });
  let checked;
  effect(() => { checked = page.initialObservationDisplayState('pm2.5', 1); });
  page.observationCheckClicked(false, 'pm2.5', 1);
  assert.equal(checked, false);
  assert.equal(otherRuns, 1);
  assert.equal(first.isGraphed, true);
  page.observationCheckClicked(true, 'pm2.5', 2);
  assert.equal(stores.observationDisplayStates['pm2.5 2'].isGraphed, false);
});

test('graph selection uses observation state and clears the range independently of checked state', async () => {
  const { page, stores, events } = createPage();
  const state = stores.observationDisplayStates['pm2.5 1'];
  state.setGraphDateRange('start', 'end');
  await page.graphObservationClicked('pm2.5', 1);
  assert.equal(state.isGraphed, false);
  assert.equal(state.isChecked, true);
  assert.equal(state.startDataTime, null);
  assert.equal(state.endDataTime, null);
  assert.equal(stores.graphInfo, undefined);
  assert.equal(events[0].type, 'graph:remove-dataset');
  page.buildChartSeriesPayload = () => ({ id: state.seriesId });
  page.observationWindow = { start: 'loaded-start', end: 'loaded-end' };
  await page.graphObservationClicked('pm2.5', 1);
  assert.equal(state.isGraphed, true);
  assert.equal(state.startDataTime, DateTime.fromISO(page.selectedStartDateTime).toUTC().toISO());
  assert.deepEqual(Array.from(page.graphedSeriesIds()), ['pm2.5 1']);
  assert.equal(events[1].type, 'graph:update-dataset');
});

test('data requests use graphed channels and update bounds only after success', async () => {
  const harness = createPage();
  const { page, stores } = harness;
  const date = value => ({ toUTC() { return this; }, toISO() { return value; } });
  assert.equal(await page.getObservationData(date('start'), date('end'), 'platform', ['pm2.5 1', 'pm2.5 2']), true);
  assert.deepEqual(harness.requested(), ['pm2.5 1']);
  const state = stores.observationDisplayStates['pm2.5 1'];
  assert.equal(state.startDataTime, 'start');
  assert.equal(state.endDataTime, 'end');
  assert.equal(stores.observationDisplayStates['pm2.5 2'].startDataTime, null);
  harness.fail();
  assert.equal(await page.getObservationData(date('new-start'), date('new-end'), 'platform', ['pm2.5 1']), false);
  assert.equal(state.startDataTime, 'start');
  page.setupDisplayObservations();
  assert.deepEqual(Array.from(page.graphedSeriesIds()), ['pm2.5 1']);
  assert.equal(stores.observationDisplayStates['pm2.5 1'].startDataTime, null);
});


test('chart adds and removes datasets without a graphInfo store', () => {
  const { context, components, stores } = createPage();
  let chart;
  class FakeChart {
    constructor(canvas, config) {
      this.data = config.data;
      this.options = { ...config.options, scales: {} };
      chart = this;
    }
    update() {}
  }
  context.Chart = FakeChart;
  context.window.Chart = FakeChart;
  const component = components.chartComponent();
  component.$refs = { canvas: {} };
  component.createChart();
  component.addDataset({ id: 'pm2.5 1', data: [], label: 'PM2.5', xAxis: { key: 'time', type: 'time' } });
  assert.equal(stores.graphInfo, undefined);
  assert.equal(chart.data.datasets.length, 1);
  const axisId = chart.data.datasets[0].yAxisID;
  assert.ok(chart.options.scales[axisId]);
  component.removeDataset('pm2.5 1');
  assert.equal(chart.data.datasets.length, 0);
  assert.equal(chart.options.scales[axisId], undefined);
});


test('checking a graphed channel with missing bounds queries and preserves other channels', async () => {
  const { page, stores, requested, requestCount, events } = createPage();
  const first = stores.observationDisplayStates['pm2.5 1'];
  const second = stores.observationDisplayStates['pm2.5 2'];
  await page.ensureObservationData('pm2.5', 1);
  const existing = page.observationTimeSeriesDoc.getSeries(first.seriesId);
  second.setGraphed(true);
  await page.observationCheckClicked(true, 'pm2.5', 2);
  assert.deepEqual(requested(), ['pm2.5 2']);
  assert.ok(second.startDataTime);
  assert.ok(second.endDataTime);
  assert.equal(page.observationTimeSeriesDoc.getSeries(first.seriesId), existing);
  assert.ok(page.observationTimeSeriesDoc.getSeries(second.seriesId));
  assert.equal(events.at(-1).type, 'graph:update-dataset');
  await page.observationCheckClicked(true, 'pm2.5', 2);
  assert.equal(requestCount(), 2);
  second.endDataTime = null;
  await page.observationCheckClicked(true, 'pm2.5', 2);
  assert.equal(requestCount(), 3);
});

test('unchecked or ungraphed channels do not query; pending loads are shared', async () => {
  const { page, stores, requestCount } = createPage();
  const second = stores.observationDisplayStates['pm2.5 2'];
  await page.observationCheckClicked(true, 'pm2.5', 2);
  assert.equal(requestCount(), 0);
  second.setChecked(false);
  await page.graphObservationClicked('pm2.5', 2);
  assert.equal(requestCount(), 0);
  await Promise.all([
    page.observationCheckClicked(true, 'pm2.5', 2),
    page.observationCheckClicked(true, 'pm2.5', 2),
  ]);
  assert.equal(requestCount(), 1);
});

test('failed channel queries leave missing bounds available for retry', async () => {
  const { page, stores, requestCount, fail, events } = createPage();
  fail();
  await page.ensureObservationData('pm2.5', 1);
  assert.equal(stores.observationDisplayStates['pm2.5 1'].startDataTime, null);
  assert.equal(events.length, 0);
  assert.ok(page.observationLoadError);
  await page.ensureObservationData('pm2.5', 1);
  assert.equal(requestCount(), 2);
});
