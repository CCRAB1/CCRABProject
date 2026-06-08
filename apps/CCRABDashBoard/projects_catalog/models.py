from django.contrib.gis.db import models as gis_models
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Q
from django.utils.text import slugify


def project_picture_upload_to(instance, filename):
    project_id = instance.project_id or "unassigned"
    return f"projects_catalog/project_pictures/{project_id}/{filename}"


def _unique_slug(model_cls, base_value, current_pk=None, max_length=255):
    fallback = "item"
    base_slug = slugify(base_value or "") or fallback
    base_slug = base_slug[:max_length].strip("-") or fallback
    candidate = base_slug
    suffix = 2

    while True:
        queryset = model_cls.objects.filter(slug=candidate)
        if current_pk is not None:
            queryset = queryset.exclude(pk=current_pk)
        if not queryset.exists():
            return candidate

        suffix_str = f"-{suffix}"
        trimmed_base = base_slug[: max_length - len(suffix_str)].strip("-") or fallback
        candidate = f"{trimmed_base}{suffix_str}"
        suffix += 1


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ProjectCatalogPage(TimestampedModel):
    project_name = models.TextField()
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    project_full_title = models.TextField(blank=True, null=True)
    project_lead = models.TextField(blank=True, null=True)
    project_lead_email = models.TextField(blank=True, null=True)
    project_lead_phone = models.TextField(blank=True, null=True)

    neighborhood = models.TextField(blank=True, null=True)
    start_date = models.DateTimeField(blank=True, null=True)
    end_date = models.DateTimeField(blank=True, null=True)

    project_url = models.TextField(blank=True, null=True)
    project_description = models.TextField(blank=True, null=True)
    project_impact = models.TextField(blank=True, null=True)

    # TEXT[] in Postgres
    keywords = models.JSONField(blank=True, null=True, default=list)
    # If you prefer a Postgres-native array field:
    # from django.contrib.postgres.fields import ArrayField
    # keywords = ArrayField(models.TextField(), blank=True, default=list)

    # GEOMETRY(GEOMETRY, 4326)
    geom = gis_models.GeometryField(srid=4326, blank=True, null=True)

    class Meta:
        db_table = '"projects"."project_catalog_pages"'
        indexes = [
            # GIST index for geometry will be created automatically for spatial queries if you add it via migrations,
            # but explicit indexes are fine too.
            gis_models.Index(fields=["geom"], name="idx_project_catalog_pages_geom"),
        ]
        constraints = [
            models.CheckConstraint(
                name="project_dates_ok",
                check=Q(end_date__isnull=True) | Q(start_date__isnull=True) | Q(end_date__gte=models.F("start_date")),
            )
        ]

    def __str__(self) -> str:
        return self.project_name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(
                model_cls=ProjectCatalogPage,
                base_value=self.project_name,
                current_pk=self.pk,
                max_length=self._meta.get_field("slug").max_length,
            )

            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                updated_fields = set(update_fields)
                updated_fields.add("slug")
                kwargs["update_fields"] = list(updated_fields)

        super().save(*args, **kwargs)


class ProjectPartner(TimestampedModel):
    project = models.ForeignKey(
        ProjectCatalogPage,
        on_delete=models.CASCADE,
        related_name="partners",
        db_column="project_id",
    )
    name = models.TextField(blank=True, null=True)
    affiliation = models.TextField(blank=True, null=True)

    class Meta:
        db_table = '"projects"."project_partners"'
        indexes = [
            models.Index(fields=["project"], name="idx_proj_partners_project_id"),
        ]

    def __str__(self) -> str:
        return self.name or f"Partner #{self.pk}"


class ProjectPicture(TimestampedModel):
    project = models.ForeignKey(
        ProjectCatalogPage,
        on_delete=models.CASCADE,
        related_name="pictures",
        db_column="project_id",
    )
    name = models.TextField(blank=True, null=True)
    picture_path = models.FileField(
        upload_to=project_picture_upload_to,
        validators=[FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "gif", "webp"])],
        blank=True,
        null=True,
        max_length=512,
    )

    class Meta:
        db_table = '"projects"."project_pictures"'
        indexes = [
            models.Index(fields=["project"], name="idx_proj_pictures_project_id"),
        ]

    def __str__(self) -> str:
        return self.name or f"Picture #{self.pk}"


class ProductCategory(models.Model):
    name = models.TextField(unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = '"projects"."product_category"'

    def __str__(self) -> str:
        return self.name


class ProductType(models.Model):
    name = models.TextField(unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = '"projects"."product_types"'

    def __str__(self) -> str:
        return self.name


class HostingLocation(TimestampedModel):
    project = models.ForeignKey(
        ProjectCatalogPage,
        on_delete=models.CASCADE,
        related_name="hosting_locations",
        db_column="project_id",
    )
    data_type = models.TextField(blank=True, null=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    data_summary = models.TextField(blank=True, null=True)
    url = models.TextField(blank=True, null=True)
    product_category = models.ForeignKey(
        ProductCategory,
        on_delete=models.SET_NULL,
        related_name="hosting_locations",
        db_column="product_category_id",
        blank=True,
        null=True,
    )

    product_types = models.ManyToManyField(
        ProductType,
        through="HostingLocationProductType",
        related_name="hosting_locations",
    )

    class Meta:
        db_table = '"projects"."hosting_locations"'
        indexes = [
            models.Index(fields=["project"], name="idx_host_locs_project_id"),
        ]

    def __str__(self) -> str:
        return f"HostingLocation #{self.pk}"

    def save(self, *args, **kwargs):
        if self.slug:
            super().save(*args, **kwargs)
            return

        if self.pk is None:
            super().save(*args, **kwargs)
            base_slug = slugify(self.data_type or "") or "resource"
            max_length = self._meta.get_field("slug").max_length
            resource_slug = f"{base_slug}-{self.pk}"
            self.slug = resource_slug[:max_length].strip("-") or f"resource-{self.pk}"
            super().save(update_fields=["slug"])
            return

        base_slug = slugify(self.data_type or "") or "resource"
        max_length = self._meta.get_field("slug").max_length
        resource_slug = f"{base_slug}-{self.pk}"
        self.slug = resource_slug[:max_length].strip("-") or f"resource-{self.pk}"

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            updated_fields = set(update_fields)
            updated_fields.add("slug")
            kwargs["update_fields"] = list(updated_fields)

        super().save(*args, **kwargs)


class HostingLocationProductType(models.Model):
    hosting_location = models.ForeignKey(
        HostingLocation,
        on_delete=models.CASCADE,
        db_column="hosting_location_id",
    )
    product_type = models.ForeignKey(
        ProductType,
        on_delete=models.PROTECT,  # matches ON DELETE RESTRICT intent
        db_column="product_type_id",
    )

    class Meta:
        db_table = '"projects"."hosting_location_product_types"'
        constraints = [
            models.UniqueConstraint(
                fields=["hosting_location", "product_type"],
                name="hosting_location_product_types_pk",
            )
        ]
        indexes = [
            models.Index(fields=["product_type"], name="idx_hlpt_product_type_id"),
        ]

    def __str__(self) -> str:
        return f"{self.hosting_location_id} -> {self.product_type_id}"
