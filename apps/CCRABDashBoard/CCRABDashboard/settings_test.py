from .settings import *  # noqa: F403,F401

# Keep tests focused on apps that exist in this checkout.
filtered_installed_apps = []
for app in INSTALLED_APPS:
    if app == "projects_catalog_react.apps.ProjectsCatalogReactConfig":
        continue
    filtered_installed_apps.append(app)
INSTALLED_APPS = filtered_installed_apps
ROOT_URLCONF = "CCRABDashboard.urls_test"

# Override DB credentials for test runs only
DATABASES["default"] = {
    **DATABASES["default"],
    "NAME": env("TEST_DATABASE_NAME", default=DATABASES["default"]["NAME"]),
    "USER": env("TEST_DATABASE_USER", default=DATABASES["default"]["USER"]),
    "PASSWORD": env("TEST_DATABASE_PASSWORD", default=DATABASES["default"]["PASSWORD"]),
    "HOST": env("TEST_DATABASE_HOST", default=DATABASES["default"]["HOST"]),
    "PORT": env("TEST_DATABASE_PORT", default=DATABASES["default"]["PORT"]),
}
