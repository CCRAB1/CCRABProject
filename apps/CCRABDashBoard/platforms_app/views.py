from django.db.models import F, Prefetch, Q
from django.http import Http404, JsonResponse, request
from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from CCRABDashboard.api_permissions import HasPrivateApiAccess
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
import json
import logging
from .models import Platform, Sensor, SourceObservationMap, PlatformSource
from .serializers import PlatformSerializer, PlatformSourceConfigurationSerializer

logger = logging.getLogger(__name__)

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # The header can contain a comma-separated list of IPs; the first is the client
        ip = x_forwarded_for.split(',')[0]
    else:
        # Fallback to direct remote address
        ip = request.META.get('REMOTE_ADDR')
    return ip

def request_log(request, api_id, level, message, **kwargs):
    client_ip = get_client_ip(request=request)
    log_message = f"Client IP: {client_ip} {api_id} {message}"
    if level == "DEBUG":
        logger.debug(log_message)
    elif level == "INFO":
        logger.info(log_message)
    elif level == "ERROR":
        logger.error(log_message)
    else:
        logger.info(log_message)


def _parse_bbox(bbox_str):
    """Parse bbox string "min_lon,min_lat,max_lon,max_lat" -> tuple of floats or None."""
    if not bbox_str:
        return None
    parts = bbox_str.split(",")
    if len(parts) != 4:
        return None
    try:
        min_lon, min_lat, max_lon, max_lat = map(float, parts)
        return (min_lon, min_lat, max_lon, max_lat)
    except ValueError:
        return None


class PlatformViewSet(APIView):
    """
    List / Retrieve platforms. Supports filtering the list by:
      - ?name=<partial_name>      (matches short_name or platform_handle)
      - ?bbox=min_lon,min_lat,max_lon,max_lat
    Returns platforms with a `sensors` attribute (populated by Prefetch).
    """

    def get(self, request):
        payload = _platform_collection_payload(request.query_params, request)
        return Response(payload)


def _platform_sensor_queryset():
    sensor_qs = (
        Sensor.objects.select_related(
            "m_type_id__m_scalar_type_id__obs_type_id",
            "m_type_id__m_scalar_type_id__uom_type_id",
        )
        .annotate(
            obs_standard_name=F("m_type_id__m_scalar_type_id__obs_type_id__standard_name"),
            obs_definition=F("m_type_id__m_scalar_type_id__obs_type_id__definition"),
            uom_display=F("m_type_id__m_scalar_type_id__uom_type_id__display"),
            uom_standard_name=F("m_type_id__m_scalar_type_id__uom_type_id__standard_name"),
            uom_definition=F("m_type_id__m_scalar_type_id__uom_type_id__definition"),
        )
        .order_by("obs_standard_name")
    )
    return sensor_qs


def _platform_queryset():
    qs = Platform.objects.all()
    sensor_qs = _platform_sensor_queryset()
    qs = qs.prefetch_related(
        Prefetch("sensor_set", queryset=sensor_qs, to_attr="sensors"),
        "platform_images_set",
    )
    return qs


def _platform_collection_payload(query_params, request):
    qs = _platform_queryset()

    name = query_params.get("name", None)
    bbox = _parse_bbox(query_params.get("bbox"))
    if name:
        qs = qs.filter(Q(short_name__icontains=name))

    elif bbox:
        min_lon, min_lat, max_lon, max_lat = bbox
        qs = qs.filter(
            fixed_longitude__gte=min_lon,
            fixed_longitude__lte=max_lon,
            fixed_latitude__gte=min_lat,
            fixed_latitude__lte=max_lat,
        )

    platforms = list(qs)
    serialized = PlatformSerializer(platforms, many=True, context={"request": request}).data
    return serialized


