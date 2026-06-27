import { DateTime } from "../../vendor/luxon/3.7.2/luxon.min.js";

export class PlatformInfo {
  constructor(serializedPayload) {
    var feature = PlatformInfo.firstFeatureFromPayload(serializedPayload) || {};
    var properties = feature.properties || {};
    var type = properties.type_id || {};
    var coordinates = PlatformInfo.parseCoordinates(properties, feature.geometry);

    this.beginDate = properties.begin_date || null;
    this.endDate = properties.end_date || null;
    this.shortName = properties.short_name || "";
    this.longName = properties.long_name || "";
    this.platformHandle = properties.platform_handle || "";
    this.description = properties.description || "";
    this.active = PlatformInfo.parseBoolean(properties.active);
    this.fixedLatitude = coordinates.latitude;
    this.fixedLongitude = coordinates.longitude;
    this.typeName = type.type_name || "";
    this.typeDescription = type.description || "";
    this.typeShortName = type.short_name || "";
    this.sensors = PlatformInfo.parseSensors(properties.sensors);
    this.neighborhood = properties.neighborhood || "";
    this.manufacturer = properties.manufacturer || "";
    this.serialNumber = properties.serial_number || "";
    this.firmwareVersion = properties.firmware_version || "";
    this.countryName = properties.country_name || "";
    this.city = properties.city || "";
    this.images = PlatformInfo.parseImages(properties.images);
    this.url = properties.url || "";
  }

  static parse(serializedPayload) {
    var payload = PlatformInfo.parseSerializedPayload(serializedPayload);

    if (payload && payload.platform_info) {
      return PlatformInfo.parse(payload.platform_info);
    }

    if (
      Array.isArray(payload) ||
      (payload && payload.type === "FeatureCollection" && Array.isArray(payload.features))
    ) {
      return new PlatformInfoCollection(payload);
    }

    return new PlatformInfo(payload);
  }

  static fromScriptElement(elementId) {
    var dataElement = document.getElementById(elementId);
    return dataElement ? PlatformInfo.parse(dataElement.textContent) : undefined;
  }

  static fetch(url, options) {
    return window.fetch(url, options).then(function (response) {
      if (!response.ok) {
        throw new Error("PlatformInfo request failed: " + response.status);
      }

      return response.json();
    }).then(function (payload) {
      return PlatformInfo.parse(payload);
    });
  }

  static parseSerializedPayload(serializedPayload) {
    if (!serializedPayload) return null;
    if (typeof serializedPayload !== "string") return serializedPayload;

    try {
      return JSON.parse(serializedPayload);
    } catch (error) {
      console.warn("Unable to parse platform info payload", error);
      return null;
    }
  }

  static featureListFromPayload(serializedPayload) {
    var payload = PlatformInfo.parseSerializedPayload(serializedPayload);

    if (!payload) return [];
    if (payload.platform_info) {
      return PlatformInfo.featureListFromPayload(payload.platform_info);
    }
    if (payload.type === "Feature") return [payload];
    if (payload.type === "FeatureCollection" && Array.isArray(payload.features)) {
      return payload.features;
    }
    if (Array.isArray(payload)) return payload;
    if (payload.properties) return [payload];

    return [];
  }

  static firstFeatureFromPayload(serializedPayload) {
    var features = PlatformInfo.featureListFromPayload(serializedPayload);
    return features.length ? features[0] : null;
  }

