from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from platforms_app.models import DataSource, Organization, Platform, Platform_status


class DataSourceFreshnessPolicyTests(SimpleTestCase):
    def test_alert_recipients_default_to_an_empty_list(self):
        source = DataSource()

        self.assertEqual(source.alert_recipients, [])

    def test_alert_recipients_validate_each_email_address(self):
        source = DataSource(
            alert_recipients=["alerts@example.com", "not-an-email"],
        )

        with self.assertRaises(ValidationError) as context:
            source.clean_fields()

        self.assertIn("alert_recipients", context.exception.message_dict)

    def test_enabled_monitoring_requires_stale_threshold(self):
        source = DataSource(freshness_monitoring_enabled=True)

        with self.assertRaises(ValidationError) as context:
            source.clean()

        self.assertIn("stale_after", context.exception.message_dict)

    def test_durations_must_be_positive(self):
        duration_fields = (
            "stale_after",
            "never_reported_after",
            "repeat_alert_after",
        )

        for field_name in duration_fields:
            with self.subTest(field_name=field_name):
                source = DataSource()
                setattr(source, field_name, timedelta(0))

                with self.assertRaises(ValidationError) as context:
                    source.clean()

                self.assertIn(field_name, context.exception.message_dict)

    def test_never_reported_threshold_defaults_to_stale_threshold(self):
        stale_after = timedelta(hours=2)
        source = DataSource(stale_after=stale_after)

        self.assertEqual(source.effective_never_reported_after, stale_after)

    def test_explicit_never_reported_threshold_takes_precedence(self):
        never_reported_after = timedelta(hours=6)
        source = DataSource(
            stale_after=timedelta(hours=2),
            never_reported_after=never_reported_after,
        )

        self.assertEqual(
            source.effective_never_reported_after,
            never_reported_after,
        )


class DataSourceFreshnessConstraintTests(TestCase):
    def test_enabled_monitoring_requires_stale_threshold_in_database(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DataSource.objects.create(
                    key="missing-threshold",
                    freshness_monitoring_enabled=True,
                )

    def test_database_rejects_nonpositive_threshold(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DataSource.objects.create(
                    key="invalid-threshold",
                    stale_after=timedelta(0),
                )


class PlatformStatusIncidentTests(TestCase):
    def setUp(self):
        organization = Organization.objects.create(short_name="test")
        self.platform = Platform.objects.create(
            organization_id=organization,
            short_name="Platform A",
            platform_handle="test.platform-a",
        )

    def create_incident(self, **overrides):
        values = {
            "platform_id": self.platform,
            "alert_type": Platform_status.AlertType.STALE,
            "stale_after": timedelta(hours=2),
        }
        values.update(overrides)
        return Platform_status.objects.create(**values)

    def test_only_one_unresolved_incident_is_allowed_per_platform(self):
        self.create_incident()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_incident(
                    alert_type=Platform_status.AlertType.NEVER_REPORTED,
                )

    def test_new_incident_is_allowed_after_resolution(self):
        incident = self.create_incident()
        incident.status = Platform_status.Status.RESOLVED
        incident.resolved_at = timezone.now()
        incident.save(update_fields=["status", "resolved_at"])

        new_incident = self.create_incident()

        self.assertEqual(new_incident.status, Platform_status.Status.OPEN)

    def test_never_reported_incident_allows_null_observation_date(self):
        incident = self.create_incident(
            alert_type=Platform_status.AlertType.NEVER_REPORTED,
            last_observation_at=None,
        )

        self.assertIsNone(incident.last_observation_at)

    def test_resolved_status_requires_resolution_date(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_incident(status=Platform_status.Status.RESOLVED)