def _platform_detail_payload(query_params, request, short_name=None):
    qs = _platform_queryset()

    if short_name:
        qs = qs.filter(Q(short_name__icontains=short_name))

    bbox = _parse_bbox(query_params.get("bbox"))
    if bbox:
        min_lon, min_lat, max_lon, max_lat = bbox
        qs = qs.filter(
            fixed_longitude__gte=min_lon,
            fixed_longitude__lte=max_lon,
            fixed_latitude__gte=min_lat,
            fixed_latitude__lte=max_lat,
        )

    platform_rows = list(qs[:1])
    if not platform_rows:
        raise Http404("Platform not found")

    platform = platform_rows[0]
    serialized = dict(PlatformSerializer(platform, context={"request": request}).data)
    return platform, serialized


@api_view(["GET"])
def platform_collection_api(request):
    payload = _platform_collection_payload(request.query_params, request)
    return Response(payload)


@api_view(["GET"])
def platform_detail_api(request, short_name):
    _, payload = _platform_detail_payload(request.query_params, request, short_name=short_name)
    return Response(payload)


def platform_collection_web_data(request):
    payload = _platform_collection_payload(request.GET, request)
    return JsonResponse(payload, safe=False)


def platform_detail_web_data(request, short_name):
    _, payload = _platform_detail_payload(request.GET, request, short_name=short_name)
    return JsonResponse(payload)


def PlatformInfo(request, short_name=None):
    platform, serialized = _platform_detail_payload(request.GET, request, short_name=short_name)
    return render(
        request,
        "platform_info.html",
        {
            "platform": platform,
            "platform_info": serialized,
        },
    )


def PlatformCatalog(request):
    serialized = _platform_collection_payload(request.GET, request)
    return render(
        request,
        "platforms_catalog_base.html",
        {
            "platform_recs": serialized,
        },
    )


def PlatformMap(request):
    return render(request, "platforms_map.html")

'''
Internal system API
'''
@api_view(["GET"])
@permission_classes([IsAuthenticated, HasPrivateApiAccess])
def platform_source_configuration(request):

    request_log(request, "platform_source_configuration", "DEBUG", "")
    data_source_key = request.query_params.get("data_source", "purple_air")

    observation_qs = (
        SourceObservationMap.objects
        .select_related(
            "sensor_id",
            "sensor_id__m_type_id",
            "sensor_id__m_type_id__m_scalar_type_id",
            "sensor_id__m_type_id__m_scalar_type_id__obs_type_id",
            "sensor_id__m_type_id__m_scalar_type_id__uom_type_id",
        )
        .filter(active=1)
        .order_by("sensor_id__s_order", "source_obs")
    )

    platform_sources = (
        PlatformSource.objects
        .select_related("data_source_id", "platform_id", "platform_id__organization_id")
        .prefetch_related(
            Prefetch(
                "sourceobservationmap_set",
                queryset=observation_qs,
                to_attr="observation_maps",
            )
        )
        .filter(
            data_source_id__key=data_source_key,
            data_source_id__active=1,
            active=1,
            platform_id__active=1,
        )
        .order_by(
            "platform_id__organization_id__row_id",
            "platform_id__platform_handle",
        )
    )
    platform_sources = list(platform_sources)
    serialized_platforms = PlatformSourceConfigurationSerializer(
        platform_sources,
        many=True,
    ).data

    config = {"organizations": []}
    org_ndx = {}
    for platform_source, platform_payload in zip(platform_sources, serialized_platforms):
        organization = platform_source.platform_id.organization_id
        org_id = organization.row_id
        #org_exists = [org_ndx for org_nfo in config["organizations"] if org_nfo["org_id"] == org_id]
        if len(org_ndx) == 0 or org_id not in org_ndx:
        #if org_id not in config["organizations"]:
            config["organizations"].append({
                "org_id": org_id,
                "short_name": organization.short_name,
                "long_name": organization.long_name,
                "platforms": [],
            })
            org_ndx[org_id] = len(config["organizations"]) - 1
        ndx = org_ndx[org_id]
        config["organizations"][ndx]["platforms"].append(platform_payload)

    return Response(config)
