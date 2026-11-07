"""Rich text editing restricted to the two catalog narrative fields."""
import re

import bleach
from django import forms
from django.utils.html import escape
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from django_summernote.widgets import SummernoteWidget

from .models import ProjectCatalogPage, ProjectLead, ProjectPartner, ProjectPicture


RICH_TEXT_TAGS = [
    "p", "br", "strong", "b", "em", "i", "u", "s", "ul", "ol", "li",
    "a", "h2", "h3", "h4", "blockquote", "pre", "code", "table", "thead",
    "tbody", "tr", "th", "td",
]


def clean_rich_text(value):
    return bleach.clean(value or "", tags=RICH_TEXT_TAGS,
                        attributes={"a": ["href", "title"]},
                        protocols=["http", "https", "mailto"], strip=True)


def editor_html(value, bullets=False):
    value = value or ""
    if re.search(r"</?[a-z][^>]*>", value, re.I):
        return clean_rich_text(value)
    parts = []
    for part in re.split(r"\r?\n" if bullets else r"\n\s*\n", value):
        if part.strip():
            text = re.sub(r"^\s*[-*]\s*", "", part).strip() if bullets else part.strip()
            tag = "li" if bullets else "p"
            parts.append(f"<{tag}>{escape(text)}</{tag}>")
    html = "".join(parts)
    return f"<ul>{html}</ul>" if bullets and parts else html


class ProjectCatalogEditorForm(forms.ModelForm):
    class Meta:
        model = ProjectCatalogPage
        fields = ["project_description", "project_impact", "neighborhood", "start_date", "end_date"]
        labels = {"project_description": "The Project", "project_impact": "The Impact"}
        widgets = {
            "project_description": SummernoteWidget(),
            "project_impact": SummernoteWidget(),
            "neighborhood": forms.TextInput(attrs={"class": "input"}),
            "start_date": forms.DateTimeInput(format="%Y-%m-%d", attrs={"type": "date", "class": "input"}),
            "end_date": forms.DateTimeInput(format="%Y-%m-%d", attrs={"type": "date", "class": "input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_dates = {"start_date": self.instance.start_date, "end_date": self.instance.end_date}
        if not self.is_bound:
            for name in ("project_description", "project_impact"):
                self.initial[name] = editor_html(self.initial.get(name), name == "project_impact")

    def clean(self):
        cleaned = super().clean()
        # A date-only control must not reset an existing time on an unchanged day.
        for name, original in self.original_dates.items():
            value = cleaned.get(name)
            if value and original:
                original_local = timezone.localtime(original) if timezone.is_aware(original) else original
                if value.date() == original_local.date():
                    cleaned[name] = original
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "End Date must be on or after Start Date.")
        return cleaned

    def clean_project_description(self):
        return clean_rich_text(self.cleaned_data["project_description"])

    def clean_project_impact(self):
        return clean_rich_text(self.cleaned_data["project_impact"])


class ProjectTeamForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Textarea):
                field.widget = forms.TextInput()
            field.widget.attrs["class"] = "input"


class ProjectTeamFormSet(forms.BaseInlineFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)
        # Never accept a row ID belonging to another project.
        form.fields[self.model._meta.pk.name].queryset = self.get_queryset()


ProjectLeadFormSet = forms.inlineformset_factory(
    ProjectCatalogPage, ProjectLead, form=ProjectTeamForm,
    formset=ProjectTeamFormSet,
    fields=("name", "organization", "email", "url", "role"),
    extra=0, can_delete=True,
)
ProjectPartnerFormSet = forms.inlineformset_factory(
    ProjectCatalogPage, ProjectPartner, form=ProjectTeamForm,
    formset=ProjectTeamFormSet,
    fields=("name", "url"), extra=0, can_delete=True,
)


class ProjectPhotoUploadForm(forms.ModelForm):
    picture_path = forms.ImageField(
        label="Choose photo", required=False,
        validators=[FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "gif", "webp"])],
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/gif,image/webp"}),
    )

    class Meta:
        model = ProjectPicture
        fields = ("picture_path", "name")
        labels = {"name": "Photo caption (optional)"}
        widgets = {"name": forms.TextInput(attrs={"class": "input"})}

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("name") and not cleaned.get("picture_path") and "picture_path" not in self.errors:
            self.add_error("picture_path", "Choose a photo to upload with this caption.")
        return cleaned
