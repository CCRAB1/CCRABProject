import re
from collections import OrderedDict

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.text import slugify
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import ProductType, ProjectCatalogPage
from .serializers import ProjectCatalogPageSerializer

PAGE_SIZE = 12


def _project_title(project_dict):
    return (
        project_dict.get("project_full_title")
        or project_dict.get("project_name")
        or "Untitled project"
    )


def _project_title_from_model(project):
    return project.project_full_title or project.project_name or "Untitled project"


def _project_code_for_url(project):
    if getattr(project, "slug", None):
        return project.slug
    return str(project.pk)


def _resource_code_for_url(location):
    if getattr(location, "slug", None):
        return location.slug
    return str(location.pk)


def _format_duration(start_date, end_date):
    if start_date and end_date:
        return f"{start_date:%b %Y} - {end_date:%b %Y}"
    if start_date:
        return f"{start_date:%b %Y} - Present"
    if end_date:
        return f"Through {end_date:%b %Y}"
    return "—"


def _first_featured_image(project_dict):
    pictures = project_dict.get("pictures") or []
    for picture in pictures:
        if picture.get("picture_path"):
            return {
                "url": picture["picture_path"],
                "alt": picture.get("name") or _project_title(project_dict),
            }
    return None


def _split_paragraphs(text):
    if not text:
        return []
    parts = []
    for part in re.split(r"\n\s*\n", text):
        cleaned_part = part.strip()
        if cleaned_part:
            parts.append(cleaned_part)
    return parts or [text.strip()]


def _split_bullets(text):
    if not text:
        return []
    lines = []
    for line in text.splitlines():
        if line.strip():
            lines.append(line.strip("- ").strip())
    return lines or [text.strip()]


def _normalized_keywords(value):
    items = []
    if isinstance(value, list):
        for keyword in value:
            keyword_text = str(keyword).strip()
            if keyword_text:
                items.append(keyword_text)
        return items

    if isinstance(value, str):
        for keyword in value.split(","):
            keyword_text = keyword.strip()
            if keyword_text:
                items.append(keyword_text)
        return items

    return items


def _project_focus_area_names(project):
    names = []
    for location in project.hosting_locations.all():
        for product_type in location.product_types.all():
            name = getattr(product_type, "name", None)
            if name and name not in names:
                names.append(name)
    names.sort()
    return names


def _resource_title(location):
    if location.data_summary:
        summary_lines = _split_paragraphs(location.data_summary)
        if summary_lines:
            return summary_lines[0]
    if location.data_type:
        return location.data_type
    if location.product_category and location.product_category.name:
        return location.product_category.name
    return "Project Resource"


def _project_queryset():
    return (
        ProjectCatalogPage.objects
        .prefetch_related(
            "partners",
            "pictures",
            "hosting_locations__product_types",
            "hosting_locations__product_category",
        )
        .order_by("id")
    )


def _resolve_project(code):
    queryset = _project_queryset()

    slug_match = queryset.filter(slug=code).first()
    if slug_match:
        return slug_match

    if str(code).isdigit():
        return get_object_or_404(queryset, pk=int(code))

    simple_match = queryset.filter(
        Q(project_name__iexact=code.replace("-", " "))
        | Q(project_full_title__iexact=code.replace("-", " "))
    ).first()
    if simple_match:
        return simple_match

    for project in queryset:
        if (
            slugify(project.project_name) == code
            or slugify(project.project_full_title or "") == code
        ):
            return project

    raise Http404("Project not found")


