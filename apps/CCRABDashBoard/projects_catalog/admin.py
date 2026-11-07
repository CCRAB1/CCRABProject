from django.contrib import admin
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html

from .forms import ProjectCatalogEditorForm

from django.contrib.gis.admin import GISModelAdmin  # requires GeoDjango; remove if not using

from .models import (
    HostingLocation,
    HostingLocationProductType,
    ProductCategory,
    ProductType,
    ProjectCatalogPage,
    ProjectCatalogPageEditor,
    ProjectLead,
    ProjectPartner,
    ProjectPicture,
)


class ProjectLeadInline(admin.TabularInline):
    model = ProjectLead
    extra = 0
    fields = ("name", "organization", "email", "url", "role")


class ProjectPartnerInline(admin.TabularInline):
    model = ProjectPartner
    extra = 0
    fields = ("name", "url")


class ProjectPictureInline(admin.TabularInline):
    model = ProjectPicture
    extra = 0
    fields = ("name", "picture_path")


@admin.register(ProjectCatalogPage)
class ProjectCatalogPageAdmin(GISModelAdmin):
    list_display = (
        "project_name",
        "slug",
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
        "project_description",
        "keywords",
    )
    list_filter = ("start_date", "end_date", "created_at", "updated_at")
    date_hierarchy = "start_date"
    readonly_fields = ("created_at", "updated_at")
    prepopulated_fields = {"slug": ("project_name",)}
    inlines = (ProjectLeadInline, ProjectPartnerInline, ProjectPictureInline)

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
            "Dates and Location",
            {"fields": ("start_date", "end_date", "neighborhood", "geom")},
        ),
        ("Metadata", {"fields": ("keywords", "created_at", "updated_at")}),
    )


@admin.register(ProjectLead)
class ProjectLeadAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "email", "role", "project")
    search_fields = ("name", "organization", "email", "role", "project__project_name")
    autocomplete_fields = ("project",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(ProjectPartner)
class ProjectPartnerAdmin(admin.ModelAdmin):
    list_display = ("name", "url", "project", "created_at", "updated_at")
    search_fields = ("name", "url", "project__project_name")
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


@admin.register(ProjectCatalogPageEditor)
class ProjectCatalogPageEditorAdmin(admin.ModelAdmin):
    form = ProjectCatalogEditorForm
    list_display = ("project_name", "slug", "updated_at")
    search_fields = ("project_name", "project_full_title", "slug")
    ordering = ("project_name",)
    readonly_fields = ("project_name", "page_editor")
    fields = ("project_name", "page_editor", "project_description", "project_impact")
    actions = None

    @admin.display(description="Page editor")
    def page_editor(self, obj):
        return format_html(
            '<a href="{}">Open editor in project page layout</a>',
            reverse("projects_catalog_detail_editor", kwargs={"code": obj.slug or str(obj.pk)}),
        )

    def change_view(self, request, object_id, form_url="", extra_context=None):
        # Open the editors in their actual sections of the project page.
        if not self.has_change_permission(request):
            raise PermissionDenied
        project = self.get_object(request, admin.utils.unquote(object_id))
        if project is None:
            raise Http404("Project not found")
        return redirect(
            "projects_catalog_detail_editor", code=project.slug or str(project.pk)
        )

    def has_module_permission(self, request):
        return self.has_change_permission(request)

    def has_view_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm("projects_catalog.change_projectcatalogpage")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.save(update_fields=["project_description", "project_impact", "updated_at"])
