import logging.config
from typing import Any, Dict, Iterator, List, Literal, Optional, Union

import requests

logger = logging.getLogger(__name__)
logger.info(f"{__name__} logger opened.")

STATION_METADATA_FIELDS = [
    "name",
    "icon",
    "model",
    "hardware",
    "location_type",
    "private",
    "latitude",
    "longitude",
    "altitude",
    "position_rating",
    "led_brightness",
    "firmware_version",
    "firmware_upgrade",
    "rssi",
    "uptime",
    "pa_latency",
    "memory",
    "last_seen",
    "last_modified",
    "date_created",
    "channel_state",
    "channel_flags",
    "channel_flags_manual",
    "channel_flags_auto",
    "confidence",
    "confidence_manual",
    "confidence_auto",
]

ENVIRONMENT_FIELDS = [
    "humidity",
    "humidity_a",
    "humidity_b",
    "temperature",
    "temperature_a",
    "temperature_b",
    "pressure",
    "pressure_a",
    "pressure_b",
]

MISCELLANEOUS_FIELDS = ["voc", "voc_a", "voc_b", "ozone1", "analog_input"]

PM1_FIELDS = [
    "pm1.0",
    "pm1.0_a",
    "pm1.0_b",
    "pm1.0_atm",
    "pm1.0_atm_a",
    "pm1.0_atm_b",
    "pm1.0_cf_1",
    "pm1.0_cf_1_a",
    "pm1.0_cf_1_b",
]

PM2_FIELDS = [
    "pm2.5_atm",
    "pm2.5_atm_a",
    "pm2.5_atm_b",
    "pm2.5_cf_1",
    "pm2.5_cf_1_a",
    "pm2.5_cf_1_b",
]

PM2_PSEUDO_FIELDS = [
    "pm2.5_10minute",
    "pm2.5_10minute_a",
    "pm2.5_10minute_b",
    "pm2.5_30minute",
    "pm2.5_30minute_a",
    "pm2.5_30minute_b",
    "pm2.5_60minute",
    "pm2.5_60minute_a",
    "pm2.5_60minute_b",
    "pm2.5_6hour",
    "pm2.5_6hour_a",
    "pm2.5_6hour_b",
    "pm2.5_24hour",
    "pm2.5_24hour_a",
    "pm2.5_24hour_b",
    "pm2.5_1week",
    "pm2.5_1week_a",
    "pm2.5_1week_b",
]

PM10_FIELDS = [
    "pm10.0",
    "pm10.0_a",
    "pm10.0_b",
    "pm10.0_atm",
    "pm10.0_atm_a",
    "pm10.0_atm_b",
    "pm10.0_cf_1",
    "pm10.0_cf_1_a",
    "pm10.0_cf_1_b",
]

VISIBILITY_FIELDS = [
    "scattering_coefficient",
    "scattering_coefficient_a",
    "scattering_coefficient_b",
    "deciviews",
    "deciviews_a",
    "deciviews_b",
    "visual_range",
    "visual_range_a",
    "visual_range_b",
]

PARTICLE_COUNT_FIELDS = [
    "0.3_um_count",
    "0.3_um_count_a",
    "0.3_um_count_b",
    "0.5_um_count",
    "0.5_um_count_a",
    "0.5_um_count_b",
    "1.0_um_count",
    "1.0_um_count_a",
    "1.0_um_count_b",
    "2.5_um_count",
    "2.5_um_count_a",
    "2.5_um_count_b",
    "5.0_um_count",
    "5.0_um_count_a",
    "5.0_um_count_b",
    "10.0_um_count",
    "10.0_um_count_a",
    "10.0_um_count_b",
]

AVERAGES = [0, 10, 30, 60, 360, 1440, 10080, 43200, 525600]


class PurpleAirAPIError(Exception):
    """Custom exception for errors interacting with PurpleAir API."""

    pass


