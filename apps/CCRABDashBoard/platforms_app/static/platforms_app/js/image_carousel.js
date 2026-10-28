import Alpine from "alpinejs";
import {DateTime} from "luxon";

import { CCRABRestClient }
  from "../../../../static/js/CCRABApiClient/src/index.js";
import { StatsJtsDocument }
  from "../../../../static/js/StatsTimeSeries/src/index.js";
import { registerGraphComponents } from "./graph.js";
import { PlatformInfo } from "./platform_info.js";
import { AlpineStore } from "./alpine_store.js";
import { ObservationDisplayState } from "./observation_display_state.js";
import {getAQIColorCode} from "./calculations.js";

//const CCRAB_BASE_URL = window.CCRAB_BASE_URL || window.location.origin;
let alpineComponentsRegistered = false;

// Define the reusable sleep utility
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

const default_obs_to_display = ["pm2.5 1", "pm2.5_EPAc 1", "pm2.5_aqi 1"];
function registerAlpineComponents() {
  if (alpineComponentsRegistered) {
    return;
  }
  alpineComponentsRegistered = true;

  registerGraphComponents(Alpine);
  const observationStates = new AlpineStore("observationDisplayStates");
  const pendingObservationLoads = new Map();
  let observationLoadCount = 0;

  Alpine.data("platformPage", function () {
    return {
      activePanel: "current_data",
      showAllObservations: false,
      isLoadingPlatform: true,
      isLoadingObservationData: false,
      platformLoadError: null,
      observationLoadError: null,
      platformInfo: null,
      requestedShortName: "",
      observationWindow: null,
      observationTimeSeriesDoc: null,
      startDateTime: null,
      endDateTime: null,
      selectedStartDateTime: "",
      selectedEndDateTime: "",
      observationRangeError: null,
      dateRangeInfoOpen: null,
      observationInfoOpen: null,
      sensorListToDisplay: null,

      async init() {
        console.log("Initializing platform page");
        this.requestedShortName = this.$root.dataset.platformShortName || "";
        await this.loadPlatform();
      },
      async loadPlatform() {
        this.isLoadingPlatform = true;
        this.platformLoadError = null;
        this.platformInfo = null;
        this.observationTimeSeriesDoc = null;
        this.startDateTime = null;
        this.endDateTime = null;
        this.selectedStartDateTime = "";
        this.selectedEndDateTime = "";
        this.observationRangeError = null;
        this.dateRangeInfoOpen = null;
        this.observationInfoOpen = null;


        const client = new CCRABRestClient({
          baseUrl: window.location.origin,
        });

        try {
          const payload = await client.getPlatformPageConfiguration(
            this.requestedShortName,
          );
          this.platformInfo = PlatformInfo.parse(payload);
          document.title = this.platformInfo.shortName + " | Platform";
          this.setupDisplayObservations();

          await this.$nextTick();
          window.dispatchEvent(new CustomEvent("platform-info-loaded"));

          const observations = this.platformInfo.observationIdentifiers();
          if (!this.platformInfo.platformHandle || observations.length === 0) {
            return;
          }
          var endDate = DateTime.local().startOf("minute");
          var startDate = endDate.minus({ hours: 24 });
          this.selectedStartDateTime = this.toDateTimeLocalValue(startDate);
          this.selectedEndDateTime = this.toDateTimeLocalValue(endDate);
          await this.getObservationData(
            startDate.toUTC(),
            endDate.toUTC(),
            this.platformInfo.platformHandle,
            observations
          );
        }
        catch (error)
        {
          console.error("Unable to load platform information", error);
          this.platformLoadError = this.platformErrorMessage(error);
        }
        finally
        {
          this.isLoadingPlatform = false;
          //Now let's graph the observations
          for (const sensor_nfo of this.platformInfo?.displayedSensors() || [])
          {
            //We will have multiple sensors of the same type, so we build the key based on name and order.
            if(this.isObservationGraphed(sensor_nfo.obsStandardName, sensor_nfo.order))
            {
                console.log("Adding seriesID: " + sensor_nfo.obsStandardName + " " + sensor_nfo.order + " to graph");
                // build data and dispatch add event
                var payload = this.buildChartSeriesPayload(sensor_nfo.obsStandardName,
                    sensor_nfo.order);
                if(payload) {
                  window.dispatchEvent(new CustomEvent("graph:add-dataset", {
                    detail: payload,
                  }));
                }
              }
          }

        }
      },
      platformErrorMessage(error) {
        if (error && error.statusCode === 404) {
          return "The requested platform could not be found.";
        }
        return "Platform information could not be loaded. Please try again.";
      },
      retryPlatformLoad() {
        this.loadPlatform();
      },
      async getObservationData(startDate, endDate, platformHandle, observations, merge = false) {
        console.debug("Querying platform: " + platformHandle + " data from: " + startDate + " to " + endDate);
        const client = new CCRABRestClient({
          baseUrl: window.location.origin,
        });
        observationLoadCount += 1;
        this.isLoadingObservationData = true;
        this.observationLoadError = null;
        // Request only channels selected for the graph.
        var requestedObservations = [];
        for (const seriesId of observations) {
          if (observationStates.get(seriesId)?.isGraphed) {
            requestedObservations.push(seriesId);
          }
        }
        try {
          let observationData = await client.getPlatformData(
            startDate,
            endDate,
            platformHandle,
            requestedObservations
          );
          var loadedDocument = StatsJtsDocument.from(observationData['properties']['timeseries']);
          if (merge && this.observationTimeSeriesDoc) {
            var combinedSeries = [];
            for (const series of this.observationTimeSeriesDoc.series) {
              if (!requestedObservations.includes(series.id)) combinedSeries.push(series);
            }
            for (const series of loadedDocument.series) combinedSeries.push(series);
            loadedDocument = new StatsJtsDocument({ header: loadedDocument.header, series: combinedSeries });
          }
          this.observationTimeSeriesDoc = loadedDocument;
          this.observationWindow = { start: startDate.toUTC().toISO(), end: endDate.toUTC().toISO() };
          for (const seriesId of requestedObservations) {
            var state = observationStates.get(seriesId);
            if (state?.isGraphed) {
              state.setGraphDateRange(this.observationWindow.start, this.observationWindow.end);
            }
          }
          return true;
        }
        catch (error) {
          console.error("Unable to load observation data", error);
          this.observationLoadError = "Current observations could not be loaded.";
          return false;
        }
        finally {
          observationLoadCount -= 1;
          this.isLoadingObservationData = observationLoadCount > 0;
        }
      },
      toDateTimeLocalValue(dateTime) {
        if (!dateTime || !dateTime.isValid) return "";
        return dateTime.toFormat("yyyy-LL-dd'T'HH:mm");
      },
      selectedDateTime(value) {
        if (!value) return null;

        var dateTime = DateTime.fromFormat(value, "yyyy-LL-dd'T'HH:mm");
        return dateTime.isValid ? dateTime : null;
      },
      async applyObservationRange() {
        var startDate = this.selectedDateTime(this.selectedStartDateTime);
        var endDate = this.selectedDateTime(this.selectedEndDateTime);
        this.observationRangeError = null;

        if (!startDate || !endDate) {
          this.observationRangeError = "Choose both a start and end date and time.";
          return;
        }

        if (startDate >= endDate) {
          this.observationRangeError = "The end date and time must be after the start date and time.";
          return;
        }

        if (!this.platformInfo || !this.platformInfo.platformHandle) return;

        var graphedSeriesIds = this.graphedSeriesIds();
        this.observationTimeSeriesDoc = null;
        var observationDataLoaded = await this.getObservationData(
          startDate.toUTC(),
          endDate.toUTC(),
          this.platformInfo.platformHandle,
          this.platformInfo.observationIdentifiers(),
        );
        if (observationDataLoaded) {
          this.refreshGraphedObservations(graphedSeriesIds);
        }
      },
      graphedSeriesIds() {
        var seriesIds = [];
        for (const sensor of this.platformInfo?.displayedSensors() || []) {
          var seriesId = this.observationSeriesId(sensor.obsStandardName, sensor.order);
          if (observationStates.get(seriesId)?.isGraphed) seriesIds.push(seriesId);
        }
        return seriesIds;
      },
      refreshGraphedObservations(graphedSeriesIds) {
        if (!this.platformInfo || !Array.isArray(graphedSeriesIds)) return;

        for (const sensor of this.platformInfo.displayedSensors()) {
          var seriesId = this.observationSeriesId(sensor.obsStandardName, sensor.order);
          if (graphedSeriesIds.indexOf(seriesId) === -1) continue;

          var payload = this.buildChartSeriesPayload(sensor.obsStandardName, sensor.order);
          if (!payload) {
            payload = {
              id: seriesId,
              label: this.formatObservationLabel(sensor.obsStandardName, sensor.order),
              data: [],
              xAxis: {
                key: "observation-time",
                type: "time",
                unit: "minute",
                tooltipFormat: "yyyy-MMM-d,  h:mm a",
                maxTicksLimit: 10,
                displayFormats: {
                  hour: "HH:MM",
                },
              },
            };
          }

          window.dispatchEvent(new CustomEvent("graph:update-dataset", {
            detail: payload,
          }));
        }
      },
      /**
       * Sets up the initial display observations based on the platform info.
       *
       * @returns {void}*/
      setupDisplayObservations() {
        console.log("Setting up display observations");
        if (!this.platformInfo) return;
        // Series IDs are scoped to the current platform page. Reset on reload.
        for (const seriesId of Object.keys(Alpine.store("observationDisplayStates"))) {
          observationStates.delete(seriesId);
        }
        this.observationWindow = null;
        for (const sensor of this.platformInfo.displayedSensors()) {
          var seriesId = this.observationSeriesId(sensor.obsStandardName, sensor.order);
          var isDefault = default_obs_to_display.includes(seriesId);
          var state = new ObservationDisplayState(sensor.obsStandardName, sensor.order, isDefault);
          state.setGraphed(isDefault);
          observationStates.set(seriesId, state);
        }
      },
      initialObservationDisplayState(obsStandardName, sensorOrder) {
        return this.getObservationDisplayState(obsStandardName, sensorOrder);
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
        const sensors = this.platformInfo?.displayedSensors() || [];
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
        const sensors = this.platformInfo?.displayedSensors() || [];
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
              var oldestRec = series.getOldestRecord();
              if(oldestRec !== undefined) {
                this.startDateTime = this.formatDateTimeStr(oldestRec.timestamp);
              }
              else
              {
                console.error("No oldest record found for timeseries: " + timeseries_id);
              }
              var latestRec = series.getLatestRecord();
              if(latestRec !== undefined) {
                this.endDateTime = this.formatDateTimeStr(latestRec.timestamp);
              }
              else
              {
                console.error("No latest record found for timeseries: " + timeseries_id);
              }
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
            obsDefinition: sensor.obsDefinition,
            obsInfoUrl: sensor.obsInfoUrl,
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
      async observationCheckClicked(checked, obsStandardName, obsSOrder) {
        var seriesId = this.observationSeriesId(obsStandardName, obsSOrder);
        observationStates.get(seriesId)?.setChecked(checked);
        await this.ensureObservationData(obsStandardName, obsSOrder);
      },
      /**
       * Toggles the display state of the observation.
       * @param obsStandardName
       * @param obsSOrder
       */
      toggleObservationDisplay(obsStandardName, obsSOrder) {
        var seriesId = this.observationSeriesId(obsStandardName, obsSOrder);
        var state = observationStates.get(seriesId);
        if (!state) return;
        state.setGraphed(!state.isGraphed);

      },
      /**
       * If the user clicks on the observation name, we figure out if we are showing or hiding the data on the
       * graph.
       * @param obsStandardName
       * @param obsSOrder
       */
      async graphObservationClicked(obsStandardName, obsSOrder) {
        var seriesId = this.observationSeriesId(obsStandardName, obsSOrder);
        var state = observationStates.get(seriesId);
        console.log(seriesId + " graph observation clicked.");
        if (!state) return;
        this.toggleObservationDisplay(obsStandardName, obsSOrder);
        if (!state.isGraphed) {
          window.dispatchEvent(new CustomEvent("graph:remove-dataset", { detail: seriesId }));
          return;
        }
        if (state.isChecked && (!state.startDataTime || !state.endDataTime)) {
          await this.ensureObservationData(obsStandardName, obsSOrder);
          return;
        }
        var payload = this.buildChartSeriesPayload(obsStandardName, obsSOrder);
        if (!payload) return;
        window.dispatchEvent(new CustomEvent("graph:add-dataset", { detail: payload }));
      },
      /** Load a selected channel once, retaining data for other channels. */
      async ensureObservationData(obsStandardName, obsSOrder) {
        var seriesId = this.observationSeriesId(obsStandardName, obsSOrder);
        var state = observationStates.get(seriesId);
        if (!state?.isChecked || !state.isGraphed || (state.startDataTime && state.endDataTime)) return;
        if (pendingObservationLoads.has(seriesId)) return pendingObservationLoads.get(seriesId);
        var start = this.selectedDateTime(this.selectedStartDateTime);
        var end = this.selectedDateTime(this.selectedEndDateTime);
        if (!start || !end || start >= end) {
          this.observationRangeError = "Choose a valid start and end date and time.";
          return;
        }
        if (!this.platformInfo?.platformHandle) return;
        this.observationRangeError = null;
        var load = (async () => {
          var loaded = await this.getObservationData(
            start.toUTC(), end.toUTC(), this.platformInfo.platformHandle, [seriesId], true,
          );
          if (loaded && state.isChecked && state.isGraphed) {
            this.refreshGraphedObservations([seriesId]);
          }
        })();
        pendingObservationLoads.set(seriesId, load);
        try {
          await load;
        } finally {
          pendingObservationLoads.delete(seriesId);
        }
      },
      /**
       * Returns whether an observation's series is currently displayed in the graph.
       * @param obsStandardName
       * @param obsSOrder
       * @returns {boolean}
       */
      isObservationGraphed(obsStandardName, obsSOrder) {
        return observationStates.get(this.observationSeriesId(obsStandardName, obsSOrder))?.isGraphed ?? false;
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
        var lastTS = null;
        var tsInterval = null;
        for(const record of series._records) {
          var ts = DateTime.fromJSDate(record.timestamp);
          if(lastTS !== null) {
            tsInterval = ts.diff(lastTS, "seconds");
          }
          lastTS = ts;
          graphData.push({x: record.timestamp.toISOString(),
            y: Number(record.value)});
        }
        var sensor = this.findSensor(obsStandardName, obsSOrder);
        //If the user turned on the pm2.5 EPA Corrected channel, we want the graph coloration to use the
        //EPA breakpoint function.
        var useAQIColorCodes = false;
        var timeSeriesIntervalSeconds = tsInterval?.seconds ?? null;
        if(obsStandardName === "pm2.5_aqi") {
          useAQIColorCodes = true;
        }
        return {
          id: seriesId,
          label: this.formatObservationLabel(obsStandardName, obsSOrder),
          data: graphData,
          AQIColorRange: useAQIColorCodes,
          timeSeriesIntervalSeconds: timeSeriesIntervalSeconds,
          xAxis: {
            key: "observation-time",
            type: "time",
            unit: "minute",       // display preference, not sampling truth
            tooltipFormat: "yyyy-MMM-d,  h:mm a",
            maxTicksLimit: 10, // Limits maximum number of labels shown on screen
            displayFormats: {
               'hour': 'HH:MM',
            }

          },
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
        return observationStates.get(this.observationSeriesId(obsStandardName, obsSOrder))?.isChecked ?? false;
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
      formatPlatformDateRange() {
        if (!this.platformInfo || !this.platformInfo.beginDate) {
          return "Not available";
        }

        var beginDate = DateTime.fromISO(this.platformInfo.beginDate);
        var beginLabel = beginDate.isValid
          ? beginDate.toFormat("yyyy-MM-dd")
          : this.platformInfo.beginDate;
        if (!this.platformInfo.endDate) {
          return beginLabel + " to Currently active";
        }

        var endDate = DateTime.fromISO(this.platformInfo.endDate);
        var endLabel = endDate.isValid
          ? endDate.toFormat("yyyy-MM-dd")
          : this.platformInfo.endDate;
        return beginLabel + " to " + endLabel;
      },
      displayValue(value) {
        return value === null || value === undefined || value === ""
          ? "Not available"
          : value;
      },
      get displayedSensorCount() {
        return this.platformInfo?.displayedSensors().length || 0;
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
      /**
       * This function is used to style the data in the Current Data tables for the current, min and max
       * values.
       * @param obsName
       * @param obsValue
       * @returns {string}
       */
      getClassForObs(obsName, obsValue)
      {
        if(obsValue !== undefined) {
          if (obsName === "pm2.5_aqi") {
            var aqiRange = getAQIColorCode(obsValue);
            return "background-color: " + aqiRange.color + ";";
          }
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

      refresh() {
        this.slideCount = this.slides().length;
        if (this.activeIndex >= this.slideCount) this.activeIndex = 0;
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
