"""OpenAPI contract and public reference for the platforms API."""

import json

from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_safe


def parameter(name, description, required=False, location="query", example=None):
    result = {
        "name": name,
        "in": location,
        "required": required,
        "description": description,
        "schema": {"type": "string"},
    }
    if example is not None:
        result["example"] = example
    return result


def ref(name):
    return {"$ref": f"#/components/schemas/{name}"}


def operation(
    identifier,
    summary,
    description,
    schema,
    parameters=(),
    public=False,
    errors=(),
    deprecated=False,
):
    responses = {
        "200": {
            "description": "Successful response",
            "content": {"application/json": {"schema": schema}},
        }
    }
    for code, message in errors:
        responses[str(code)] = {
            "description": message,
            "content": {"application/json": {"schema": ref("Error")}},
        }
    if not public:
        responses["401"] = {"description": "Missing, expired, or invalid bearer token."}
    return {
        "operationId": identifier,
        "summary": summary,
        "description": description,
        "tags": ["Platforms"],
        "parameters": list(parameters),
        "security": [] if public else [{"bearerAuth": []}],
        "deprecated": deprecated,
        "responses": responses,
    }


def build_schema():
    bbox = parameter(
        "bbox",
        "Bounding box: min_lon,min_lat,max_lon,max_lat. Malformed values are ignored.",
        example="-80.1,32.7,-79.8,33.0",
    )
    filters = [
        parameter(
            "name",
            "Case-insensitive partial short_name match. Takes precedence over bbox.",
        ),
        bbox,
    ]
    paths = {}

    def add(route, op):
        paths[reverse(route)] = {"get": op}

    collection = operation(
        "listPlatforms",
        "List platforms",
        (
            "Returns an unpaginated GeoJSON FeatureCollection. Sensors follow the "
            "platform's serving policy."
        ),
        ref("PlatformCollection"),
        filters,
    )
    add("platform-list-api", collection)
    detail_path = reverse(
        "platform-detail-api", kwargs={"short_name": "SHORT_NAME"}
    ).replace("SHORT_NAME", "{short_name}")
    paths[detail_path] = {
        "get": operation(
            "getPlatform",
            "Get a platform",
            (
                "Returns the first case-insensitive partial short_name match, "
                "optionally constrained by bbox."
            ),
            ref("Platform"),
            [
                parameter(
                    "short_name", "Platform short name (partial match).", True, "path"
                ),
                bbox,
            ],
            errors=[(404, "No matching platform.")],
        )
    }
    add(
        "platform-list-web-data",
        operation(
            "legacyPlatformList",
            "Legacy public platform list",
            (
                "Public alias for the platform collection; prefer the authenticated "
                "collection for API integrations."
            ),
            ref("PlatformCollection"),
            filters,
            public=True,
            deprecated=True,
        ),
    )
    add(
        "platforminfo",
        operation(
            "legacyPlatformInfo",
            "Legacy authenticated platform list",
            "Alias for the authenticated platform collection.",
            ref("PlatformCollection"),
            filters,
            deprecated=True,
        ),
    )
    add(
        "platform-configuration-api",
        operation(
            "getPlatformConfiguration",
            "Get platform display configuration",
            (
                "Includes all sensors and their display flags, including sensors "
                "excluded from served observations. Uses the first partial short_name "
                "match."
            ),
            ref("PlatformConfiguration"),
            [
                parameter("short_name", "Platform short name (partial match).", True),
                bbox,
            ],
            public=True,
            errors=[(400, "Missing short_name."), (404, "No matching platform.")],
        ),
    )
    add(
        "platform_configuration",
        operation(
            "getSourceConfiguration",
            "Get ingestion source configuration",
            (
                "Requires a JWT for a user in the private_api_access group. Returns "
                "active platforms for the selected active data source, grouped by "
                "organization, with observation mappings."
            ),
            ref("SourceConfiguration"),
            [
                parameter(
                    "data_source",
                    "Data source key. Defaults to purple_air.",
                    example="purple_air",
                )
            ],
            errors=[(403, "User lacks private_api_access group membership.")],
        ),
    )
    add(
        "platform_data_request",
        operation(
            "getPlatformObservations",
            "Request observations",
            (
                "Returns a GeoJSON Feature with JSON timeseries in "
                "properties.timeseries. Date bounds are inclusive; start_date must "
                "not exceed end_date. Only served observation/order pairs are "
                "accepted. No readings returns timeseries: []."
            ),
            ref("ObservationFeature"),
            [
                parameter(
                    "platform_handle",
                    "Exact platform_handle from platform properties.",
                    True,
                ),
                parameter(
                    "start_date",
                    "ISO 8601 datetime; use an explicit timezone.",
                    True,
                    example="2026-01-01T00:00:00Z",
                ),
                parameter(
                    "end_date",
                    "ISO 8601 datetime; use an explicit timezone.",
                    True,
                    example="2026-01-02T00:00:00Z",
                ),
                parameter(
                    "observations",
                    (
                        "Comma-separated '<obs_standard_name> <s_order>' pairs from "
                        "the platform's sensors. Duplicate pairs are removed."
                    ),
                    True,
                    example="pm2_5 1,air_temperature 1",
                ),
            ],
            public=True,
            errors=[
                (
                    400,
                    (
                        "Missing or invalid parameters, unknown platform, reversed "
                        "dates, or unavailable observation/order pair."
                    ),
                )
            ],
        ),
    )
    sensor_properties = {}
    for field in (
        "short_name",
        "obs_standard_name",
        "obs_definition",
        "info_url",
        "uom_display",
        "uom_standard_name",
        "uom_definition",
    ):
        sensor_properties[field] = {"type": "string", "nullable": True}
    for field in ("s_order", "active"):
        sensor_properties[field] = {"type": "integer", "nullable": True}
    properties = {"sensors": {"type": "array", "items": ref("Sensor")}}
    for field in (
        "begin_date",
        "end_date",
        "short_name",
        "long_name",
        "platform_handle",
        "description",
        "neighborhood",
        "manufacturer",
        "serial_number",
        "firmware_version",
        "country_name",
        "city",
        "url",
    ):
        properties[field] = {"type": "string", "nullable": True}
    for field in ("fixed_latitude", "fixed_longitude"):
        properties[field] = {"type": "number", "nullable": True}
    properties.update(
        {
            "active": {"type": "integer", "nullable": True},
            "type_id": {"type": "object", "nullable": True},
            "images": {"type": "array", "items": {"type": "object"}},
        }
    )
    schemas = {
        "Error": {
            "type": "object",
            "description": (
                "A detail message or field names mapped to validation error lists."
            ),
            "additionalProperties": True,
        },
        "Sensor": {"type": "object", "properties": sensor_properties},
        "Geometry": {
            "type": "object",
            "nullable": True,
            "properties": {
                "type": {"type": "string", "example": "Point"},
                "coordinates": {"type": "array", "items": {"type": "number"}},
            },
        },
        "Platform": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["Feature"]},
                "geometry": ref("Geometry"),
                "properties": {"type": "object", "properties": properties},
            },
        },
        "PlatformCollection": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["FeatureCollection"]},
                "features": {"type": "array", "items": ref("Platform")},
            },
        },
        "PlatformConfiguration": {
            "allOf": [
                ref("Platform"),
                {
                    "type": "object",
                    "properties": {
                        "properties": {
                            "type": "object",
                            "properties": {
                                "sensors": {
                                    "type": "array",
                                    "items": {
                                        "allOf": [
                                            ref("Sensor"),
                                            {
                                                "type": "object",
                                                "properties": {
                                                    "display": {"type": "boolean"}
                                                },
                                            },
                                        ]
                                    },
                                }
                            },
                        }
                    },
                },
            ]
        },
        "SourceConfiguration": {
            "type": "object",
            "properties": {
                "organizations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "org_id": {"type": "integer"},
                            "short_name": {"type": "string"},
                            "long_name": {"type": "string"},
                            "platforms": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "description": (
                                        "Source platform metadata, "
                                        "external_identifier, active flag and "
                                        "observations with source/target names, "
                                        "units, activity flags, sensor_id, m_type_id "
                                        "and s_order."
                                    ),
                                },
                            },
                        },
                    },
                }
            },
        },
        "ObservationFeature": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["Feature"]},
                "geometry": ref("Geometry"),
                "properties": {
                    "type": "object",
                    "properties": {
                        "platform_handle": {"type": "string"},
                        "start_date": {"type": "string"},
                        "end_date": {"type": "string"},
                        "timeseries": {
                            "oneOf": [
                                {
                                    "type": "object",
                                    "description": (
                                        "JSON timeseries document with header and data."
                                    ),
                                },
                                {"type": "array", "maxItems": 0},
                            ]
                        },
                    },
                },
            },
        },
    }
    mapping_properties = {}
    for field in (
        "source_obs",
        "source_uom",
        "source_identifier",
        "target_obs",
        "target_uom",
    ):
        mapping_properties[field] = {"type": "string", "nullable": True}
    for field in (
        "source_active",
        "target_active",
        "sensor_id",
        "m_type_id",
        "s_order",
    ):
        mapping_properties[field] = {"type": "integer", "nullable": True}
    source_properties = {
        "observations": {"type": "array", "items": ref("ObservationMapping")},
        "active": {"type": "integer", "nullable": True},
    }
    for field in (
        "platform_handle",
        "short_name",
        "external_identifier",
        "country_code",
        "neighborhood",
    ):
        source_properties[field] = {"type": "string", "nullable": True}
    for field in ("latitude", "longitude"):
        source_properties[field] = {"type": "number", "nullable": True}
    schemas["ObservationMapping"] = {"type": "object", "properties": mapping_properties}
    schemas["SourcePlatform"] = {"type": "object", "properties": source_properties}
    organization = schemas["SourceConfiguration"]["properties"]["organizations"][
        "items"
    ]
    organization["properties"]["platforms"]["items"] = ref("SourcePlatform")
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "CCRAB Platforms API",
            "version": "1.0.0",
            "description": (
                "Platform metadata, display configuration, ingestion mappings, and "
                "observations. Other CCRAB APIs are outside this reference."
            ),
        },
        "tags": [{"name": "Platforms"}],
        "paths": paths,
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                }
            },
            "schemas": schemas,
        },
    }


@require_safe
def openapi_schema(request):
    return JsonResponse(build_schema(), json_dumps_params={"indent": 2})


@require_safe
def api_help(request):
    schema = build_schema()
    endpoints = []
    for path, methods in schema["paths"].items():
        op = methods["get"].copy()
        op["path"] = path
        op["response_json"] = json.dumps(
            op["responses"]["200"]["content"]["application/json"]["schema"], indent=2
        )
        endpoints.append(op)
    return render(
        request,
        "platforms_app/api_help.html",
        {
            "schema": schema,
            "endpoints": endpoints,
            "schemas_json": json.dumps(schema["components"]["schemas"], indent=2),
        },
    )
