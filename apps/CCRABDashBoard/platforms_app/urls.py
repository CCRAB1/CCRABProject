from django.urls import path
from . import views

urlpatterns = [
    path("data/platforms/<str:short_name>/", views.platform_detail_web_data, name="platform-detail-web-data"),

    # Legacy aliases
    path("platforms/data/", views.platform_collection_web_data, name="platform-data"),

    # Template pages
    path("platform_info/<str:short_name>/", views.PlatformInfo, name="platform_info"),
    path("", views.PlatformCatalog, name="platform_catalog"),
    path("platforms_map/", views.PlatformMap, name="platforms_map"),

]
