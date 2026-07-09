export function registerGraphComponents(Alpine) {
  Alpine.data("chartComponent", function (options) {
    var config = options || {};
    var chart = null;

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
          },
        });

      },

      addDataset(id, label, points) {
        if (!chart) return;

        chart.data.datasets.push({
          id: id,
          label: label,
          data: points,
          borderColor: "#2364aa",
          tension: 0.25,
        });

        chart.update();
      },

      removeDataset(id) {
        if (!chart) return;

        chart.data.datasets = chart.data.datasets.filter((dataset) => {
          return dataset.id !== id;
        });

        chart.update();
      },
      toggleDataset(dataset) {
        if (!chart || !dataset || !dataset.id || !Array.isArray(dataset.data)) {
          console.warn("Invalid graph dataset payload", dataset);
          return;
        }
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
