from django.urls import path

from . import views

urlpatterns = [
    path("platforms/", views.platform_collection_api, name="platform-list-api"),
    path("platforms/<str:short_name>/", views.platform_detail_api, name="platform-detail-api"),

    # Legacy aliases
    path("v1/platform_info/", views.PlatformViewSet.as_view(), name="platforminfo"),

    path("v1/system/platform_configuration/", views.platform_source_configuration, name="platform_configuration")

]
