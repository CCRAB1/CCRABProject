from django.contrib import admin
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.gis.admin import GISModelAdmin  # requires GeoDjango; remove if not using

from .models import (
    HostingLocation,
    HostingLocationProductType,
    ProductCategory,
    ProductType,
    ProjectCatalogPage,
    ProjectPartner,
    ProjectPicture,
)


class ProjectPartnerInline(admin.TabularInline):
    model = ProjectPartner
    extra = 0
    fields = ("name", "affiliation")


class ProjectPictureInline(admin.TabularInline):
    model = ProjectPicture
    extra = 0
    fields = ("name", "picture_path")


@admin.register(ProjectCatalogPage)
class ProjectCatalogPageAdmin(GISModelAdmin):
    list_display = (
        "project_name",
        "slug",
        "project_lead",
        "start_date",
        "end_date",
        "project_url",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "project_name",
        "slug",
        "project_full_title",
        "project_lead",
        "project_lead_email",
        "project_description",
        "keywords",
    )
    list_filter = ("start_date", "end_date", "created_at", "updated_at")
    date_hierarchy = "start_date"
    readonly_fields = ("created_at", "updated_at")
    prepopulated_fields = {"slug": ("project_name",)}
    inlines = (ProjectPartnerInline, ProjectPictureInline)

    fieldsets = (
        (
            "Project",
            {
                "fields": (
                    "project_name",
                    "slug",
                    "project_full_title",
                    "project_description",
                    "project_impact",
                    "project_url",
                )
            },
        ),
        (
            "Lead Contact",
            {"fields": ("project_lead", "project_lead_email", "project_lead_phone")},
        ),
        (
            "Dates and Location",
            {"fields": ("start_date", "end_date", "neighborhood", "geom")},
        ),
        ("Metadata", {"fields": ("keywords", "created_at", "updated_at")}),
    )


@admin.register(ProjectPartner)
class ProjectPartnerAdmin(admin.ModelAdmin):
    list_display = ("name", "affiliation", "project", "created_at", "updated_at")
    search_fields = ("name", "affiliation", "project__project_name")
    list_filter = ("created_at", "updated_at")
    autocomplete_fields = ("project",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(ProjectPicture)
class ProjectPictureAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "picture_path", "created_at", "updated_at")
    search_fields = ("name", "picture_path", "project__project_name")
    list_filter = ("created_at", "updated_at")
    autocomplete_fields = ("project",)
    readonly_fields = ("created_at", "updated_at")


class HostingLocationProductTypeInline(admin.TabularInline):
    model = HostingLocationProductType
    extra = 0
    autocomplete_fields = ("product_type",)


@admin.register(HostingLocation)
class HostingLocationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "project",
        "slug",
        "product_category",
        "data_type",
        "url",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "project__project_name",
        "slug",
        "product_category__name",
        "data_type",
        "data_summary",
        "url",
    )
    list_filter = ("product_category", "data_type", "created_at", "updated_at")
    autocomplete_fields = ("project", "product_category")
    readonly_fields = ("created_at", "updated_at")
    fields = (
        "project",
        "slug",
        "product_category",
        "data_type",
        "data_summary",
        "url",
        "created_at",
        "updated_at",
    )
    inlines = (HostingLocationProductTypeInline,)


@admin.register(ProductType)
class ProductTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name", "description")


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name", "description")


@admin.register(HostingLocationProductType)
class HostingLocationProductTypeAdmin(admin.ModelAdmin):
    list_display = ("hosting_location", "product_type")
    search_fields = (
        "hosting_location__project__project_name",
        "product_type__name",
    )
    autocomplete_fields = ("hosting_location", "product_type")


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    date_hierarchy = "action_time"
    list_display = (
        "action_time",
        "user",
        "content_type",
        "object_repr",
        "action_label",
    )
    list_filter = ("action_flag", "content_type", "user")
    search_fields = ("object_repr", "change_message", "user__username", "user__email")
    ordering = ("-action_time",)
    list_select_related = ("user", "content_type")
    readonly_fields = (
        "action_time",
        "user",
        "content_type",
        "object_id",
        "object_repr",
        "action_flag",
        "change_message",
    )
    actions = None

    @admin.display(description="Action")
    def action_label(self, obj):
        return {
            ADDITION: "Added",
            CHANGE: "Changed",
            DELETION: "Deleted",
        }.get(obj.action_flag, "Unknown")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
