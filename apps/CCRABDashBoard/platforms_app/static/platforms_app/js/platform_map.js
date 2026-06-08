// Debounce helper
function debounce(fn, wait) {
    let t;
    return function (...args) {
        clearTimeout(t);
        t = setTimeout(() => fn.apply(this, args), wait);
    };
}
function onEachFeature(feature, layer) {
    layer.on('click', function (e) {
        var url = undefined;
        if (feature.properties && feature.properties.short_name) {
            url = "/platform_info/" + feature.properties.short_name;
        }
        if (!url)
            return;
        window.location.href = url;

    })
}

function getJsonHeaders() {
    const headers = {Accept: "application/json"};
    const mapEl = document.getElementById("map");
    const apiToken = mapEl?.dataset?.apiToken || "";
    if (apiToken) {
        headers.Authorization = `Bearer ${apiToken}`;
    }
    return headers;
}

async function get_platforms() {
    const mapEl = document.getElementById("map");
    let url = "/platforms_catalog/data/platforms/";
    if (mapEl && mapEl.dataset && mapEl.dataset.platformsUrl) {
        url = mapEl.dataset.platformsUrl;
    }

    const response = await fetch(url, {headers: getJsonHeaders()});
    const platforms_data = await response.json();

    platforms_data.features.forEach(platform => {
        console.log(platform.properties.short_name);
    });
    var platforms_layer = L.geoJSON(platforms_data, {
        onEachFeature: onEachFeature
    }).addTo(map);
    map.fitBounds(platforms_layer.getBounds());
}

function initialize_map(map) {
    // Load on page load
    get_platforms();


// Ensure map is invalidated after it's ready (helps initial render)
    map.whenReady(function () {
        map.invalidateSize();
    });
// Target container to observe
    const mapContainer = document.getElementById('map');

// Handler to call when resize happens
    const handleResize = debounce(function () {
        if (!map) return;
        // invalidateSize will make Leaflet recompute the internal size and re-render tiles
        map.invalidateSize({debounceMoveend: true});
    }, 100); // 100ms debounce

// Use ResizeObserver if available to detect size changes of the container
    if (typeof ResizeObserver !== 'undefined') {
        const ro = new ResizeObserver(handleResize);
        ro.observe(mapContainer);
        // also observe the column in case parent resizing matters
        const mapCol = document.getElementById('map-col');
        if (mapCol) ro.observe(mapCol);
    } else {
        // Fallback: listen to window resize
        window.addEventListener('resize', handleResize);
    }

// If your layout toggles classes (e.g., a sidebar is hidden/shown),
// you may want to call handleResize after the toggle. Example toggle button:
    document.getElementById('toggle-width').addEventListener('click', function () {
        var col = document.querySelector('.column.is-one-third');
        if (col) {
            col.classList.remove('is-one-third');
            col.classList.add('is-half');
        } else {
            col = document.querySelector('.column.is-half');
            col.classList.remove('is-half');
            col.classList.add('is-one-third');
        }
        // toggle a class that will change column width (for demo)
        //col.classList.toggle('is-half');
        // After the layout change completes, force a resize/invalidate
        // use setTimeout 0 to wait for DOM reflow, then call
        setTimeout(handleResize, 50);
    });

// Extra safety: call invalidateSize when a Bulma navbar burger toggles (common case)
// (If you use Bulma nav, hook into the toggling element(s) and call handleResize)
    document.addEventListener('click', function (e) {
        // This is generic: if a click toggles a column display/class, we ask Leaflet to resize soon after
        // Fine to keep inexpensive because of debounce.
        setTimeout(handleResize, 80);
    });

// If the map is inside a tab or modal that becomes visible later, call map.invalidateSize() after it opens.
// Example helper to call from other code:
    window.invalidateLeafletMap = function () {
        setTimeout(() => {
            map.invalidateSize();
        }, 50);
    };

}
//Create the leaflet map object. We don't set a center point yet, we have to wait until the
//REST request for the platform info finishes.
const map = L.map('map');
map.setZoom(10);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; [OpenStreetMap](https://www.openstreetmap.org) contributors'
}).addTo(map);

initialize_map();
