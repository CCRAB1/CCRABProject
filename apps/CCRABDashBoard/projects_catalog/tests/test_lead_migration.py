from importlib import import_module

from django.apps import apps
from django.db import connection
from django.test import TestCase

from projects_catalog.models import ProjectLead
from projects_catalog.tests.factories import create_project


class ProjectLeadMigrationTests(TestCase):
    def migrate_leads(self):
        migration = import_module(
            "projects_catalog.migrations.0004_migrate_project_leads"
        )
        with connection.schema_editor(atomic=False) as schema_editor:
            migration.migrate_project_leads(apps, schema_editor)

    def test_copies_contacts_and_preserves_original_fields(self):
        project = create_project(
            "Legacy Contact",
            project_lead="Jane Smith",
            project_lead_email="jane@example.com",
            project_lead_phone="555-0100",
        )

        self.migrate_leads()

        lead = project.leads.get()
        self.assertEqual(lead.name, "Jane Smith")
        self.assertEqual(lead.email, "jane@example.com")
        self.assertIsNone(lead.organization)
        self.assertIsNone(lead.url)
        self.assertIsNone(lead.role)
        project.refresh_from_db()
        self.assertEqual(project.project_lead, "Jane Smith")
        self.assertEqual(project.project_lead_email, "jane@example.com")
        self.assertEqual(project.project_lead_phone, "555-0100")

    def test_missing_values_and_repeated_runs(self):
        named = create_project("Name Only", project_lead_email=None)
        emailed = create_project("Email Only", project_lead=None)
        create_project("Empty", project_lead=None, project_lead_email=None)
        create_project("Blank", project_lead="  ", project_lead_email="  ")
        other = ProjectLead.objects.create(project=named, name="Another Lead")

        self.migrate_leads()
        self.migrate_leads()

        self.assertEqual(ProjectLead.objects.count(), 3)
        self.assertTrue(ProjectLead.objects.filter(pk=other.pk).exists())
        self.assertTrue(named.leads.filter(name="Name Only Lead", email=None).exists())
        self.assertTrue(emailed.leads.filter(name="", email="lead@example.com").exists())
