(function () {
  "use strict";

  function replaceSensorOptions(sensorSelect, sensors, selectedValue) {
    var matchedSelection = selectedValue === "";

    sensorSelect.options.length = 0;
    sensorSelect.add(new Option("---------", ""));

    for (var index = 0; index < sensors.length; index += 1) {
      var sensor = sensors[index];
      var option = new Option(sensor.label, sensor.value);

      if (String(sensor.value) === selectedValue) {
        option.selected = true;
        matchedSelection = true;
      }

      sensorSelect.add(option);
    }

    if (!matchedSelection) {
      sensorSelect.value = "";
    }

    sensorSelect.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function getSensorOptionsUrl(platformSourceSelect) {
    var wrapper = platformSourceSelect.closest(".related-widget-wrapper");

    if (platformSourceSelect.dataset.sensorOptionsUrl) {
      return platformSourceSelect.dataset.sensorOptionsUrl;
    }

    if (wrapper && wrapper.dataset.sensorOptionsUrl) {
      return wrapper.dataset.sensorOptionsUrl;
    }

    return "";
  }

  function loadSensorOptions(platformSourceSelect, sensorSelect) {
    var optionsUrl = getSensorOptionsUrl(platformSourceSelect);
    var platformSourceId = platformSourceSelect.value;
    var selectedSensorId = sensorSelect.value;
    var requestUrl;

    if (!optionsUrl) {
      return;
    }

    if (!platformSourceId) {
      replaceSensorOptions(sensorSelect, [], "");
      return;
    }

    requestUrl = optionsUrl + "?platform_source_id=" + encodeURIComponent(platformSourceId);

    fetch(requestUrl, {
      credentials: "same-origin",
      headers: {
        "X-Requested-With": "XMLHttpRequest",
      },
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Unable to load sensor options.");
        }
        return response.json();
      })
      .then(function (data) {
        replaceSensorOptions(sensorSelect, data.sensors || [], selectedSensorId);
      })
      .catch(function () {
        replaceSensorOptions(sensorSelect, [], "");
      });
  }

  function initializeSensorFilter() {
    var platformSourceSelect = document.getElementById("id_platform_source_id");
    var sensorSelect = document.getElementById("id_sensor_id");

    if (!platformSourceSelect || !sensorSelect) {
      return;
    }

    platformSourceSelect.addEventListener("change", function () {
      loadSensorOptions(platformSourceSelect, sensorSelect);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeSensorFilter);
  } else {
    initializeSensorFilter();
  }
})();
