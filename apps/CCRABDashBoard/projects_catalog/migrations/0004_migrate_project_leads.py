from django.db import migrations


def migrate_project_leads(apps, schema_editor):
    ProjectCatalogPage = apps.get_model("projects_catalog", "ProjectCatalogPage")
    ProjectLead = apps.get_model("projects_catalog", "ProjectLead")
    database = schema_editor.connection.alias

    projects = ProjectCatalogPage.objects.using(database).only(
        "id", "project_lead", "project_lead_email"
    )
    for project in projects.iterator():
        name = project.project_lead or ""
        email = project.project_lead_email or ""
        if not name.strip() and not email.strip():
            continue

        # Preserve the legacy values, including contacts that only have an email.
        ProjectLead.objects.using(database).get_or_create(
            project_id=project.pk,
            name=name,
            email=email or None,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("projects_catalog", "0003_project_lead"),
    ]

    operations = [
        # Keep copied contacts on rollback: they may have been edited or used.
        migrations.RunPython(migrate_project_leads, migrations.RunPython.noop),
    ]
