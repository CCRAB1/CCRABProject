import datetime

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


def require_unused_platform_status(apps, schema_editor):
    platform_status = apps.get_model("platforms_app", "Platform_status")
    database_alias = schema_editor.connection.alias
    if platform_status.objects.using(database_alias).exists():
        raise RuntimeError(
            "The platform_status table contains legacy rows. Migrate or remove "
            "those rows before applying the data-freshness schema migration."
        )


class Migration(migrations.Migration):
    dependencies = [
        ("platforms_app", "0011_backfill_data_source_sensor_defaults"),
    ]

    operations = [
        migrations.RunPython(
            require_unused_platform_status,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AddField(
            model_name="datasource",
            name="freshness_monitoring_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="datasource",
            name="never_reported_after",
            field=models.DurationField(
                blank=True,
                help_text=(
                    "Time allowed before alerting for a platform that has never "
                    "reported. Uses stale_after when left blank."
                ),
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="datasource",
            name="repeat_alert_after",
            field=models.DurationField(
                blank=True,
                help_text=(
                    "Time between repeat notifications for an unresolved incident. "
                    "Leave blank to notify only when the incident opens."
                ),
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="datasource",
            name="send_recovery_alert",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="datasource",
            name="stale_after",
            field=models.DurationField(
                blank=True,
                help_text=(
                    "Maximum age of the latest observation before a platform is "
                    "considered stale."
                ),
                null=True,
            ),
        ),
        migrations.AddConstraint(
            model_name="datasource",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("freshness_monitoring_enabled", False))
                    | models.Q(("stale_after__isnull", False))
                ),
                name="ck_data_source_monitoring_stale_after",
            ),
        ),
        migrations.AddConstraint(
            model_name="datasource",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("stale_after__isnull", True))
                    | models.Q(("stale_after__gt", datetime.timedelta(0)))
                ),
                name="ck_data_source_stale_after_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="datasource",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("never_reported_after__isnull", True))
                    | models.Q(
                        ("never_reported_after__gt", datetime.timedelta(0))
                    )
                ),
                name="ck_data_source_never_reported_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="datasource",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("repeat_alert_after__isnull", True))
                    | models.Q(("repeat_alert_after__gt", datetime.timedelta(0)))
                ),
                name="ck_data_source_repeat_alert_positive",
            ),
        ),
        migrations.RenameField(
            model_name="platform_status",
            old_name="begin_date",
            new_name="opened_at",
        ),
        migrations.RenameField(
            model_name="platform_status",
            old_name="end_date",
            new_name="resolved_at",
        ),
        migrations.RemoveField(
            model_name="platform_status",
            name="expected_end_date",
        ),
        migrations.RemoveField(
            model_name="platform_status",
            name="platform_handle",
        ),
        migrations.AddField(
            model_name="platform_status",
            name="acknowledged_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="platform_status",
            name="alert_type",
            field=models.CharField(
                choices=[
                    ("never_reported", "Never reported"),
                    ("stale", "Stale data"),
                ],
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="platform_status",
            name="details",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="platform_status",
            name="last_notified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="platform_status",
            name="last_observation_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="platform_status",
            name="notification_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="platform_status",
            name="stale_after",
            field=models.DurationField(
                help_text="Snapshot of the threshold that triggered this incident."
            ),
        ),
        migrations.AlterField(
            model_name="platform_status",
            name="opened_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AlterField(
            model_name="platform_status",
            name="platform_id",
            field=models.ForeignKey(
                db_column="platform_id",
                on_delete=django.db.models.deletion.CASCADE,
                to="platforms_app.platform",
            ),
        ),
        migrations.AlterField(
            model_name="platform_status",
            name="status",
            field=models.CharField(
                choices=[
                    ("open", "Open"),
                    ("acknowledged", "Acknowledged"),
                    ("resolved", "Resolved"),
                ],
                default="open",
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="platform_status",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("stale_after__gt", datetime.timedelta(0))
                ),
                name="ck_platform_status_stale_after_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="platform_status",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        ("resolved_at__isnull", False),
                        ("status", "resolved"),
                    )
                    | models.Q(
                        ("resolved_at__isnull", True),
                        ("status__in", ["open", "acknowledged"]),
                    )
                ),
                name="ck_platform_status_resolution",
            ),
        ),
        migrations.AddConstraint(
            model_name="platform_status",
            constraint=models.UniqueConstraint(
                condition=models.Q(("resolved_at__isnull", True)),
                fields=("platform_id",),
                name="uq_open_platform_freshness_incident",
            ),
        ),
        migrations.AddIndex(
            model_name="platform_status",
            index=models.Index(
                fields=["status", "opened_at"],
                name="i_platform_status_opened",
            ),
        ),
    ]
