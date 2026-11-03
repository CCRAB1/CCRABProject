from django.urls import path
from . import views

urlpatterns = [
    # Template pages
    path("platform_info/<str:short_name>/", views.PlatformInfo, name="platform_info"),
    path("", views.PlatformCatalog, name="platform_catalog"),
    path("platforms_map/", views.PlatformMap, name="platforms_map"),

]