def _project_list_payload(query_params):
    queryset = _project_queryset()

    query = query_params.get("q", "").strip()
    keywords = query_params.get("keywords", "").strip()
    project_type = query_params.get("project_type", "").strip()
    neighborhood = query_params.get("neighborhood", "").strip()
    region = query_params.get("region", "").strip()

    keyword_query = keywords or query
    if keyword_query:
        queryset = queryset.filter(
            Q(project_name__icontains=keyword_query)
            | Q(project_full_title__icontains=keyword_query)
            | Q(project_description__icontains=keyword_query)
            | Q(project_impact__icontains=keyword_query)
            | Q(project_lead__icontains=keyword_query)
            | Q(keywords__icontains=keyword_query)
        )

    if project_type:
        queryset = queryset.filter(
            hosting_locations__product_types__name__iexact=project_type
        )

    if neighborhood:
        queryset = queryset.filter(neighborhood__icontains=neighborhood)

    if region:
        queryset = queryset.filter(
            Q(neighborhood__icontains=region)
            | Q(project_description__icontains=region)
            | Q(keywords__icontains=region)
        )

    queryset = queryset.distinct()
    paginator = Paginator(queryset, PAGE_SIZE)
    page_number = query_params.get("page") or 1
    page_obj = paginator.get_page(page_number)

    page_projects = list(page_obj.object_list)
    serialized = ProjectCatalogPageSerializer(page_projects, many=True).data
    project_lookup = {}
    for project in page_projects:
        project_lookup[project.pk] = project

    results = []
    for project in serialized:
        project_id = project["id"]
        model_obj = project_lookup[project_id]
        results.append(
            {
                "id": project_id,
                "slug": _project_code_for_url(model_obj),
                "project_name": project.get("project_name"),
                "project_full_title": project.get("project_full_title"),
                "start_date": project.get("start_date"),
                "end_date": project.get("end_date"),
                "pictures": project.get("pictures") or [],
                "project_detail_url": reverse(
                    "project-detail",
                    kwargs={"code": _project_code_for_url(model_obj)},
                ),
            }
        )

    if paginator.count:
        start = (page_obj.number - 1) * PAGE_SIZE + 1
        end = start + len(results) - 1
    else:
        start, end = 0, 0

    payload = {
        "count": paginator.count,
        "page": page_obj.number,
        "total_pages": paginator.num_pages,
        "displaying": {"start": start, "end": end},
        "results": results,
    }
    return payload


def _project_facets_payload():
    project_types = []
    product_type_values = ProductType.objects.order_by("name").values_list(
        "name",
        flat=True,
    )
    for project_type_name in product_type_values:
        project_types.append(project_type_name)

    neighborhoods = []
    neighborhood_values = (
        ProjectCatalogPage.objects.exclude(neighborhood__isnull=True)
        .exclude(neighborhood__exact="")
        .order_by("neighborhood")
        .values_list("neighborhood", flat=True)
        .distinct()
    )
    for neighborhood_name in neighborhood_values:
        neighborhoods.append(neighborhood_name)

    payload = {
        "project_types": project_types,
        "neighborhoods": neighborhoods,
        "neighborhood": neighborhoods,
        "regions": neighborhoods,
    }
    return payload


def _project_detail_payload(code):
    project = _resolve_project(code)
    project_data = ProjectCatalogPageSerializer(project).data

    prev_project = (
        ProjectCatalogPage.objects.filter(pk__lt=project.pk).order_by("-pk").first()
    )
    next_project = (
        ProjectCatalogPage.objects.filter(pk__gt=project.pk).order_by("pk").first()
    )

    payload = dict(project_data)
    payload["slug"] = _project_code_for_url(project)
    payload["previous_project"] = _project_nav_payload(prev_project)
    payload["next_project"] = _project_nav_payload(next_project)
    return payload


def _project_nav_payload(project):
    if project is None:
        return None

    return {
        "id": project.id,
        "slug": _project_code_for_url(project),
        "project_name": project.project_name,
        "project_full_title": project.project_full_title,
        "project_detail_url": reverse(
            "project-detail",
            kwargs={"code": _project_code_for_url(project)},
        ),
    }


def _hosting_location_payload(location, project):
    product_type_ids = []
    for product_type in location.product_types.all():
        product_type_ids.append(product_type.id)

    payload = {
        "id": location.id,
        "project_id": location.project_id,
        "data_type": location.data_type,
        "data_summary": location.data_summary,
        "url": location.url,
        "resource_detail_url": reverse(
            "project-resource-detail",
            kwargs={
                "code": _project_code_for_url(project),
                "resource_slug": _resource_code_for_url(location),
            },
        ),
        "product_category_id": location.product_category_id,
        "product_type_id": product_type_ids,
        "created_at": location.created_at,
        "updated_at": location.updated_at,
    }
    return payload


