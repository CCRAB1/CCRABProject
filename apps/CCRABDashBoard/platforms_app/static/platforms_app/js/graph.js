import {getEPABreakpoint} from "./calculations";

const graphColors = [
  {
    name: "Ocean Blue",
    borderColor: "#2563eb",
    backgroundColor: "rgba(37, 99, 235, 0.12)",
  },
  {
    name: "Deep Navy",
    borderColor: "#1e3a8a",
    backgroundColor: "rgba(30, 58, 138, 0.12)",
  },
  {
    name: "Sky Blue",
    borderColor: "#0284c7",
    backgroundColor: "rgba(2, 132, 199, 0.12)",
  },
  {
    name: "Cyan",
    borderColor: "#0891b2",
    backgroundColor: "rgba(8, 145, 178, 0.12)",
  },
  {
    name: "Indigo",
    borderColor: "#4f46e5",
    backgroundColor: "rgba(79, 70, 229, 0.12)",
  },
  {
    name: "Violet",
    borderColor: "#7c3aed",
    backgroundColor: "rgba(124, 58, 237, 0.12)",
  },
  {
    name: "Purple",
    borderColor: "#9333ea",
    backgroundColor: "rgba(147, 51, 234, 0.12)",
  },
  {
    name: "Slate",
    borderColor: "#475569",
    backgroundColor: "rgba(71, 85, 105, 0.12)",
  },
  {
    name: "Cool Gray",
    borderColor: "#64748b",
    backgroundColor: "rgba(100, 116, 139, 0.12)",
  },
];


export function registerGraphComponents(Alpine) {
    if (!Alpine.store("graph")) {
        Alpine.store("graph", {
            plottedIds: [],

            has(id) {
                return this.plottedIds.includes(id);
            },

            add(id) {
                if (!this.has(id)) {
                  console.log("Adding id: " + id + " to graph")
                    this.plottedIds.push(id);
                }
            },

            remove(id) {
                this.plottedIds = this.plottedIds.filter((item) => {
                    console.log("Removing id: " + id + " to graph")
                    return item !== id;
                });
            },
        });
    }
    Alpine.data("chartComponent", function (options) {
        var config = options || {};
        var chart = null;
        var currentColorIndex = 0;
        return {
            chartType: config.type || "line",
            chartData: config.data || {
                labels: [],
                datasets: [],
            },
            chartOptions: config.options || {},

            init() {
                this.$nextTick(() => {
                    this.createChart();
                });
            },

            destroy() {
                if (chart) {
                    chart.destroy();
                    chart = null;
                }
            },

            createChart() {
                if (chart) return;

                if (!window.Chart) {
                    console.warn("Chart.js is unavailable.");
                    return;
                }

                var canvas = this.$refs.canvas;
                if (!canvas) return;
                chart = new window.Chart(this.$refs.canvas, {
                    type: this.chartType,
                    data: {
                        labels: [],
                        datasets: [],
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                          x: {
                            type: "category",
                          },
                        },

                    },
                });

            },

            addDataset(dataset) {
                if (!chart || !dataset || !dataset.id || !Array.isArray(dataset.data)) {
                    console.warn("Invalid graph dataset payload", dataset);
                    return;
                }
                var axisId = "y-" + dataset.id.replaceAll(" ", "-");
                console.debug("Adding dataset id: " + dataset.id + "axis: " + axisId);
                //chart.options.scales = chart.options.scales || {};
                if(!(axisId in chart.options.scales))
                {
                    chart.options.scales[axisId] = {};
                }
                chart.options.scales[axisId] = {
                    type: "linear",
                    position: chart.data.datasets.length % 2 === 0 ? "left" : "right",
                    title: {
                        display: true,
                        text: dataset.units || dataset.label,
                    },
                    grid: {
                        drawOnChartArea: chart.data.datasets.length === 0,
                    },
                };
                if(currentColorIndex == graphColors.length) {
                    currentColorIndex = 0;
                }

                chart.data.datasets.push({
                    id: dataset.id,
                    label: dataset.label,
                    data: dataset.data,
                    yAxisID: axisId,
                    borderColor: graphColors[currentColorIndex].borderColor,
                    backgroundColor: graphColors[currentColorIndex].backgroundColor,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    tension: 0.25,

                });
                if (chart.scales && chart.scales.y) {
                  delete chart.scales.y;
                }

                chart.update("none");
            },

            removeDataset(id) {
                if (!chart) return;

                var existingIndex = chart.data.datasets.filter((dataset) => {
                    return dataset.id !== id;
                });
                var axisId = "y-" + id.replaceAll(" ", "-");
                console.debug("Removing dataset id: " + id + "axis: " + axisId);

                if (existingIndex) {
                    chart.data.datasets.splice(id, 1);
                }

                var axisStillUsed = chart.data.datasets.some((item) => {
                    return item.yAxisID === axisId;
                });

                if (!axisStillUsed && chart.options.scales) {
                    console.log("Deleting chart scale: " + axisId);
                    delete chart.options.scales[axisId];
                    if (chart.scales) {
                      if(axisId in chart.scales) {
                          delete chart.scales[axisId];
                      }
                    }
                }
                chart.update("none");
            },
            toggleDataset(dataset) {
                if (!chart || !dataset || !dataset.id || !Array.isArray(dataset.data)) {
                    console.warn("Invalid graph dataset payload", dataset);
                    return;
                }
                var axisId = "y-" + dataset.id.replaceAll(" ", "-");

                chart.options.scales = chart.options.scales || {};

                chart.options.scales[axisId] = {
                    type: "linear",
                    position: chart.data.datasets.length % 2 === 0 ? "left" : "right",
                    title: {
                        display: true,
                        text: dataset.units || dataset.label,
                    },
                    grid: {
                        drawOnChartArea: chart.data.datasets.length === 0,
                    },
                };

                var existingIndex = chart.data.datasets.findIndex((item) => {
                    return item.id === dataset.id;
                });

                if (existingIndex >= 0) {
                    chart.data.datasets.splice(existingIndex, 1);
                } else {
                    chart.data.datasets.push({
                        id: dataset.id,
                        label: dataset.label,
                        data: dataset.data,
                        borderColor: "#2364aa",
                        tension: 0.25,
                    });
                }

                chart.update();
            }
        };
    });
}
