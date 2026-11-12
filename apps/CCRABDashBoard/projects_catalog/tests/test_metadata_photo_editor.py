import tempfile
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import Mock

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from projects_catalog.models import Neighborhood
from projects_catalog.forms import ProjectCatalogEditorForm
from projects_catalog.tests.factories import create_project
from projects_catalog.views import projects_catalog_detail_editor


class MetadataPhotoEditorTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        settings = override_settings(MEDIA_ROOT=self.media.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.project = create_project("Metadata Photos")
        self.url = reverse("projects_catalog_detail_editor", args=[self.project.slug])
        self.river = Neighborhood.objects.create(name="River District")
        self.uptown = Neighborhood.objects.create(name="Uptown")
        self.data = {
            "project_description": "<p>Description</p>", "project_impact": "<p>Impact</p>",
            "neighborhoods": [str(self.river.pk), str(self.uptown.pk)], "start_date": "2026-01-12", "end_date": "2026-11-07",
            "leads-TOTAL_FORMS": "0", "leads-INITIAL_FORMS": "0",
            "partners-TOTAL_FORMS": "0", "partners-INITIAL_FORMS": "0",
        }

    def upload(self):
        stream = BytesIO()
        Image.new("RGB", (8, 8), "blue").save(stream, format="PNG")
        return SimpleUploadedFile("photo.png", stream.getvalue(), content_type="image/png")

    def submit(self):
        request = RequestFactory().post(self.url, self.data)
        request.user = Mock(is_authenticated=True)
        request.user.has_perms.return_value = True
        return projects_catalog_detail_editor(request, self.project.slug)

    def test_edits_existing_metadata_and_saves_photo_with_one_submit(self):
        self.data.update({"photo-picture_path": self.upload(), "photo-name": "River monitoring"})
        self.assertEqual(self.submit().status_code, 302)
        self.project.refresh_from_db()
        self.assertQuerySetEqual(self.project.neighborhoods.all(), ["River District", "Uptown"], transform=str)
        self.assertEqual(self.project.start_date.date().isoformat(), "2026-01-12")
        self.assertEqual(self.project.end_date.date().isoformat(), "2026-11-07")
        photo = self.project.pictures.get()
        self.assertEqual(photo.name, "River monitoring")
        self.assertTrue(photo.picture_path.name.startswith(f"projects_catalog/project_pictures/{self.project.pk}/"))
        self.assertTrue(photo.picture_path.storage.exists(photo.picture_path.name))
        photo.picture_path.open("rb")
        with Image.open(photo.picture_path) as image:
            self.assertEqual(image.format, "PNG")
        photo.picture_path.close()

    def test_invalid_date_order_prevents_photo_and_metadata_saves(self):
        self.data.update({"end_date": "2025-01-01", "photo-picture_path": self.upload()})
        response = self.submit()
        self.assertEqual(response.status_code, 200)
        self.assertIn("End Date must be on or after Start Date", response.content.decode())
        self.assertFalse(self.project.pictures.exists())
        self.project.refresh_from_db()
        self.assertFalse(self.project.neighborhoods.filter(pk=self.river.pk).exists())

    def test_fake_image_rejected_without_partial_saves(self):
        self.data["photo-picture_path"] = SimpleUploadedFile("fake.png", b"not an image", content_type="image/png")
        self.assertEqual(self.submit().status_code, 200)
        self.assertFalse(self.project.pictures.exists())
        self.project.refresh_from_db()
        self.assertFalse(self.project.neighborhoods.filter(pk=self.river.pk).exists())

    def test_no_upload_keeps_existing_photos(self):
        photo = self.project.pictures.create(name="Existing", picture_path="existing.png")
        self.assertEqual(self.submit().status_code, 302)
        photo.refresh_from_db()
        self.assertEqual(photo.picture_path.name, "existing.png")
        self.assertEqual(self.project.pictures.count(), 1)

    def test_optional_metadata_can_be_cleared(self):
        self.data.update({"neighborhoods": [], "start_date": "", "end_date": ""})
        self.assertEqual(self.submit().status_code, 302)
        self.project.refresh_from_db()
        self.assertFalse(self.project.neighborhoods.exists())
        self.assertIsNone(self.project.start_date)
        self.assertIsNone(self.project.end_date)

    def test_unchanged_calendar_day_preserves_existing_time(self):
        original = datetime(2026, 1, 12, 15, 30, tzinfo=timezone.utc)
        self.project.start_date = original
        self.project.save(update_fields=["start_date"])
        self.assertEqual(self.submit().status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.start_date, original)

    def test_initial_fields_use_existing_values_and_date_controls(self):
        self.project.start_date = datetime(2026, 1, 12, tzinfo=timezone.utc)
        form = ProjectCatalogEditorForm(instance=self.project)
        self.assertIn('type="date"', str(form["start_date"]))
        self.assertIn('value="2026-01-12"', str(form["start_date"]))
        self.assertEqual(form.initial["neighborhoods"], list(self.project.neighborhoods.all()))