  static parseNumber(value) {
    var parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  static parseBoolean(value) {
    if (typeof value === "boolean") return value;
    if (typeof value === "number") return value !== 0;
    if (typeof value === "string") {
      return value.toLowerCase() === "true" || value === "1";
    }

    return false;
  }

  static parseDate(value) {
    if (!value) return null;

    var parsed = DateTime.fromISO(value);
    return parsed.isValid ? parsed : null;
  }

  static parseCoordinates(properties, geometry) {
    var sourceProperties = properties || {};
    var latitude = PlatformInfo.parseNumber(sourceProperties.fixed_latitude);
    var longitude = PlatformInfo.parseNumber(sourceProperties.fixed_longitude);

    if ((latitude === null || longitude === null) && geometry) {
      var coordinates = geometry.coordinates || [];
      longitude = longitude === null
        ? PlatformInfo.parseNumber(coordinates[0])
        : longitude;
      latitude = latitude === null
        ? PlatformInfo.parseNumber(coordinates[1])
        : latitude;
    }

    return {
      latitude: latitude,
      longitude: longitude,
    };
  }

  static normalizeSensor(sensor) {
    var source = sensor || {};
    var order = PlatformInfo.parseNumber(source.s_order);

    return {
      shortName: source.short_name || "",
      order: order,
      channelLabel: order === 1 ? "A" : "B",
      obsStandardName: source.obs_standard_name || "",
      obsDefinition: source.obs_definition || "",
      uomDisplay: source.uom_display || "",
      uomStandardName: source.uom_standard_name || "",
      uomDefinition: source.uom_definition || "",
    };
  }

  static normalizeImage(image) {
    var source = image || {};

    return {
      rowId: source.row_id || null,
      name: source.name || "",
      description: source.description || "",
      filepath: source.filepath || "",
    };
  }

  static parseSensors(sensors) {
    var normalized = [];
    var sourceSensors = Array.isArray(sensors) ? sensors : [];

    for (var i = 0; i < sourceSensors.length; i += 1) {
      normalized.push(PlatformInfo.normalizeSensor(sourceSensors[i]));
    }

    return normalized;
  }

  static parseImages(images) {
    var normalized = [];
    var sourceImages = Array.isArray(images) ? images : [];

    for (var i = 0; i < sourceImages.length; i += 1) {
      normalized.push(PlatformInfo.normalizeImage(sourceImages[i]));
    }

    return normalized;
  }

  static findByShortName(collection, shortName) {
    if (!collection || typeof collection.findByShortName !== "function") {
      return undefined;
    }

    return collection.findByShortName(shortName);
  }

  get hasCoordinates() {
    return this.fixedLatitude !== null && this.fixedLongitude !== null;
  }

  observationNames() {
    var observationList = [];

    for (var i = 0; i < this.sensors.length; i += 1) {
      var sensor = this.sensors[i];
      var observationName = sensor.obsStandardName || sensor.shortName;
      if (observationName && observationList.indexOf(observationName) === -1) {
        observationList.push(observationName);
      }
    }

    return observationList;
  }

  observationQueryValue() {
    return this.observationNames().join(",");
  }

  observationRequestParams(startDate, endDate) {
    var params = new URLSearchParams();
    params.set("platform_handle", this.platformHandle);
    params.set("observations", this.observationQueryValue());

    if (startDate && startDate.toISO) params.set("start_date", startDate.toISO());
    else if (startDate) params.set("start_date", String(startDate));

    if (endDate && endDate.toISO) params.set("end_date", endDate.toISO());
    else if (endDate) params.set("end_date", String(endDate));

    return params;
  }

  parsedBeginDate() {
    return PlatformInfo.parseDate(this.beginDate);
  }

  parsedEndDate() {
    return PlatformInfo.parseDate(this.endDate);
  }

  displayName() {
    return this.longName || this.shortName;
  }
}

export class PlatformInfoCollection {
  constructor(serializedPayload) {
    var features = PlatformInfo.featureListFromPayload(serializedPayload);

    this.items = [];
    for (var i = 0; i < features.length; i += 1) {
      this.items.push(new PlatformInfo(features[i]));
    }
  }

  findByShortName(shortName) {
    for (var i = 0; i < this.items.length; i += 1) {
      if (this.items[i].shortName === shortName) {
        return this.items[i];
      }
    }

    return undefined;
  }
}
