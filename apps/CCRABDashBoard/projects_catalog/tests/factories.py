from datetime import UTC, datetime

from django.utils import timezone

from projects_catalog.models import (
    HostingLocation,
    HostingLocationProductType,
    ProductCategory,
    ProductType,
    ProjectCatalogPage,
    ProjectPartner,
    ProjectPicture,
)


def utc_datetime(year, month, day):
    return timezone.make_aware(datetime(year, month, day), UTC)


def create_project(name, **overrides):
    description = f"{name} description paragraph one.\n\n{name} paragraph two."
    payload = {
        "project_name": name,
        "project_full_title": f"{name} Full Title",
        "project_description": description,
        "project_impact": "- Impact one\n- Impact two",
        "project_lead": f"{name} Lead",
        "project_lead_email": "lead@example.com",
        "project_url": "https://example.com/project",
        "keywords": ["environment", "community"],
        "neighborhood": "Default Neighborhood",
    }
    for key, value in overrides.items():
        payload[key] = value
    return ProjectCatalogPage.objects.create(**payload)


def create_product_type(name, description=""):
    return ProductType.objects.create(name=name, description=description)


def create_product_category(name, description=""):
    return ProductCategory.objects.create(name=name, description=description)


def create_hosting_location(
    project,
    data_type="Dataset",
    data_summary="Resource summary.",
    product_category=None,
    product_types=None,
    **overrides,
):
    payload = {
        "project": project,
        "data_type": data_type,
        "data_summary": data_summary,
        "url": "https://example.com/resource",
        "product_category": product_category,
    }
    for key, value in overrides.items():
        payload[key] = value

    location = HostingLocation.objects.create(**payload)
    if product_types:
        for product_type in product_types:
            HostingLocationProductType.objects.create(
                hosting_location=location,
                product_type=product_type,
            )
    return location


def create_partner(project, name, affiliation):
    return ProjectPartner.objects.create(
        project=project,
        name=name,
        affiliation=affiliation,
    )


def create_picture(
    project,
    name="Hero",
    picture_path="projects_catalog/project_pictures/test/hero.jpg",
):
    return ProjectPicture.objects.create(
        project=project,
        name=name,
        picture_path=picture_path,
    )
