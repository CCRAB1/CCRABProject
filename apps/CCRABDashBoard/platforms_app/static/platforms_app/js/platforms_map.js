import Alpine from "../../vendor/alpinejs/3.15.12/module.esm.min.js";

const DEFAULT_CENTER = [32.7765, -79.9311];
const DEFAULT_ZOOM = 10;

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

function markerColor(feature) {
    return isActivePlatform(feature) ? "#2f80ed" : "#7a8594";
}

document.addEventListener("alpine:init", () => {
    Alpine.data("platformsMap", () => ({
        allPlatforms: [],
        errorMessage: "",
        isLoading: false,
        layerByFeatureKey: {},
        map: null,
        platformLayer: null,
        resizeObserver: null,
        searchTerm: "",
        showInactive: false,
        visiblePlatforms: [],

        init() {
            this.$nextTick(() => {
                this.initializeMap();
                this.observeMapSize();
                this.loadPlatforms();

                this.$watch("searchTerm", () => this.updateVisiblePlatforms());
                this.$watch("showInactive", () => this.updateVisiblePlatforms());
            });
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
                    pointToLayer: (feature, latLng) => window.L.circleMarker(latLng, {
                        color: "#ffffff",
                        fillColor: markerColor(feature),
                        fillOpacity: 0.9,
                        opacity: 1,
                        radius: 8,
                        weight: 2,
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

            return `
                <span class="platform-popup-title">${name}</span>
                <span class="platform-popup-meta">${meta}</span>
            `;
        },
    }));
});

window.Alpine = Alpine;
Alpine.start();
