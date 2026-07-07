import { CCRABRestClient } from "../../js/CCRABApiClient/src/index.js";
import Alpine from "../../vendor/alpinejs/3.15.12/module.esm.min.js";
import { DateTime } from "../../vendor/luxon/3.7.2/luxon.min.js";
import { PlatformInfo } from "./platform_info.js";
import { StatsJtsDocument } from "../../js/StatsTimeSeries/src/index.js";
import {DEFAULT_BASE_URL} from "../../js/CCRABApiClient/src/index.js";;

//const CCRAB_BASE_URL = window.CCRAB_BASE_URL || window.location.origin;
let alpineComponentsRegistered = false;

// Define the reusable sleep utility
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

const default_obs_to_display = ["air_temperature 1", "air_pressure 1", "relative_humidity 1", "pm2.5 1"];
function registerAlpineComponents() {
  if (alpineComponentsRegistered) {
    return;
  }
  alpineComponentsRegistered = true;

  Alpine.data("platformPage", function () {
    return {
      activePanel: "current_data",
      showAllObservations: false,
      isLoadingObservationData: false,
      platformInfo: null,
      observationWindow: null,
      observationTimeSeriesDoc: null,
      startDateTime: null,
      endDateTime: null,
      currentObservationsToDisplay: null,
      sensorListToDisplay: null,
      observationChart: null,

      init() {
        console.log("Initializing platform page");
        var endDate = DateTime.utc();
        var startDate = endDate.minus({ hours: 24 });
        console.log("Getting platformInfo from page element.")
        this.platformInfo = PlatformInfo.fromScriptElement("platform-info-data");
        this.setupDisplayObservations();
        this.createChart("graph-container");
        if (this.platformInfo !== null) {
          console.log("Querying data for platform: " + this.platformInfo.platformHandle + " from: " + startDate + " to " + endDate);
          this.getObservationData(
            startDate,
            endDate,
            this.platformInfo.platformHandle,
            this.platformInfo.observationNames()
          );
        }
      },
      async getObservationData(startDate, endDate, platformHandle, observations) {
        console.debug("Querying platform: " + platformHandle + " data from: " + startDate + " to " + endDate);
        const client = new CCRABRestClient({
          baseUrl: DEFAULT_BASE_URL
        });
        this.isLoadingObservationData = true;
        try {
          let observationData = await client.getPlatformData(
            startDate,
            endDate,
            platformHandle,
            observations
          );
          this.observationTimeSeriesDoc = StatsJtsDocument.from(observationData['properties']['timeseries']);

        }
        finally {
          this.isLoadingObservationData = false;
        }
      },
      /**
       *
       */
      createChart(chartID) {
        console.log("Creating chart");
        var chart_id = document.getElementById(chartID);
        this.observationChart = new Chart(
          chart_id,
          {
            type: 'line',
            data: {
                labels: [], // No labels initially
                datasets: [] // No datasets initially
            },
            options: {
              responsive: true,
              scales: {
                  y: {
                      beginAtZero: true // Ensures scale starts nicely
                  }
              }
            }
          });
      },
      addObservationToChart(label, newData) {
          this.observationChart.data.labels.push(label);
          this.observationChart.data.datasets.forEach((dataset) => {
              dataset.data.push(newData);
          });
          this.observationChart.update();
      },
      removeObservationToChart() {
          this.observationChart.data.labels.pop();
          this.observationChart.data.datasets.forEach((dataset) => {
              dataset.data.pop();
          });
          this.observationChart.update();
      },
      /**
       * Sets up the initial display observations based on the platform info.
       *
       * @returns {void}*/
      setupDisplayObservations() {
        console.log("Setting up display observations");
        var platform_handle = this.platformInfo.platformHandle;
        var initial_setup = false;
        if(this.currentObservationsToDisplay == null) {
          initial_setup = true;
          this.currentObservationsToDisplay = {};
          this.currentObservationsToDisplay[platform_handle] = {};
        }
        for (const sensor_nfo of this.platformInfo.sensors)
        {
          if(initial_setup)
          {
            //We will have multiple sensors of the same type, so we build the key based on name and order.
            var obs_key = sensor_nfo.obsStandardName + " " + sensor_nfo.order;
            this.currentObservationsToDisplay[platform_handle][obs_key] = false;
            if(default_obs_to_display.includes(obs_key)) {
              console.log("Setting default observation to true: " + obs_key);
              this.currentObservationsToDisplay[platform_handle][obs_key] = true;
            }
          }
        }
      },
      /**
       * Determines the initial display state of the observations based on the platform info.
       *
       * @param check_box_obs_name
       * @param check_box_sensor_order
       */
      initialObservationDisplayState(check_box_obs_name, check_box_sensor_order) {
        var initial_state = false;
        if(this.currentObservationsToDisplay != null) {
          var platform_handle = this.platformInfo.platformHandle;
          var obs_state = Object.entries(this.currentObservationsToDisplay[platform_handle]);
          for(const [observation, state] of obs_state) {
            var check_box_obs_name_key = check_box_obs_name + " " + check_box_sensor_order;
            if (check_box_obs_name_key == observation) {
              console.log("Observation is in the list of observations to display: " + check_box_obs_name_key);
              initial_state = this.currentObservationsToDisplay[platform_handle][observation];
              if(initial_state) {
                console.log("Observation is set to true: " + check_box_obs_name_key);
              }
              break;
            }
          }
        }
        return initial_state;
      },
      setPanel(panel) {
        this.activePanel = panel;
        this.$nextTick(function () {
          window.dispatchEvent(
            new CustomEvent("platform-panel-changed", { detail: { panel: panel } })
          );
        });
      },
      formatDateTimeStr(timestamp_rec) {
        var dt = DateTime.fromJSDate(timestamp_rec);
        var formattedDateTime = dt.toFormat("yyyy-MM-dd hh:mm:ss a");
        return formattedDateTime
      },

      /**
       * This funciton creates the listing of the observation the platform collects.
       * @returns {{key: string, obsStandardName: *, sensorOrder: *, units}[]}
       */
      get platformInfoTableRows() {
        const sensors = this.platformInfo.sensors || [];
        return sensors.map((sensor) => {
          return {
            key: `${sensor.obsStandardName}-${sensor.order}`,
            obsStandardName: sensor.obsStandardName,
            sensorOrder: sensor.order,
            units: sensor.uomDisplay || sensor.uomStandardName
          };
        });
      },

      get observationTableRows() {
        const sensors = this.platformInfo.sensors || [];
        return sensors.map((sensor) => {
          var timeseries_id = sensor.obsStandardName + " " + sensor.order;
          var stats = {
            min: "N/A",
            max: "N/A",
            most_recent: "N/A"
          };
          if (this.observationTimeSeriesDoc != null) {
            var series = this.observationTimeSeriesDoc.getSeries(timeseries_id);
            if (series !== undefined) {
              //Get the start/end date from the series.
              this.startDateTime = this.formatDateTimeStr(series.getOldestRecord().timestamp);
              this.endDateTime = this.formatDateTimeStr(series.getLatestRecord().timestamp);
              //stats = series.getStats();
              stats = {
                min: series.min_record,
                max: series.max_record,
                most_recent: series.getLatestRecord()
              }
            } else {
              console.error("Timeseries ID: " + timeseries_id + " is undefined.");
            }
          }
          return {
            key: `${sensor.obsStandardName}-${sensor.order}`,
            obsStandardName: sensor.obsStandardName,
            obsSOrder: sensor.order,
            units: sensor.uomDisplay || sensor.uomStandardName,
            display: this.displayObservation(sensor.obsStandardName, sensor.order),
            stats,
          };
        });
      },
      displayObservation(obsStandardName, obsSOrder) {
        var platform_handle = this.platformInfo.platformHandle;
        if(platform_handle in this.currentObservationsToDisplay) {
          var current_platform_settings = this.currentObservationsToDisplay[platform_handle];
          var obs_key = obsStandardName + " " + obsSOrder;
          if(obs_key in current_platform_settings) {
            return current_platform_settings[obs_key];
          }
        }
        return false;
      },

      formatObservationValue(value) {
        if (value === null || value === undefined) return "No data";
        if (!Number.isFinite(Number(value))) return String(value);

        return Number(value).toFixed(2);
      },
      /**
       * Determines if the observation should be displayed based on the current state of the check box.
       * @param checked
       * @param obsStandardName
       * @param obsSOrder
       */
      observationCheckClicked(checked, obsStandardName, obsSOrder) {
        console.log("Displaying observation: " + obsStandardName + " Order: " + obsSOrder + " Checked: " + checked);
        var obs_key = obsStandardName + " " + obsSOrder;
        if(!(this.platformInfo.platformHandle in this.currentObservationsToDisplay))
        {
          this.platformInfo.platformHandle[this.platformInfo.platformHandle] = {};
        }
        var current_platform_settings = this.currentObservationsToDisplay[this.platformInfo.platformHandle];
        current_platform_settings[obs_key] = !!checked;
      },
      graphObservationClicked(obsStandardName, obsSOrder) {
        console.log("Toggling observation: " + obsStandardName + " Order: " + obsSOrder);
      }
    };
  });

  Alpine.data("platformCarousel", function (options) {
    return {
      activeIndex: 0,
      autoplay: Boolean(options && options.autoplay),
      interval: Number((options && options.interval) || 5000),
      loop: !options || options.loop !== false,
      pauseOnHover: !options || options.pauseOnHover !== false,
      slideCount: Number((options && options.slideCount) || 0),
      timer: null,
      restartTimer: null,
      rafPending: false,
      hoverOrFocusPaused: false,

      init() {
        this.slideCount = this.slides().length;
        this.updateFromScroll();
        this.startAutoplay();
      },

      slides() {
        return Array.from(this.$root.querySelectorAll("[data-carousel-slide]"));
      },

      viewport() {
        return this.$refs.viewport;
      },

      canScroll() {
        var viewport = this.viewport();
        return viewport && viewport.scrollWidth > viewport.clientWidth + 1;
      },

      atStart() {
        var viewport = this.viewport();
        return !viewport || viewport.scrollLeft <= 1;
      },

      atEnd() {
        var viewport = this.viewport();
        if (!viewport) return true;

        var maxScroll = viewport.scrollWidth - viewport.clientWidth;
        return viewport.scrollLeft >= maxScroll - 1;
      },

      prefersReducedMotion() {
        return (
          window.matchMedia &&
          window.matchMedia("(prefers-reduced-motion: reduce)").matches
        );
      },

      closestVisibleSlideIndex() {
        var viewport = this.viewport();
        var slides = this.slides();
        if (!viewport || !slides.length) return 0;

        var viewportRect = viewport.getBoundingClientRect();
        var bestIndex = 0;
        var bestDelta = Infinity;

        slides.forEach(function (slide, index) {
          var delta = Math.abs(slide.getBoundingClientRect().left - viewportRect.left);
          if (delta < bestDelta) {
            bestDelta = delta;
            bestIndex = index;
          }
        });

        return bestIndex;
      },

      updateFromScroll() {
        this.activeIndex = this.closestVisibleSlideIndex();
      },

      scheduleScrollUpdate() {
        if (this.rafPending) return;

        this.rafPending = true;
        window.requestAnimationFrame(() => {
          this.rafPending = false;
          this.updateFromScroll();
        });
      },

      scrollToIndex(index, behavior) {
        var slides = this.slides();
        if (!slides.length) return;

        var targetIndex = Math.max(0, Math.min(index, slides.length - 1));
        this.activeIndex = targetIndex;
        slides[targetIndex].scrollIntoView({
          behavior: behavior || "smooth",
          inline: "start",
          block: "nearest",
        });
      },

      previous() {
        var targetIndex = this.activeIndex - 1;
        if (targetIndex < 0 && this.loop) targetIndex = this.slideCount - 1;

        this.scrollToIndex(targetIndex);
        this.restartAutoplay();
      },

      next() {
        var targetIndex = this.activeIndex + 1;
        if (targetIndex >= this.slideCount && this.loop) targetIndex = 0;

        this.scrollToIndex(targetIndex);
        this.restartAutoplay();
      },

      advance() {
        var targetIndex = this.activeIndex + 1;
        if (targetIndex >= this.slideCount && this.loop) targetIndex = 0;

        this.scrollToIndex(targetIndex);
      },

      goTo(index) {
        this.scrollToIndex(index);
        this.restartAutoplay();
      },

      pause() {
        if (!this.pauseOnHover) return;

        this.hoverOrFocusPaused = true;
        this.stopAutoplay();
      },

      resume() {
        if (!this.pauseOnHover) return;

        this.hoverOrFocusPaused = false;
        this.startAutoplay();
      },

      stopAutoplay() {
        if (this.timer) {
          window.clearInterval(this.timer);
          this.timer = null;
        }

        if (this.restartTimer) {
          window.clearTimeout(this.restartTimer);
          this.restartTimer = null;
        }
      },

      startAutoplay() {
        if (!this.autoplay) return;
        if (this.prefersReducedMotion()) return;
        if (this.hoverOrFocusPaused) return;
        if (!this.canScroll()) return;
        if (this.timer) return;

        this.timer = window.setInterval(() => {
          if (!this.canScroll()) return;

          if (this.atEnd()) {
            if (this.loop) this.scrollToIndex(0);
            else this.stopAutoplay();
          } else {
            this.advance();
          }
        }, this.interval);
      },

      restartAutoplay(delay) {
        if (!this.autoplay || this.prefersReducedMotion()) return;

        this.stopAutoplay();
        this.restartTimer = window.setTimeout(() => {
          this.restartTimer = null;
          if (!this.hoverOrFocusPaused) this.startAutoplay();
        }, delay || this.interval);
      },
    };
  });
}



window.Alpine = Alpine;
registerAlpineComponents();
Alpine.start();