def _project_products_payload(code):
    project = _resolve_project(code)
    category_map = OrderedDict()
    for location in project.hosting_locations.all():
        category_name = "Uncategorized"
        if location.product_category and location.product_category.name:
            category_name = location.product_category.name

        location_payload = _hosting_location_payload(location, project)
        if category_name not in category_map:
            category_map[category_name] = []

        category_map[category_name].append(location_payload)

    payload = {"categories": category_map, "slug": _project_code_for_url(project)}
    return payload


@api_view(["GET"])
def project_list_api(request):
    payload = _project_list_payload(request.query_params)
    return Response(payload)


@api_view(["GET"])
def project_facets_api(_request):
    payload = _project_facets_payload()
    return Response(payload)


@api_view(["GET"])
def project_detail_api(_request, code):
    payload = _project_detail_payload(code)
    return Response(payload)


@api_view(["GET"])
def project_products_api(_request, code):
    payload = _project_products_payload(code)
    return Response(payload)


def project_list_web_data(request):
    payload = _project_list_payload(request.GET)
    return JsonResponse(payload)


def project_facets_web_data(_request):
    payload = _project_facets_payload()
    return JsonResponse(payload)


def project_detail_web_data(_request, code):
    payload = _project_detail_payload(code)
    return JsonResponse(payload)


def project_products_web_data(_request, code):
    payload = _project_products_payload(code)
    return JsonResponse(payload)


def project_resource_detail_page(request, code, resource_slug):
    project = _resolve_project(code)

    selected_resource = None
    for resource in project.hosting_locations.all():
        if resource.slug == resource_slug:
            selected_resource = resource
            break

    if selected_resource is None and str(resource_slug).isdigit():
        for resource in project.hosting_locations.all():
            if resource.pk == int(resource_slug):
                selected_resource = resource
                break

    if selected_resource is None:
        raise Http404("Resource not found")

    resource_product_types = []
    for product_type in selected_resource.product_types.all():
        if product_type.name and product_type.name not in resource_product_types:
            resource_product_types.append(product_type.name)
    resource_product_types.sort()

    resource_about_paragraphs = _split_paragraphs(selected_resource.data_summary)
    if not resource_about_paragraphs:
        fallback_bits = []
        if selected_resource.data_type:
            fallback_bits.append(
                f"This resource type is {selected_resource.data_type}."
            )
        if selected_resource.url:
            fallback_bits.append("Use the external link below to access the resource.")
        if fallback_bits:
            resource_about_paragraphs = fallback_bits
        else:
            resource_about_paragraphs = [
                "Resource details were not provided for this item."
            ]

    neighborhoods = []
    if project.neighborhood:
        neighborhoods.append(project.neighborhood)

    context = {
        "project_code": _project_code_for_url(project),
        "project_title": _project_title_from_model(project),
        "project_detail_url": reverse(
            "project-detail",
            kwargs={"code": _project_code_for_url(project)},
        ),
        "resource_title": _resource_title(selected_resource),
        "about_project_paragraphs": _split_paragraphs(project.project_description),
        "about_resource_paragraphs": resource_about_paragraphs,
        "resource_external_url": selected_resource.url,
        "resource_category": (
            selected_resource.product_category.name
            if (
                selected_resource.product_category
                and selected_resource.product_category.name
            )
            else "Uncategorized"
        ),
        "resource_types": resource_product_types,
        "focus_areas": _project_focus_area_names(project),
        "keywords": _normalized_keywords(project.keywords),
        "neighborhoods": neighborhoods,
    }
    context["resource_payload"] = {
        "resource_title": context["resource_title"],
        "about_project_paragraphs": context["about_project_paragraphs"],
        "about_resource_paragraphs": context["about_resource_paragraphs"],
        "resource_external_url": context["resource_external_url"],
        "resource_category": context["resource_category"],
        "resource_types": context["resource_types"],
        "focus_areas": context["focus_areas"],
        "keywords": context["keywords"],
        "neighborhoods": context["neighborhoods"],
    }
    return render(request, "project_resource_detail.html", context)


def projects_index_page(request):
    return render(request, "projects_index.html")


def project_detail_page(request, code):
    return render(request, "project_catalog_detail.html", {"project_code": code})


def projects_map_page(request):
    return render(request, "projects_map.html")