class PurpleAirClient:
    BASE_URL = "https://api.purpleair.com/v1"

    def __init__(self, api_key: str, timeout: float = 10.0):
        if not api_key:
            logger.error("API key must be provided.")
            raise ValueError("API key must be provided.")
        self.api_key = api_key
        self.headers = {
            "X-API-Key": self.api_key
            # "Accept": "application/json",
            # "Content-Type": "application/json",
        }
        self.timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> Union[Dict[str, Any], str, Iterator[str]]:
        url = f"{self.BASE_URL}{path}"
        resp = requests.request(
            method,
            url,
            headers=self.headers,
            params=params,
            json=json_body,
            timeout=self.timeout,
        )
        if resp.status_code < 200 or resp.status_code >= 300:
            try:
                err = resp.json()
                logger.error(err)
            except Exception as e:
                err = resp.text
                logger.exception(e)
            raise PurpleAirAPIError(f"Error {resp.status_code} {method} {url}: {err}")
        try:
            content_type = resp.headers.get("Content-Type", "").lower()
            if content_type == "application/json":
                data = resp.json()
                try:
                    resp.close()
                except Exception:
                    pass
                return data
            # If caller asked for streaming, return a safe iterator of decoded lines
            if stream:

                def _line_iterator() -> Iterator[str]:
                    try:
                        # decode_unicode=True yields str lines
                        for raw_line in resp.iter_lines(decode_unicode=True):
                            # iter_lines can yield b'' or None; skip falsy empty lines? keep them if important
                            # We yield the line exactly as iter_lines provided (it is already str)
                            yield raw_line
                    finally:
                        # always close the response to release the connection
                        try:
                            resp.close()
                        except Exception:
                            pass

                return _line_iterator()

            else:
                return resp.text
        except Exception as e:
            logger.exception(e)
            raise PurpleAirAPIError(f"Non-JSON response {method} {url}: {e}")

    # ----- Organization endpoints -----
    #
    # Documentation is lighter here; adjust if your account has more operations.

    def get_organization(self) -> Dict[str, Any]:
        """
        GET /v1/organization
        Retrieve details of the organization to which your API key belongs.
        """
        path = "/organization"
        return self._request("GET", path)

    # ----- Sensor endpoints -----

    def get_sensor(
        self, sensor_index: int, fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        GET /v1/sensors/{sensor_index}
        Retrieve real-time (or latest) data for a specific sensor.
        :param sensor_index: sensor’s unique index
        :param fields: list of fields to include (optional)
        """
        path = f"/sensors/{sensor_index}"
        params: Dict[str, Any] = {}
        if fields:
            params["fields"] = ",".join(fields)
        return self._request("GET", path, params=params)

    def get_sensors(
        self,
        sensor_indices: List[int],
        fields: Optional[List[str]] = None,
        show_only: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        GET /v1/sensors
        Retrieve real-time data for multiple sensors.
        :param sensor_indices: list of sensor_index values
        :param fields: list of fields to include
        :param show_only: optional filter to show only certain sensor indices
        """
        path = "/sensors"
        params: Dict[str, Any] = {}
        if sensor_indices:
            params["sensor_index"] = ",".join(str(i) for i in sensor_indices)
        if show_only:
            params["show_only"] = ",".join(str(i) for i in show_only)
        if fields:
            params["fields"] = ",".join(fields)
        return self._request("GET", path, params=params)

    def get_sensor_history(
        self,
        sensor_index: int,
        start_timestamp: int,
        end_timestamp: int,
        average: Optional[int] = None,
        fields: Optional[List[str]] = None,
        return_format: Literal["json", "csv"] = "json",
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        GET /v1/sensors/{sensor_index}/history
        Retrieve historical data for a given sensor, between given timestamps.
        Requires that your key/account has access to history endpoints.
        :param sensor_index: sensor index
        :param start_timestamp: UNIX epoch (seconds) or as required by API
        :param end_timestamp: UNIX epoch
        :param average: averaging interval, if supported
        :param fields: which fields to return
        """
        path = f"/sensors/{sensor_index}/history"
        params: Dict[str, Any] = {
            "start_timestamp": start_timestamp,
            "end_timestamp": end_timestamp,
        }
        if average is not None:
            params["average"] = average
        if fields:
            params["fields"] = ",".join(fields)
        if return_format == "csv":
            # self.headers["Content-Type"] = "application/json"
            path = f"{path}/csv"
        return self._request("GET", path, params=params, stream=stream)

    # ----- Group endpoints -----

    def create_group(self, name: str) -> Dict[str, Any]:
        """
        POST /v1/groups
        Create a new group given a name. Returns group metadata.
        Requires WRITE access.
        """
        path = "/groups"
        body = {"name": name}
        return self._request("POST", path, json_body=body)

    def get_groups(self) -> Dict[str, Any]:
        """
        GET /v1/groups
        List all groups you own.
        """
        path = "/groups"
        return self._request("GET", path)

    def get_group_detail(self, group_id: int) -> Dict[str, Any]:
        """
        GET /v1/groups/{group_id}
        Get detail of a specific group, including its members.
        """
        path = f"/groups/{group_id}"
        return self._request("GET", path)

    def update_group(self, group_id: int, name: Optional[str] = None) -> Dict[str, Any]:
        """
        PUT /v1/groups/{group_id}
        Update metadata for a group (e.g. rename).
        """
        path = f"/groups/{group_id}"
        body: Dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if not body:
            raise ValueError("No fields to update for group.")
        return self._request("PUT", path, json_body=body)

    def delete_group(self, group_id: int) -> Dict[str, Any]:
        """
        DELETE /v1/groups/{group_id}
        Delete the specified group.
        """
        path = f"/groups/{group_id}"
        return self._request("DELETE", path)

    def add_member_to_group(self, group_id: int, sensor_index: int) -> Dict[str, Any]:
        """
        POST /v1/groups/{group_id}/members
        Add a sensor (by sensor_index) to a group.
        """
        path = f"/groups/{group_id}/members"
        body = {"sensor_index": sensor_index}
        return self._request("POST", path, json_body=body)

    def remove_member_from_group(self, group_id: int, member_id: int) -> Dict[str, Any]:
        """
        DELETE /v1/groups/{group_id}/members/{member_id}
        Remove a member (sensor) from the group.
        """
        path = f"/groups/{group_id}/members/{member_id}"
        return self._request("DELETE", path)

    def get_members_data(
        self,
        group_id: int,
        fields: Optional[List[str]] = None,
        modified_since: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        GET /v1/groups/{group_id}/members/data
        Get real-time data for all members in a group.
        :param fields: which data fields to include
        :param modified_since: only sensors modified since this timestamp
        """
        path = f"/groups/{group_id}/members/data"
        params: Dict[str, Any] = {}
        if fields:
            params["fields"] = ",".join(fields)
        if modified_since is not None:
            params["modified_since"] = modified_since
        return self._request("GET", path, params=params)

    def get_member_data(
        self, group_id: int, member_id: int, fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        GET /v1/groups/{group_id}/members/{member_id}/data
        Get data for a specific member in a group.
        """
        path = f"/groups/{group_id}/members/{member_id}/data"
        params: Dict[str, Any] = {}
        if fields:
            params["fields"] = ",".join(fields)
        return self._request("GET", path, params=params)
