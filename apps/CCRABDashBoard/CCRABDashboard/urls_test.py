from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import RedirectView, TemplateView

urlpatterns = [
    path("", TemplateView.as_view(template_name="index.html"), name="home"),
    path("admin/", admin.site.urls),
    path("projects_catalog_admin/", RedirectView.as_view(url="/admin/", permanent=False)),
    path("api/", include("CCRABDashboard.api.urls")),
    path("platforms_catalog/", include("platforms_app.urls")),
    path("projects_catalog/", include("projects_catalog.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
