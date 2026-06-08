from datetime import UTC, datetime
from types import SimpleNamespace

from django.test import SimpleTestCase

from projects_catalog.views import (
    _first_featured_image,
    _format_duration,
    _normalized_keywords,
    _resource_title,
    _split_bullets,
    _split_paragraphs,
)


class CatalogHelperFunctionTests(SimpleTestCase):
    def test_format_duration_with_start_and_end(self):
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 6, 1, tzinfo=UTC)

        value = _format_duration(start, end)

        self.assertEqual(value, "Jan 2024 - Jun 2024")

    def test_format_duration_with_only_start(self):
        start = datetime(2024, 1, 1, tzinfo=UTC)

        value = _format_duration(start, None)

        self.assertEqual(value, "Jan 2024 - Present")

    def test_format_duration_with_only_end(self):
        end = datetime(2024, 6, 1, tzinfo=UTC)

        value = _format_duration(None, end)

        self.assertEqual(value, "Through Jun 2024")

    def test_format_duration_without_dates(self):
        value = _format_duration(None, None)

        self.assertEqual(value, "—")

    def test_first_featured_image_returns_first_image_with_path(self):
        payload = {
            "project_name": "Air Monitoring",
            "pictures": [
                {"name": "Missing path"},
                {"name": "Hero", "picture_path": "/media/hero.jpg"},
                {"name": "Second", "picture_path": "/media/second.jpg"},
            ],
        }

        featured = _first_featured_image(payload)

        self.assertEqual(featured["url"], "/media/hero.jpg")
        self.assertEqual(featured["alt"], "Hero")

    def test_first_featured_image_returns_none_when_no_paths(self):
        payload = {
            "project_name": "Air Monitoring",
            "pictures": [
                {"name": "Missing path"},
                {"name": "Also missing"},
            ],
        }

        featured = _first_featured_image(payload)

        self.assertIsNone(featured)

    def test_split_paragraphs_splits_on_blank_lines(self):
        text = "Paragraph one.\n\nParagraph two.\n\n   Paragraph three."

        parts = _split_paragraphs(text)

        self.assertEqual(
            parts,
            ["Paragraph one.", "Paragraph two.", "Paragraph three."],
        )

    def test_split_paragraphs_returns_empty_list_for_empty_text(self):
        self.assertEqual(_split_paragraphs(""), [])
        self.assertEqual(_split_paragraphs(None), [])

    def test_split_bullets_strips_dash_prefixes(self):
        text = "- First bullet\n- Second bullet\nThird bullet"

        bullets = _split_bullets(text)

        self.assertEqual(bullets, ["First bullet", "Second bullet", "Third bullet"])

    def test_split_bullets_returns_empty_list_for_empty_text(self):
        self.assertEqual(_split_bullets(""), [])
        self.assertEqual(_split_bullets(None), [])

    def test_normalized_keywords_from_list(self):
        value = [" air ", "", None, "water", 100]

        keywords = _normalized_keywords(value)

        self.assertEqual(keywords, ["air", "None", "water", "100"])

    def test_normalized_keywords_from_csv_text(self):
        value = " air, water , ,habitat "

        keywords = _normalized_keywords(value)

        self.assertEqual(keywords, ["air", "water", "habitat"])

    def test_normalized_keywords_from_unknown_type(self):
        keywords = _normalized_keywords({"air": True})

        self.assertEqual(keywords, [])

    def test_resource_title_prefers_data_summary_first_paragraph(self):
        location = SimpleNamespace(
            data_summary="Summary line one.\n\nMore details.",
            data_type="Dataset",
            product_category=SimpleNamespace(name="Maps"),
        )

        title = _resource_title(location)

        self.assertEqual(title, "Summary line one.")

    def test_resource_title_uses_data_type_when_summary_missing(self):
        location = SimpleNamespace(
            data_summary="",
            data_type="Dataset",
            product_category=SimpleNamespace(name="Maps"),
        )

        title = _resource_title(location)

        self.assertEqual(title, "Dataset")

    def test_resource_title_uses_category_when_summary_and_type_missing(self):
        location = SimpleNamespace(
            data_summary=None,
            data_type=None,
            product_category=SimpleNamespace(name="Maps"),
        )

        title = _resource_title(location)

        self.assertEqual(title, "Maps")

    def test_resource_title_falls_back_to_default(self):
        location = SimpleNamespace(
            data_summary=None,
            data_type=None,
            product_category=None,
        )

        title = _resource_title(location)

        self.assertEqual(title, "Project Resource")
