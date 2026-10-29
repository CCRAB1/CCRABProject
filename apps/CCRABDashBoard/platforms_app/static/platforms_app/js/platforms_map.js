import Alpine from "alpinejs";
import { DateTime } from "luxon";
import { CCRABRestClient } from "../../../../static/js/CCRABApiClient/src/index.js";
import { StatsJtsDocument } from "../../../../static/js/StatsTimeSeries/src/index.js";
import { getAQIColorCode } from "./calculations.js";

const DEFAULT_CENTER = [32.7765, -79.9311];
const DEFAULT_ZOOM = 10;
const REFRESH_INTERVAL_MS = 15 * 60 * 1000;
const AQI_SERIES_ID = "pm2.5_aqi 1";
const NO_DATA_COLOR = "#7a8594";

function debounce(fn, wait) {
    let timeout;

    return function (...args) {
        window.clearTimeout(timeout);
        timeout = window.setTimeout(() => fn.apply(this, args), wait);
    };
}

function normalizeText(value) {
    return String(value || "").trim().toLowerCase();
}

function isFiniteNumber(value) {
    return Number.isFinite(Number(value));
}

function escapeHtml(value) {
    return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function platformCoordinates(feature) {
    const geometryCoordinates = feature?.geometry?.coordinates;

    if (
        Array.isArray(geometryCoordinates) &&
        geometryCoordinates.length >= 2 &&
        isFiniteNumber(geometryCoordinates[0]) &&
        isFiniteNumber(geometryCoordinates[1])
    ) {
        return [Number(geometryCoordinates[1]), Number(geometryCoordinates[0])];
    }

    const properties = feature?.properties || {};
    const latitude = properties.fixed_latitude;
    const longitude = properties.fixed_longitude;

    if (isFiniteNumber(latitude) && isFiniteNumber(longitude)) {
        return [Number(latitude), Number(longitude)];
    }

    return null;
}

function featureWithPointGeometry(feature) {
    const coordinates = platformCoordinates(feature);

    if (!coordinates) {
        return null;
    }

    return {
        ...feature,
        geometry: {
            type: "Point",
            coordinates: [coordinates[1], coordinates[0]],
        },
    };
}

function isActivePlatform(feature) {
    const active = feature?.properties?.active;

    if (active === undefined || active === null || active === "") {
        return true;
    }

    if (typeof active === "boolean") {
        return active;
    }

    return ["1", "true", "yes"].includes(String(active).toLowerCase());
}

document.addEventListener("alpine:init", () => {
    Alpine.data("platformsMap", () => ({
        allPlatforms: [],
        aqiByPlatformHandle: {},
        observationErrorMessage: "",
        isLoadingObservations: false,
        errorMessage: "",
        isLoading: false,
        layerByFeatureKey: {},
        map: null,
        platformLayer: null,
        resizeObserver: null,
        refreshTimer: null,
        searchTerm: "",
        showInactive: false,
        visiblePlatforms: [],

        init() {
            this.$nextTick(() => {
                this.initializeMap();
                this.observeMapSize();
                this.loadPlatforms();
                this.startRefreshTimer();

                this.$watch("searchTerm", () => this.updateVisiblePlatforms());
                this.$watch("showInactive", () => this.updateVisiblePlatforms());
            });
        },

        startRefreshTimer() {
            if (this.refreshTimer !== null) {
                window.clearInterval(this.refreshTimer);
            }
            this.refreshTimer = window.setInterval(() => {
                if (!this.isLoading) {
                    this.loadObservations();
                }
            }, REFRESH_INTERVAL_MS);
        },

        destroy() {
            window.clearInterval(this.refreshTimer);
            this.refreshTimer = null;
            this.resizeObserver?.disconnect();
        },

        get statusLabel() {
            if (this.isLoading) {
                return "Loading platforms";
            }

            if (this.errorMessage) {
                return "Platform data unavailable";
            }

            return `${this.visiblePlatforms.length} of ${this.allPlatforms.length} platforms`;
        },

        initializeMap() {
            if (!window.L) {
                this.errorMessage = "Map library unavailable.";
                return;
            }

            this.map = window.L.map(this.$refs.map, {
                scrollWheelZoom: true,
            }).setView(DEFAULT_CENTER, DEFAULT_ZOOM);

            window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
                    attribution: "&copy; OpenStreetMap contributors",
                    referrerPolicy: "strict-origin-when-cross-origin"
            }).addTo(this.map);

            this.map.whenReady(() => this.invalidateMap());
        },

        observeMapSize() {
            if (!this.$refs.map) {
                return;
            }

            const handleResize = debounce(() => this.invalidateMap(), 100);

            if (typeof ResizeObserver !== "undefined") {
                this.resizeObserver = new ResizeObserver(handleResize);
                this.resizeObserver.observe(this.$refs.map);

                const stage = this.$refs.map.closest(".platforms-map-stage");
                if (stage) {
                    this.resizeObserver.observe(stage);
                }
            } else {
                window.addEventListener("resize", handleResize);
            }
        },

        invalidateMap() {
            if (!this.map) {
                return;
            }

            window.setTimeout(() => {
                this.map.invalidateSize({ debounceMoveend: true });
            }, 50);
        },

        getJsonHeaders() {
            const headers = { Accept: "application/json" };
            const apiToken = this.$refs.map?.dataset?.apiToken || "";

            if (apiToken) {
                headers.Authorization = `Bearer ${apiToken}`;
            }

            return headers;
        },

        async loadPlatforms() {
            const url =
                this.$refs.map?.dataset?.platformsUrl || "/platforms_catalog/data/platforms/";

            this.errorMessage = "";
            this.isLoading = true;

            try {
                const response = await window.fetch(url, { headers: this.getJsonHeaders() });

                if (!response.ok) {
                    throw new Error(`Platform request failed with status ${response.status}`);
                }

                const platformsData = await response.json();
                this.allPlatforms = Array.isArray(platformsData.features)
                    ? platformsData.features
                    : [];
                this.updateVisiblePlatforms();
                this.fitVisiblePlatforms();
                await this.loadObservations();
            } catch (error) {
                console.warn("Platform map data error", error);
                this.allPlatforms = [];
                this.visiblePlatforms = [];
                this.renderVisiblePlatforms();
                this.errorMessage = "Unable to load platform locations.";
            } finally {
                this.isLoading = false;
                this.invalidateMap();
            }
        },

        async loadObservations() {
            if (this.isLoadingObservations) return;

            const endDate = DateTime.utc();
            const startDate = endDate.minus({ hours: 1 });
            const client = new CCRABRestClient({
                baseUrl: window.location.origin,
                accessToken: this.$refs.map?.dataset?.apiToken || null,
            });
            this.observationErrorMessage = "";
            this.isLoadingObservations = true;

            // Bound concurrent requests so a large catalog does not flood the API.
            const handles = [];
            for (const feature of this.allPlatforms) {
                const handle = feature?.properties?.platform_handle;
                if (handle && !handles.includes(handle)) {
                    handles.push(handle);
                }
            }
            let nextIndex = 0;
            const loadNext = async () => {
                while (nextIndex < handles.length) {
                    const handle = handles[nextIndex++];
                    try {
                        const record = await this.getObservationData(client, startDate, endDate, handle);
                        if (record) {
                            this.aqiByPlatformHandle[handle] = record;
                        } else {
                            delete this.aqiByPlatformHandle[handle];
                        }
                    } catch (error) {
                        delete this.aqiByPlatformHandle[handle];
                        console.warn("Platform map AQI data error", handle, error);
                        this.observationErrorMessage = "Some AQI readings could not be loaded. Gray markers have no recent AQI data.";
                    } finally {
                        this.updatePlatformMarker(handle);
                    }
                }
            };

            try {
                const workers = [];
                for (let index = 0; index < Math.min(4, handles.length); index++) {
                    workers.push(loadNext());
                }
                await Promise.all(workers);
            } finally {
                this.isLoadingObservations = false;
            }
        },

        async getObservationData(client, startDate, endDate, platformHandle) {
            const observationData = await client.getPlatformData(
                startDate, endDate, platformHandle, [AQI_SERIES_ID],
            );
            const document = StatsJtsDocument.from(observationData.properties.timeseries);
            const series = document.getSeries(AQI_SERIES_ID);
            let latest = null;
            for (const record of series?.records || []) {
                const timestamp = record.timestamp.getTime();
                if (record.value === null || record.value === undefined || record.value === "" ||
                    !Number.isFinite(Number(record.value)) ||
                    !Number.isFinite(timestamp) || timestamp < startDate.toMillis() || timestamp > endDate.toMillis()) {
                    continue;
                }
                if (!latest || timestamp > latest.timestamp.getTime()) {
                    latest = record;
                }
            }
            return latest;
        },

        markerColor(feature) {
            const record = this.aqiByPlatformHandle[feature?.properties?.platform_handle];
            return record ? getAQIColorCode(Number(record.value))?.color || NO_DATA_COLOR : NO_DATA_COLOR;
        },

        markerIcon(feature) {
            const record = this.aqiByPlatformHandle[feature?.properties?.platform_handle];
            const value = record ? Number(record.value).toFixed(0) : "—";
            const color = this.markerColor(feature);
            const textColor = ["#8F3F97", "#7E0023", NO_DATA_COLOR].includes(color)
                ? "#ffffff" : "#151515";
            return window.L.divIcon({
                className: "platform-aqi-marker",
                html: `<span class="platform-aqi-marker-value" style="background-color: ${color}; color: ${textColor};">${escapeHtml(value)}</span>`,
                iconSize: [36, 36],
                iconAnchor: [18, 18],
                popupAnchor: [0, -18],
            });
        },

        updatePlatformMarker(platformHandle) {
            for (const feature of this.visiblePlatforms) {
                if (feature?.properties?.platform_handle !== platformHandle) continue;
                const layer = this.layerByFeatureKey[this.featureKey(feature)];
                if (layer) {
                    layer.setIcon(this.markerIcon(feature));
                    layer.setPopupContent(this.popupContent(feature));
                }
            }
        },

        updateVisiblePlatforms() {
            const term = normalizeText(this.searchTerm);

            this.visiblePlatforms = this.allPlatforms.filter((feature) => {
                if (!this.showInactive && !isActivePlatform(feature)) {
                    return false;
                }

                if (!term) {
                    return true;
                }

                return this.searchableText(feature).includes(term);
            });

            this.renderVisiblePlatforms();
        },

        searchableText(feature) {
            const properties = feature?.properties || {};

            return normalizeText([
                properties.short_name,
                properties.long_name,
                properties.platform_handle,
                properties.neighborhood,
                properties.city,
                properties.manufacturer,
                properties.serial_number,
            ].join(" "));
        },

        renderVisiblePlatforms() {
            if (!this.map) {
                return;
            }

            if (this.platformLayer) {
                this.platformLayer.remove();
            }

            this.layerByFeatureKey = {};

            const features = this.visiblePlatforms
                .map((feature) => featureWithPointGeometry(feature))
                .filter(Boolean);

            this.platformLayer = window.L.geoJSON(
                {
                    type: "FeatureCollection",
                    features,
                },
                {
                    pointToLayer: (feature, latLng) => window.L.marker(latLng, {
                        icon: this.markerIcon(feature),
                        title: this.platformName(feature),
                        alt: this.platformName(feature),
                    }),
                    onEachFeature: (feature, layer) => {
                        layer.bindPopup(this.popupContent(feature));
                        layer.on("click", () => {
                            const url = this.platformDetailUrl(feature);
                            if (url !== "#") {
                                window.location.href = url;
                            }
                        });
                    },
                }
            ).addTo(this.map);

            this.platformLayer.eachLayer((layer) => {
                this.layerByFeatureKey[this.featureKey(layer.feature)] = layer;
            });

            this.invalidateMap();
        },

        fitVisiblePlatforms() {
            if (!this.map || !this.platformLayer || this.platformLayer.getLayers().length === 0) {
                return;
            }

            const bounds = this.platformLayer.getBounds();
            if (bounds.isValid()) {
                this.map.fitBounds(bounds.pad(0.12), {
                    maxZoom: 14,
                    padding: [24, 24],
                });
            }
        },

        focusPlatform(feature, openPopup = true) {
            if (!this.map) {
                return;
            }

            const layer = this.layerByFeatureKey[this.featureKey(feature)];
            if (!layer || !layer.getLatLng) {
                return;
            }

            this.map.panTo(layer.getLatLng(), { animate: true, duration: 0.35 });

            if (openPopup) {
                layer.openPopup();
            }
        },

        featureKey(feature) {
            const properties = feature?.properties || {};
            return properties.short_name || properties.platform_handle || JSON.stringify(feature?.geometry || {});
        },

        platformName(feature) {
            const properties = feature?.properties || {};
            return properties.long_name || properties.short_name || "Unnamed platform";
        },

        platformMeta(feature) {
            const properties = feature?.properties || {};
            const meta = [
                properties.neighborhood,
                properties.city,
            ].filter(Boolean);

            return meta.join(" | ");
        },

        sensorCountLabel(feature) {
            const sensors = feature?.properties?.sensors;
            const count = Array.isArray(sensors) ? sensors.length : 0;
            return `${count} sensor${count === 1 ? "" : "s"}`;
        },

        platformDetailUrl(feature) {
            const shortName = feature?.properties?.short_name;
            if (!shortName) {
                return "#";
            }

            const template =
                this.$refs.map?.dataset?.platformDetailUrl ||
                "/platforms_catalog/platform_info/__short_name__/";

            return template.replace("__short_name__", encodeURIComponent(shortName));
        },

        popupContent(feature) {
            const name = escapeHtml(this.platformName(feature));
            const meta = escapeHtml(this.platformMeta(feature));
            const record = this.aqiByPlatformHandle[feature?.properties?.platform_handle];
            const aqiLabel = record
                ? `PM2.5 AQI: ${escapeHtml(Number(record.value).toFixed(0))} · ${escapeHtml(DateTime.fromJSDate(record.timestamp).toLocaleString(DateTime.DATETIME_SHORT))}`
                : "No PM2.5 AQI data in the past hour";

            return `
                <span class="platform-popup-title">${name}</span>
                <span class="platform-popup-meta">${meta}</span>
                <span class="platform-popup-meta">${aqiLabel}</span>
            `;
        },
    }));
});

window.Alpine = Alpine;
Alpine.start();
