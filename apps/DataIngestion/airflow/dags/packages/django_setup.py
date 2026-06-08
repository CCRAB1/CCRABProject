import os
import sys

_DJANGO_READY = False

def setup_django():
    global _DJANGO_READY

    if _DJANGO_READY:
        return

    from airflow.sdk import Variable

    django_project_path = Variable.get(
        "CCRAB_DJANGO_PROJECT_PATH",
        default=None,
    )
    if django_project_path is None:
        raise Exception("No Django project path provided")

    if django_project_path not in sys.path:
        sys.path.insert(0, django_project_path)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CCRABDashboard.settings")

    import django
    from django.apps import apps

    if not apps.ready:
        django.setup()

    _DJANGO_READY = True