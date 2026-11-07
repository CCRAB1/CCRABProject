from unittest.mock import Mock, patch

from django.test import RequestFactory, TestCase
from django.urls import reverse

from projects_catalog.models import ProjectLead, ProjectPartner
from projects_catalog.tests.factories import create_project
from projects_catalog.views import projects_catalog_detail_editor


class ProjectTeamEditorTests(TestCase):
    def setUp(self):
        self.project = create_project("Team Editor")
        self.url = reverse("projects_catalog_detail_editor", args=[self.project.slug])
        self.data = {
            "project_description": "<p>New project</p>",
            "project_impact": "<p>New impact</p>",
            "leads-TOTAL_FORMS": "1", "leads-INITIAL_FORMS": "0",
            "leads-0-name": "Lead Name", "leads-0-organization": "University",
            "leads-0-email": "lead@example.com", "leads-0-url": "https://example.com/lead",
            "leads-0-role": "Researcher",
            "partners-TOTAL_FORMS": "1", "partners-INITIAL_FORMS": "0",
            "partners-0-name": "Partner Name", "partners-0-url": "https://example.com/partner",
        }

    def submit(self):
        request = RequestFactory().post(self.url, self.data)
        request.user = Mock(is_authenticated=True)
        request.user.has_perms.return_value = True
        return projects_catalog_detail_editor(request, self.project.slug)

    def test_one_save_persists_all_sections_and_separate_fields(self):
        response = self.submit()
        self.assertEqual(response.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.project_description, "<p>New project</p>")
        self.assertEqual(self.project.project_impact, "<p>New impact</p>")
        lead = self.project.leads.get()
        for field in ("name", "organization", "email", "url", "role"):
            self.assertEqual(getattr(lead, field), self.data[f"leads-0-{field}"])
        partner = self.project.partners.get()
        self.assertEqual(partner.name, "Partner Name")
        self.assertEqual(partner.url, "https://example.com/partner")

    def test_invalid_lead_prevents_all_saves_and_preserves_input(self):
        original = self.project.project_description
        self.data["leads-0-email"] = "invalid-email"
        response = self.submit()
        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(self.project.project_description, original)
        self.assertFalse(self.project.leads.exists())
        self.assertFalse(self.project.partners.exists())
        self.assertIn("invalid-email", response.content.decode())
        self.assertIn("New impact", response.content.decode())

    def test_invalid_partner_url_prevents_all_saves(self):
        self.data["partners-0-url"] = "javascript:alert(1)"
        response = self.submit()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.project.leads.exists())
        self.assertFalse(self.project.partners.exists())
        self.assertIn("Enter a valid URL", response.content.decode())

    def test_partner_url_is_optional(self):
        self.data["partners-0-url"] = ""
        self.assertEqual(self.submit().status_code, 302)
        self.assertIsNone(self.project.partners.get().url)

    def test_edit_and_delete_existing_rows(self):
        lead = ProjectLead.objects.create(project=self.project, name="Old lead")
        partner = ProjectPartner.objects.create(project=self.project, name="Old partner")
        self.data.update({
            "leads-INITIAL_FORMS": "1", "leads-0-id": str(lead.pk),
            "partners-INITIAL_FORMS": "1", "partners-0-id": str(partner.pk),
            "partners-0-DELETE": "on",
        })
        self.assertEqual(self.submit().status_code, 302)
        lead.refresh_from_db()
        self.assertEqual(lead.name, "Lead Name")
        self.assertFalse(ProjectPartner.objects.filter(pk=partner.pk).exists())

    def test_foreign_project_row_cannot_be_changed(self):
        other = create_project("Other project")
        lead = ProjectLead.objects.create(project=other, name="Other lead")
        self.data.update({"leads-INITIAL_FORMS": "1", "leads-0-id": str(lead.pk)})
        self.assertEqual(self.submit().status_code, 200)
        lead.refresh_from_db()
        self.assertEqual(lead.name, "Other lead")
        self.assertEqual(lead.project_id, other.pk)
        self.assertFalse(self.project.partners.exists())

    def test_missing_management_data_is_rejected(self):
        del self.data["leads-TOTAL_FORMS"]
        self.assertEqual(self.submit().status_code, 200)
        self.assertFalse(self.project.partners.exists())

    def test_failure_rolls_back_narrative_and_team_changes(self):
        original = self.project.project_description
        with patch("projects_catalog.views.ProjectPartnerFormSet.save", side_effect=RuntimeError("save failure")):
            with self.assertRaises(RuntimeError):
                self.submit()
        self.project.refresh_from_db()
        self.assertEqual(self.project.project_description, original)
        self.assertFalse(self.project.leads.exists())

    def test_render_has_one_save_button_and_team_management_fields(self):
        request = RequestFactory().get(self.url)
        request.user = Mock(is_authenticated=True)
        request.user.has_perms.return_value = True
        response = projects_catalog_detail_editor(request, self.project.slug)
        html = response.content.decode()
        self.assertEqual(html.count('type="submit"'), 1)
        self.assertIn('name="leads-TOTAL_FORMS"', html)
        self.assertIn('name="partners-TOTAL_FORMS"', html)
        self.assertIn('data-team-add>Add lead', html)
        self.assertNotIn('No changes have been saved.', html)
