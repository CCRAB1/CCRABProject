from unittest.mock import Mock, patch

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.contrib import admin
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse
from django_summernote.widgets import SummernoteWidget

from projects_catalog.admin import ProjectCatalogPageAdmin, ProjectCatalogPageEditorAdmin
from projects_catalog.models import ProjectCatalogPage, ProjectCatalogPageEditor


class ProjectCatalogEditorAdminTests(SimpleTestCase):
    def setUp(self):
        self.model_admin = admin.site._registry[ProjectCatalogPageEditor]
        self.request = RequestFactory().get("/admin/")
        self.request.user = Mock()
        self.request.user.has_perm.return_value = True

    def test_separate_registration_preserves_original_admin(self):
        self.assertIsInstance(admin.site._registry[ProjectCatalogPage], ProjectCatalogPageAdmin)
        self.assertIsInstance(self.model_admin, ProjectCatalogPageEditorAdmin)
        self.assertEqual(ProjectCatalogPageEditor._meta.verbose_name_plural, "Project Catalog Pages Editor")
        self.assertIs(ProjectCatalogPageEditor._meta.concrete_model, ProjectCatalogPage)
        self.assertTrue(reverse("admin:projects_catalog_projectcatalogpageeditor_changelist"))

    def test_form_only_edits_narratives_with_summernote(self):
        form = self.model_admin.get_form(self.request)
        self.assertEqual(set(form.base_fields), {"project_description", "project_impact"})
        for field in form.base_fields.values():
            self.assertIsInstance(field.widget, SummernoteWidget)

    def test_uses_existing_project_permission(self):
        self.assertTrue(self.model_admin.has_change_permission(self.request))
        self.request.user.has_perm.assert_called_with("projects_catalog.change_projectcatalogpage")
        self.request.user.has_perm.return_value = False
        self.assertFalse(self.model_admin.has_module_permission(self.request))
        self.assertFalse(self.model_admin.has_view_permission(self.request))
        self.assertFalse(self.model_admin.has_add_permission(self.request))
        self.assertFalse(self.model_admin.has_delete_permission(self.request))

    def test_save_updates_only_narratives(self):
        obj = Mock()
        self.model_admin.save_model(self.request, obj, Mock(), True)
        obj.save.assert_called_once_with(update_fields=["project_description", "project_impact", "updated_at"])

    def test_link_opens_existing_page_editor(self):
        obj = ProjectCatalogPageEditor(pk=1, slug="example")
        self.assertIn(reverse("projects_catalog_detail_editor", args=["example"]), self.model_admin.page_editor(obj))

    def test_selecting_project_opens_editors_in_page_sections(self):
        project = ProjectCatalogPageEditor(pk=1, slug="example")
        with patch.object(self.model_admin, "get_object", return_value=project):
            response = self.model_admin.change_view(self.request, "1")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("projects_catalog_detail_editor", args=["example"]))

    def test_page_editor_entry_requires_project_change_permission(self):
        self.request.user.has_perm.return_value = False
        with self.assertRaises(PermissionDenied):
            self.model_admin.change_view(self.request, "1")

    def test_missing_project_returns_404(self):
        with patch.object(self.model_admin, "get_object", return_value=None):
            with self.assertRaises(Http404):
                self.model_admin.change_view(self.request, "999")
