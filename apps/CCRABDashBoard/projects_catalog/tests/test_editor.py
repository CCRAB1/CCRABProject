from unittest.mock import Mock, patch

from django.contrib.auth.models import AnonymousUser
from django.contrib.staticfiles import finders
from django_summernote.utils import get_config
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse

from projects_catalog.forms import ProjectCatalogEditorForm, clean_rich_text, editor_html
from projects_catalog.models import ProjectCatalogPage
from projects_catalog.views import projects_catalog_detail_editor


class ProjectEditorTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.project = ProjectCatalogPage(pk=1, slug="example", project_name="Example")
        self.url = reverse("projects_catalog_detail_editor", args=["example"])

    def request(self, method="get", data=None, allowed=True):
        request = getattr(self.factory, method)(self.url, data=data)
        request.user = Mock(is_authenticated=True)
        request.user.has_perms.return_value = allowed
        return request

    def test_anonymous_redirects_to_login(self):
        request = self.factory.get(self.url)
        request.user = AnonymousUser()
        self.assertEqual(projects_catalog_detail_editor(request, "example").status_code, 302)

    def test_permission_required_for_get_and_post(self):
        for method in ["get", "post"]:
            with self.assertRaises(PermissionDenied):
                projects_catalog_detail_editor(self.request(method, allowed=False), "example")

    @patch("projects_catalog.views._resolve_project")
    def test_editor_preserves_layout_and_renders_two_widgets(self, resolve):
        self.project.pk = None
        resolve.return_value = self.project
        response = projects_catalog_detail_editor(self.request(), "example")
        html = response.content.decode()
        for text in ["id_project_description", "id_project_impact", "Save changes", "Project team", "Project products", "csrfmiddlewaretoken"]:
            self.assertIn(text, html)
        self.assertEqual(html.count('<iframe'), 2)

    @patch("projects_catalog.views.transaction.atomic")
    @patch.object(ProjectCatalogPage, "save")
    @patch("projects_catalog.views._resolve_project")
    def test_save_only_updates_narrative_fields(self, resolve, save, atomic):
        resolve.return_value = self.project
        response = projects_catalog_detail_editor(self.request("post", {
            "project_description": '<p onclick="bad()">Updated <b>project</b></p>',
            "project_impact": '<ul><li>Impact</li></ul>',
            "project_name": "Unwanted change",
            "leads-TOTAL_FORMS": "0", "leads-INITIAL_FORMS": "0",
            "partners-TOTAL_FORMS": "0", "partners-INITIAL_FORMS": "0",
        }), "example")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.project.project_description, "<p>Updated <b>project</b></p>")
        self.assertEqual(self.project.project_name, "Example")
        save.assert_called_once_with(update_fields=["project_description", "project_impact", "neighborhood", "start_date", "end_date", "updated_at"])

    def test_plain_text_keeps_paragraphs_and_impact_bullets(self):
        self.assertEqual(editor_html("One\n\nTwo"), "<p>One</p><p>Two</p>")
        self.assertEqual(editor_html("- One\n- Two", True), "<ul><li>One</li><li>Two</li></ul>")
        self.assertEqual(editor_html("A & B"), "<p>A &amp; B</p>")

    def test_dangerous_html_is_stripped(self):
        html = clean_rich_text('<a href="javascript:bad()" x-init="bad()">Link</a><img src=x onerror="bad()">')
        self.assertEqual(html, "<a>Link</a>")

    def test_both_sections_can_be_cleared(self):
        form = ProjectCatalogEditorForm(data={"project_description": "", "project_impact": ""}, instance=self.project)
        self.assertTrue(form.is_valid(), form.errors)

    def test_attachment_upload_is_disabled(self):
        response = self.client.post(reverse("django_summernote-upload_attachment"))
        self.assertEqual(response.status_code, 403)

    def test_iframe_stylesheets_use_bundled_assets(self):
        response = self.client.get(reverse("django_summernote-editor", args=["id_project_description"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/summernote/summernote-lite.min.css")
        self.assertNotContains(response, 'summernote-lite.css')
        config = get_config()
        for asset in config["default_css"] + config["default_js"]:
            with self.subTest(asset=asset):
                self.assertIsNotNone(finders.find(asset))
