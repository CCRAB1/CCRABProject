import Alpine from "alpinejs";
import { Chart, registerables } from "chart.js";
import "chartjs-adapter-luxon";

import {
  registerPlatformCatalogComponents,
} from "../platforms_app/static/platforms_app/js/platforms_catalog.js";

Chart.register(...registerables);
window.Chart = Chart;
window.Alpine = Alpine;

registerPlatformCatalogComponents(Alpine);

// Bundle the existing platform behavior and all of its npm imports.
await import("../platforms_app/static/platforms_app/js/image_carousel.js");