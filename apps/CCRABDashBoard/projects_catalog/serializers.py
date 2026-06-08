from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from .models import (
    HostingLocation,
    HostingLocationProductType,
    ProductCategory,
    ProductType,
    ProjectCatalogPage,
    ProjectPartner,
    ProjectPicture,
)


class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ("id", "name", "description")


class ProductTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductType
        fields = ("id", "name", "description")


class ProjectPartnerSerializer(serializers.ModelSerializer):
    project_id = serializers.PrimaryKeyRelatedField(
        source="project",
        queryset=ProjectCatalogPage.objects.all(),
    )

    class Meta:
        model = ProjectPartner
        fields = ("id", "project_id", "name", "affiliation", "created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")


class ProjectPictureSerializer(serializers.ModelSerializer):
    project_id = serializers.PrimaryKeyRelatedField(
        source="project",
        queryset=ProjectCatalogPage.objects.all(),
    )

    class Meta:
        model = ProjectPicture
        fields = (
            "id",
            "project_id",
            "name",
            "picture_path",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")


class HostingLocationProductTypeSerializer(serializers.ModelSerializer):
    hosting_location_id = serializers.PrimaryKeyRelatedField(
        source="hosting_location",
        queryset=HostingLocation.objects.all(),
    )
    product_type_id = serializers.PrimaryKeyRelatedField(
        source="product_type",
        queryset=ProductType.objects.all(),
    )

    class Meta:
        model = HostingLocationProductType
        fields = ("id", "hosting_location_id", "product_type_id")


class HostingLocationSerializer(serializers.ModelSerializer):
    project_id = serializers.PrimaryKeyRelatedField(
        source="project",
        queryset=ProjectCatalogPage.objects.all(),
    )
    product_category_id = serializers.PrimaryKeyRelatedField(
        source="product_category",
        queryset=ProductCategory.objects.all(),
        required=False,
        allow_null=True,
    )
    product_types = ProductTypeSerializer(many=True, read_only=True)
    product_type_id = serializers.PrimaryKeyRelatedField(
        source="product_types",
        many=True,
        queryset=ProductType.objects.all(),
        required=False,
    )

    class Meta:
        model = HostingLocation
        fields = (
            "id",
            "project_id",
            "slug",
            "data_type",
            "data_summary",
            "url",
            "product_category_id",
            "product_types",
            "product_type_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")


class ProjectCatalogPageSerializer(serializers.ModelSerializer):
    partners = ProjectPartnerSerializer(many=True, read_only=True)
    pictures = ProjectPictureSerializer(many=True, read_only=True)
    hosting_locations = HostingLocationSerializer(many=True, read_only=True)

    class Meta:
        model = ProjectCatalogPage
        fields = (
            "id",
            "slug",
            "project_name",
            "project_full_title",
            "project_lead",
            "project_lead_email",
            "project_lead_phone",
            "neighborhood",
            "start_date",
            "end_date",
            "project_url",
            "project_description",
            "project_impact",
            "keywords",
            "geom",
            "partners",
            "pictures",
            "hosting_locations",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")


class ProjectCatalogPageGeoSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = ProjectCatalogPage
        geo_field = "geom"
        fields = (
            "id",
            "slug",
            "project_name",
            "project_full_title",
            "project_lead",
            "project_url",
            "neighborhood",
            "start_date",
            "end_date",
            "keywords",
        )
