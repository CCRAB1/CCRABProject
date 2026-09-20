import Alpine from "alpinejs";
import {DateTime} from "luxon";

import { StatsJtsDocument }
  from "../../../../static/js/StatsTimeSeries/src/index.js";
import {getAQIColorCode} from "./calculations.js";

export function registerPlatformCatalogComponents(Alpine) {
  Alpine.data("platformCatalog", function () {
    const documents = new Map();

    return {
      dataRevision: 0,
      loadError: null,

      init() {
        const element = document.getElementById(
          "platforms-jts-documents"
        );

        if (!element) {
          return;
        }

        try {
          const payload = JSON.parse(element.textContent);

          for (
            const [platformHandle, jtsPayload]
            of Object.entries(payload)
          ) {
            if (!jtsPayload) {
              continue;
            }

            documents.set(
              platformHandle,
              StatsJtsDocument.from(jtsPayload)
            );
          }

          this.dataRevision += 1;
        } catch (error) {
          console.error(
            "Unable to parse platform observations",
            error
          );

          this.loadError =
            "Platform observations could not be loaded.";
        }
      },

      getSeries(platformHandle, observationId) {
        this.dataRevision;

        const document = documents.get(platformHandle);

        if (!document) {
          return undefined;
        }

        return document.getSeries(observationId) || null;
      },

      getLatestRecord(platformHandle, observationId) {
        const series = this.getSeries(
          platformHandle,
          observationId
        );

        return series
          ? series.getLatestRecord()
          : undefined;
      },

      getLatestValue(platformHandle, observationId) {
        const record = this.getLatestRecord(
          platformHandle,
          observationId
        );

        return record ? record.value : undefined;
      },

      getLatestTimestamp(platformHandle, observationId) {
        const record = this.getLatestRecord(
          platformHandle,
          observationId
        );

        return record ? record.timestamp : undefined;
      },

      hasObservation(platformHandle, observationId) {
        return this.getLatestRecord(
          platformHandle,
          observationId
        ) !== undefined;
      },

      getObservationRange(platformHandle, observationId) {
        const value = Number(
          this.getLatestValue(
            platformHandle,
            observationId
          )
        );

        if (!Number.isFinite(value)) {
          return undefined;
        }

        return getAQIColorCode(value);
      },

      getObservationCategory(platformHandle, observationId) {
        const range = this.getObservationRange(
          platformHandle,
          observationId
        );

        return range ? range.category : "Unknown";
      },

      observationStyle(platformHandle, observationId) {
        const range = this.getObservationRange(
          platformHandle,
          observationId
        );

        return {
          "--platform-aqi-color": range !== undefined ? range.color : "#b5b5b5",
        };
      },

      formatObservationValue(value) {
        const numericValue = Number(value);

        if (!Number.isFinite(numericValue)) {
          return "—";
        }

        return Math.round(numericValue).toString();
      },

      formatObservationTimestamp(timestamp) {
        if (!(timestamp instanceof Date)) {
          return "unknown";
        }

        return DateTime
          .fromJSDate(timestamp)
          .toFormat("MMM d, h:mm a");
      },

      observationAriaLabel(platformHandle, observationId) {
        const value = this.getLatestValue(
          platformHandle,
          observationId
        );

        if (value === null || value === undefined) {
          return "No recent PM2.5 AQI observation";
        }

        const category = this.getObservationCategory(
          platformHandle,
          observationId
        );

        return `Current PM2.5 AQI ${Math.round(value)}, ${category}`;
      },
    };
  });
}
