import { CCRABRestClient } from "../../js/CCRABApiClient/src/index.js";
import Alpine from "../../vendor/alpinejs/3.15.12/module.esm.min.js";
import { DateTime } from "../../vendor/luxon/3.7.2/luxon.min.js";
import { registerGraphComponents } from "./graph.js";
import { PlatformInfo } from "./platform_info.js";
import { StatsJtsDocument } from "../../js/StatsTimeSeries/src/index.js";
import {DEFAULT_BASE_URL} from "../../js/CCRABApiClient/src/index.js";
import {getEPABreakpoint} from "./calculations.js";

//const CCRAB_BASE_URL = window.CCRAB_BASE_URL || window.location.origin;
let alpineComponentsRegistered = false;

// Define the reusable sleep utility
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

const default_obs_to_display = ["pm2.5_EPAc 1", "pm2.5_atm 1"];
function registerAlpineComponents() {
  if (alpineComponentsRegistered) {
    return;
  }
  alpineComponentsRegistered = true;

  registerGraphComponents(Alpine);

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

      init() {
        console.log("Initializing platform page");
        var endDate = DateTime.utc();
        var startDate = endDate.minus({ hours: 24 });
        console.log("Getting platformInfo from page element.")
        this.platformInfo = PlatformInfo.fromScriptElement("platform-info-data");
        this.setupDisplayObservations();
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

      /**
       * This funciton creates the listing of the observation the platform collects.
       * @returns {{key: string, obsStandardName: *, sensorOrder: *, units}[]}
       */
      get platformInfoTableRows() {
        const sensors = this.platformInfo.sensors || [];
        return sensors.map((sensor) => {
          return {
            key: `${sensor.obsStandardName}-${sensor.order}`,
            active: sensor.active,
            obsStandardName: sensor.obsStandardName,
            sensorOrder: sensor.order,
            sensorLabel: sensor.channelLabel,
            units: sensor.uomDisplay || sensor.uomStandardName
          };
        });
      },
      /**
       * This is an iterator that returns the data we want to display in the tab.
       * @returns {{key: string, obsStandardName: *, obsSOrder: *, units, display: *, stats: {min: *, max: *, most_recent: *}|*}[]}
       */
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
            obsSOrderLabel: this.formatSOrder(sensor.order),
            units: sensor.uomDisplay || sensor.uomStandardName,
            display: this.getObservationDisplayState(sensor.obsStandardName,
                                                      sensor.order),
            stats,
          };
        });
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
          this.currentObservationsToDisplay[this.platformInfo.platformHandle] = {};
        }
        var current_platform_settings = this.currentObservationsToDisplay[this.platformInfo.platformHandle];
        current_platform_settings[obs_key] = !!checked;
      },
      /**
       * If the user clicks on the observation name, we figure out if we are showing or hiding the data on the
       * graph.
       * @param obsStandardName
       * @param obsSOrder
       */
      graphObservationClicked(obsStandardName, obsSOrder) {
        console.log("Toggling observation: " + obsStandardName + " Order: " + obsSOrder);
        var seriesId = this.observationSeriesId(obsStandardName, obsSOrder);
        if (Alpine.store("graph").has(seriesId))
        {
          console.log("Removing seriesID: " + seriesId + " from graph")
          Alpine.store("graph").remove(seriesId);
          window.dispatchEvent(new CustomEvent("graph:remove-dataset", {
            detail: seriesId,
          }));
        }
        else {
          Alpine.store("graph").add(seriesId);
          // build data and dispatch add event
          var payload = this.buildChartSeriesPayload(obsStandardName, obsSOrder);
          if (!payload) return;

          window.dispatchEvent(new CustomEvent("graph:add-dataset", {
            detail: payload,
          }));
        }
      },
      buildChartSeriesPayload(obsStandardName, obsSOrder) {
        if (!this.observationTimeSeriesDoc) return null;

        var seriesId = this.observationSeriesId(obsStandardName, obsSOrder);
        var series = this.observationTimeSeriesDoc.getSeries(seriesId);
        if (!series) {
          console.warn("Timeseries ID: " + seriesId + " is undefined.");
          return null;
        }
        var graphData = [];
        for(const record of series._records) {
          var ts = DateTime.fromJSDate(record.timestamp);
          graphData.push({x: ts.toFormat("yyyy-MM-dd hh:mm:ss a"),
            y: Number(record.value)});
        }
        var sensor = this.findSensor(obsStandardName, obsSOrder);
        //If the user turned on the pm2.5 EPA Corrected channel, we want the graph coloration to use the
        //EPA breakpoint function.
        var useEPABreakpoints = false;
        if(obsStandardName === "pm2.5_EPAc") {
          useEPABreakpoints = this;
        }
        return {
          id: seriesId,
          label: this.formatObservationLabel(obsStandardName, obsSOrder),
          data: graphData,
          useEPABreakpoints: useEPABreakpoints
        };
      },
      findSensor(obsStandardName, obsSOrder) {
        const sensors = this.platformInfo?.sensors || [];
        return sensors.find((sensor) => {
          return (
            sensor.obsStandardName === obsStandardName &&
            String(sensor.order) === String(obsSOrder)
          );
        });
      },
      observationSeriesId(obsStandardName, obsSOrder) {
        return obsStandardName + " " + obsSOrder;
      },
      formatObservationLabel(obsStandardName, obsSOrder) {
        return obsStandardName + " " + this.formatSOrder(obsSOrder);
      },
      /**
       * Given the parameters, determine what the display state of the observation is.
       * @param obsStandardName
       * @param obsSOrder
       * @returns {*|boolean}
       */
      getObservationDisplayState(obsStandardName, obsSOrder)
      {
          var obs_key = obsStandardName + " " + obsSOrder;
          if(this.platformInfo.platformHandle in this.currentObservationsToDisplay &&
              (obs_key in this.currentObservationsToDisplay[this.platformInfo.platformHandle]))
          {
              return this.currentObservationsToDisplay[this.platformInfo.platformHandle][obs_key];
          }
          return false;
      },
      /**
       * Formats the passed in value for display.
       * @param value
       * @returns {string}
       */
      formatObservationValue(value) {
        if (value === null || value === undefined) return "No data";
        if (!Number.isFinite(Number(value))) return String(value);

        return Number(value).toFixed(2);
      },
      /**
       * Formats the passed in timestamp param for display.
       * @param timestamp_rec
       * @returns {string}
       */
      formatDateTimeStr(timestamp_rec) {
        var dt = DateTime.fromJSDate(timestamp_rec);
        var formattedDateTime = dt.toFormat("yyyy-MM-dd hh:mm:ss a");
        return formattedDateTime
      },
      /**
       * Formats the sOrder to the more industry appropriate format.
       * @param sOrder
       */
      formatSOrder(sOrder) {
        if(sOrder == 1) {
          return 'A';
        }
        else if(sOrder == 2) {
          return 'B';
        }
        return String(sOrder);
      },
      getClassForObs(obsName, obsValue)
      {
        if(obsName === "pm2.5_EPAc")
        {
          var epaRange = getEPABreakpoint(obsValue);
          return "{color: " + epaRange.color + "}";
        }
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
        var viewport = this.viewport();
        if (!viewport || !slides.length) return;

        //if (!slides.length) return;

        var targetIndex = Math.max(0, Math.min(index, slides.length - 1));
        var targetSlide = slides[targetIndex];
        var targetLeft =
          targetSlide.getBoundingClientRect().left -
          viewport.getBoundingClientRect().left +
          viewport.scrollLeft;

        this.activeIndex = targetIndex;
        viewport.scrollTo({
            left: targetLeft,
            behavior: behavior || "smooth",
          });

        /*slides[targetIndex].scrollIntoView({
          behavior: behavior || "smooth",
          inline: "start",
          block: "nearest",
        });*/
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
