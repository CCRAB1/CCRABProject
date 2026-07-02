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

function registerAlpineComponents() {
  if (alpineComponentsRegistered) {
    return;
  }
  alpineComponentsRegistered = true;

  Alpine.data("platformPage", function () {
    return {
      activePanel: "observations",
      showAllObservations: false,
      isLoadingObservationData: false,
      platformInfo: null,
      observationWindow: null,
      observationTimeSeriesDoc: null,
      startDateTime: null,
      endDateTime: null,

      init() {
        var endDate = DateTime.utc();
        var startDate = endDate.minus({ hours: 1 });
        this.platformInfo = PlatformInfo.fromScriptElement("platform-info-data");
        if (this.platformInfo !== null) {

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

      get observationTableRows() {
        const sensors = this.platformInfo.sensors || [];
        return sensors.map((sensor) => {
          var timeseries_id = sensor.obsStandardName + " " + sensor.order;
          var stats = {
            min: "N/A",
            max: "N/A",
            most_recent: "N/A"
          };
          if(this.observationTimeSeriesDoc != null) {
            var series = this.observationTimeSeriesDoc.getSeries(timeseries_id);
            if(series !== undefined) {
              //Get the start/end date from the series.
              this.startDateTime = this.formatDateTimeStr(series.getOldestRecord().timestamp);
              this.endDateTime = this.formatDateTimeStr(series.getLatestRecord().timestamp);
              //stats = series.getStats();
              stats = {
                min: series.min_record,
                max: series.max_record,
                most_recent: series.getLatestRecord()
              }
            }
            else
            {
              console.error("Timeseries ID: " + timeseries_id + " is undefined.");
            }
          }
          return {
            key: `${sensor.obsStandardName}-${sensor.order}`,
            obsStandardName: timeseries_id,
            channelLabel: sensor.channelLabel,
            units: sensor.uomDisplay || sensor.uomStandardName,
            stats,
          };
        });
      },
      formatObservationValue(value) {
        if (value === null || value === undefined) return "No data";
        if (!Number.isFinite(Number(value))) return String(value);

        return Number(value).toFixed(2);
      },

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
