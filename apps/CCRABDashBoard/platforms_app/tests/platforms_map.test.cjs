const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { DateTime } = require('luxon');
const { JtsDocument, TimeSeries } = require('@eagle-io/timeseries');

const root = path.resolve(__dirname, '../..');
function createMap(respond) {
    let factory;
    const requests = [];
    const timers = new Map();
    let nextTimerId = 1;
    const context = vm.createContext({
        DateTime, JtsDocument, TimeSeries,
        console: { warn() {} },
        Alpine: { data(name, value) { factory = value; }, start() {} },
        document: { addEventListener(event, callback) { callback(); } },
        window: { setInterval(callback, delay) { const id = nextTimerId++; timers.set(id, { callback, delay }); return id; }, clearInterval(id) { timers.delete(id); }, location: { origin: 'http://localhost' }, L: { divIcon(options) { return options; } } },
        CCRABRestClient: class {
            constructor(options) { this.options = options; }
            async getPlatformData(start, end, handle, observations) {
                requests.push({ start, end, handle, observations, options: this.options });
                return respond(handle, start, end);
            }
        },
    });
    for (const filename of [
        'static/js/StatsTimeSeries/src/stats_time_series.js',
        'static/js/StatsTimeSeries/src/stats_jts_document.js',
        'platforms_app/static/platforms_app/js/calculations.js',
        'platforms_app/static/platforms_app/js/platforms_map.js',
    ]) {
        const source = fs.readFileSync(path.join(root, filename), 'utf8')
            .replace(/^import\s+[\s\S]*?;\s*$/gm, '')
            .replace(/export (class|function) /g, '$1 ');
        vm.runInContext(source, context, { filename });
    }
    const map = factory();
    map.$refs = { map: { dataset: { apiToken: 'test-token' } } };
    return { map, requests, timers };
}

function payload(records) {
    return { properties: { timeseries: {
        docType: 'jts', version: '1.0',
        header: { columns: { 1: { id: 'pm2.5_aqi 1', dataType: 'NUMBER' } } },
        data: records.map(([ts, value]) => ({ ts, f: { 1: { v: value } } })),
    } } };
}
const feature = handle => ({ properties: { platform_handle: handle, short_name: handle } });

test('requests the past hour of AQI and colors from the newest valid reading', async () => {
    const { map, requests } = createMap((handle, start, end) => payload([
        [end.minus({ minutes: 5 }).toISO(), 125],
        [end.minus({ minutes: 20 }).toISO(), 25],
        [end.minus({ minutes: 1 }).toISO(), null],
        [end.toISO(), 'invalid'],
        [start.minus({ seconds: 1 }).toISO(), 200],
        [end.plus({ minutes: 1 }).toISO(), 250],
    ]));
    const platform = feature('one');
    map.allPlatforms = [platform, platform];
    map.visiblePlatforms = [platform];
    let icon;
    let popup;
    map.layerByFeatureKey.one = {
        setIcon(value) { icon = value; },
        setPopupContent(value) { popup = value; },
    };
    await map.loadObservations();
    assert.equal(requests.length, 1);
    assert.deepEqual(Array.from(requests[0].observations), ['pm2.5_aqi 1']);
    assert.equal(requests[0].end.diff(requests[0].start, 'hours').hours, 1);
    assert.equal(requests[0].start.offset, 0);
    assert.equal(requests[0].options.accessToken, 'test-token');
    assert.equal(map.markerColor(platform), '#FF7E00');
    assert.match(icon.html, /background-color: #FF7E00/);
    assert.match(icon.html, />125<\/span>/);
    assert.match(popup, /PM2.5 AQI: 125/);
    assert.equal(map.isLoadingObservations, false);
});

test('empty and failed requests keep locations and allow other platforms to load', async () => {
    const { map } = createMap((handle, start, end) => {
        if (handle === 'failed') throw new Error('API unavailable');
        return payload(handle === 'empty' ? [] : [[end.toISO(), 0]]);
    });
    map.allPlatforms = ['empty', 'failed', 'good'].map(feature);
    await map.loadObservations();
    assert.equal(map.allPlatforms.length, 3);
    assert.equal(map.markerColor(feature('empty')), '#7a8594');
    assert.equal(map.markerColor(feature('failed')), '#7a8594');
    assert.equal(map.markerColor(feature('good')), '#00E400');
    assert.match(map.markerIcon(feature('good')).html, />0<\/span>/);
    assert.match(map.markerIcon(feature('empty')).html, />—<\/span>/);
    assert.match(map.observationErrorMessage, /could not be loaded/);
    assert.equal(map.isLoadingObservations, false);
    assert.match(map.popupContent(feature('empty')), /No PM2.5 AQI data in the past hour/);
});


test('refresh timer runs every 15 minutes, avoids duplicates and is cleared on destroy', () => {
    const { map, timers } = createMap();
    let loads = 0;
    map.loadObservations = () => { loads++; };
    map.startRefreshTimer();
    map.startRefreshTimer();
    assert.equal(timers.size, 1);
    const timer = timers.get(map.refreshTimer);
    assert.equal(timer.delay, 15 * 60 * 1000);
    timer.callback();
    assert.equal(loads, 1);
    map.isLoading = true;
    timer.callback();
    assert.equal(loads, 1);
    map.destroy();
    assert.equal(timers.size, 0);
    assert.equal(map.refreshTimer, null);
});

test('refresh skips overlapping loads and clears markers whose latest hour has no data', async () => {
    let resolveRequest;
    const { map, requests } = createMap(() => new Promise(resolve => { resolveRequest = resolve; }));
    const platform = feature('one');
    map.allPlatforms = [platform];
    map.visiblePlatforms = [platform];
    map.aqiByPlatformHandle.one = { value: 125 };
    let icon;
    map.layerByFeatureKey.one = { setIcon(value) { icon = value; }, setPopupContent() {} };
    const pending = map.loadObservations();
    await map.loadObservations();
    assert.equal(requests.length, 1);
    resolveRequest(payload([]));
    await pending;
    assert.equal(map.aqiByPlatformHandle.one, undefined);
    assert.match(icon.html, /background-color: #7a8594/);
    assert.match(icon.html, />—<\/span>/);
    assert.equal(map.isLoadingObservations, false);
});
